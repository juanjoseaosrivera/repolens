import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AppStateService } from '../../core/app-state.service';
import { StreamingService } from '../../core/streaming.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface SourceChunk {
  file_path: string;
  start_line: number;
  end_line: number;
  score: number;
}

/**
 * Chat shell — the primary user surface.
 * Wired to the streaming backend via POST-based SSE.
 */
@Component({
  selector: 'rl-chat-shell',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './chat-shell.component.html',
  styleUrl: './chat-shell.component.scss',
})
export class ChatShellComponent {
  private readonly state = inject(AppStateService);
  private readonly streaming = inject(StreamingService);

  protected readonly repositoryId = computed(() => this.state.selectedRepoId());
  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly draft = signal('');
  protected readonly isStreaming = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly sources = signal<SourceChunk[]>([]);

  send(): void {
    const text = this.draft().trim();
    const repoId = this.repositoryId();
    if (!text || this.isStreaming()) return;

    if (!repoId) {
      this.errorMessage.set('Select a repository first.');
      return;
    }

    this.errorMessage.set(null);
    this.sources.set([]);
    this.messages.update((msgs) => [...msgs, { role: 'user', content: text }]);
    this.draft.set('');

    // Add placeholder assistant message
    this.messages.update((msgs) => [
      ...msgs,
      { role: 'assistant', content: '' },
    ]);
    this.isStreaming.set(true);

    this.streaming
      .postStream('/chat', { repository_id: repoId, question: text })
      .subscribe({
        next: (data) => {
          try {
            const parsed = JSON.parse(data) as {
              type: string;
              data: string | SourceChunk[];
            };

            if (parsed.type === 'sources') {
              this.sources.set(parsed.data as SourceChunk[]);
            } else if (parsed.type === 'token') {
              this.messages.update((msgs) => {
                const updated = [...msgs];
                const last = updated[updated.length - 1];
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + (parsed.data as string),
                  };
                }
                return updated;
              });
            }
          } catch {
            // ignore unparseable events
          }
        },
        error: (err) => {
          this.isStreaming.set(false);
          this.errorMessage.set(
            err instanceof Error ? err.message : 'Stream failed',
          );
        },
        complete: () => {
          this.isStreaming.set(false);
        },
      });
  }
}
