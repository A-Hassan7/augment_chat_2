# Bridge Orchestrator

Manages the full lifecycle of bridge containers — creation, configuration, health monitoring, and deletion.

```
  create_bridge()          ┌─────────────────────────┐        ┌──────────────┐
  stop_bridge()    ──────► │   BridgeOrchestrator    │──────► │    Docker    │
  start_bridge()           │                         │        │  (containers │
  delete_bridge()          │  1. Render config        │        │  + volumes)  │
  check_status()           │     from template        │        └──────────────┘
                           │  2. Provision container  │
                           │  3. Start & health check │        ┌──────────────┐
                           │  4. Update DB record     │──────► │  PostgreSQL  │
                           │                         │        │  (bridge     │
                           └─────────────────────────┘        │   records)   │
                                       │                       └──────────────┘
                                       ▼
                           ┌─────────────────────────┐
                           │   DockerClientManager    │
                           │  local or remote hosts   │
                           └─────────────────────────┘
```

---

## Overview

The orchestrator handles:
- **Bridge Creation**: Creates Docker containers with custom configurations
- **Configuration Management**: Generates bridge configs from Jinja2 templates
- **Health Monitoring**: Monitors bridge health via HTTP endpoints
- **Multi-host Support**: Can deploy bridges across multiple Docker hosts
- **Volume Management**: Manages persistent storage for bridge data

## Components

### BridgeOrchestrator

Main class that orchestrates bridge lifecycle:

- `create_bridge()` - Complete bridge creation workflow
- `start_bridge()` - Start a stopped bridge
- `stop_bridge()` - Stop a running bridge  
- `delete_bridge()` - Remove bridge and optionally its data
- `check_bridge_status()` - Check bridge health

### WhatsAppBridge

Bridge-specific configuration class for WhatsApp bridges:

- Static configuration (Docker image, template name, health endpoints)
- Instance-specific fields (IDs, tokens, ports, parameters)
- `initialize()` method to generate tokens and config parameters

### DockerClientManager

Manages Docker client connections with caching and multi-host support:

- `get_client(host)` - Get or create Docker client for a host
- `close_all()` - Close all open Docker connections
- Connection pooling and caching

## Configuration

Configuration lives in `homeserver/config.py`, split across two classes:

### `BridgeManagerConfig` (orchestrator-relevant fields)

| Field | Description | Default |
|---|---|---|
| `RESTART_POLICY` | Docker restart policy | `{"Name": "unless-stopped"}` |
| `NETWORK_MODE` | Docker network mode | `None` (Docker default) |
| `TEMPLATES_DIR` | Jinja2 template directory | `bridge_manager/orchestrator/config_templates/` |
| `CONFIGS_DIR` | Generated config output directory | `bridge_manager/orchestrator/configs/` |
| `BRIDGE_MANAGER_HOSTNAME` | Hostname containers use to reach the bridge manager | `host.docker.internal` |
| `DOCKER_NETWORK` | Docker network to attach containers to | env: `BRIDGE_MANAGER_DOCKER_NETWORK` |

### `WhatsAppBridgeConfig`

| Field | Description | Default |
|---|---|---|
| `docker_image` | Docker image | `dock.mau.dev/mautrix/whatsapp:latest` |
| `config_template` | Template filename | `whatsapp.yaml` |
| `config_path_in_container` | Where config is placed inside the container | `/data/config.yaml` |
| `health_live_endpoint` | Liveness check path | `_matrix/mau/live` |
| `health_ready_endpoint` | Readiness check path | `_matrix/mau/ready` |

Accessed via `BRIDGE_MANAGER_CONFIG.WHATSAPP` (e.g. `BRIDGE_MANAGER_CONFIG.WHATSAPP.docker_image`).

## Bridge Creation Workflow

When creating a bridge, the orchestrator follows this workflow:

1. **Initialize Configuration**
   - Generate unique IDs (appservice_id, bot_username)
   - Generate authentication tokens (as_token, hs_token)
   - Create volume name for persistent storage

2. **Allocate Resources**
   - Find available port for appservice
   - Build appservice address that homeserver can reach

3. **Create Container**
   - Pull Docker image if needed
   - Create Docker volume for persistent data
   - Create container with proper configuration

4. **Generate Configuration**
   - Render Jinja2 template with bridge parameters
   - Use `[[ ]]` delimiters to avoid conflicts with bridge's `{{ }}`

5. **Copy Configuration**
   - Create tar archive with config file
   - Copy into container at specified path

6. **Start Bridge**
   - Start the Docker container
   - Update status to STARTING

7. **Health Checks**
   - Poll liveness endpoint (`/_matrix/mau/live`)
   - Poll readiness endpoint (`/_matrix/mau/ready`)
   - Wait up to 60 seconds for healthy status
   - Update status to RUNNING when healthy

## Config Templates

Bridge configuration templates are Jinja2 templates stored in `orchestrator/config_templates/`.

### Template Variables

