# Bridge Manager Appservice

A pure proxy layer that sits between the Matrix homeserver and bridge instances, handling authentication, routing, and logging for all traffic flowing in both directions.

```
                              ┌───────────────────────────┐
                              │                           │
  ┌────────────┐   events     │   BRIDGE MANAGER          │   events    ┌─────────────────┐
  │            │ ◄─────────►  │      APPSERVICE           │ ◄─────────► │  WhatsApp Bridge│
  │ Homeserver │              │                           │             ├─────────────────┤
  │            │ ◄──────────  │      :5001                │ ◄────────── │  Telegram Bridge│
  └────────────┘   responses  │                           │   responses ├─────────────────┤
                              │  • Auth & token swap      │             │  Signal Bridge  │
                              │  • Bridge routing         │             ├─────────────────┤
                              │  • Request logging        │             │  ...            │
                              │                           │             └─────────────────┘
                              └───────────────────────────┘
```

---

## Architecture Diagram

```
                        BRIDGE MANAGER APPSERVICE
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │   POST /homeserver/_matrix/app/v1/{path}                           │
  │                        │                                            │
  │              ┌─────────▼──────────┐                                │
  │              │  1. Authenticate   │  validate hs_token              │
  │              │  2. Route request  │  BridgeRouter → identify bridge │
  │              │  3. Swap token     │  hs_token → bridge's as_token   │
  │              │  4. Transform      │  HomeserverRequestHandler       │
  │              │  5. Forward        │  → http://{bridge.ip}:{bridge.port}│
  │              └─────────┬──────────┘                                │
  │                        │                                            │
  │   GET /bridge/{id}/_matrix/{path}                                  │
  │                        │                                            │
  │              ┌─────────▼──────────┐                                │
  │              │  1. Authenticate   │  validate bridge's as_token    │
  │              │  2. Lookup bridge  │  BridgeRegistry → by URL param │
  │              │  3. Swap token     │  as_token → bridge manager's   │
  │              │  4. Transform      │  BridgeRequestHandler          │
  │              │  5. Forward        │  → homeserver URL              │
  │              └─────────┬──────────┘                                │
  │                        │                                            │
  │              ┌─────────▼──────────┐                                │
  │              │   RequestTracker   │  logs to request_logs table    │
  │              └────────────────────┘                                │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘

  Homeserver ──► Appservice ──► Bridge
  Bridge     ──► Appservice ──► Homeserver
```

### Token Flow

```
  Homeserver → Bridge
  ─────────────────────────────────────────────────────────────────
  Homeserver sends:   Authorization: Bearer <hs_token>
  Appservice checks:  incoming token == bridge.hs_token ✓
  Appservice sends:   Authorization: Bearer <bridge.as_token>
  Bridge receives:    its own expected AS token

  Bridge → Homeserver
  ─────────────────────────────────────────────────────────────────
  Bridge sends:       Authorization: Bearer <bridge.as_token>
  Appservice checks:  incoming token == bridge.as_token ✓
  Appservice sends:   Authorization: Bearer <BRIDGE_MANAGER.AS_TOKEN>
  Homeserver receives: bridge manager's registered AS token
```

---

## Routes

| Route | Direction | Description |
|---|---|---|
| `* /homeserver/_matrix/app/v1/{path}` | Homeserver → Bridge | Receives Matrix appservice events from the homeserver and proxies to the correct bridge |
| `* /bridge/{bridge_id}/_matrix/{path}` | Bridge → Homeserver | Receives requests from a bridge (e.g. user registration, room creation) and proxies to the homeserver |
| `GET /health` | — | Health check |

---

## Files

| File | Responsibility |
|---|---|
| `appservice.py` | FastAPI app, the two proxy endpoints, request/response flow |
| `router.py` | `BridgeRouter` — identifies which bridge a homeserver request belongs to using 8 strategies |
| `registry.py` | `BridgeRegistry` — bridge lookup and caching (used for bridge → homeserver direction) |
| `token_manager.py` | `TokenManager` — validates tokens and handles the token swap logic |
| `models.py` | Enums: `RequestSource`, `BridgeDiscoveryMethod` |
| `handlers/` | Path-specific request transformation pipeline (see below) |

