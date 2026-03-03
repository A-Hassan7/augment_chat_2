# Copilot Instructions — Matrix Manager

## What Is This Project?

The **matrix_manager** is the orchestration layer of the Augment Chat monorepo. It sits between the `augment_chat` AI pipeline and the individual `homeserver` deployments, managing a fleet of homeservers and routing users and operations to the right one.

> **Status:** Early development. The architecture and API contracts are designed (see `README.md`). Implementation is in progress — `manager/api/routes/` is the primary build area.

### Where This Fits

```
augment_chat/            ← monorepo root
├── augment_chat/        ← AI pipeline — consumes Matrix events, generates suggestions
├── matrix_manager/      ← THIS PROJECT — orchestrates homeserver fleet
└── homeserver/          ← single homeserver deployment unit (Synapse + bridge manager)
```

`matrix_manager` calls out to multiple `homeserver` instances via their management APIs. `augment_chat` calls `matrix_manager` for all Matrix operations (user registration, bridge creation, etc.) rather than talking to homeservers directly.

---

## What This Project Does

```
augment_chat
    └── POST /users/register, /users/{id}/bridges, etc.
            └── matrix_manager
                    ├── selects optimal homeserver (capacity, health)
                    ├── registers user on chosen homeserver
                    ├── routes operations to correct homeserver
                    └── tracks capacity + health across fleet
                            └── homeserver-001 API
                            └── homeserver-002 API
                            └── homeserver-N   API
```

**Core responsibilities:**
- User registration: assign each new user to a homeserver based on capacity
- User registry: store and look up which homeserver a user lives on
- Request routing: proxy Matrix operations to the correct homeserver
- Fleet health: periodic health checks, capacity metric collection
- Homeserver lifecycle: register/deregister homeservers in the fleet

---

## Planned Architecture

These are the components being built (see `README.md` for full design):

| Component | Path | Responsibility |
|---|---|---|
| API | `manager/api/` | FastAPI app — entry point for all external calls |
| Core Manager | `manager/core/` | Homeserver selection, routing, capacity logic |
| User Registry | `manager/user_registry/` | User → homeserver mapping, Matrix user ID storage |
| Homeserver Controller | `manager/homeserver_controller/` | Per-homeserver operations (rooms, bridges, messages) |
| Homeserver Client | `manager/homeserver_client/` | Low-level HTTP client for homeserver management APIs |
| Database | `manager/database/` | SQLAlchemy models + repositories (`homeservers`, `user_homeserver_registry`, `capacity_metrics`) |

### Planned API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/users/register` | Register user, assign homeserver |
| `GET` | `/users/{user_id}/homeserver` | Get user's assigned homeserver |
| `POST` | `/users/{user_id}/bridges` | Create a bridge for a user |
| `GET` | `/users/{user_id}/bridges` | List user's bridges |
| `DELETE` | `/users/{user_id}/bridges/{bridge_id}` | Delete a bridge |
| `GET` | `/homeservers` | List all homeservers with status |
| `GET` | `/health` | Health check |

---

## Conventions to Follow When Building

- **Repository pattern** — all DB access via `*Repository` classes in `manager/database/repositories.py`. No raw queries in business logic.
- **Per-service isolation** — each logical component (`user_registry/`, `core/`, etc.) gets its own folder with an `interface.py` as its public surface.
- **Config centralised** — all config goes in `config.py` via a `MatrixManagerConfig` dataclass loaded from `.env`. Never hardcode URLs, ports, or credentials.
- **Homeserver selection is pluggable** — Phase 1 is round-robin; Phase 2 is load-based. The selection algorithm should be swappable without changing the API layer.
- **`homeserver_client/` is the only layer that talks to homeservers** — no other component should make direct HTTP calls to homeserver instances.

---

## Implementation Phases

The README defines 5 phases. Current focus is **Phase 1**:

1. **Phase 1 (current):** Database models, basic API scaffold, homeserver registration, round-robin selection, homeserver client
2. **Phase 2:** User registration flow, homeserver assignment, user registry lookup
3. **Phase 3:** Bridge operations (create, delete, status), room operations
4. **Phase 4:** Capacity tracking, health monitoring, metric collection
5. **Phase 5:** Load-based selection, admin interface, user migration tools

---

## Dev Workflows

```bash
# First-time setup
cd matrix_manager
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values

# Run API server (once implemented)
python run_matrix_manager.py   # FastAPI on :8001
```

---

## Relationship with `homeserver/`

`matrix_manager` does **not** import from `homeserver/` directly — they communicate over HTTP. The `homeserver` management API (run via `homeserver/run_bridge_manager.py`) exposes endpoints that `HomeserverClient` in this project calls. Keep the boundary clean.

---

## Gotchas

- `manager/api/routes/` is currently empty — this is where implementation starts.
- There is no `config.py` yet — create it following the `MatrixManagerConfig` design in `README.md`.
- Do not confuse the `bridge_manager` inside `homeserver/` (per-homeserver bridge proxy) with this project's bridge management endpoints (fleet-level bridge assignment).

---

## Keep This File Updated

Update this file when:
- A new component or module is scaffolded
- A phase is completed and the next begins
- The API contract changes
- Key architectural decisions are made
