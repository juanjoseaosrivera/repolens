# RepoLens — UI Context

This document defines the UI design context for RepoLens: who it is for, the principles that shape the interface, the information architecture, the core flows, and the conventions a contributor needs to know before touching the frontend. It complements `architecture-context.md` (which covers the technical shape of the Angular app) and `code-standards.md` (which covers code conventions).

When in doubt: **the developer's flow comes first**. RepoLens is a tool, not a product to admire.

## 1. Audience and tone

### 1.1 Who uses RepoLens

The primary users are working software engineers operating on real codebases:

- **Developers** trying to understand where a feature lives or how a function is wired in.
- **Lead engineers / architects** mapping data flow and assessing the blast radius of a proposed change.
- **DevOps / platform engineers** answering operational questions about a codebase (env vars, dependencies).

These users live in editors and terminals. They are not impressed by motion or chrome. They reward precision, density, and speed.

### 1.2 Tone

- **Direct.** No marketing language inside the product. Buttons say what they do.
- **Technical.** File paths, line numbers, symbol names, and commit SHAs are first-class data, not decoration.
- **Sober.** Confident about what the system knows; explicit about what it doesn't. The agent says "I don't have enough context" before it guesses.
- **No emojis in the product UI.** Status uses iconography from the chosen component library (Material or PrimeNG), not emoji.

## 2. Design principles

1. **Code is the protagonist.** The UI exists to surface code, citations, and reasoning. The chrome is minimal; the content is dense.
2. **Show your work.** Every answer is accompanied by the chunks it was based on and (Phase 3+) the tool calls the agent made. The trace panel is not optional polish — it is core.
3. **Streaming first.** The user should see the agent thinking as it happens. Latency hidden behind a spinner is wasted user trust.
4. **Keyboard-first.** Power users should rarely need a mouse. Submit, navigate, copy, open-in-editor — all reachable via keyboard.
5. **Stable layout.** Content shifts during streaming are a bug. Reserve space for the components that will appear.
6. **Sensible defaults, escapable.** A new user should get value without configuring anything. A power user should be able to override every default.
7. **Trust through citations.** Every claim the agent makes links back to a specific file path and line range. No claim without a citation.

## 3. Information architecture

RepoLens has a small, deliberate set of surfaces. Resist adding new top-level screens.

### 3.1 Top-level surfaces

```
┌─────────────────────────────────────────────────────────────┐
│  Top bar  │  Repo selector  │  User menu                    │
├──────────┬─────────────────────────────────┬────────────────┤
│          │                                 │                │
│  Sessions│           Chat surface          │  Trace panel   │
│  list    │  (messages, streaming response) │  (chunks /     │
│  (left   │                                 │   tool calls)  │
│  rail)   │  ──────────────────────────────│                │
│          │           Composer             │                │
└──────────┴─────────────────────────────────┴────────────────┘
```

- **Top bar.** Repo selector (active repository), user menu, status indicator (ingestion progress, connection state).
- **Left rail — Sessions list.** Past conversations for the active repo. Collapsible. Search by title.
- **Center — Chat surface.** Messages, streaming agent response, citations. The composer is anchored at the bottom.
- **Right rail — Trace panel.** Retrieved chunks (Phase 2+), agent tool calls (Phase 3+), and reasoning steps. Collapsible.

### 3.2 Secondary surfaces

- **Repository management.** Add/remove a repository, view ingestion status, re-index.
- **Settings.** Model selection (when exposed), retrieval defaults, theme.
- **Auth surfaces.** Sign-in, sign-out, session expired states.

There are no marketing pages, no tutorials inside the app, no onboarding carousels. A short empty-state with a single example prompt is the entire onboarding.

## 4. Core user flows

### 4.1 First-time user

1. User signs in (OAuth/OIDC at the API edge; JWT to the client).
2. User lands on an empty chat surface with a single CTA: **"Add a repository"**.
3. User adds a repo (URL or local path, depending on deployment). Ingestion starts; the top bar shows progress.
4. Once ingestion crosses a usable threshold, the composer becomes active. A short "Try asking..." example prompt is shown — one example, not a list.
5. User asks a question; the answer streams; chunks appear in the trace panel as they are retrieved.

### 4.2 Returning user

1. Last active repo is preselected.
2. Last session is recoverable from the left rail. New session is one keystroke away (`Cmd/Ctrl + N`).
3. Asking a question is the default action — focus lands in the composer.

### 4.3 Asking a question (the hot loop)

1. User types in the composer; submits with `Enter` (Shift+Enter for newline).
2. The user message renders immediately.
3. A streaming agent message appears beneath it. Tokens arrive as they are produced.
4. In Phase 2+, the trace panel populates with retrieved chunks as the retrieval call returns.
5. In Phase 3+, the trace panel shows tool calls in order with their arguments and a one-line summary of the result.
6. Citations in the answer are clickable. Clicking opens the corresponding chunk in the trace panel and scrolls it into view.

### 4.4 Inspecting a citation

