- keep it very simple to start
- similarity search returns relevent message transcripts
  - select * from message_transcript_chunk_vectorstore where  'Where does Dean live?' <> embeddings
- convert parsed messages into transcripts
- chunk transcripts
- create embeddings



## Enrichment

The vectorstore may sometimes require enriching messages with other information from the matrix server. For instance we might need to replace the matrix user id with the profile name from the bridge.

### Profiles
I need profiles from the matrix server to replace the matrix usernames with profiles names from the bridge. Transcripts currently contain matrix user ids which aren't very useful 