# Matrix Manager

The Matrix Manager orchestrates Matrix homeserver infrastructure and provides an abstraction layer between the Augment Chat application and the underlying Matrix ecosystem.

## Purpose

The Matrix Manager is responsible for:
- Managing multiple Matrix homeserver deployments
- Assigning users to homeservers based on capacity
- Routing Matrix operations to the correct homeserver
- Tracking homeserver health and capacity metrics
- Providing a unified API for all Matrix operations

## Architecture

```
┌─────────────────────────────────────────┐
│        Matrix Manager                    │
│  (Orchestration Layer)                   │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  User Registry Service             │ │
│  │  - User → Homeserver mappings      │ │
│  │  - Matrix user ID tracking         │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Core Manager Logic                │ │
│  │  - Homeserver selection            │ │
│  │  - Capacity tracking               │ │
│  │  - Health monitoring               │ │
│  │  - Request routing                 │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Homeserver Controller             │ │
│  │  - Individual homeserver ops       │ │
│  │  - Room operations                 │ │
│  │  - Message sending                 │ │
│  │  - Bridge management               │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  Database                           │ │
│  │  - user_homeserver_registry        │ │
│  │  - homeservers                      │ │
│  │  - capacity_metrics                 │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
           │         │         │
           ↓         ↓         ↓
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │HS-001 API│ │HS-002 API│ │HS-N   API│
    └──────────┘ └──────────┘ └──────────┘
```

## Components

### 1. API Layer (`api/`)
FastAPI application exposing Matrix operations to Augment Chat.

**Endpoints:**
- `POST /users/register` - Register user and assign homeserver
- `POST /users/{user_id}/bridges` - Create bridge for user
- `GET /users/{user_id}/bridges` - List user's bridges
- `GET /users/{user_id}/homeserver` - Get user's homeserver info
- `DELETE /users/{user_id}/bridges/{bridge_id}` - Delete bridge
- `GET /homeservers` - List all homeservers with status
- `GET /health` - Health check

### 2. User Registry Service (`user_registry/`)
Manages user-to-homeserver assignments.

**Responsibilities:**
- Track which homeserver each user is registered on
- Store Matrix user IDs and credentials
- Provide lookup functionality for routing

**Database Schema:**
```sql
CREATE Matrix Manager Core (`manager/`)
Core orchestration logic for homeserver fleet management.

**Responsibilities:**
- Select optimal homeserver for new users
- Track homeserver capacity metrics
- Monitor homeserver health
- Route requests to appropriate homeserver
- Handle homeserver registration and lifecycle

**Homeserver Selection Logic:**
- Phase 1: Round-robin or simple capacity check
- Phase 2: Load-based (active users, event throughput)

### 4. Homeserver Controller (`homeserver_controller/`)
Handles operations for individual homeservers.

**Responsibilities:**
- Execute operations on specific homeserver
- Create/manage Matrix rooms
- Send messages to rooms
- Create/delete/query bridges for users
- User account operations
- Proxy Matrix client API calls

**Interface:**
```python
class HomeserverController:
    def create_room(self, homeserver_id: str, user_id: str, room_config: dict) -> dict
    def send_message(self, homeserver_id: str, room_id: str, message: str) -> dict
    def invite_user(self, homeserver_id: str, room_id: str, user_id: str) -> bool
    def create_bridge(self, homeserver_id: str, user_id: str, bridge_type: str) -> dict
    def delete_bridge(self, homeserver_id: str, user_id: str, bridge_id: str) -> bool
    def get_bridge_status(self, homeserver_id: str, bridge_id: str) -> dict
    def get_user_bridges(self, homeserver_id: str, user_id: str) -> list
```
- Select optimal homeserver for new users
- Track homeserver capacity metrics
- Monitor homeserver health
- Route API requests to appropriate homeserver
- Handle homeserver registration and lifecycle

**Homeserver Selection Logic:**
- Phase 1: Round-robin or simple capacity check
- Phase 2: Load-based (active users, event throughput)

**Database Schema:**
```sql
CREATE TABLE homeservers (
    5. Homeserver Client (`homeserver_client/`)
Low-level HTTP client for communicating with individual homeserver management APIs.

**Interface:**
```python
class HomeserverClient:
    def create_user(self, homeserver_url: str, username: str, password: str) -> dict
    def create_room(self, homeserver_url: str, user_id: str, room_config: dict) -> dict
    def send_message(self, homeserver_url: str, room_id: str, message: str) -> dict
    def create_bridge(self, homeserver_url: str, user_id: str, bridge_type: str) -> dict
    def get_bridge_status(self, homeserver_url: str, bridge_id: str) -> dict
    def delete_bridge(self, homeserver_url: str, bridge_id: str) -> bool
    def get_user_bridges(self, homeserver_url: str, user_id: str) -> list
    def get_capacity_metrics(self, homeserver_url: str) -> dict
```

### 6ctive_users INT,
    event_rate FLOAT,              -- events per minute
    cpu_usage FLOAT,
    memory_usage FLOAT,
    timestamp TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (homeserver_id) REFERENCES homeservers(homeserver_id)
);
```

### 4. Homeserver Client (`homeserver_client/`)
HTTP client for communicating with individual homeserver management APIs.

**Interface:**
```python
class HomeserverClient:
    def create_user(self, homeserver_url: str, username: str, password: str) -> dict
    def create_bridge(self, homeserver_url: str, user_id: str, bridge_type: str) -> dict
    def get_bridge_status(self, homeserver_url: str, bridge_id: str) -> dict
    def delete_bridge(self, homeserver_url: str, bridge_id: str) -> bool
    def get_user_bridges(self, homeserver_url: str, user_id: str) -> list
    def get_capacity_metrics(self, homeserver_url: str) -> dict
