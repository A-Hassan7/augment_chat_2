# Bridge Manager Requests UI

A tiny, plain-JS dashboard to explore `bridge_manager.requests`.

## Setup

Ensure the project root `.env` contains database settings used by `bridge_manager`:

- `DRIVERNAME=postgresql`
- `HOST=...`
- `PORT=...`
- `USERNAME=...`
- `PASSWORD=...`
- `DATABASE=...`

## Run

```zsh
# install dependencies
npm install --prefix bridge_manager/ui

# start server
npm run start --prefix bridge_manager/ui
```

Open `http://localhost:3050`.

Use filters to narrow by `source`, `method`, `homeserver_id`, `bridge_id`, or time. Click a row to view full `inbound_request`, `outbound_request`, and `response` payloads.

## Notes

- The server queries Postgres directly using the same `.env` as `bridge_manager`.
- No FastAPI endpoints are added; this is a minimal Node server serving a single page and two data routes.
- Change port via `BRIDGE_REQUESTS_UI_PORT` env var if needed.
