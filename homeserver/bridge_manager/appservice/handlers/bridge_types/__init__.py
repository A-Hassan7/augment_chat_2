"""
Registry that maps bridge types to the correct BridgeRequestHandler subclass.

  BridgeHandlerRegistry.get_handler("whatsapp")  → WhatsAppBridgeRequestHandler
  BridgeHandlerRegistry.get_handler("discord")   → BridgeRequestHandler (generic)
  BridgeHandlerRegistry.get_handler("unknown")   → BridgeRequestHandler (generic)

Handler instances are cached by bridge type so the PathRouter is only compiled
once per bridge type per process lifetime.

Adding support for a new bridge type:
1. Create handlers/bridge_types/<type>.py with a subclass of BridgeRequestHandler.
2. Import it here and add it to _registry.
"""

from typing import Dict, Type

from ..bridge_handler import BridgeRequestHandler
from .whatsapp import WhatsAppBridgeRequestHandler


class BridgeHandlerRegistry:
    """
    Maps bridge_type strings to BridgeRequestHandler subclasses and caches
    one handler instance per bridge type.
    """

    _registry: Dict[str, Type[BridgeRequestHandler]] = {
        "whatsapp": WhatsAppBridgeRequestHandler,
    }

    # Cached instances keyed by bridge type string
    _instances: Dict[str, BridgeRequestHandler] = {}

    @classmethod
    def get_handler(cls, bridge_type: str) -> BridgeRequestHandler:
        """
        Return the handler instance for the given bridge type.

        Falls back to the generic BridgeRequestHandler for any unregistered
        bridge type so that existing pass-through behaviour is preserved.

        Args:
            bridge_type: Bridge type string, e.g. "whatsapp", "discord".

        Returns:
            Cached BridgeRequestHandler (or subclass) instance.
        """
        if bridge_type not in cls._instances:
            handler_class = cls._registry.get(bridge_type, BridgeRequestHandler)
            cls._instances[bridge_type] = handler_class()
        return cls._instances[bridge_type]
