import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AppStateService, ToolCall } from '../../core/app-state.service';
import { StreamingService } from '../../core/streaming.service';
import type { SourceChunk } from '../traces/trace-panel.component';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * Chat shell — the primary user surface.
 * Supports both the simple /chat endpoint and the agent /agent/chat endpoint.
 * Handles token, sources, tool_call_start, tool_call_result, and metrics SSE events.
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
  protected readonly sources = computed(() => this.state.sources());
  protected readonly useAgent = signal(true);

  send(): void {
    const text = this.draft().trim();
    const repoId = this.repositoryId();
    if (!text || this.isStreaming()) return;

    if (!repoId) {
      this.errorMessage.set('Select a repository first.');
      return;
    }

    this.errorMessage.set(null);
    this.state.sources.set([]);
    this.state.toolCalls.set([]);
    this.state.agentMetrics.set(null);
    this.state.focusedChunkIndex.set(null);
    this.messages.update((msgs) => [...msgs, { role: 'user', content: text }]);
    this.draft.set('');

    this.messages.update((msgs) => [
      ...msgs,
      { role: 'assistant', content: '' },
    ]);
    this.isStreaming.set(true);

    const endpoint = this.useAgent() ? '/agent/chat' : '/chat';

    this.streaming
      .postStream(endpoint, { repository_id: repoId, question: text })
      .subscribe({
        next: (data) => {
          try {
            const parsed = JSON.parse(data) as {
              type: string;
              data: unknown;
            };

            switch (parsed.type) {
              case 'sources':
                this.state.sources.set(parsed.data as SourceChunk[]);
                break;

              case 'token':
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
                break;

              case 'tool_call_start': {
                const tc = parsed.data as {
                  step: number;
                  tool: string;
                  input: Record<string, unknown>;
                };
                this.state.toolCalls.update((calls) => [
                  ...calls,
                  {
                    step: tc.step,
                    tool: tc.tool,
                    input: tc.input,
                    status: 'running' as const,
                  },
                ]);
                break;
              }

              case 'tool_call_result': {
                const tr = parsed.data as {
                  step: number;
                  tool: string;
                  result: string;
                };
                this.state.toolCalls.update((calls) =>
                  calls.map((c) =>
                    c.step === tr.step
                      ? { ...c, result: tr.result, status: 'done' as const }
                      : c,
                  ),
                );
                break;
              }

              case 'metrics':
                this.state.agentMetrics.set(
                  parsed.data as { elapsed_seconds: number; steps: number },
                );
                break;
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

  toggleAgent(): void {
    this.useAgent.update((v) => !v);
  }

  focusChunk(index: number): void {
    this.state.focusedChunkIndex.set(index);
    const el = document.getElementById('chunk-' + index);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}
