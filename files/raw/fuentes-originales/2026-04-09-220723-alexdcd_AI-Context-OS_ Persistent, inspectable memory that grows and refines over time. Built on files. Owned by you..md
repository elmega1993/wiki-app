---
title: "alexdcd/AI-Context-OS: Persistent, inspectable memory that grows and refines over time. Built on files. Owned by you."
source: "https://github.com/alexdcd/AI-Context-OS"
author:
published:
created: 2026-04-09
description: "Persistent, inspectable memory that grows and refines over time. Built on files. Owned by you. - alexdcd/AI-Context-OS"
tags:
  - "clippings"
---
## MEMM - AI Context OS

Translations:

- [ES](https://github.com/alexdcd/AI-Context-OS/blob/main/README.es.md)
- Website: [https://memm.dev/](https://memm.dev/)

Extended system docs:

- [Documentation Index](https://github.com/alexdcd/AI-Context-OS/blob/main/docs/README.md)
- [Technical Paper](https://github.com/alexdcd/AI-Context-OS/blob/main/docs/paper.md)
- [Technical Whitepaper](https://github.com/alexdcd/AI-Context-OS/blob/main/docs/whitepaper.md)

AI Context OS is a desktop app (`Tauri v2 + React + TypeScript + Rust`) that turns a local folder into a universal, tool-agnostic memory layer for AI agents.

This project is not a chat UI and not a wrapper around one provider. It is a filesystem-first brain layer with deterministic context loading (`L0/L1/L2`) and adapter-based integrations.

## Core thesis

- Canonical state lives in files.
- Context is routed, not improvised.
- Integrations are adapters, never the source of truth.
- UX should only promise real capabilities.
- Context quality must be observable and governable.

## Storage model (important clarification)

AI Context OS is filesystem-first:

- Memories, journal pages, tasks, rules, router artifacts, and scratch output are plain files in the workspace.
- The canonical source of truth is the workspace file tree.

AI Context OS also uses a local SQLite DB for observability:

- Path: `{workspace}/.cache/observability.db`
- Purpose: telemetry and optimization signals (requests served, usage stats, health snapshots, pending optimizations)
- Non-canonical: it does not replace or own your memory data model

## Progressive memory model: L0, L1, L2

Every memory has 3 levels:

- `L0`: one-line summary in frontmatter (`l0`)
- `L1`: operational summary body
- `L2`: full detail body

Memory files are Markdown with YAML frontmatter and level markers:

```
---
id: stack-tecnologico
type: context
l0: "Project tech stack and conventions"
importance: 0.9
tags: [stack, architecture]
related: [convenciones-codigo]
---

<!-- L1 -->
Short operational summary.

<!-- L2 -->
Long-form detailed content.
```

## Workspace structure

AI Context OS uses a "Zero Gravity" architecture: the physical folder a file lives in has **zero impact** on its semantic classification. The system scans recursively and classifies everything via YAML frontmatter.

```
~/AI-Context-OS/
├── inbox/          ← temporary capture zone (landing pad)
├── sources/        ← external references (read-only by default)
├── .ai/            ← hidden system infrastructure
│   ├── rules/      ← behavioral rules for AI agents (top attention)
│   ├── journal/    ← daily logs and sessions
│   ├── tasks/      ← task tracking
│   ├── scratch/    ← temporary AI output buffer (TTL-based)
│   ├── config.yaml ← workspace configuration
│   └── index.yaml  ← auto-generated L0 catalog
├── User_Folders/   ← cosmetic, user-defined (e.g., Projects/, Notes/)
├── .cache/
├── claude.md       ← master router (auto-generated)
├── .cursorrules
└── .windsurfrules
```

Key notes:

- System infrastructure is fixed: `inbox/`, `sources/`, and `.ai/` — everything else is user-defined.
- Journal pages live in `.ai/journal/YYYY-MM-DD.md`.
- Tasks are markdown files in `.ai/tasks/` with YAML frontmatter.
- `claude.md` exists for compatibility, but the architecture target is adapter-first with neutral core output.
- Moving a memory file between user folders does **not** break indexing — classification comes from `type:` in frontmatter.

## Architecture

### Frontend

- React app shell and routes in [src/App.tsx](https://github.com/alexdcd/AI-Context-OS/blob/main/src/App.tsx)
- State in [src/lib/store.ts](https://github.com/alexdcd/AI-Context-OS/blob/main/src/lib/store.ts) and [src/lib/settingsStore.ts](https://github.com/alexdcd/AI-Context-OS/blob/main/src/lib/settingsStore.ts)
- IPC bridge in [src/lib/tauri.ts](https://github.com/alexdcd/AI-Context-OS/blob/main/src/lib/tauri.ts)
- TS contracts in [src/lib/types.ts](https://github.com/alexdcd/AI-Context-OS/blob/main/src/lib/types.ts)

### Backend

- Tauri bootstrap and command registry in [src-tauri/src/lib.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/lib.rs)
- Shared runtime state in [src-tauri/src/state.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/state.rs)
- Domain types in [src-tauri/src/core/types.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/types.rs)
- Scoring in [src-tauri/src/core/scoring.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/scoring.rs)
- Router + adapters in [src-tauri/src/core/router.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/router.rs) and [src-tauri/src/core/compat.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/compat.rs)
- Observability in [src-tauri/src/core/observability.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/observability.rs)
- MCP servers in [src-tauri/src/core/mcp.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/mcp.rs) and [src-tauri/src/core/mcp\_http.rs](https://github.com/alexdcd/AI-Context-OS/blob/main/src-tauri/src/core/mcp_http.rs)

## What is working right now (verified from code)

Implemented and wired:

- Workspace initialization, config load/save, and watcher rebind
- Memory CRUD (create/read/update/delete + file operations like rename/duplicate/move)
- File tree and raw file read/write from UI
- Router regeneration and adapter artifact writing (`claude.md`, `.cursorrules`, `.windsurfrules`)
- Context simulation endpoint and scoring pipeline
- Graph data generation and graph view
- Governance checks: conflicts, decay candidates, consolidation suggestions, scratch TTL candidates
- Journal pages (`get/save/list/get_today`)
- Task CRUD and task-state toggle
- Onboarding flow and template bootstrap
- Backup/restore commands
- Observability queries + health score + optimization suggestion flow
- MCP stdio server and MCP HTTP server (`127.0.0.1:3847/mcp`)
- Connectors page with local status and bridge actions (copy context, generate handoff file)

Working with limitations (important):

- Bridge tier currently supports copy/handoff flows, not full remote-native integration.
- Connector capabilities vary by tool; “universal” means universal core model + adapters, not identical feature depth everywhere.
- Some UX labels/copy still need consistency polish.

## Roadmap

This roadmap reflects the current codebase plus the alignment doc (`REVISION-TECNICA-ALINEACION-2026-03-29.md`).

### 1\. Adapter-first hardening

- Keep neutral core generation as primary architecture.
- Preserve compatibility artifacts (`claude.md`) without letting them become canonical.
- Continue reducing implicit tool-specific assumptions in core flows.

### 2\. Connector honesty and tier clarity

- Keep clear tiers (`Local Native`, `Bridge`, future `Remote`).
- Match UI copy to real capabilities per connector.
- Expand bridge handoff ergonomics without over-claiming.

### 3\. Deterministic scoring evolution

- Continue conservative improvements in lexical expansion and intent weighting.
- Improve graph proximity in bounded, interpretable steps.
- Avoid opaque retrieval dependencies that break portability.

### 4\. Governance + observability loop

- Turn optimization suggestions into safer guided actions.
- Improve health score explainability and user trust.
- Use telemetry to reduce context overloading and stale memory accumulation.

## Invariants (do not break)

- `src/lib/types.ts` must mirror `src-tauri/src/core/types.rs`
- New Rust command must be registered in:
- UI text should be Spanish by default in product screens
- Theme must use CSS variables, no hardcoded ad-hoc colors
- Keep `L0/L1/L2` memory semantics explicit across docs and code

## Development

Requirements:

- Node.js + npm
- Rust toolchain
- Tauri v2 system dependencies

Commands:

```
npm install
npm run dev
npm run tauri dev
npm run build
```

Release by Git tag:

```
git tag v0.1.0
git push origin v0.1.0
```