import { Component, computed, inject, signal } from '@angular/core';

import { AppStateService } from '../../core/app-state.service';

import hljs from 'highlight.js/lib/core';
import python from 'highlight.js/lib/languages/python';
import typescript from 'highlight.js/lib/languages/typescript';
import javascript from 'highlight.js/lib/languages/javascript';
import xml from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import json from 'highlight.js/lib/languages/json';
import yaml from 'highlight.js/lib/languages/yaml';
import bash from 'highlight.js/lib/languages/bash';
import sql from 'highlight.js/lib/languages/sql';
import go from 'highlight.js/lib/languages/go';
import java from 'highlight.js/lib/languages/java';
import rust from 'highlight.js/lib/languages/rust';

hljs.registerLanguage('python', python);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('css', css);
hljs.registerLanguage('json', json);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('shell', bash);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('go', go);
hljs.registerLanguage('java', java);
hljs.registerLanguage('rust', rust);

export interface SourceChunk {
  file_path: string;
  start_line: number;
  end_line: number;
  content: string;
  language: string | null;
  score: number;
}

@Component({
  selector: 'rl-trace-panel',
  standalone: true,
  templateUrl: './trace-panel.component.html',
  styles: [
    ':host { display: flex; flex-direction: column; height: 100%; }',
    'pre code { font-family: var(--font-mono); }',
  ],
})
export class TracePanelComponent {
  private readonly state = inject(AppStateService);

  protected readonly sources = computed(() => this.state.sources());
  protected readonly toolCalls = computed(() => this.state.toolCalls());
  protected readonly metrics = computed(() => this.state.agentMetrics());
  protected readonly collapsed = signal(false);
  protected readonly focusedIndex = computed(() => this.state.focusedChunkIndex());

  private readonly highlightCache = new Map<string, string>();

  highlightCode(code: string, language: string | null): string {
    const key = (language ?? '') + ':' + code;
    const cached = this.highlightCache.get(key);
    if (cached !== undefined) return cached;

    let result: string;
    if (language && hljs.getLanguage(language)) {
      result = hljs.highlight(code, { language }).value;
    } else {
      result = hljs.highlightAuto(code).value;
    }

    this.highlightCache.set(key, result);
    return result;
  }

  formatInput(input: Record<string, unknown>): string {
    return Object.entries(input)
      .filter(([k]) => k !== 'repository_id')
      .map(([k, v]) => k + ': ' + String(v).slice(0, 100))
      .join(', ');
  }

  focusChunk(index: number): void {
    this.state.focusedChunkIndex.set(index);
    this.collapsed.set(false);
    const el = document.getElementById('chunk-' + index);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}
