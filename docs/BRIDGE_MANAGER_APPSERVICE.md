# Bridge Manager Appservice — Design & Operation

## Overview

The Bridge Manager appservice sits between Matrix homeservers and external bridge processes (e.g. mautrix-whatsapp). It proxies, rewrites, and logs requests to:

- Allow multiple bridge instances to share a single homeserver by encoding bridge-specific usernames.
- Rewrite usernames and request paths when traffic flows between homeserver and bridges.
- Persist requests and responses for troubleshooting and analytics.

## Key components

### FastAPI app
Location: `bridge_manager.appservice.appservice`

- Two catchall endpoints:
  - `POST/GET/… /homeserver/{path:path}` — receives requests from the homeserver and forwards/rewrites them to the appropriate bridge(s).
  - `POST/GET/… /bridge/{path:path}` — receives requests from external bridge processes and forwards/rewrites to the homeserver.
- Each incoming request is converted into a `RequestContext` before handler logic runs. The `RequestContext` is also stored on `request.state.request_context` for backward compatibility.

### RequestContext
Location: `bridge_manager.appservice.models.RequestContext`

A centralized request representation and helper. Main points:

- Creation: `RequestContext.create(request, bridge_manager_config, source, request_logger)`
  - Reads the ASGI request body exactly once.
  - Parses JSON when possible and extracts headers and query params.
  - Creates an initial request row via the `RequestLogger` (if provided).
- Key attributes exposed to handlers:
  - `request` (FastAPI `Request`) — original request
  - `source` (enum `RequestSource`) — `HOMESERVER` or `BRIDGE`
  - `body_bytes`, `body_json`, `headers` (dict), `query_params` (dict)
  - `transaction_id`, `request_id`, `trace_id`
  - `bridge_instance`, `bridge_type`, `bridge_id`, `bridge_username` (when resolvable)
- Convenience methods:
  - `mark_forwarded(...)`, `attach_response(...)`, `mark_handled(...)`, `mark_unhandled()`
  - `rewrite_bridge_username_in_path(target_username)`
  - `rewrite_usernames_in_body(direction)`

### RequestSource (enum)
Defined in `models.py` — values:
- `RequestSource.HOMESERVER` = "homeserver"
- `RequestSource.BRIDGE` = "bridge"

`RequestContext` enforces/coerces this enum for safety.

### Services

- `HomeserverService` (`bridge_manager.appservice.homeserver_service`)
  - Accepts `RequestContext` and handles endpoints such as `ping`, `users`, and `transactions`.
  - Uses `RequestContext` to avoid re-reading the body and to rewrite usernames in transaction payloads.

- `BridgeService` and implementations (e.g. `WhatsappBridgeService` in `bridge_manager.appservice.bridge_service`)
  - Accepts `RequestContext` and handles bridge-specific endpoints.
  - Forwards requests to the homeserver, sets appropriate auth headers, and logs responses.

### BridgeRegistry
Resolves bridge instances by `bridge_id` or `as_token` and returns objects with bridge metadata (url, tokens) used for forwarding.

### RequestLogger + Repositories
Synchronous SQLAlchemy repositories persist `Requests`, `Responses`, and `UnhandledEndpoints`. The `RequestContext` factory writes the initial request row; responses and unhandled endpoints are attached/updated by helper methods.

## Typical flow

1. Request arrives at a catchall (`/homeserver/...` or `/bridge/...`).
2. The catchall builds a `RequestContext` via `RequestContext.create(...)` with `source` set to either `"homeserver"` or `"bridge"`.
3. Factory reads the body once and creates a request log row (if `RequestLogger` provided).
4. The service handler (`homeserver_service.handle_request` or `bridge_service.handle_request`) receives the `RequestContext` and operates on it.
5. Services perform path/body rewrites as needed and forward requests using `send_request`, which includes the original request id so responses get attached to the log entry.

## Username encoding & rewrites

Format used by the appservice for encoded usernames:

- Encoded form: `@{NAMESPACE}{bridge_type}_{bridge_id}__{bridge_username}:{homeserver}`
- Example: `@_bridge_manager__whatsapp_1__alice:matrix.localhost.me`

Rewrites:
- When sending to homeserver: convert encoded form -> plain `@alice:matrix.localhost.me`.
- When sending to bridge: convert plain form -> encoded form for that bridge instance (requires bridge metadata).

## Important implementation notes

- Single-body-read: `RequestContext.create` reads the ASGI body once. Handlers must use `request_ctx.body_bytes` / `request_ctx.body_json` instead of `await request.body()`.
- Backward compatibility: Catchalls store `request_ctx` on `request.state.request_context` so legacy code can access it.
- Enum typing: `RequestContext.source` is an enum; invalid values raise errors during creation.
- Transaction routing: an in-memory map `TRANSACTION_ID_TO_BRIDGE_MAPPER` maps transaction IDs to bridge AS tokens for ping/transaction flows — this should be persisted to DB in production.

## How to run & smoke test

1. Create and activate a Python virtualenv and install requirements:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Start the appservice (from repo root):

   ```bash
   python -m bridge_manager.appservice.appservice
   ```

3. Example curl calls (replace host/port/tokens as needed):

- Homeserver ping (example):

   ```bash
   curl -X POST \
     http://localhost:8000/homeserver/_matrix/app/v1/ping \
     -H 'Content-Type: application/json' \
     -d '{"transaction_id":"123"}'
   ```

- Bridge ping (example, replace `<AS_TOKEN>`):

   ```bash
   curl -X POST \
     http://localhost:8000/bridge/_matrix/client/v1/appservice/whatsapp/ping \
     -H 'Authorization: Bearer <AS_TOKEN>' \
     -H 'Content-Type: application/json' \
     -d '{"transaction_id":"123"}'
   ```

## Code locations to inspect

- `bridge_manager/appservice/models.py` — `RequestContext`, `RequestSource`
- `bridge_manager/appservice/appservice.py` — catchall wiring
- `bridge_manager/appservice/homeserver_service.py`
- `bridge_manager/appservice/bridge_service.py`
- `bridge_manager/request_logger.py` and `bridge_manager/database/repositories.py`

## Remaining loose ends & recommendations

- Run repository-wide lints and tests to ensure there are no leftover places that call `await request.body()` after the `RequestContext` is created.
- Persist `TRANSACTION_ID_TO_BRIDGE_MAPPER` into the database to survive restarts.
- Add unit tests for `RequestContext.create`, forwarding, and rewrite helpers.
- Harden auth in the bridge catchall: explicitly reject unknown AS tokens and log details for security/forensics.
- Consider accepting `RequestSource` enum values directly in callers (instead of strings) for stronger typing.

---

If you want, I can now:

- Run a repo-wide linter/tests.
- Convert the in-memory transaction map to a DB-backed table and repository.
- Add unit tests for `RequestContext` and the forwarding logic.

Tell me which next step to take.

