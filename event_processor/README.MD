# Event Processor

This module reacts to new events (messages or other room events) in the matrix server and processes these events. The events may be audio messages or images or plain text messages that require specific handling. These will be parsed for further processing.

## Responsibilities include:
1. Listen to inserts on the event_json table in the matrix server
  a. setup replication (between synapse and augment chat)
  b. create postgreSQL notifications on event_json table inserts


### Listening to matrix server events

The current process relies on PostgerSQL logical replication to replicate the matrix synapse event_json table in the augment chat database. Inserts to the replicated event_json table in the augment chat database create notifications that the event processors listen to. I'm using PostgreSQL notify/listen approach.

**a. Setup replication:**

1. Ensure both databases have their `wal_level` set to `logical`. Change using the postgresql.conf file or through the query below. Restart server.
```sql
alter system set wal_level = 'logical'
```

2. Create publisher on the synapse database
```sql
CREATE PUBLICATION event_json_pub
    FOR TABLE public.event_json (event_id, room_id, internal_metadata, json, format_version)
    WITH (publish = 'insert, update, delete, truncate', publish_via_partition_root = false);
```

3. Create subscription
```sql
CREATE SUBSCRIPTION event_json_sub
    CONNECTION 'host=host.docker.internal port=5432 user=synapse dbname=synapse'
    PUBLICATION event_json_pub
    WITH (connect = true, enabled = true, create_slot = false, slot_name = test, synchronous_commit = 'off', binary = false, streaming = 'False', two_phase = false, disable_on_error = false, run_as_owner = false, password_required = true, origin = 'any');
```

4. Replication requires both databases to have the same fully qualified table names. Therefore I need to create the exact same schema and table in the augment chat database as in the synapse database.
```sql
CREATE TABLE IF NOT EXISTS public.event_json
(
    event_id text COLLATE pg_catalog."default" NOT NULL,
    room_id text COLLATE pg_catalog."default" NOT NULL,
    internal_metadata text COLLATE pg_catalog."default" NOT NULL,
    json text COLLATE pg_catalog."default" NOT NULL,
    format_version integer,
    CONSTRAINT event_json_event_id_key UNIQUE (event_id)
)
```

The `event_json` table should now be replicated in the augment chat database.



**b. Create notifications on event_json insert**

I need to be notified of every insert on the `event_json` table in order to process the event.

1. create the function that will be triggered on every insert
```sql
CREATE OR REPLACE FUNCTION matrix_event_json_notify() 
RETURNS trigger AS $$
DECLARE payload json;
BEGIN
    -- create a json payload with the event_id and the 
	payload := json_build_object(
		'event_id', NEW.event_id,
		'event_json', NEW.json::jsonb
	);
    PERFORM pg_notify('matrix_event_json', payload::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
```

2. create the trigger on the events_json table on insert
```sql
-- Create a trigger that calls the function after insert
CREATE TRIGGER matrix_event_json_trigger
AFTER INSERT ON public.event_json
FOR EACH ROW EXECUTE FUNCTION matrix_event_json_notify();
```

3. by default postgreSQL doesn't create triggers on logical replication tables. I will need to manually enable triggers to be created on the `event_json` table.
```sql
ALTER TABLE public.event_json
ENABLE ALWAYS TRIGGER matrix_event_json_trigger;
```


After the above, every insert in the `event_json` table should create a notification in the `matrix_event_json` notification channel. Listening to this channel will return a payload object with the event_id and the json from each event_json entry.

We can listen to the `metrix_event_json` notification channel using the event_listener.py