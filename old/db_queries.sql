-- Create a function that will be triggered on insert
CREATE OR REPLACE FUNCTION matrix_event_json_notify() RETURNS trigger AS 
$$
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
$$
LANGUAGE plpgsql;

-- Create a trigger that calls the function after insert
CREATE TRIGGER matrix_event_json_trigger
AFTER INSERT ON public.event_json
FOR EACH ROW EXECUTE FUNCTION matrix_event_json_notify();



ALTER TABLE public.event_json
ENABLE ALWAYS TRIGGER matrix_event_json_trigger;
 


select pg_notify('matrix_event_json', 'blah')


select event_id, json::jsonb->'origin_server_ts', json::jsonb, json::jsonb->'content'
from public.event_json
order by json::jsonb->'origin_server_ts' desc


select * from event_processor.processed_events;
select * from event_processor.parsed_messages order by message_timestamp desc;

select * from event_processor.parsed_messages where event_id = '$fS_tQAdyNtIHCzsBjFfx-WeLp9avz1WEGu0DNjz4RCc'

select json::jsonb from public.event_json where event_id = '$fS_tQAdyNtIHCzsBjFfx-WeLp9avz1WEGu0DNjz4RCc'

select *
from public.event_json


select * 
from event_processor.parsed_messages
where event_id = '$Fv0Mu08BswY1iavff7ujJA3y4B7ZIo2uLAXMVNCmX5U'


select events.event_id, events.json
from public.event_json events
left join event_processor.processed_events processed
	on events.event_id = processed.event_id
where processed.event_id is null


select * from event_processor.parsed_messages
drop table event_processor.parsed_messages
drop table event_processor.processed_events


select *
from event_processor.parsed_messages
where room_id = '!XmrPIdtctqAqNrJWUy:matrix.localhost.me'
order by message_timestamp



select * from vector_store.transcripts;



select *
from vector_store.transcripts
order by created_at desc



select id, room_id, max_message_depth, num_transcripts, document, embedding
from vector_store.transcript_chunks
-- where room_id = '!UjrtheOflpFTQlqPsB:matrix.localhost.me'

select event_id, room_id, transcript
from vector_store.transcripts
order by created_at desc



drop table vector_store.transcript_chunks;
drop table vector_store.transcripts;

 
select max(max_message_depth)
from vector_store.transcript_chunks
group by room_id



-- gets new messages after the max depth of the newest chunk
-- this includes the overlap
(
	-- get transcripts after the last chunked message
	select *
	from vector_store.transcripts
	where 
		depth > 63
		and room_id = '!UjrtheOflpFTQlqPsB:matrix.localhost.me'
)
union 
(
	-- get the overlapping transcripts if a new chunk were to be created
	select *
	from vector_store.transcripts
	where 
		depth <= 63
		and room_id = '!UjrtheOflpFTQlqPsB:matrix.localhost.me'
	order by depth desc
	limit 10
)
order by message_timestamp asc



   
select * from vector_store.transcript_chunks where room_id = '!UjrtheOflpFTQlqPsB:matrix.localhost.me'

select * from vector_store.transcripts
select count(*) from event_processor.parsed_messages


select * from event_processor.parsed_messages where event_id = 'test'
select * from event_processor.processed_events where event_id = 'test'
