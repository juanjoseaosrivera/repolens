import { Injectable, signal } from '@angular/core';

/**
 * Minimal shared application state.
 * Phase 1: just the selected repository ID.
 */
@Injectable({ providedIn: 'root' })
export class AppStateService {
  readonly selectedRepoId = signal<string | null>(null);
}
