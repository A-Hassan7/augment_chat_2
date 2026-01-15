implement embeddings for the transcript chunk retrieval piece

HOW:
- replicate ai
- implement the llm interface
    - does the request to the service need to be async bearing in mind it needs to be executed by a worker
    - If not the each worker would stuck with a single request

    callback implementation:
    - I send an async request to the llm provider
    - when the request comes back, I need to do something with it
    - when the request is sent, do I wait for it to complete?
    - async/await already solves this problem
    - await doesn't block the executtion of the code in the main thread
    - it's forked as a separete process
    - I need to create success and failure events

    - I don't need asyncio because I would still have to wait for the execution of the function
    - asyncio is useful when I need to create multiple tasks that can run side by side
    - in the case of my application I don't need that
    - It would only work if I wanted to create 10 embeddings at the same time and then insert them
    - however in my case I'm only creating a single embedding at a time mostly
    - so there's no need to async
    - I just need to queue the function and have it insert embeddings into the database when it's done

Reqs:
- keep log of requests
- async processed through a queue