### `handlers/` — Request transformation pipeline

After authentication, bridge/homeserver lookup, and token swap the appservice wraps the request data in a `ProxyContext` and passes it through a handler selected by bridge type.  The handler may return a modified copy of the context; the appservice then uses the final context to perform the HTTP forward.

```
handlers/
├── __init__.py
├── base.py                  — ProxyContext dataclass, PathRouter, RequestHandlerBase
├── bridge_handler.py        — BridgeRequestHandler      (Bridge → HS, generic)
├── homeserver_handler.py    — HomeserverRequestHandler  (HS → Bridge, generic)
├── bridge_types/
│   ├── __init__.py          — BridgeHandlerRegistry
│   └── whatsapp.py          — WhatsAppBridgeRequestHandler
└── homeserver_types/
    └── __init__.py          — HomeserverHandlerRegistry
```

#### `ProxyContext`

Immutable-friendly dataclass (use `dataclasses.replace()` to produce modified copies):

| Field | Description |
|---|---|
| `method` | HTTP method |
| `path` | Request path |
| `headers` | Request headers (already token-swapped) |
| `query_params` | Query string parameters |
| `body` | Raw request body bytes |
| `target_url` | Full URL the request will be forwarded to |

#### `PathRouter`

Maps compiled regex patterns to handler callables.  Patterns are checked in registration order; the first match wins.

```python
router = PathRouter()
router.register(r"client/versions$", handler_fn)
```

#### `BridgeHandlerRegistry` / `HomeserverHandlerRegistry`

Each registry maps a `bridge_type` string to a handler class and caches one instance per type.  The appservice calls the registry with `bridge.bridge_type` so the correct handler is selected automatically.

```python
# Bridge → Homeserver
handler = BridgeHandlerRegistry.get_handler(bridge.bridge_type)

# Homeserver → Bridge
handler = HomeserverHandlerRegistry.get_handler(bridge.bridge_type)
```

If a bridge type has no registered handler, the registry falls back to the generic `BridgeRequestHandler` / `HomeserverRequestHandler`, preserving existing pass-through behaviour.

#### Route priority — generic vs type-specific

Both handler base classes use a two-level registration pattern:

```
_register_routes()
  ├── _register_type_specific_routes()   ← runs first (bridge-type subclass overrides)
  └── _register_generic_routes()         ← runs second (base class, fallback)
```

`PathRouter` uses first-match-wins, so type-specific routes registered first take priority.  Paths not claimed by the type-specific handler fall through to the generic routes.

#### Adding a bridge-type-specific transform

1. Create `handlers/bridge_types/<type>.py` with a subclass of `BridgeRequestHandler`.
2. Override `_register_type_specific_routes()` and register any path handlers.
3. Add the class to `BridgeHandlerRegistry._registry` in `bridge_types/__init__.py`.

```python
# handlers/bridge_types/discord.py
from dataclasses import replace
from ..bridge_handler import BridgeRequestHandler
from ..base import ProxyContext

class DiscordBridgeRequestHandler(BridgeRequestHandler):
    def _register_type_specific_routes(self) -> None:
        self.router.register(r"client/v3/account/whoami$", self._handle_whoami)

    async def _handle_whoami(self, context: ProxyContext) -> ProxyContext:
        # Discord-specific whoami transform
        return replace(context, ...)
```

```python
# handlers/bridge_types/__init__.py  — add one line
_registry = {
    "whatsapp": WhatsAppBridgeRequestHandler,
    "discord":  DiscordBridgeRequestHandler,   # ← new
}
```

#### Adding a generic transform (applies to all bridges)

Add a handler method to `BridgeRequestHandler._register_generic_routes()` or `HomeserverRequestHandler._register_generic_routes()`.

---

## Request Flow: Homeserver → Bridge

