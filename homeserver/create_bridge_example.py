"""
Example script to create and start a WhatsApp bridge.

This demonstrates how to use the orchestrator interface to create a bridge.
"""

from bridge_manager.database.models import BridgeType
from bridge_manager.database.engine import DatabaseEngine
from bridge_manager.orchestrator import BridgeOrchestrator
from config import BridgeManagerConfig


def create_whatsapp_bridge():
    """Create a WhatsApp bridge instance."""

    # Get database session
    db_engine = DatabaseEngine()

    with db_engine.get_session() as session:
        print("Creating WhatsApp bridge...")

        # Create the bridge
        orchestrator = BridgeOrchestrator()
        bridge = orchestrator.create_bridge(
            bridge_type=BridgeType.WHATSAPP,
            homeserver_id=BridgeManagerConfig.HOMESERVER_ID,
            owner_matrix_username="@admin:hs001.matrix.me",
            docker_host=None,  # Use local Docker
        )

        print(f"✅ Bridge created successfully!")
        print(f"   Bridge ID: {bridge.bridge_id}")
        print(f"   Container ID: {bridge.container_id}")
        print(f"   Status: {bridge.status.value}")
        print(f"   Port: {bridge.port}")
        print(f"   AS Token: {bridge.as_token}")
        print(f"   HS Token: {bridge.hs_token}")

        return bridge.bridge_id


def check_bridge_status(bridge_id: str):
    """Check the status of a bridge."""

    db_engine = DatabaseEngine()

    with db_engine.get_session() as session:
        print(f"\nChecking bridge status for {bridge_id}...")

        orchestrator = BridgeOrchestrator()
        status = orchestrator.check_bridge_status(
            bridge_id=bridge_id,
        )

        print(f"✅ Bridge status: {status.value}")


if __name__ == "__main__":
    # Create a bridge
    bridge_id = create_whatsapp_bridge()

    # Check its status
    check_bridge_status(bridge_id)

    print("\n📝 Next steps:")
    print(f"   1. The bridge is now running on the assigned port")
    print(f"   2. Bridge ID: {bridge_id}")
    print(
        f"   3. The homeserver will route requests through the bridge manager appservice"
    )
    print(f"   4. Use the bridge ID to interact with this specific bridge instance")
