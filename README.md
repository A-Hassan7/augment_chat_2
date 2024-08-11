# Augment Chat

Mind dump:
- Register a user
- Create a user account on the matrix homeserver
- Log the user into a bridge (just whatsapp at the moment)
- Parse raw events into messages (raw events received from PostgreSQL logical replication with the matrix database)
- Create embeddings
- Search embeddings to create summaries
- Use summaries to generate suggestions

TODO:
1. Schema design