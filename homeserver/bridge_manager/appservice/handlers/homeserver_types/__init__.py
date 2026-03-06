"""
Registry that maps bridge types to the correct HomeserverRequestHandler subclass.

  HomeserverHandlerRegistry.get_handler("whatsapp")  → HomeserverRequestHandler (generic)
  HomeserverHandlerRegistry.get_handler("discord")   → HomeserverRequestHandler (generic)

No bridge-type-specific homeserver-to-bridge transforms exist yet.  When one is
needed, follow the same pattern as bridge_types/:

1. Create handlers/homeserver_types/<type>.py with a subclass of
   HomeserverRequestHandler that overrides _register_type_specific_routes().
2. Import it here and add it to _registry.

Handler instances are cached by bridge type so the PathRouter is only compiled
once per bridge type per process lifetime.
"""

from typing import Dict, Type

from ..homeserver_handler import HomeserverRequestHandler


class HomeserverHandlerRegistry:
    """
    Maps bridge_type strings to HomeserverRequestHandler subclasses and caches
    one handler instance per bridge type.
    """

    _registry: Dict[str, Type[HomeserverRequestHandler]] = {
        # No bridge-type-specific homeserver handlers yet.
        # Example when adding one:
        #   "whatsapp": WhatsAppHomeserverRequestHandler,
    }

    # Cached instances keyed by bridge type string
    _instances: Dict[str, HomeserverRequestHandler] = {}

    @classmethod
    def get_handler(cls, bridge_type: str) -> HomeserverRequestHandler:
        """
        Return the handler instance for the given bridge type.

        Falls back to the generic HomeserverRequestHandler for any unregistered
        bridge type.

        Args:
            bridge_type: Bridge type string, e.g. "whatsapp", "discord".

        Returns:
            Cached HomeserverRequestHandler (or subclass) instance.
        """
        if bridge_type not in cls._instances:
            handler_class = cls._registry.get(bridge_type, HomeserverRequestHandler)
            cls._instances[bridge_type] = handler_class()
        return cls._instances[bridge_type]
