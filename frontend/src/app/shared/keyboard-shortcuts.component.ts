import { Component, HostListener, signal } from '@angular/core';

interface Shortcut {
  keys: string;
  description: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: '?', description: 'Show keyboard shortcuts' },
  { keys: 'Esc', description: 'Close this dialog' },
  { keys: '/', description: 'Focus chat input' },
  { keys: 'Ctrl+Enter', description: 'Send message' },
];

@Component({
  selector: 'rl-keyboard-shortcuts',
  standalone: true,
  template: `
    @if (visible()) {
      <div class="fixed inset-0 z-50 flex items-center justify-center"
           style="background: rgba(0,0,0,0.4)"
           (click)="visible.set(false)"
           role="dialog"
           aria-label="Keyboard shortcuts">
        <div class="rounded-lg p-6 shadow-xl max-w-sm w-full"
             style="background: var(--color-surface); color: var(--color-text)"
             (click)="$event.stopPropagation()">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold">Keyboard Shortcuts</h2>
            <button class="text-sm px-2 py-1 rounded"
                    style="color: var(--color-text-muted)"
                    (click)="visible.set(false)"
                    aria-label="Close">
              Esc
            </button>
          </div>
          <div class="space-y-2">
            @for (s of shortcuts; track s.keys) {
              <div class="flex items-center justify-between py-1">
                <span class="text-sm" style="color: var(--color-text-muted)">
                  {{ s.description }}
                </span>
                <kbd class="rounded px-2 py-0.5 text-xs font-mono"
                     style="background: var(--color-surface-alt); border: 1px solid var(--color-border)">
                  {{ s.keys }}
                </kbd>
              </div>
            }
          </div>
        </div>
      </div>
    }
  `,
})
export class KeyboardShortcutsComponent {
  protected readonly visible = signal(false);
  protected readonly shortcuts = SHORTCUTS;

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    // Ignore when typing in input fields
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
      // Allow Escape to close the dialog even from inputs
      if (event.key === 'Escape' && this.visible()) {
        this.visible.set(false);
        event.preventDefault();
      }
      return;
    }

    if (event.key === '?') {
      this.visible.update((v) => !v);
      event.preventDefault();
    } else if (event.key === 'Escape') {
      this.visible.set(false);
    } else if (event.key === '/') {
      // Focus the chat input
      const input = document.querySelector<HTMLInputElement>(
        'rl-chat-shell input[type="text"]',
      );
      if (input) {
        input.focus();
        event.preventDefault();
      }
    }
  }
}
