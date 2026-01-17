# Homeserver Deployment

Automated deployment and management of Synapse homeservers with worker scaling, load balancing, and monitoring.

## Overview

This module provides complete homeserver deployment automation including:
- **PostgreSQL database** with persistent storage
- **Redis** for worker communication
- **Synapse** main process and generic workers
- **Nginx** load balancer with consistent hashing
- **Prometheus** metrics collection
- **Grafana** monitoring dashboards

## Quick Start

### Deploy a New Homeserver

```python
from matrix_manager.homeserver.deploy import deploy

# Deploy with 2 workers
result = deploy(
    homeserver_id="HS-001",
    domain="example.com",
    admin_username="admin",
    admin_password="secure_password",
    num_workers=2
)

print(f"Homeserver URL: {result['homeserver_url']}")
print(f"Admin user: {result['admin_user']}")
```

### Access Services

After deployment:
- **Homeserver**: `http://localhost:8008` (main process)
- **Nginx**: `http://localhost:80` (load balanced)
- **Prometheus**: `http://localhost:9090` (metrics)
- **Grafana**: `http://localhost:3000` (dashboards, admin/admin)

### Scale Workers

```bash
# Scale to 5 workers
python scale_workers.py HS-001 5

# Scale down to monolith (0 workers)
python scale_workers.py HS-001 0

# Check worker status
python scale_workers.py HS-001 status
```

## Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│                    Nginx (80)                    │
│           Load Balancer + Health Checks          │
└───────────────┬─────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
┌───▼────┐             ┌───▼────────┐
│ Main   │             │ Worker 1-N │
│ Process│◄───Redis───►│ (8001-N)   │
│ (8008) │             │            │
└───┬────┘             └────┬───────┘
    │                       │
    └───────┬───────────────┘
            │
    ┌───────▼────────┐
    │   PostgreSQL   │
    │     (5432)     │
    └────────────────┘

Monitoring Stack:
┌────────────────┐      ┌──────────────┐
│  Prometheus    │─────►│   Grafana    │
│    (9090)      │      │    (3000)    │
└────────────────┘      └──────────────┘
```

### Worker Distribution

Workers use **consistent hashing** based on client IP address for:
- Session affinity (sticky sessions)
- Optimal load distribution
- Minimal session disruption on scaling

### Data Flow

1. **Client Request** → Nginx (port 80)
2. **Nginx** → Hashes client IP → Routes to worker
3. **Worker** → Processes request → Queries PostgreSQL
4. **Worker** → Replicates via Redis → Other workers
5. **All processes** → Export metrics → Prometheus
6. **Grafana** → Queries Prometheus → Displays dashboards

## Configuration

### Environment Variables

```bash
# Required for deployment
SYNAPSE_SERVER_NAME=example.com
SYNAPSE_REPORT_STATS=yes
```

### Docker Images

Configurable in `deploy.py`:
- `POSTGRES_IMAGE`: postgres:15-alpine
- `SYNAPSE_IMAGE`: matrixdotorg/synapse:latest
- `REDIS_IMAGE`: redis:7-alpine
- `NGINX_IMAGE`: nginx:alpine
- `PROMETHEUS_IMAGE`: prom/prometheus:latest
- `GRAFANA_IMAGE`: grafana/grafana:latest

### Ports

| Service | Internal | External | Purpose |
|---------|----------|----------|---------|
| Synapse Main | 8008 | 8008 | HTTP API |
| Workers | 8083 | 8001-N | HTTP API |
| Nginx | 80 | 80 | Load balancer |
| Nginx Status | 8080 | 8080 | Metrics |
| PostgreSQL | 5432 | 5432 | Database |
| Redis | 6379 | - | Worker comms |
| Prometheus | 9090 | 9090 | Metrics |
| Grafana | 3000 | 3000 | Dashboards |

## Persistent Storage

All data stored in deployment directory:
```
deployments/
└── HS-001/
    ├── postgres_data/     # PostgreSQL data
    ├── synapse/
    │   └── data/          # Synapse data + configs
    │       ├── homeserver.yaml
    │       ├── media_store/
    │       └── workers/
    │           ├── worker1.yaml
    │           └── worker2.yaml
    ├── nginx/
    │   └── nginx.conf
    ├── prometheus/
    │   ├── prometheus.yml
    │   └── data/          # Metrics storage
    └── grafana/
        └── data/          # Dashboard configs
