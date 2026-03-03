# Homeserver

Automated deployment and management of a Matrix Synapse homeserver with optional worker scaling, bridge management, load balancing, and monitoring.

```
  Clients
     │
     ▼
  ┌──────┐       ┌─────────────────────────────────────────────────────┐
  │Nginx │       │  SYNAPSE HOMESERVER STACK (Docker)                  │
  │ :80  │──────►│                                                     │
  └──────┘       │   ┌─────────────┐   ┌───────────────────────────┐  │
                 │   │  Synapse    │   │  Workers (optional)       │  │
                 │   │  Main :8008 │   │  :8100, :8101, ...        │  │
                 │   └──────┬──────┘   └──────────┬────────────────┘  │
                 │          │  Redis (worker replication)              │
                 │          └─────────────┬────────────────────────┘  │
                 │                        │                            │
                 │                 ┌──────▼──────┐                    │
                 │                 │ PostgreSQL  │                    │
                 │                 │   :5432     │                    │
                 │                 └─────────────┘                    │
                 │                                                     │
                 │   ┌────────────────┐   ┌─────────┐                │
                 │   │  Prometheus    │──►│ Grafana │                │
                 │   │   :9090        │   │  :3000  │                │
                 │   └────────────────┘   └─────────┘                │
                 └─────────────────────────────────────────────────────┘
                                         │
                             ┌───────────▼───────────┐
                             │   Bridge Manager      │
                             │   Appservice :5001    │
                             │   (proxy layer)       │
                             └──────────┬────────────┘
                                        │
                         ┌──────────────┼──────────────┐
                         ▼              ▼              ▼
                   ┌──────────┐  ┌──────────┐  ┌──────────┐
                   │ WhatsApp │  │ Telegram │  │  Signal  │
                   │  Bridge  │  │  Bridge  │  │  Bridge  │
                   └──────────┘  └──────────┘  └──────────┘
```

> This project is **self-contained** — it has its own virtualenv, dependencies, database schema, and config. Do not import from the parent `augment_chat/` project.

---

## Two Separate Processes

There are two things that run here independently:

| Process | Script | Purpose |
|---|---|---|
| Synapse stack | `deploy.py` | Deploys all Docker containers (Synapse, Postgres, Nginx, etc.) |
| Bridge Manager | `run_bridge_manager.py` | Starts the FastAPI appservice proxy for bridges |

---

## Setup

```bash
cd matrix_manager/homeserver
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
```

---

## Deploying the Homeserver Stack

```bash
# Monolith (no workers)
python3 deploy.py

# Or deploy with workers programmatically
from deploy import DeploymentPlan
plan = DeploymentPlan(homeserver_id="hs-001", domain="localhost", num_workers=3)
plan.execute()
```

This deploys the following Docker containers onto an isolated network:

| Container | Port | Purpose |
|---|---|---|
| `{id}_postgres` | 5432 | Database |
| `{id}_redis` | 6379 | Worker replication (workers mode only) |
| `{id}_synapse` | 8008 | Synapse main process |
| `{id}_worker_N` | 8100+ | Generic workers (optional) |
| `{id}_nginx` | 80 / 8080 | Load balancer / metrics |
| `{id}_prometheus` | 9090 | Metrics collection |
| `{id}_grafana` | 3000 | Monitoring dashboards |

All persistent data is written to `deployments/{homeserver-id}/`.

### Scaling Workers

```bash
python3 helpers/worker_manager.py hs-001 --scale 5   # scale up
python3 helpers/worker_manager.py hs-001 --scale 0   # back to monolith
python3 helpers/worker_manager.py hs-001 --status     # check status
```

When scaling, the system automatically updates the Synapse `instance_map`, regenerates the Nginx upstream config, and reloads both services.

Workers use **consistent IP hashing** in Nginx for session affinity.

---

## Running the Bridge Manager

```bash
cd matrix_manager/homeserver
source .venv/bin/activate
python3 run_bridge_manager.py
```

On first run this will:
1. Create the `bridge_manager` database schema
2. Register the homeserver from `.env` values
3. Start the FastAPI appservice on `HOST:PORT` (default `:5001`)

**Required `.env` values before first run:**
- `HOMESERVER_ID`, `HOMESERVER_NAME`, `HOMESERVER_URL`, `HOMESERVER_HS_TOKEN`
- `BRIDGE_MANAGER_INSTANCE_ID`, `BRIDGE_MANAGER_AS_TOKEN`
- `BRIDGE_MANAGER_DATABASE_URL`

See the [bridge_manager/appservice README](bridge_manager/appservice/README.md) and [orchestrator README](bridge_manager/orchestrator/README.md) for details on how bridges work.

---

## Configuration

All config lives in `config.py`, driven by environment variables in `.env`. Key sections:

- **`BridgeManagerConfig`** — appservice host/port, tokens, Docker settings, bridge config
- **`WhatsAppBridgeConfig`** — Docker image, template, health endpoints for WhatsApp bridges
- Synapse/Postgres/Nginx ports and image tags are also defined here

---

## Directory Structure

```
homeserver/
├── deploy.py                  # Deploys the Synapse stack
├── run_bridge_manager.py      # Starts the bridge manager appservice
├── config.py                  # All configuration
├── requirements.txt
├── .env / .env.example
├── bridge_manager/            # Appservice proxy + orchestrator
│   ├── appservice/            # FastAPI proxy (auth, routing, logging)
│   ├── orchestrator/          # Bridge container lifecycle manager
│   └── database/              # SQLAlchemy models + repositories
├── helpers/
│   ├── worker_manager.py      # Worker scaling tool
│   └── nginx_manager.py       # Nginx config management
├── services/                  # One class per Docker service
│   ├── postgres.py
│   ├── redis.py
│   ├── synapse.py
│   ├── worker.py
│   ├── nginx.py
│   ├── prometheus.py
│   └── grafana.py
├── templates/                 # Docker/Nginx/Synapse config templates
└── deployments/               # Per-homeserver runtime data
    └── {homeserver-id}/
        ├── data/              # Synapse data + homeserver.yaml
        ├── postgres_data/
        ├── nginx/
        ├── prometheus/
        └── grafana/
```

---

## Common Operations

```bash
# Check container status
docker ps --filter "name=hs-001"

# View Synapse logs
docker logs hs-001_synapse -f

# Restart Synapse
docker restart hs-001_synapse

# Test Matrix API
curl http://localhost/_matrix/client/versions

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Clean up a deployment entirely
docker ps -a --filter "name=hs-001" -q | xargs docker rm -f
docker network rm hs-001_network
rm -rf deployments/hs-001
```

---

## Troubleshooting

| Problem | Check |
|---|---|
| Workers not starting | `docker logs hs-001_worker1` — usually Redis unreachable or bad config |
| Nginx 502 errors | `curl http://localhost:80/health` — verify worker containers are running |
| Database connection errors | `docker exec hs-001_postgres psql -U synapse -c "SELECT count(*) FROM pg_stat_activity;"` |
| Bridge manager `ModuleNotFoundError` | Ensure you're running from the `homeserver/` directory |
| Port conflicts | Workers auto-select ports from 8100; check with `lsof -i :8100` |
| Docker connection issues | Ensure Docker is running: `docker ps` |

