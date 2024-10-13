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


commands = [
    "python -c 'from event_processor import EventProcessorInterface; EventProcessorInterface().run_event_listener();'",
    "python -c 'from event_processor import EventProcessorInterface; EventProcessorInterface().run_event_processor_worker();'",
    "python -c 'from vector_store import VectorStoreInterface; VectorStoreInterface().run_worker();'",
    "python -c 'from llm_service import LLMInterface; LLMInterface().run_worker();'",
]


# create a subprocess for each queue worker
async def main():
    processes = [await asyncio.create_subprocess_shell(cmd) for cmd in commands]
    outputs = [await process.wait() for process in processes]


asyncio.run(main())