```

## Monitoring

### Prometheus Metrics

Collected from:
- **Synapse main process** (port 9000)
- **All workers** (port 9000 each)
- **Nginx** (port 8080/nginx_status)

Key metrics:
- `synapse_http_server_requests_received_total` - Request rate
- `synapse_http_server_response_time_seconds` - Response times
- `synapse_storage_connections` - Database connections
- `synapse_storage_events_persisted_events_total` - Event processing
- `process_resident_memory_bytes` - Memory usage

### Grafana Dashboards

Setup dashboards automatically:
```bash
python setup_grafana.py HS-001
```

Access: `http://localhost:3000` (admin/admin)

Dashboard includes:
- Request rate per worker
- Response time percentiles (p95, p99)
- Active connections
- Database pool usage
- Memory consumption
- Event processing rate
- Federation metrics

### Health Checks

Built-in health endpoints:
- Nginx: `http://localhost:80/health`
- Prometheus: `http://localhost:9090/-/healthy`
- Grafana: `http://localhost:3000/api/health`

## Operations

### Scaling

**Scale up:**
```bash
python scale_workers.py HS-001 5
```
- Creates new worker configs
- Deploys worker containers
- Updates instance map
- Regenerates nginx upstream config
- Updates prometheus scrape targets
- Reloads nginx and prometheus

**Scale down:**
```bash
python scale_workers.py HS-001 1
```
- Stops and removes worker containers
- Deletes worker config files
- Updates all configs
- Reloads services

### Maintenance

**Restart a worker:**
```bash
docker restart HS-001_worker2
```

**Restart main process:**
```bash
docker restart HS-001_synapse
```

**View logs:**
```bash
# Main process
docker logs HS-001_synapse

# Specific worker
docker logs HS-001_worker1

# Follow logs
docker logs -f HS-001_worker1
```

**Backup data:**
```bash
# Backup PostgreSQL
docker exec HS-001_postgres pg_dump -U synapse_user synapse > backup.sql

# Backup media store
tar -czf media_backup.tar.gz deployments/HS-001/synapse/data/media_store/
```

**Restore data:**
```bash
# Restore PostgreSQL
docker exec -i HS-001_postgres psql -U synapse_user synapse < backup.sql

# Restore media store
tar -xzf media_backup.tar.gz -C deployments/HS-001/synapse/data/
```

### Debugging

**Check container status:**
```bash
docker ps -a | grep HS-001
```

**Check network connectivity:**
```bash
docker network inspect HS-001_network
```

**Test nginx config:**
```bash
docker exec HS-001_nginx nginx -t
```

**Test prometheus config:**
```bash
docker exec HS-001_prometheus promtool check config /etc/prometheus/prometheus.yml
```

**Verify metrics:**
```bash
# Synapse main metrics
curl http://localhost:9000/metrics

# Worker metrics
curl http://localhost:9001/metrics  # worker1 internal

# Nginx metrics
curl http://localhost:8080/nginx_status

# Prometheus targets
curl http://localhost:9090/api/v1/targets
```

## Performance Tuning

### Worker Count

Recommendations:
- **Light load**: 0-2 workers (monolith sufficient)
- **Medium load**: 2-4 workers
- **Heavy load**: 5-10 workers
- **Very heavy**: 10+ workers with load balancing

Monitor CPU/memory to determine optimal count.

### Database Tuning

