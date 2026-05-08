import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

/**
 * SSE streaming service for agent token and tool-call events.
 * Supports both GET (EventSource) and POST (fetch ReadableStream) patterns.
 */
@Injectable({ providedIn: 'root' })
export class StreamingService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private readonly zone: NgZone) {}

  /**
   * Open a GET-based SSE connection and emit each message data string.
   * The observable completes when the server closes the stream.
   */
  stream(path: string): Observable<string> {
    return new Observable<string>((subscriber) => {
      const url = `${this.baseUrl}${path}`;
      const source = new EventSource(url);

      source.onmessage = (event: MessageEvent<string>) => {
        this.zone.run(() => subscriber.next(event.data));
      };

      source.onerror = () => {
        this.zone.run(() => {
          source.close();
          subscriber.complete();
        });
      };

      return () => source.close();
    });
  }

  /**
   * POST a JSON body and stream back SSE events via fetch + ReadableStream.
   * Each emitted value is the raw `data:` field content (unparsed).
   */
  postStream(path: string, body: unknown): Observable<string> {
    return new Observable<string>((subscriber) => {
      const controller = new AbortController();

      fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) {
            const err = await response.json();
            throw new Error(
              (err as Record<string, string>)['detail'] ??
                `HTTP ${response.status}`,
            );
          }
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          const read = (): void => {
            reader
              .read()
              .then(({ done, value }) => {
                if (done) {
                  this.zone.run(() => subscriber.complete());
                  return;
                }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                // Keep incomplete last line in buffer
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                  if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                      this.zone.run(() => subscriber.complete());
                      return;
                    }
                    this.zone.run(() => subscriber.next(data));
                  }
                }
                read();
              })
              .catch((err) => {
                this.zone.run(() => subscriber.error(err));
              });
          };
          read();
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') {
            this.zone.run(() => subscriber.complete());
          } else {
            this.zone.run(() => subscriber.error(err));
          }
        });

      return () => controller.abort();
    });
  }
}
