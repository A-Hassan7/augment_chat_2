# Augment Chat Documentation

## Overview

**Augment Chat** is a backend system designed to enhance personal conversations on platforms like WhatsApp, Instagram, and Messenger by providing real-time, context-aware joke suggestions using a language model. The system syncs messages from these platforms (via Matrix bridges), processes them, and injects witty, relevant suggestions into ongoing chats.

---

## Architecture

### High-Level Flow

1. **Message Sync**: Messages from external platforms are synced to a Matrix Synapse server using bridges (e.g., WhatsApp bridge).
2. **Event Replication**: The `event_json` table from Synapse is replicated into the Augment Chat database using PostgreSQL logical replication.
3. **Event Processing**: Inserts on the replicated table trigger notifications, which are picked up by the event processor.
4. **Message Parsing & Storage**: Events are parsed and stored as structured messages.
5. **Vector Store**: Messages are chunked, embedded, and stored for similarity search.
6. **Suggestion Generation**: The system uses the LLM to generate joke suggestions based on chat context.
7. **API**: Exposes endpoints for retrieving transcripts and suggestions.

---

## Core Components

### 1. Matrix Synapse
- Acts as the central message hub.
- All messages from external platforms are bridged here.

### 2. Bridges (e.g., WhatsApp Bridge)
- Connects user accounts from external platforms to Matrix.
- Managed by the `bridge_manager` module.

### 3. Event Processor
- Listens for new events in the replicated `event_json` table.
- Uses PostgreSQL triggers and notifications to react to new messages.
- Parses events and stores them in `parsed_messages` and `processed_events` tables.
- See: `event_processor/README.MD` for replication and trigger setup.

### 4. Queue Controller
- Manages distributed processing using Redis and Python RQ.
- Each service (event processor, vector store, LLM, etc.) has its own worker and queue for scalability.

### 5. Vector Store
- Converts parsed messages into transcripts.
- Chunks transcripts and creates embeddings for similarity search.
- Supports enrichment (e.g., replacing Matrix user IDs with profile names).
- See: `vector_store/README.md`.

### 6. LLM Service
- Handles requests to the language model for embeddings and completions.
- Processes requests asynchronously via the queue.
- See: `llm_service/README.md`.

### 7. Suggestions Service
- Reads messages and generates joke suggestions using prompts.
- Integrates with the LLM service for context-aware responses.

### 8. Summarizers
- (Optional) Creates summaries of large chats to fit within LLM context windows.
- Can generate general or user-specific summaries (quirks, inside jokes, etc.).
- See: `summarizers/README.md`.

### 9. Users Service
- Manages user registration and authentication.
- Creates Matrix accounts and bridges for users.
- See: `users_service/README.md`.

---

## API

- Exposes endpoints for:
  - Retrieving chat transcripts (`/transcripts`)
  - Backfilling transcripts (`/backfill_transcripts`)
  - Generating suggestions (`/generate_suggestion`)
- See: `api/main.py`

---

## Development Notes

- All processing is event-driven and distributed via Redis queues.
- Logical replication and triggers are used for real-time event processing.
- Embeddings and similarity search are central to context injection for the LLM.
- User and bridge management is modular for easy extension to new platforms.

---

## Extending & Customizing

- Add new bridges by extending the `bridge_manager`.
- Swap or extend LLM providers in `llm_service`.
- Customize prompts and suggestion logic in `suggestions_service`.
- Enrich transcripts and user profiles in `vector_store`.