PostgreSQL settings in deployment:
```python
# In deploy.py _deploy_postgres()
environment={
    'POSTGRES_MAX_CONNECTIONS': '200',  # Increase for more workers
    'POSTGRES_SHARED_BUFFERS': '256MB',
    'POSTGRES_EFFECTIVE_CACHE_SIZE': '1GB',
}
```

### Nginx Tuning

Worker connections:
```nginx
# In nginx.conf
events {
    worker_connections 2048;  # Increase for high concurrency
}
```

### Synapse Tuning

Edit `homeserver.yaml`:
```yaml
# Database connection pool per process
database:
  args:
    cp_min: 5
    cp_max: 10

# Caching
caches:
  global_factor: 2.0
  per_cache_factors:
    get_users_who_share_room_with_user: 5.0
```

## Troubleshooting

### Workers not starting

Check logs:
```bash
docker logs HS-001_worker1
```

Common issues:
- Redis not accessible (check network)
- Config syntax error (validate yaml)
- Port already in use (check port mapping)

### Nginx 502 errors

Check upstream health:
```bash
docker exec HS-001_nginx cat /etc/nginx/nginx.conf
curl http://localhost:80/health
```

Verify workers running:
```bash
python scale_workers.py HS-001 status
```

### High memory usage

Check process memory:
```bash
docker stats HS-001_synapse HS-001_worker1 HS-001_worker2
```

Solutions:
- Reduce cache sizes in homeserver.yaml
- Scale up workers to distribute load
- Add memory limits to containers

### Database connection errors

Check connections:
```bash
docker exec HS-001_postgres psql -U synapse_user -d synapse -c "SELECT count(*) FROM pg_stat_activity;"
```

Solutions:
- Increase `POSTGRES_MAX_CONNECTIONS`
- Tune `cp_max` in database config
- Check for connection leaks

## Security Considerations

### Production Deployment

**Required changes:**
1. Change default passwords (Grafana admin, PostgreSQL)
2. Use TLS/SSL certificates (Let's Encrypt)
3. Restrict port exposure (only 80/443 public)
4. Enable firewall rules
5. Use secrets management (not env vars)
6. Regular security updates

**Nginx TLS:**
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
}
```

### Network Isolation

Containers on isolated network:
- Internal communication only
- Expose only necessary ports
- Use Docker secrets for credentials

## API Integration

Deploy from Matrix Manager API:

```python
from matrix_manager.homeserver.deploy import deploy

# Called by homeserver_controller
def create_homeserver(user_id: str):
    result = deploy(
        homeserver_id=f"HS-{user_id}",
        domain=f"user{user_id}.matrix.example.com",
        admin_username=f"user{user_id}",
        admin_password=generate_secure_password(),
        num_workers=2
    )
    
    # Store in database
    save_homeserver_record(user_id, result)
    
    return result
```

## Development

### Testing

```bash
# Deploy test homeserver
python -c "from deploy import deploy; deploy('TEST-001', 'test.local', 'admin', 'test', 1)"

# Run health checks
curl http://localhost:80/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health

# Cleanup
docker stop TEST-001_synapse TEST-001_postgres TEST-001_redis TEST-001_nginx
docker rm TEST-001_synapse TEST-001_postgres TEST-001_redis TEST-001_nginx
docker network rm TEST-001_network
rm -rf deployments/TEST-001/
```

### Adding New Components

1. Add Docker image constant
2. Create deployment method
3. Update network configuration
4. Add to monitoring
5. Update documentation

## References

- [Synapse Documentation](https://matrix-org.github.io/synapse/)
- [Synapse Worker Configuration](https://matrix-org.github.io/synapse/latest/workers.html)
- [Prometheus Nginx Exporter](https://github.com/nginxinc/nginx-prometheus-exporter)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)

    a. scalable appservice instance
    b. be able to deploy on remote servers
        a. the docker sdk can connect to remote clients
    

3. Create client to manage homeserver
