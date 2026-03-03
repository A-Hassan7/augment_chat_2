# Copilot Instructions — Matrix Homeserver

## What Is This Project?

This is the **homeserver sub-project** of **Augment Chat** (`augment_chat/`). It lives at `homeserver/` (repo root) and is intentionally self-contained — its own virtualenv, dependencies, config, and database schema.

### The Bigger Picture: Augment Chat

Augment Chat is a backend that:
1. Ingests chat messages from WhatsApp (and other platforms) via Matrix Synapse bridges
2. Builds conversation transcripts and vector embeddings
3. Uses LLMs to generate joke/conversation suggestions
4. Exposes suggestions via a FastAPI endpoint

The full pipeline: `Matrix Synapse → PostgreSQL replication → event_processor → vector_store → llm_service → suggestions_service → FastAPI`

Messages arrive through **Matrix bridges** (WhatsApp, Telegram, etc.). Each bridge connects to a **Synapse homeserver**. Those homeservers are what this sub-project provisions and manages.

### Where This Project Fits

```
augment_chat/               ← monorepo root
├── augment_chat code        ← AI pipeline (events, embeddings, suggestions)
├── matrix_manager/          ← orchestration layer (assigns users to homeservers,
│                               routes operations, tracks capacity) — IN PROGRESS
└── homeserver/              ← THIS PROJECT
    ├── deploy.py                 runs the Synapse Docker stack
    ├── run_bridge_manager.py     starts the bridge proxy appservice
    └── ...
```

**The matrix_manager** is the component responsible for orchestrating and managing multiple homeserver deployments. It will:
- Assign users to homeservers based on capacity
- Deploy new homeserver instances on demand via `deploy.py`
- Route Matrix operations to the correct homeserver
- Track homeserver health and capacity

The `homeserver/` project provides the per-homeserver tooling that `matrix_manager` calls into.

---

## What This Project Does

Two independent processes:

| Process | Script | What it does |
|---|---|---|
| Synapse stack | `deploy.py` | Provisions all Docker containers for a homeserver |
| Bridge Manager | `run_bridge_manager.py` | Starts the FastAPI appservice proxy for bridges |

### 1. Synapse Stack (`deploy.py`)

Deploys a full Matrix homeserver as Docker containers on an isolated network:

- `{id}_postgres` — PostgreSQL database
- `{id}_redis` — Worker replication (only in distributed mode)
- `{id}_synapse` — Synapse main process (:8008)
- `{id}_worker_N` — Generic workers (:8100+)
- `{id}_nginx` — Load balancer (:80) with consistent IP hashing
- `{id}_prometheus` — Metrics (:9090)
- `{id}_grafana` — Dashboards (:3000)

Each homeserver's data lives in `deployments/{homeserver-id}/`.

Workers can be scaled up/down without redeployment:
```bash
python3 helpers/worker_manager.py hs-001 --scale 5
```

### 2. Bridge Manager (`run_bridge_manager.py`)

A FastAPI proxy (`:5001`) that sits between Synapse and bridge containers. It:
- Authenticates and routes requests in both directions (HS→bridge, bridge→HS)
- Swaps auth tokens transparently so bridges and Synapse never need direct knowledge of each other
- Provisions bridge containers on demand via `BridgeOrchestrator`
- Logs every request to `bridge_manager.request_logs`

See `bridge_manager/appservice/README.md` and `bridge_manager/orchestrator/README.md` for full detail.

---

## Key Files & Modules

| Path | Purpose |
|---|---|
| `config.py` | **Single source of truth** for all config — `BridgeManagerConfig`, `WhatsAppBridgeConfig`, port assignments, Docker images |
| `deploy.py` | `DeploymentPlan` class — builds and executes the Docker service list |
| `run_bridge_manager.py` | Entry point — initialises DB schema, registers homeserver, starts FastAPI |
| `services/` | One class per Docker service (`postgres.py`, `synapse.py`, `nginx.py`, etc.) each inheriting `BaseService` |
| `helpers/worker_manager.py` | CLI tool for scaling workers up/down |
| `helpers/nginx_manager.py` | Regenerates and reloads Nginx upstream config |
| `bridge_manager/appservice/appservice.py` | Two FastAPI proxy endpoints (HS→bridge, bridge→HS) |
| `bridge_manager/request_logger_ui/` | Browser-based inspector for `request_logs` — run with `python3 -m bridge_manager.request_logger_ui` |
| `bridge_manager/appservice/router.py` | `BridgeRouter` — 8-strategy bridge discovery |
| `bridge_manager/appservice/registry.py` | `BridgeRegistry` — bridge lookup with caching |
| `bridge_manager/orchestrator/orchestrator.py` | `BridgeOrchestrator` — full bridge container lifecycle |
| `bridge_manager/orchestrator/bridges/whatsapp_bridge.py` | `WhatsAppBridge` — per-instance state (tokens, IDs, port, volume name) |
| `bridge_manager/database/models.py` | SQLAlchemy models: `Bridge`, `Homeserver`, `RequestLog`, `RoomBridgeMapping`, etc. |
| `bridge_manager/database/repositories.py` | All DB access via repository classes — no raw SQL in app code |
| `bridge_manager/logger.py` | `BridgeLogger` (stdout) + `RequestTracker` (DB logging) |

