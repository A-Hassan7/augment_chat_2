# Copilot Instructions for Augment Chat

## Big Picture
- **Purpose:** Backend that ingests Matrix-bridged chat events, builds transcripts + embeddings, and serves joke suggestions via FastAPI.
- **Event-driven pipeline:** PostgreSQL logical replication → `event_processor` parses/store → `vector_store` builds transcripts/embeddings → `llm_service` and `suggestions_service` generate suggestions.
- **Queues:** Work is distributed via Redis/RQ queues: `event_processor`, `vector_store`, `llm` (see `queue_controller/queue_controller.py`).
- **Bridges:** WhatsApp and other platforms connect through Matrix Synapse bridges managed by `bridge_manager`.

## Key Modules & Files
- API: `api/main.py` FastAPI app exposing `/transcripts`, `/backfill_transcripts`, `/generate_suggestion`.
- Event Processor: `event_processor/` handles replication triggers, parsing, storage; see `event_processor/README.MD`.
- Vector Store: `vector_store/` transcripts, chunking, embeddings, enrichment; see `vector_store/README.md`.
- LLM Service: `llm_service/` providers and async job handling via RQ; see `llm_service/README.md`.
- Suggestions: `suggestions_service/` prompts and suggestion generation; `prompts.py`, `suggestions.py`.
- Bridge Manager: `bridge_manager/` appservice integration, homeserver configs, and client; see `bridge_manager/appservice/*.py`.
- Users: `users_service/` Matrix account creation/auth flows.
- Config: `config.py` (global), plus per-module `config.py` files controlling DB/Redis and debug flags.
- DB Layer: `*/database/` with `engine.py`, `models.py`, `repositories.py` per service.
- Architecture Doc: `docs/ARCHITECTURE.md` high-level design and data flow.

## Conventions & Patterns
- **Per-service isolation:** Each service has its own `database` package and repository layer. Follow this layout when adding new services.
- **RQ queues via `QueueController`:** Use `QueueController().get_queue("vector_store")` etc. Respect `GlobalConfig.DEBUG_MODE` and `GlobalConfig.USE_FAKE_REDIS` for sync/testing.
- **Interfaces:** Import service entry points via interface modules (e.g., `from vector_store import VectorStoreInterface`). Prefer these over direct class access.
- **Enrichment:** Vector store supports user/profile enrichment. New enrichers should live under `vector_store/` and be wired through transcript building.
- **Config first:** Check `GlobalConfig` and per-module `config.py` before adding env vars; keep flags centralized.
- **FastAPI responses:** Return JSON-ready dicts/lists. API endpoints in `api/main.py` expect repository outputs directly.

## Dev Workflows
- **Run API locally:**
  ```zsh
  python run_api.py
  ```
  - App runs `api.main:app` with Uvicorn. CORS allows `localhost:5500`.

- **Generate a suggestion (typical call):**
  - `GET /generate_suggestion?room_id=<matrix_room_id>&until_message_event_id=<optional_event_id>`
  - Endpoint polls RQ job and returns latest suggestions from `SuggestionsRepository`.

- **Backfill transcripts:**
  - `POST /backfill_transcripts?room_id=<matrix_room_id>` triggers `vector_store.backfill_room(room_id)`.

- **Queues & testing:**
  - For synchronous execution during dev/tests, set debug to use `FakeStrictRedis` via `GlobalConfig` flags. Workers are managed per queue.

## Integrations & Data Flow
- **Matrix Synapse:** Upstream message source; events replicated into local DB (`event_json`).
- **PostgreSQL logical replication:** Inserts trigger notifications consumed by `event_processor` to parse and store into `parsed_messages` and `processed_events`.
- **Redis/RQ:** Asynchronous job dispatch for event → vector → LLM → suggestion pipeline.

## Examples You Can Follow
- **API to Vector Store:** `api/main.py:get_transcripts` calls `VectorStoreInterface.get_transcripts_by_room_id(room_id, limit)` and returns plain JSON.
- **Suggestion Job:** `api/main.py:generate_suggestion` enqueues `Suggestions.generate_jokes(room_id, until_message_event_id)` and polls status for up to ~20s.
- **Queue usage:** `queue_controller/queue_controller.py` shows queue names and how to get `Queue` and `Worker` instances.

## When Adding Features
- Add new service with `interface.py`, `config.py`, and `database/` (`engine.py`, `models.py`, `repositories.py`).
- Wire async tasks through RQ queues; update `QueueController.QUEUES` if introducing a new queue.
- Prefer repository methods for DB interactions; keep SQLAlchemy models in per-service `models.py`.
- Use existing endpoint patterns for API: simple params, return JSON dicts, poll jobs if async.

## Gotchas
- `GlobalConfig.DEBUG_MODE` affects RQ `is_async`; verify before assuming background processing.
- Per-module configs may override globals; check local `config.py` in the service.
- Matrix/bridge configs live under `bridge_manager/appservice`; ensure homeserver/registration files align when bridging.

## Quick Pointers
- Start with `docs/ARCHITECTURE.md` for system flow.
- Inspect `event_processor/README.MD`, `vector_store/README.md`, `llm_service/README.md` for concrete setup steps.
- Use `run_api.py` for quick API brings-up while developing.
