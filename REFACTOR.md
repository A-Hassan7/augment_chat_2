# Project Refactor Plan

## Goal
Separate the Matrix infrastructure management from the Augment Chat application logic, creating two independent systems that communicate via well-defined APIs.

---

## Architecture Components

### 1. Augment Chat Application (This repository, refactored)
**Responsibilities:**
- User registration and authentication
- Event processing pipeline (event_processor, vector_store, llm_service, suggestions_service)
- Business logic: transcripts, embeddings, joke suggestions
- Consumes events from Kafka stream
- Provides user-facing API

**Key Change:** No longer manages Matrix infrastructure directly. All Matrix operations go through Matrix Manager API.

**Data Sources:**
- Kafka event stream (from all homeservers via Debezium CDC)
- Own PostgreSQL database for processed data

---

### 2. Matrix Manager (New separate project)
**Responsibilities:**
- Homeserver orchestration and lifecycle management
- User-to-homeserver assignment and registry
- Homeserver selection (primitive initially, load-based later)
- Abstract Matrix complexity for Augment Chat
- Track homeserver capacity and health

**API Endpoints:**
- Register user → assigns homeserver, creates Matrix account
- Create bridge for user → routes to correct homeserver
- Query user's homeserver/bridges
- Health checks and capacity metrics

**Data Model:**
```sql
user_homeserver_registry:
  - user_id → homeserver_id mapping
  - matrix_user_id (@user:domain)
  
homeservers:
  - homeserver_id, base_url
  - capacity, status, metrics
```

---

### 3. Homeserver Deployment (One per instance, e.g., HS-001, HS-002)
Each homeserver is a self-contained unit with:

**Components:**
- **Synapse** (Matrix homeserver)
- **PostgreSQL** (dedicated DB per homeserver)
- **Bridge Manager** (application service registered with Synapse)
  - Scales horizontally behind load balancer
  - Has own database for user→bridge mappings
  - Manages bridge lifecycle
  - Proxies bridge events to Synapse
- **Bridges** (WhatsApp, Telegram, Signal, etc.)
  - One bridge instance per user per platform
  - Not shared between users
  - Managed by Bridge Manager

**Management API:**
- Create user account
- Create/delete/status bridges for users
- Capacity metrics
- Bridge status queries (via bridge bot)

**Event Flow:**
```
Bridge → Bridge Manager → Synapse → Postgres → Debezium → Kafka
```

---

## User Journey Flow

### 1. User Registration
```
User → Augment Chat API → Matrix Manager API → 
Homeserver Manager (selects HS) → Homeserver creates Matrix user →
Return credentials to Augment Chat
```

### 2. Bridge Creation
```
User requests WhatsApp bridge → Augment Chat API → 
Matrix Manager API → Homeserver Manager (lookup user's HS) → 
Homeserver Management API → Bridge Manager spawns bridge container →
Bridge provides login QR/link → User completes auth
```

### 3. Message Flow
```
WhatsApp → Bridge → Bridge Manager → Synapse → 
Postgres → Debezium → Kafka → Augment Chat Event Consumer → 
Processing Pipeline → Suggestions
```

---

## Key Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Homeserver Sharing** | Multiple users per homeserver | Cost efficiency, horizontal scaling when capacity reached |
| **Bridge Isolation** | Dedicated bridge per user | Security, session isolation |
| **User Binding** | Permanent homeserver assignment | Simplicity, no migration complexity |
| **Event Ingestion** | Kafka/Debezium CDC | Clean separation, homeserver-agnostic, scalable |
| **Federation** | Not required | Simplified architecture |
| **Bridge Manager Scaling** | Horizontal behind LB | Handle increased load per homeserver |
| **Deployment** | Containerized, distributed | Flexibility, not tied to single host |

---

## Component Ownership

```
Matrix Manager owns:
  - Homeserver registry
  - User→Homeserver mappings
  - Homeserver orchestration

Homeserver owns:
  - Bridge Manager
  - Bridges for its users
  - User→Bridge mappings
  - Synapse instance
  - PostgreSQL instance

Augment Chat owns:
  - Event processing
  - Business logic
  - Suggestions pipeline
  - User-facing features
```

---

## Implementation Roadmap

### New Components to Build:
1. **Matrix Manager** (new project)
   - API server
   - Homeserver orchestration service
   - User registry database

2. **Homeserver Management API** (per homeserver deployment)
   - User creation endpoints
   - Bridge management endpoints
   - Capacity/health metrics

3. **Event Streaming Infrastructure**
   - Debezium connectors for each homeserver Postgres
   - Kafka cluster
   - Event consumer in Augment Chat

### Components to Refactor:
1. **Augment Chat API**
   - Remove direct Matrix/bridge management
   - Add Matrix Manager client
   - Update user registration flow

2. **Bridge Manager**
   - Adapt to work within homeserver deployment
   - Add database for user→bridge mappings
   - Implement management API

3. **Event Processor**
   - Consume from Kafka instead of direct DB replication
   - Handle events from multiple homeservers

### Components to Preserve:
1. Vector store, LLM service, suggestions pipeline (minimal changes)
2. Bridge Manager appservice logic (moved to homeserver context)
3. Core event processing patterns

---

## Open Questions for Implementation

1. **Homeserver selection algorithm** - What metrics define "capacity"?
2. **Debezium configuration** - Which Postgres tables to stream from Synapse?
3. **Bridge Manager deployment** - Docker Compose template per homeserver?
4. **API authentication** - How does Augment Chat auth with Matrix Manager?
5. **Homeserver provisioning** - Manual or automated spin-up?

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│          Augment Chat Application                       │
│  (event processing, vectors, LLM, suggestions)          │
└────────────────────┬────────────────────────────────────┘
                     │ ALL Matrix operations
                     ↓
┌─────────────────────────────────────────────────────────┐
│          Matrix Manager API                              │
│  - User→Homeserver registry                             │
│  - Homeserver orchestration                             │
│  - Routes requests to correct homeserver                │
└─────┬───────────────┬───────────────┬───────────────────┘
      │               │               │
      ↓               ↓               ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Homeserver 1│ │ Homeserver 2│ │ Homeserver N│
│ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │
│ │ Synapse │ │ │ │ Synapse │ │ │ │ Synapse │ │
│ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │
│ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │
│ │Postgres │ │ │ │Postgres │ │ │ │Postgres │ │
│ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │
│ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │
│ │ Bridge  │ │ │ │ Bridge  │ │ │ │ Bridge  │ │
│ │ Manager │ │ │ │ Manager │ │ │ │ Manager │ │
│ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │
│   Bridges:  │ │   Bridges:  │ │             │
│   • WA(U1)  │ │   • WA(U5)  │ │             │
│   • TG(U2)  │ │   • SIG(U6) │ │             │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┴───────────────┘
                       ↓
              Debezium CDC → Kafka
                       ↓
              Augment Chat Event Consumer
```


