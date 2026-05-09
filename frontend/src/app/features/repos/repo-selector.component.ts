import { Component, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';

interface Repo {
  id: string;
  name: string;
  url: string;
  status: string;
}

/**
 * Left-rail repository selector — lists repos and allows adding new ones.
 * Emits the selected repository ID to the parent.
 */
@Component({
  selector: 'rl-repo-selector',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="flex flex-col gap-4">
      <h2 class="text-sm font-semibold uppercase" style="color: var(--color-text-muted)">
        Repositories
      </h2>

      <!-- Add repo form -->
      <div class="flex flex-col gap-2">
        <input
          type="text"
          class="w-full rounded border px-2 py-1 text-sm focus:outline-none focus:ring-1"
          style="border-color: var(--color-border); --tw-ring-color: var(--color-primary)"
          placeholder="Git clone URL..."
          [ngModel]="repoUrl()"
          (ngModelChange)="repoUrl.set($event)"
          (keydown.enter)="addRepo()"
        />
        <button
          class="rounded px-2 py-1 text-sm font-medium text-white disabled:opacity-50"
          style="background: var(--color-primary)"
          [disabled]="!repoUrl().trim() || isAdding()"
          (click)="addRepo()"
        >
          {{ isAdding() ? 'Adding...' : 'Add & Ingest' }}
        </button>
      </div>

      @if (error()) {
        <p class="text-xs" style="color: var(--color-error)">{{ error() }}</p>
      }

      <!-- Repo list -->
      <div class="flex flex-col gap-1">
        @for (repo of repos(); track repo.id) {
          <div
            class="group flex items-center rounded transition-colors"
            [style.background]="selectedId() === repo.id ? 'var(--color-primary)' : 'transparent'"
          >
            <button
              class="min-w-0 flex-1 px-2 py-1.5 text-left text-sm"
              [style.color]="selectedId() === repo.id ? '#fff' : 'var(--color-text)'"
              (click)="selectRepo(repo)"
            >
              <span class="block truncate font-medium">{{ repo.name }}</span>
              <span class="block truncate text-xs opacity-70">{{ repo.status }}</span>
            </button>
            <button
              class="mr-1 shrink-0 rounded p-1 opacity-0 transition-opacity hover:bg-black/10 group-hover:opacity-100"
              [style.color]="selectedId() === repo.id ? '#fff' : 'var(--color-text-muted)'"
              title="Delete repository"
              aria-label="Delete repository {{ repo.name }}"
              (click)="deleteRepo($event, repo)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
                <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
        } @empty {
          <p class="text-xs" style="color: var(--color-text-muted)">
            No repositories yet. Add one above.
          </p>
        }
      </div>
    </div>
  `,
})
export class RepoSelectorComponent implements OnInit {
  readonly repoSelected = output<string>();

  protected readonly repos = signal<Repo[]>([]);
  protected readonly selectedId = signal<string | null>(null);
  protected readonly repoUrl = signal('');
  protected readonly isAdding = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
    this.loadRepos();
  }

  selectRepo(repo: Repo): void {
    this.selectedId.set(repo.id);
    this.repoSelected.emit(repo.id);
  }

  addRepo(): void {
    const url = this.repoUrl().trim();
    if (!url || this.isAdding()) return;

    this.isAdding.set(true);
    this.error.set(null);

    this.api.post<Repo>('/repos', { url }).subscribe({
      next: (repo) => {
        this.repoUrl.set('');
        this.isAdding.set(false);
        this.loadRepos();
        this.selectRepo(repo);
      },
      error: (err) => {
        this.isAdding.set(false);
        this.error.set(err?.error?.detail ?? 'Failed to add repository');
      },
    });
  }

  deleteRepo(event: Event, repo: Repo): void {
    event.stopPropagation();
    if (!confirm(`Delete "${repo.name}"? This cannot be undone.`)) return;

    this.api.delete(`/repos/${repo.id}`).subscribe({
      next: () => {
        if (this.selectedId() === repo.id) {
          this.selectedId.set(null);
        }
        this.loadRepos();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to delete repository');
      },
    });
  }

  loadRepos(): void {
    this.api.get<Repo[]>('/repos').subscribe({
      next: (repos) => this.repos.set(repos),
      error: () => this.error.set('Failed to load repositories'),
    });
  }
}
