import { Component, signal } from '@angular/core';

type Theme = 'light' | 'dark' | 'system';

@Component({
  selector: 'rl-theme-toggle',
  standalone: true,
  template: `
    <button
      class="rounded p-1.5 text-sm transition-colors"
      style="color: var(--color-text-muted)"
      (click)="cycle()"
      [attr.aria-label]="'Switch theme (current: ' + theme() + ')'"
      [title]="'Theme: ' + theme()"
    >
      @switch (theme()) {
        @case ('light') { <span>&#9728;</span> }
        @case ('dark') { <span>&#9790;</span> }
        @case ('system') { <span>&#9881;</span> }
      }
    </button>
  `,
})
export class ThemeToggleComponent {
  protected readonly theme = signal<Theme>(this.loadTheme());

  cycle(): void {
    const order: Theme[] = ['light', 'dark', 'system'];
    const idx = order.indexOf(this.theme());
    const next = order[(idx + 1) % order.length]!;
    this.theme.set(next);
    this.applyTheme(next);
  }

  private loadTheme(): Theme {
    if (typeof localStorage === 'undefined') return 'system';
    return (localStorage.getItem('rl-theme') as Theme) ?? 'system';
  }

  private applyTheme(theme: Theme): void {
    const root = document.documentElement;
    if (theme === 'system') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
    localStorage.setItem('rl-theme', theme);
  }
}