1. Citation in the answer is rendered inline as `path/to/file.py:42-78`.
2. Clicking it focuses the corresponding chunk in the trace panel.
3. The chunk shows the file path, line range, language-specific syntax highlighting, and a "Open in editor" affordance (where supported by deployment).

### 4.5 Adding / re-indexing a repository

1. User opens repository management from the top bar.
2. Adds a repository (URL or path); ingestion is queued.
3. Status is visible: queued → cloning → parsing → embedding → indexing → ready.
4. Re-index is a single button per repo; previous embeddings are invalidated by content hash, not deleted blindly.

## 5. Component conventions

### 5.1 Composition

- Standalone components only. No NgModules.
- Components are dumb where possible. Inputs in, outputs out, signals for local UI state.
- Feature folders own their components (`features/chat/`, `features/repos/`, `features/traces/`); cross-feature components live in `shared/`.
- One component per concern. A `MessageList` does not own a composer; a `Composer` does not own message rendering.

### 5.2 Naming (UI-facing)

- File names: `kebab-case.component.ts`, `kebab-case.component.html`, `kebab-case.component.scss`.
- Class names: `PascalCaseComponent`.
- Selectors: `rl-<feature>-<role>` — `rl-chat-shell`, `rl-trace-panel`, `rl-message-bubble`. The `rl-` prefix avoids collisions with library components.

### 5.3 Inputs, outputs, signals

- Use `input()` / `input.required()` for inputs, `output()` for outputs (Angular 17.3+ signal APIs). No legacy `@Input` / `@Output` decorators in new code.
- Local state uses `signal()`. Derived state uses `computed()`. `effect()` is reserved for synchronization with the outside world (logging, persistence, scroll behavior).
- Components default to `OnPush` change detection.

## 6. Streaming UX

Streaming is core to the experience. The rules below are non-negotiable.

- **Token streaming.** Agent responses render token-by-token. The cursor at the end of the streaming bubble pulses to indicate progress.
- **Tool-call events.** When the agent invokes a tool, an event is rendered into the trace panel immediately, with its arguments. When the tool returns, the event is updated in place — never duplicated.
- **Cancellation is first-class.** A streaming response can be cancelled by the user (`Esc` or a visible "Stop" button). Cancellation is not a hard error; the partial response is preserved.
- **Reconnection.** SSE drops are handled centrally in a `StreamingService`. The user sees a brief "Reconnecting…" status, not a wall of red.
- **Backpressure.** If tokens arrive faster than the UI can render (rare, but possible on poor devices), batching happens at the service layer; the chat surface is never blocked.
- **No fake streaming.** If a response is not actually streaming (e.g., a small synchronous endpoint), it is rendered in one frame. Don't simulate streaming with `setTimeout`.

## 7. Trace panel

The trace panel is the system's accountability layer. It is the difference between RepoLens and a black-box chatbot.

- **Retrieved chunks** (Phase 2+). Listed in the order the agent received them after reranking. Each chunk shows file path, line range, language tag, and the chunk content with syntax highlighting. The relevance score is shown but de-emphasized.
- **Tool calls** (Phase 3+). Listed chronologically. Each entry shows tool name, arguments, a result summary, and is expandable for full input/output.
- **Reasoning steps** (Phase 3+). When the agent emits an intermediate "thinking" message, it is rendered as a muted line in the trace panel — not in the main chat.
- **Linked to citations.** Clicking a citation in the answer scrolls the corresponding chunk into view in the panel. Hovering a chunk highlights its citation in the answer.
- **Collapsible.** The panel can be collapsed for screen-real-estate reasons, but it is open by default. Don't hide the system's homework.

## 8. Empty, loading, and error states

Every surface has a defined state for each of these. Never leave a blank component.

- **Empty.** A short, specific message and one suggested action. "No sessions yet — ask a question to start one." Not "No data."
- **Loading.** Skeleton placeholders for content with predictable shape (chunk lists, message bubbles). Spinner only for genuinely indeterminate operations.
- **Error.** Plain language, what went wrong, what to do next. Include a retry affordance where applicable. Do not show stack traces to end users; show a correlation ID they can paste into a support channel.
- **Degraded.** When ingestion is incomplete, the composer is disabled with a clear "Indexing…" message and a progress estimate. The user is never silently shown stale data.

## 9. Styling and design tokens

### 9.1 Tooling

- **Tailwind CSS** for layout, spacing, typography utilities.
- **Component library** — Angular Material or PrimeNG (one is chosen at the start of frontend work; do not mix). Used for complex widgets: dialogs, menus, snack bars, tables.
- **No inline `style="..."`.** No hex codes scattered through templates.

### 9.2 Tokens

Design tokens are defined once in `frontend/src/styles/tokens.scss` (or an equivalent Tailwind config layer) and referenced everywhere else.