---

## Conventions & Patterns

- **Config is centralised in `config.py`** — never hardcode images, ports, tokens, or paths. `BridgeManagerConfig` is the single instance (`BRIDGE_MANAGER_CONFIG`). `WhatsAppBridgeConfig` is accessed via `BRIDGE_MANAGER_CONFIG.WHATSAPP`.

- **Static bridge config vs instance state** — `WhatsAppBridgeConfig` in `config.py` owns static settings (Docker image, template, health endpoints). `WhatsAppBridge` in `bridges/whatsapp_bridge.py` owns per-instance runtime state (tokens, IDs, ports, volume name). Don't put static config on the bridge class.

- **Repository pattern** — all DB access goes through `*Repository` classes in `bridge_manager/database/repositories.py`. No raw queries in endpoints or orchestrator code.

- **Service isolation** — `bridge_manager` has its own `database/` package (models + repositories). The Synapse stack services live in `services/`. Keep them separate.

- **Request logging** — every request to the appservice is logged immediately via `RequestTracker` before any auth or routing. `response_source` distinguishes appservice-generated errors (`"appservice"`) from upstream responses (`"upstream"`). See `bridge_manager/logger.py`.

- **Token swap pattern** — the appservice never passes tokens through unchanged:
  - HS→bridge: `hs_token` in → `bridge.as_token` out
  - bridge→HS: `bridge.as_token` in → `BRIDGE_MANAGER_CONFIG.AS_TOKEN` out

- **Run from `homeserver/` directory** — the project adds its own directory to `sys.path`. Always `cd homeserver` from the repo root before running anything.

- **Self-contained** — do not import from the parent `augment_chat/` project. This project must be independently deployable.

---

## Database Schema

Managed by SQLAlchemy. Schema is created automatically on first run of `run_bridge_manager.py` via `create_schema_and_tables()`. All tables live in the `bridge_manager` schema.

Key tables:
- `bridge_manager.bridges` — one row per provisioned bridge container
- `bridge_manager.homeservers` — the single registered homeserver for this instance
- `bridge_manager.request_logs` — every request proxied through the appservice
- `bridge_manager.room_bridge_mappings` — which rooms belong to which bridge
- `bridge_manager.transaction_mappings` — cached transaction→bridge routing

---

## Adding a New Bridge Type

1. Create `bridge_manager/orchestrator/bridges/{type}_bridge.py` — dataclass with `SERVICE`, `initialize()`, token/ID generation, volume name
2. Add a `{Type}BridgeConfig` dataclass to `config.py` with Docker image, template, health endpoints — attach to `BridgeManagerConfig`
3. Add a Jinja2 config template to `bridge_manager/orchestrator/config_templates/` (use `[[ ]]` delimiters)
4. Add the new `BridgeType` enum value to `bridge_manager/database/models.py`
5. Wire into `BridgeOrchestrator.create_bridge()` in `orchestrator.py`

---

## Dev Workflows

```bash
# First-time setup
cd homeserver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values

# Deploy Synapse stack
python3 deploy.py

# Start bridge manager appservice
python3 run_bridge_manager.py

# Scale workers
python3 helpers/worker_manager.py hs-001 --scale 3

# Check bridge manager health
curl http://localhost:5001/health

# Debug recent requests (connect to the bridge manager DB)
# SELECT timestamp, source, method, path, status_code, response_source, error
# FROM bridge_manager.request_logs ORDER BY timestamp DESC LIMIT 20;
```

---

## Gotchas

- `BRIDGE_MANAGER_CONFIG.WHATSAPP.docker_image` is the authoritative image — `WhatsAppBridge` class no longer has `DOCKER_IMAGE` on it.
- The bridge manager supports only **one homeserver per instance**. Running with multiple homeservers registered will raise an error at startup.
- When scaling workers, Synapse needs a restart so the `instance_map` is picked up — this is a known limitation.
- The `request_logs.response_source` column distinguishes who generated a response. Always set it when calling `tracker.log_response()`.
- `RequestTracker` is created at the very top of each endpoint handler — before any auth. This ensures every request is logged even if it fails immediately.

---

## Keep This File Updated

Update this file when:
- A new service, module, or bridge type is added
- The directory structure changes meaningfully
- A key architectural decision is made (new pattern, new abstraction)
- The relationship between `matrix_manager` and `homeserver` evolves
