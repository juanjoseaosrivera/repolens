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
          <button
            class="rounded px-2 py-1.5 text-left text-sm transition-colors"
            [style.background]="selectedId() === repo.id ? 'var(--color-primary)' : 'transparent'"
            [style.color]="selectedId() === repo.id ? '#fff' : 'var(--color-text)'"
            (click)="selectRepo(repo)"
          >
            <span class="block truncate font-medium">{{ repo.name }}</span>
            <span class="block truncate text-xs opacity-70">{{ repo.status }}</span>
          </button>
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

  loadRepos(): void {
    this.api.get<Repo[]>('/repos').subscribe({
      next: (repos) => this.repos.set(repos),
      error: () => this.error.set('Failed to load repositories'),
    });
  }
}
