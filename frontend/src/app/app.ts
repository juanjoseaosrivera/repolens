import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AppStateService } from './core/app-state.service';
import { RepoSelectorComponent } from './features/repos/repo-selector.component';
import { TracePanelComponent } from './features/traces/trace-panel.component';
import { KeyboardShortcutsComponent } from './shared/keyboard-shortcuts.component';
import { ThemeToggleComponent } from './shared/theme-toggle.component';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RepoSelectorComponent,
    TracePanelComponent,
    ThemeToggleComponent,
    KeyboardShortcutsComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  standalone: true,
})
export class App {
  private readonly state = inject(AppStateService);

  onRepoSelected(repoId: string): void {
    this.state.selectedRepoId.set(repoId);
  }
}
