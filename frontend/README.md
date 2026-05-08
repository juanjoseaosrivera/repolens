# RepoLens — Frontend

Angular 21 single-page application for the RepoLens code analysis system. Provides a chat interface for asking questions about ingested codebases, with real-time streaming responses and source citations.

## Setup

```bash
npm install
npx ng serve
```

The UI is available at **http://localhost:4200**. The backend must be running at `http://localhost:8000` (configured in `src/environments/environment.ts`).

## Architecture

### Layout

```
┌─────────────────────────────────────────────────────┐
│ RepoLens                                    v0.1.0  │  ← sticky header
├──────────────┬──────────────────┬───────────────────┤
│ Left Rail    │  Chat Surface    │  Trace Panel      │
│ (hidden <md) │  (router-outlet) │  (hidden <lg)     │
│              │                  │                   │
│ Repo         │  Message list    │  Phase 2          │
│ Selector     │  Sources bar     │  placeholder      │
│              │  Composer        │                   │
└──────────────┴──────────────────┴───────────────────┘
```

The layout uses a three-column responsive grid. The left rail and trace panel collapse on smaller screens.

### Component tree

```
App (app.ts)
├── RepoSelectorComponent (features/repos/)
│   └── Repo list + add form
└── <router-outlet>
    └── ChatShellComponent (features/chat/)  [lazy-loaded]
        ├── Message list (user/assistant bubbles)
        ├── Sources bar (file path + line range badges)
        ├── Error banner
        └── Composer (input + send button)
```

### Data flow

1. **Repository selection**: `RepoSelectorComponent` calls `POST /repos` to add and `GET /repos` to list. On select, it writes the repo ID to `AppStateService.selectedRepoId` (a shared signal).

2. **Chat**: `ChatShellComponent` reads `selectedRepoId` from `AppStateService`. On send, it calls `StreamingService.postStream('/chat', { repository_id, question })` which opens a fetch-based SSE stream.

3. **Streaming**: The SSE stream emits three event types:
   - `sources` — chunk metadata (file path, line range, score) → rendered as badges in the sources bar
   - `token` — a text token → appended to the current assistant message bubble
   - `[DONE]` — stream complete → `isStreaming` set to false

## Module reference

### Core services (`src/app/core/`)

| File | Description |
|------|-------------|
| `api.service.ts` | Central HTTP client wrapper. `get<T>(path)` and `post<T>(path, body)`. Base URL from environment config. |
| `streaming.service.ts` | SSE streaming. `stream(path)` for GET-based EventSource. `postStream(path, body)` for POST-based fetch + ReadableStream with SSE parsing. Both integrate with Angular's `NgZone`. |
| `app-state.service.ts` | Minimal shared state. Exposes `selectedRepoId` signal. Injected by both `App` and `ChatShellComponent`. |
| `error.interceptor.ts` | Global HTTP error handler. Logs errors with status and method, then re-throws for feature-level handling. |

### Feature components (`src/app/features/`)

#### `chat/chat-shell.component.ts`

The primary user surface. Manages:
- `messages` signal — array of `{ role, content }` objects
- `draft` signal — current input text
- `isStreaming` signal — true while SSE stream is open
- `sources` signal — retrieved chunk metadata from the last query
- `errorMessage` signal — error text (e.g. "Select a repository first")

The `send()` method validates input, appends the user message, opens a POST-based SSE stream, and incrementally builds the assistant response token by token.

#### `repos/repo-selector.component.ts`

Left-rail component with:
- Text input + button to add a new repository (calls `POST /repos`)
- List of all repositories (calls `GET /repos`)
- Click to select a repository (writes to `AppStateService`)
- Visual indicator of selected repo and ingestion status

### Routing (`src/app/app.routes.ts`)

Single route at `''` that lazy-loads `ChatShellComponent`:

```typescript
export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/chat/chat-shell.component').then(
        (m) => m.ChatShellComponent,
      ),
  },
];
```

### Environment configuration (`src/environments/`)

| File | `production` | `apiUrl` |
|------|:---:|---|
| `environment.ts` | `false` | `http://localhost:8000` |
| `environment.prod.ts` | `true` | `/api` |

## Design system

CSS custom properties defined in `src/styles.scss`:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#6366f1` | Buttons, user message bubbles, active states |
| `--color-primary-hover` | `#4f46e5` | Hover states |
| `--color-surface` | `#ffffff` | Main background |
| `--color-surface-alt` | `#f8fafc` | Side panels, assistant bubbles |
| `--color-text` | `#0f172a` | Primary text |
| `--color-text-muted` | `#64748b` | Secondary text, labels |
| `--color-border` | `#e2e8f0` | Dividers, input borders |
| `--color-error` | `#ef4444` | Error text and borders |
| `--color-success` | `#22c55e` | Success indicators |
| `--font-sans` | `Inter, system-ui, ...` | Body text |
| `--font-mono` | `JetBrains Mono, ...` | Code blocks |

Styling uses Tailwind CSS v4 utility classes with these tokens applied via `var()`.

## Development

```bash
# Development server (hot reload)
npx ng serve

# Type-check
npx tsc --noEmit

# Production build
npx ng build

# Unit tests
npx ng test
```

### Build budgets

- Initial bundle: 500 kB warning, 1 MB error
- Component styles: 2 kB warning, 4 kB error

### TypeScript configuration

Strict mode is enabled with all additional safety checks:
- `strict: true`
- `noUncheckedIndexedAccess: true`
- `exactOptionalPropertyTypes: true`
- `noImplicitOverride: true`
- `noPropertyAccessFromIndexSignature: true`
- `noImplicitReturns: true`
- `noFallthroughCasesInSwitch: true`

Angular compiler also runs in strict mode (`strictTemplates`, `strictInjectionParameters`, `strictInputAccessModifiers`).

## Future work (Phase 2+)

- **Trace panel** (`features/traces/`): side panel showing retrieved chunks with syntax highlighting and citation linking
- **Auth gate**: OAuth2/OIDC login flow with JWT token management
- **Dark/light theme**: toggle using the existing CSS custom property system
- **Keyboard shortcuts**: `?` cheatsheet, Cmd+Enter to send, etc.
