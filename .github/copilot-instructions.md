# Copilot Instructions for Augment Chat Monorepo

## What This Repo Is
**Augment Chat** is a monorepo containing three sub-projects that together form a platform for bridging external chat platforms (WhatsApp, Telegram, etc.) into Matrix, processing those messages, and generating AI-powered suggestions.

```
augment_chat/                  ← monorepo root
├── homeserver/                ← Matrix infrastructure (Synapse deployment + bridge management)
├── matrix_manager/            ← Orchestrates and manages homeserver deployments
├── augment_chat/              ← AI pipeline (events → embeddings → suggestions) [root level for now]
└── augment_chat.code-workspace
```

Open `augment_chat.code-workspace` to see all three projects in VS Code. To scope a coding agent to a single project, open that subfolder directly.

---

## The Three Sub-Projects

### 1. `homeserver/`
Manages a single Matrix homeserver deployment. Responsible for:
- Deploying Synapse + workers + Postgres + monitoring via Docker
- Running the **bridge manager appservice** — a FastAPI proxy that sits between Synapse and individual bridge containers
- Provisioning and managing bridge containers (WhatsApp, etc.) via the orchestrator

**Entry points:**
- `homeserver/deploy.py` — deploys the Synapse stack
- `homeserver/run_bridge_manager.py` — starts the bridge manager appservice

**Has its own:** `.env`, `config.py`, `requirements.txt`, `README.md`, `.github/copilot-instructions.md`

> When working on `homeserver/` open it as an isolated folder so the agent uses its own instructions file.

---

### 2. `matrix_manager/`
Orchestrates **multiple homeserver deployments** from a central place. Responsible for:
- Provisioning new homeserver instances
- Managing capacity and routing users to the right homeserver
- High-level homeserver lifecycle (create, scale, destroy)

> This project is earlier in development. Check `matrix_manager/` for current state.

---

### 3. `augment_chat/` (root level)
The AI pipeline that processes Matrix chat events and generates suggestions. Responsible for:
- Ingesting Matrix events via PostgreSQL logical replication
- Parsing, storing, and building transcripts + embeddings
- Generating AI suggestions via LLM

**Key modules:** `api/`, `event_processor/`, `vector_store/`, `llm_service/`, `suggestions_service/`, `users_service/`, `bridge_manager/`, `queue_controller/`

---

## How The Projects Relate

```
matrix_manager
    └── provisions and manages → homeserver instances
                                      └── Synapse + bridge manager
                                                └── bridges (WhatsApp etc.)
                                                        └── Matrix events
                                                                └── augment_chat pipeline
                                                                        └── AI suggestions
```

---

## Workspace & Dev Setup

```bash
# Open full monorepo
code augment_chat.code-workspace

# Work on a single project in isolation
code homeserver/
code matrix_manager/
```

Each sub-project manages its own dependencies and environment. See the `README.md` inside each subfolder for setup instructions.

---

## Gotchas
- `homeserver/` was previously located at `matrix_manager/homeserver/` — it has been moved to the repo root.
- The `augment_chat` sub-project code currently lives at the repo root (not in an `augment_chat/` subfolder). This will be reorganised in future.
- Each sub-project has its own `.env` file — do not mix environment variables between projects.
- When making cross-project changes, use the full workspace (`augment_chat.code-workspace`) so all paths resolve correctly.

---

## Keeping This File Up To Date
Update this file when:
- A new sub-project is added to the monorepo
- A sub-project is moved or renamed
- The relationship between projects changes significantly