```

### 5. Database Layer (`database/`)
SQLAlchemy models, engine, and repositories.

```
database/
├── engine.py           # Database connection
├── models.py           # SQLAlchemy models
└── repositories.py     # Data access layer
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. **Database Setup**
   - Create database models for `homeservers` and `user_homeserver_registry`
   - Set up connection management
   - Create repositories

2. **Basic API**
   - FastAPI app scaffold
   - Health check endpoint
   - Matrix Manager Core**
   - Homeserver registration (manual for now)
   - Simple selection algorithm (round-robin)
   - Request routing logic

4. **Homeserver Client**
   - HTTP client for homeserver API communication
   - Error handling and retries)
   - Simple selection algorithm (round-robin)
   - Homeserver client for API communication

### Phase 2: User Management
1. **User Registry Service**
   - User registration flow
   - Homeserver assignment
   - Lookup functionality
Homeserver Controller**
   - Implement bridge operations (create, delete, query)
   - Room operations (create, invite, send message)
   - Route operations to correct homeserver

2. **API Endpoints**
   - POST /users/{user_id}/bridges (create bridge)
   - GET /users/{user_id}/bridges (list bridges)
   - DELETE /users/{user_id}/bridges/{bridge_id}
   - POST /rooms (create room)
   - POST /rooms/{room_id}/messages (send message)
   - List bridges endpoint
   - Delete bridge endpoint

2. **Bridge Status**
   - Query bridge status through homeserver
   - Handle bridge bot interactions

### Phase 4: Monitoring & Metrics
1. **Capacity Tracking**
   - Collect metrics from homeservers
   - Store in capacity_metrics table
   - Update current_users count

2. **Health Checks**
   - Periodic homeserver health pings
   - Update status in database
   - Alert on failures

### Phase 5: Advanced Features
1. **Smart Selection**
   - Load-based homeserver selection
   - Predictive capacity planning

2. **Admin Interface**
   - Homeserver CRUD operations
   - User migration tools (future)
   - Metrics dashboard

## Configuration

```python
# config.py
class MatrixManagerConfig:
    # Database
    DATABASE_URL: str
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    
    # Homeserver Selection
    SELECTION_ALGORITHM: str = "round-robin"  # or "load-based"
    MAX_USERS_PER_HOMESERVER: int = 1000
    
    # Health Check
    HEALTH_CHECK_INTERVAL: int = 60  # seconds
    
    # Timeouts
    HOMESERVER_REQUEST_TIMEOUT: int = 30
```

## API Request/Response Examples

### Register User
```bash
POST /users/register
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "password": "secure_password"
}

Response:
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "matrix_user_id": "@john_doe:hs001.domain.com",
  "homeserver_id": "HS-001",
  "homeserver_url": "https://hs001.domain.com",
  "access_token": "syt_..."
}
```

### Create Bridge
```bash
POST /users/{user_id}/bridges
{
  "bridge_type": "whatsapp"
}

Response:
{
  "bridge_id": "whatsapp_550e8400",
  "bridge_type": "whatsapp",
  "status": "pending_auth",
  "auth_url": "https://bridge.domain.com/qr/abc123"
}
```

### List User Bridges
```bash
GET /users/{user_id}/bridges

Response:
{
  "bridges": [
    {
      "bridge_id": "whatsapp_550e8400",
      "bridge_type": "whatsapp",
      "status": "connected",
      "created_at": "2026-01-11T10:00:00Z"
    },
    {
      "bridge_id": "telegram_550e8400",
      "bridge_type": "telegram",
      "status": "disconnected",
      "created_at": "2026-01-10T15:30:00Z"
    }
  ]
}
```

## Running the Matrix Manager

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up database
python -m matrix_manager.database.setup

# Run API server
python run_matrix_manager.py
```

### Docker
```bash
docker build -t matrix-manager .
docker run -p 8001:8001 matrix-manager
```

## Integration with Augment Chat

Augment Chat should use the Matrix Manager client to perform all Matrix operations:

```python
from matrix_manager_client import MatrixManagerClient

client = MatrixManagerClient(base_url="http://matrix-manager:8001")

# Register user
response = client.register_user(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    username="john_doe",
    password="secure_password"
)

# Create bridge
bridge = client.create_bridge(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    bridge_type="whatsapp"
)
```

## Dependencies

- FastAPI
- SQLAlchemy
- psycopg2
- httpx (async HTTP client)
- pydantic
- uvicorn

## Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=matrix_manager tests/
```

## Future Enhancements

1. **Auto-scaling**: Automatically provision new homeservers when capacity is reached
2. **User Migration**: Move users between homeservers for load balancing
3. **Multi-region**: Deploy homeservers across geographic regions
4. **Metrics Dashboard**: Web UI for monitoring homeserver health and capacity
5. **Backup/Recovery**: Homeserver backup and disaster recovery procedures