Templates use `[[ variable ]]` syntax (to avoid conflicts with bridge's `{{ }}`):

**Required variables:**
- `homeserver_name` - Domain of homeserver (e.g., matrix.example.com)
- `homeserver_address` - HTTP address (e.g., http://synapse:8008)
- `appservice_address` - Where homeserver can reach this bridge
- `appservice_hostname` - Hostname to bind (0.0.0.0 for all interfaces)
- `appservice_port` - Port to listen on
- `appservice_id` - Unique appservice ID
- `bot_username` - Bot username for this bridge
- `appservice_as_token` - Application service token
- `appservice_hs_token` - Homeserver token

### Example Template Usage

```yaml
homeserver:
    address: [[ homeserver_address ]]
    domain: [[ homeserver_name ]]

appservice:
    address: [[ appservice_address ]]
    hostname: [[ appservice_hostname ]]
    port: [[ appservice_port ]]
    id: [[ appservice_id ]]
    
    bot:
        username: [[ bot_username ]]
    
    as_token: [[ appservice_as_token ]]
    hs_token: [[ appservice_hs_token ]]
```

## Docker Host Support

The orchestrator supports deploying bridges to different Docker hosts:

```python
# Deploy to local Docker
bridge = orchestrator.create_bridge(
    bridge_type=BridgeType.WHATSAPP,
    homeserver_id="homeserver-123",
    docker_host=None,  # Uses default local Docker
)

# Deploy to remote Docker host
bridge = orchestrator.create_bridge(
    bridge_type=BridgeType.WHATSAPP,
    homeserver_id="homeserver-123",
    docker_host="tcp://192.168.1.100:2375",
)

# Deploy over SSH
bridge = orchestrator.create_bridge(
    bridge_type=BridgeType.WHATSAPP,
    homeserver_id="homeserver-123",
    docker_host="ssh://user@192.168.1.100",
)
```

Docker client connections are cached per host for efficiency.

## Health Monitoring

Bridges expose health endpoints that the orchestrator polls:

- **Liveness** (`/_matrix/mau/live`): Is the bridge process running?
- **Readiness** (`/_matrix/mau/ready`): Is the bridge ready to handle requests?

Health checks are performed:
- During bridge creation (wait for ready)
- When explicitly checking status
- Can be used for monitoring/alerting

## Error Handling

The orchestrator defines specific exceptions for different failure modes:

- `BridgeCreationError` - Failed to create bridge
- `BridgeStartError` - Failed to start bridge  
- `BridgeStopError` - Failed to stop bridge
- `BridgeDeletionError` - Failed to delete bridge
- `ConfigurationError` - Config generation/template error
- `DockerConnectionError` - Can't connect to Docker host
- `HealthCheckError` - Bridge failed health checks

All exceptions inherit from `OrchestratorError`.

## Usage Examples

### Create a WhatsApp Bridge

```python
from bridge_manager.orchestrator.orchestrator import BridgeOrchestrator
from bridge_manager.database.models import BridgeType

with BridgeOrchestrator() as orchestrator:
    bridge = orchestrator.create_bridge(
        bridge_type=BridgeType.WHATSAPP,
        homeserver_id="hs-abc123",
        owner_matrix_username="@user:example.com",
    )
    print(f"Created bridge {bridge.orchestrator_id}")
    print(f"Container: {bridge.container_name}")
    print(f"Port: {bridge.port}")
```

### Check, Stop, Start, Delete

```python
from bridge_manager.orchestrator.orchestrator import BridgeOrchestrator

with BridgeOrchestrator() as orchestrator:
    status = orchestrator.check_bridge_status("bridge-123")

    orchestrator.stop_bridge("bridge-123")
    orchestrator.start_bridge("bridge-123")

    orchestrator.delete_bridge("bridge-123", remove_volume=True)

# Docker connections are automatically closed when exiting context
```

## Adding New Bridge Types

To add support for a new bridge type:

1. **Create Bridge Class** (like `WhatsAppBridge`):
   ```python
   @dataclass
   class TelegramBridge:
       SERVICE = "telegram"
       DOCKER_IMAGE = "dock.mau.dev/mautrix/telegram:latest"
       CONFIG_TEMPLATE_FILENAME = "telegram.yaml"
       
       def initialize(self, bridge_id, homeserver_id, ...):
           # Generate IDs, tokens, config params
           pass
   ```

2. **Create Config Template**:
   - Add `telegram.yaml` to `orchestrator/config_templates/`
   - Use `[[ variable ]]` syntax for template variables

3. **Update Config** (`homeserver/config.py`):
   ```python
   @dataclass
   class TelegramBridgeConfig:
       docker_image: str = "dock.mau.dev/mautrix/telegram:latest"
       config_template: str = "telegram.yaml"
       # ...
   ```

4. **Update Orchestrator** (`orchestrator/orchestrator.py`):
   ```python
   def create_bridge(self, bridge_type, ...):
       if bridge_type == BridgeType.TELEGRAM:
           bridge = TelegramBridge()
       # ...
   ```

5. **Add to Database Models** (`bridge_manager/database/models.py`):
   ```python
   class BridgeType(str, Enum):
       WHATSAPP = "whatsapp"
       TELEGRAM = "telegram"  # Add here
   ```

## Dependencies

- `docker` - Docker SDK for Python
- `jinja2` - Template engine for config generation
- `requests` - HTTP client for health checks
- `sqlalchemy` - Database ORM

## Notes

- Containers are created with `restart_policy: unless-stopped` by default
- Volumes are used for persistent bridge data
- Ports are dynamically allocated using socket binding
- Health checks timeout after 60 seconds by default
- Docker connections are cached and reused per host
- Config templates use `[[ ]]` delimiters to avoid conflicts
