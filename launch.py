from event_processor import EventProcessorInterface
from config import GlobalConfig

# when running in debug mode I only need to initialise the event listener
# the event listener acts as the triggering event all/most other processes
# setting GlobalConfig.DEBUG_MODE = True puts the event queue in synchronouse mode
# which tells it to execute processes on the same process/thread
# debug mode also uses a fake redis emulator so a real redis instance is not required.
debug = True
if debug:
    GlobalConfig.DEBUG_MODE = True

    interface = EventProcessorInterface()
    interface.run_event_listener()


# in non debug mode I need to create workers so I'll have to initialise services individually
