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



# Augmented Chat (Conversational Jokes)

### Aim: Carisma as a service

The goal is to create the backend engine for an app that will give the user conversational, and witty joke suggestions during an online chat. The engine will read the users conversation history, create summaries of their interaction, and use that infromation to provide relevent witty remarks and jokes which the user can use in their conversation.

### Why: Augmented conversations as the future of online chatting

Large Language Models can understand context and create human like responses. LLMs have become tramendously popular, and will continue to do as as they become staples in chatbots and emailing. I'm aming to inject LLMs into personal conversations to enrich the online messaging experience. A new kind of messaging - augmented messaging.

### How: Messages -> Vectorstore -> Prompt Generation -> Response

Using vectorstores, it's possible to inject relevent context from a large corpus of text into an LLM with a token limit. Summary chains can then be used to condense larger, relevent pieces of text, into consise bits of information that can be used by the LLM.