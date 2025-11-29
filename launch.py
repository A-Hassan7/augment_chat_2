import asyncio

from config import GlobalConfig

from event_processor import EventProcessorInterface

# when running in debug mode I only need to initialise the event listener
# the event listener acts as the triggering event all/most other processes
# setting GlobalConfig.DEBUG_MODE = True puts the event queue in synchronouse mode
# which tells it to execute processes on the same process/thread
debug = False

if debug:
    GlobalConfig.DEBUG_MODE = True
    GlobalConfig.USE_FAKE_REDIS = False

    EventProcessorInterface().run_event_listener()


# if not in debug then create a process for each component
commands = [
    # Event processor processes
    "python -c 'from event_processor import EventProcessorInterface; EventProcessorInterface().run_event_listener();'",
    "python -c 'from event_processor import EventProcessorInterface; EventProcessorInterface().backfill();'",
    "python -c 'from event_processor import EventProcessorInterface; EventProcessorInterface().run_event_processor_worker();'",
    # Vectorstore processes
    "python -c 'from vector_store import VectorStoreInterface; VectorStoreInterface().run_worker();'",
    "python -c 'from vector_store import VectorStoreInterface; VectorStoreInterface().backfill(all_rooms=True);'",
    # LLM service processes
    "python -c 'from llm_service import LLMInterface; LLMInterface().run_worker();'",
    # Bridge manager
    "python -c \"import uvicorn; uvicorn.run('api.main:app')\"",
]


# create a subprocess for process listed above
async def main():
    processes = [await asyncio.create_subprocess_shell(cmd) for cmd in commands]
    outputs = [await process.wait() for process in processes]


asyncio.run(main())