The homeserver sends Matrix appservice events to the bridge manager instead of directly to each bridge. The appservice:

1. **Authenticates** — checks `Authorization: Bearer <token>` is present.
2. **Routes** — `BridgeRouter.identify_bridge()` tries up to 8 strategies in order to figure out which bridge owns this request:
   - Auth token match
   - `user_id` query param
   - Username in path
   - Cached transaction ID
   - Events in transaction body
   - Room ID lookup
   - Username in body
   - Owner username fallback
3. **Validates token** — confirms the token matches the identified bridge's `hs_token`.
4. **Swaps token** — replaces `hs_token` with the bridge's `as_token` so the bridge accepts the request.
5. **Transforms** — `HomeserverHandlerRegistry.get_handler(bridge.bridge_type)` returns the handler for this bridge type (e.g. `HomeserverRequestHandler` for all types currently).  Any registered path handler may modify the method, headers, query params, body, or target URL.
6. **Forwards** — sends the modified request to `http://localhost:{bridge.port}/_matrix/app/v1/{path}`.
7. **Logs** — records the raw incoming and outgoing requests plus the response in `request_logs`.

## Request Flow: Bridge → Homeserver

Bridges are configured to send their outbound Matrix API calls to the bridge manager instead of directly to the homeserver. The URL format is `http://bridge-manager:5001/bridge/{bridge_id}/_matrix/{path}`. The appservice:

1. **Authenticates** — checks `Authorization: Bearer <token>` is present.
2. **Looks up bridge** — finds the bridge by `bridge_id` in the URL via `BridgeRegistry`. Falls back to token-based lookup if the ID isn't found.
3. **Validates token** — confirms the token matches the bridge's registered `as_token`.
4. **Swaps token** — replaces the bridge's `as_token` with the bridge manager's own `AS_TOKEN` so the homeserver recognises it as a legitimate registered appservice.
5. **Transforms** — `BridgeHandlerRegistry.get_handler(bridge.bridge_type)` returns the handler for this bridge type (e.g. `WhatsAppBridgeRequestHandler` for `"whatsapp"`).  Any registered path handler may modify the method, headers, query params, body, or target URL (e.g. stripping `user_id` from `/_matrix/client/versions`).
6. **Forwards** — sends the modified request to `{homeserver.url}/_matrix/{path}`.
7. **Logs** — records the raw incoming and outgoing requests plus the response in `request_logs`.

---

## Logging

Every request is logged to the `bridge_manager.request_logs` database table via `RequestTracker` **immediately on arrival**, before any auth or routing takes place. This means every request is recorded regardless of whether it succeeds or fails.

Each row captures:

- `raw_incoming_request` — the request exactly as it arrived (method, path, headers, body)
- `raw_outgoing_request` — the request as it was forwarded after token replacement (null if the request was rejected before forwarding)
- `status_code`, `response_body`, `duration_ms` — filled in once a response is produced
- `error` — set if the downstream target was unreachable, timed out, or auth/routing failed
- `response_source` — who produced the response:
  - `"upstream"` — status code and body came from the bridge or homeserver
  - `"appservice"` — response was generated internally (e.g. auth failure, bridge not found, connection error)
  - `null` — request is still in-flight

Useful debug query:
```sql
SELECT
    timestamp,
    source,
    method,
    path,
    status_code,
    response_source,
    duration_ms,
    error,
    raw_incoming_request,
    raw_outgoing_request
FROM bridge_manager.request_logs
ORDER BY timestamp DESC
LIMIT 20;
```

### Request Logger UI

A browser-based inspector for the `request_logs` table. Run it with:

```bash
python3 -m bridge_manager.request_logger_ui
```

Features:
- Table view of all logged requests with filtering and column toggle
- Click any row to open a **detail pullover** showing the raw incoming request, raw outgoing request, and response body side-by-side
- JSON syntax highlighting in all three panes
- Drag the top edge of the pullover to resize its height
- Drag the dividers between the three panes to resize them horizontally
- Dark/light theme toggle
