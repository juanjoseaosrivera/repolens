import { Injectable, signal } from '@angular/core';

import type { SourceChunk } from '../features/traces/trace-panel.component';

export interface ToolCall {
  step: number;
  tool: string;
  input: Record<string, unknown>;
  result?: string;
  status: 'running' | 'done';
}

/**
 * Shared application state.
 * Phase 1: selected repository ID.
 * Phase 2: retrieved sources for the trace panel.
 * Phase 3: tool calls from the agent.
 */
@Injectable({ providedIn: 'root' })
export class AppStateService {
  readonly selectedRepoId = signal<string | null>(null);
  readonly sources = signal<SourceChunk[]>([]);
  readonly focusedChunkIndex = signal<number | null>(null);
  readonly toolCalls = signal<ToolCall[]>([]);
  readonly agentMetrics = signal<{ elapsed_seconds?: number; steps?: number } | null>(null);
}
