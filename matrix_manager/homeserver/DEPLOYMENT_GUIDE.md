# Matrix Homeserver Deployment Guide

## Architecture Overview

The deployment system uses a **service-based architecture** where each component (PostgreSQL, Redis, Synapse, Workers, Nginx, Prometheus, Grafana) is managed as an independent service with:

- **Pre-flight validation** - Verify configs before deploying anything
- **Health checking** - Wait for services to be ready before proceeding
- **Automatic rollback** - Clean up on failure
- **Dynamic scaling** - Add/remove workers without redeployment

### Service Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Network                          │
│                                                               │
│  ┌──────────┐  ┌───────┐  ┌─────────┐  ┌─────────────────┐ │
│  │PostgreSQL│  │ Redis │  │ Synapse │  │ Workers (0-50)  │ │
│  │   :5432  │  │ :6379 │  │  :8008  │  │ :8100+          │ │
│  └──────────┘  └───────┘  └─────────┘  └─────────────────┘ │
│       │            │           │               │             │
│       └────────────┴───────────┴───────────────┘             │
│                          │                                    │
│                    ┌─────▼─────┐                             │
│                    │   Nginx   │ :80 (API), :8080 (metrics) │
│                    └───────────┘                             │
│                                                               │
│  ┌────────────┐   ┌─────────┐                               │
│  │ Prometheus │   │ Grafana │                               │
│  │   :9090    │◄──│  :3000  │                               │
│  └────────────┘   └─────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Deploy a Homeserver

**Monolith Mode (No Workers):**
```bash
python3 deploy_v2.py my-homeserver --workers 0
```

**Distributed Mode (With Workers):**
```bash
python3 deploy_v2.py my-homeserver --workers 3
```

**Validate Before Deploying:**
```bash
python3 deploy_v2.py my-homeserver --workers 3 --validate-only
```

### 2. Check Status

```bash
python3 deploy_v2.py my-homeserver --status
```

Or check containers directly:
```bash
docker ps --filter "name=my-homeserver"
```

### 3. Scale Workers

**Scale Up:**
```bash
python3 helpers/worker_manager.py my-homeserver --scale 5
```

**Scale Down:**
```bash
python3 helpers/worker_manager.py my-homeserver --scale 2
```

**Remove All Workers (Monolith Mode):**
```bash
python3 helpers/worker_manager.py my-homeserver --scale 0
```

**Check Worker Status:**
```bash
python3 helpers/worker_manager.py my-homeserver --status
```

## Service Endpoints

After deployment, access services at:

| Service        | Endpoint                      | Purpose                      |
|----------------|-------------------------------|------------------------------|
| Matrix API     | http://localhost:80           | Client/Federation API        |
| Synapse Direct | http://localhost:8008         | Direct Synapse access        |
| Prometheus     | http://localhost:9090         | Metrics collection           |
| Grafana        | http://localhost:3000         | Visualization dashboard      |
| Nginx Metrics  | http://localhost:8080/metrics | Nginx Prometheus metrics     |
| Workers        | http://localhost:8100+        | Individual worker ports      |

**Default Grafana credentials:** `admin` / `admin` (change on first login)

## File Structure

```
homeserver/
├── deploy_v2.py              # Main deployment orchestrator
├── config.py                 # Global configuration
├── deployments/              # Per-homeserver data
│   └── <homeserver-id>/
│       ├── data/            # Synapse data & configs
│       ├── postgres_data/   # PostgreSQL data
│       ├── nginx/           # Nginx configs
│       ├── prometheus/      # Prometheus configs
│       └── grafana/         # Grafana configs & dashboards
└── helpers/
    ├── worker_manager.py     # Worker scaling tool
    └── services/            # Service implementations
        ├── base.py          # Abstract base service
        ├── postgres.py      # PostgreSQL service
        ├── redis.py         # Redis service
        ├── synapse.py       # Synapse homeserver
        ├── worker.py        # Worker containers
        ├── nginx.py         # Load balancer
        ├── prometheus.py    # Metrics collection
        └── grafana.py       # Visualization
```

## Common Operations

### Test Matrix API
```bash
curl http://localhost/_matrix/client/versions
```

### View Synapse Logs
```bash
docker logs my-homeserver_synapse -f
```

### View Worker Logs
```bash
docker logs my-homeserver_worker1 -f
```

### Access Prometheus Metrics
```bash
curl http://localhost:9090/api/v1/targets
```

### Restart a Service
```bash
docker restart my-homeserver_synapse
```

### Clean Up Deployment
```bash
docker ps --filter "name=my-homeserver" -q | xargs docker stop
docker ps -a --filter "name=my-homeserver" -q | xargs docker rm
docker network rm my-homeserver_network
rm -rf deployments/my-homeserver
```

## Scaling Behavior

When you scale workers, the system automatically:

1. **Deploys/removes worker containers** as needed
2. **Updates Synapse's `instance_map`** configuration
3. **Regenerates Nginx upstream** configuration and reloads
4. **Regenerates Prometheus scrape targets** and reloads

**Note:** Currently requires a Synapse restart when scaling due to `instance_map` updates. Workers must be registered in the main Synapse config for internal replication communication.

## Troubleshooting

### Workers Not Starting
- Check if Synapse is healthy: `docker logs my-homeserver_synapse`
- Verify Redis is running: `docker ps --filter "name=redis"`
- Check worker logs: `docker logs my-homeserver_worker1`

### Port Conflicts
- Workers auto-select available ports starting from 8100
- If conflicts occur, stop conflicting containers
- Check port usage: `lsof -i :8100`

### Health Check Failures
- Services have 60-second health check timeout
- Check container logs for startup errors
- Verify network connectivity between containers

### Database Connection Issues
- Ensure PostgreSQL is healthy before Synapse starts
- Check database name matches (underscores, not hyphens)
- Verify network: `docker network inspect my-homeserver_network`

## Development

To add a new service:

1. Create service class in `helpers/services/` inheriting from `BaseService`
2. Implement required methods: `validate_config()`, `generate_config()`, `deploy()`, `is_healthy()`
3. Add service to `DeploymentPlan._build_service_list()` in `deploy_v2.py`
4. Service will automatically participate in validation, deployment, and rollback

See existing services for implementation patterns.