- **Color.** Semantic names — `--color-bg`, `--color-bg-muted`, `--color-text`, `--color-text-muted`, `--color-accent`, `--color-success`, `--color-warning`, `--color-danger`. Never reference raw hex codes in components.
- **Spacing.** Use Tailwind's spacing scale (`p-2`, `gap-4`, `mt-6`). Do not introduce one-off pixel values.
- **Typography.** A small set: display, body, code. Code uses a monospaced stack (`ui-monospace, SFMono-Regular, ...`). Body and display share a sans-serif stack.
- **Radius and elevation.** Two corner radii (small, medium). Two elevations (rest, raised). Resist adding more.

### 9.3 Theme

- **Dark mode is first-class.** Developers spend hours in dark IDEs; the default theme is dark. Light mode is supported and respects `prefers-color-scheme`.
- **Theme is applied via CSS variables on `:root`.** Components reference variables, not theme values directly.
- **Code blocks** use a syntax-highlight theme that matches the active app theme.

## 10. Code rendering

Code is content of record in this product. It is not a decoration.

- **Syntax highlighting.** A library that supports the languages RepoLens ingests (TypeScript, Python, Go, Rust, Java, JavaScript, etc.). Highlighting is consistent between the chat surface (when the agent quotes code) and the trace panel.
- **Fixed-width font, no line wrapping inside code blocks.** Horizontal scroll instead. Wrapping breaks code reading.
- **Line numbers.** Shown for chunk views in the trace panel. Aligned to the file's actual line numbers, not chunk-relative.
- **Copy-to-clipboard.** Every code block has an unobtrusive copy affordance.
- **No editing in code blocks.** RepoLens displays code; it does not edit code.

## 11. Keyboard shortcuts

Power users do not click. The minimum shortcut surface:

- **`/` or `Cmd/Ctrl + K`** — focus the composer.
- **`Cmd/Ctrl + Enter`** — submit message (alternate to plain `Enter`, useful when multi-line is the default).
- **`Esc`** — cancel current streaming response; close any open dialog.
- **`Cmd/Ctrl + N`** — new session.
- **`Cmd/Ctrl + B`** — toggle left rail.
- **`Cmd/Ctrl + I`** — toggle trace panel.
- **`?`** — open keyboard shortcut reference.

Shortcuts are listed in a single, discoverable cheatsheet behind `?`. They are documented in code, not folklore.

## 12. Accessibility

- **WCAG 2.1 AA** is the target. New components are evaluated against it.
- **Color contrast.** All text/background pairs meet AA contrast in both themes.
- **Focus management.** Visible focus rings always. Tab order is logical. Modals trap focus and restore it on close.
- **Semantic markup.** Buttons are `<button>`, links are `<a>`. ARIA roles only when semantics cannot be expressed natively.
- **Live regions.** Streaming messages use an `aria-live="polite"` region so screen readers announce updates without overwhelming.
- **Reduced motion.** Animations respect `prefers-reduced-motion`.
- **Keyboard parity.** Every action achievable with a mouse is achievable with a keyboard.

## 13. Responsiveness

RepoLens is desktop-first; mobile is a courtesy view, not a primary surface.

- **≥ 1280px** — full three-pane layout (left rail, chat, trace panel).
- **768–1279px** — trace panel collapses to a slide-over; left rail collapses to icons.
- **< 768px** — single-column chat. Trace panel and rail are accessed via overlays. Some power-user features are de-prioritized; the read path remains usable.

Layout breakpoints are defined as design tokens; components do not introduce new ones.

## 14. Internationalization

- **English-first.** Copy lives in resource files (`.json` or Angular's `$localize`) from day one, even before translation is funded.
- **No string concatenation in templates.** Use placeholders so translators can reorder.
- **Code, file paths, symbol names, and citations are never localized.** They are user data.

## 15. Performance budgets

- **Initial JS payload (gzip):** ≤ 250 KB on the chat surface.
- **First contentful paint:** < 1.5s on a baseline laptop.
- **Time to interactive:** < 2.5s on a baseline laptop.
- **Streaming UI overhead:** rendering 1k tokens of streamed text should not drop below 60fps on a baseline laptop.
- **Lazy-load** every non-critical surface (settings, repo management).

Bundles and route chunks are checked in CI; regressions outside budget block the merge.

## 16. Observability (frontend)

- **Errors** are reported to a structured client logger (Sentry-style) with the trace ID from the active request.
- **Performance marks** are emitted around streaming start, first token, and stream end. Slow streams are surfaced in dashboards.
- **No PII or repository content** in client telemetry. Identifiers and shapes only.

## 17. What this product is not

These are recurring asks that should be politely declined unless scope explicitly changes:

- **Not an editor.** RepoLens does not modify the user's repository.
- **Not a code review tool.** It explains code; it does not score PRs.
- **Not a generic chat client.** Every feature serves understanding-an-existing-codebase. New features are evaluated against that goal.
- **Not a marketing surface.** No banners, popovers, or upsells inside the product.

## 18. Source

This UI context derives from the frontend stack and primary user stories defined in `REPOLENS-PRD.md` v1.1.0, the architectural choices in `architecture-context.md`, and the conventions in `code-standards.md`. When the product scope or stack changes, this document is updated in the same PR.
