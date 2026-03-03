# Copilot Instructions — Augment Chat

## What Is This Project?

This is the **augment_chat sub-project** of the Augment Chat monorepo. It is the AI pipeline that processes Matrix chat messages and generates conversation suggestions.

> **Note:** This code currently lives at the monorepo root. It will be moved into its own `augment_chat/` subfolder in a future reorganisation.

### The Bigger Picture

The full platform works like this:

```
matrix_manager
    └── provisions → homeserver instances
                         └── Synapse + bridge manager
                                  └── bridges (WhatsApp, Telegram, etc.)
                                           └── Matrix events
                                                    └── augment_chat pipeline  ← THIS PROJECT
                                                             └── AI suggestions
```

`homeserver/` and `matrix_manager/` are sibling sub-projects in the monorepo. See the root `.github/copilot-instructions.md` for the full monorepo overview.

---

## What This Project Does

Ingests Matrix-bridged chat events, builds transcripts + vector embeddings, and serves AI-generated joke/conversation suggestions via FastAPI.

**Event-driven pipeline:**
```
PostgreSQL logical replication
    → event_processor  (parse + store events)
    → vector_store     (build transcripts + embeddings)
    → llm_service      (generate suggestions via LLM)
    → suggestions_service
    → FastAPI /generate_suggestion
```

Work is distributed across Redis/RQ queues: `event_processor`, `vector_store`, `llm`.

---

## Key Modules & Files

| Path | Purpose |
|---|---|
| `api/main.py` | FastAPI app — `/transcripts`, `/backfill_transcripts`, `/generate_suggestion` |
| `event_processor/` | Handles replication triggers, parsing, storage; see `event_processor/README.MD` |
| `vector_store/` | Transcripts, chunking, embeddings, enrichment; see `vector_store/README.md` |
| `llm_service/` | LLM providers and async job handling via RQ; see `llm_service/README.md` |
| `suggestions_service/` | Prompt construction and suggestion generation (`prompts.py`, `suggestions.py`) |
| `bridge_manager/` | AppService integration, homeserver configs, Matrix client |
| `users_service/` | Matrix account creation and auth flows |
| `queue_controller/` | RQ queue and worker management (`queue_controller.py`) |
| `config.py` | Global config (`GlobalConfig`) — DB, Redis, debug flags |
| `docs/ARCHITECTURE.md` | High-level design and data flow |

---

## Conventions & Patterns

- **Per-service isolation:** Each service has its own `database/` package with `engine.py`, `models.py`, `repositories.py`. Follow this layout when adding new services.
- **RQ queues via `QueueController`:** Use `QueueController().get_queue("vector_store")` etc. Respect `GlobalConfig.DEBUG_MODE` and `GlobalConfig.USE_FAKE_REDIS` for sync/testing.
- **Interfaces:** Import service entry points via interface modules (e.g. `from vector_store import VectorStoreInterface`). Prefer these over direct class access.
- **Enrichment:** Vector store supports user/profile enrichment. New enrichers should live under `vector_store/` and be wired through transcript building.
- **Config first:** Check `GlobalConfig` and per-module `config.py` before adding env vars — keep flags centralised.
- **FastAPI responses:** Return JSON-ready dicts/lists. API endpoints in `api/main.py` expect repository outputs directly.

---

## Dev Workflows

```bash
# Run API locally
python run_api.py
# Starts api.main:app via Uvicorn. CORS allows localhost:5500.

# Generate a suggestion
GET /generate_suggestion?room_id=<matrix_room_id>&until_message_event_id=<optional_event_id>
# Polls RQ job, returns latest suggestions from SuggestionsRepository.

# Backfill transcripts
POST /backfill_transcripts?room_id=<matrix_room_id>
# Triggers vector_store.backfill_room(room_id).
```

---

## When Adding Features

- Add new service with `interface.py`, `config.py`, and `database/` (`engine.py`, `models.py`, `repositories.py`).
- Wire async tasks through RQ queues; update `QueueController.QUEUES` if introducing a new queue.
- Prefer repository methods for DB interactions; keep SQLAlchemy models in per-service `models.py`.
- Use existing endpoint patterns: simple params, return JSON dicts, poll jobs if async.

---

## Gotchas

- `GlobalConfig.DEBUG_MODE` affects RQ `is_async` — verify before assuming background processing.
- Per-module configs may override globals; check the local `config.py` in the service you're working in.
- Matrix/bridge configs live under `bridge_manager/appservice/`; ensure homeserver/registration files align when bridging.

---

## Quick Pointers

- Start with `docs/ARCHITECTURE.md` for system flow.
- `event_processor/README.MD`, `vector_store/README.md`, `llm_service/README.md` for concrete setup steps.
- `run_api.py` for quick API startup during development.
- `queue_controller/queue_controller.py` for queue names and worker management.

---

## Keep This File Updated

Update this file when:
- A new service or module is added to the pipeline
- The queue structure changes
- Key architectural decisions are made
- The code is moved into its own `augment_chat/` subfolder (update paths accordingly)
