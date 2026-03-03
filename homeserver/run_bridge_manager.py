#!/usr/bin/env python3
"""
Run the Bridge Manager Appservice.

This starts the proxy layer that routes traffic between the homeserver and bridge instances.

IMPORTANT: Run this from the repo root:
    cd homeserver
    python3 run_bridge_manager.py
"""

import uvicorn
import sys
import os

# Make homeserver self-contained - add its directory to Python path
HOMESERVER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOMESERVER_DIR)

# Import from main config (which loads from homeserver/.env)
from config import BRIDGE_MANAGER_CONFIG
from bridge_manager.database.models import create_schema_and_tables
from bridge_manager.database.repositories import HomeserverRepository
from bridge_manager.appservice.appservice import app

if __name__ == "__main__":
    # Initialize database schema and tables
    print("Initializing database schema...")
    try:
        create_schema_and_tables()
        print("✓ Database initialized")
    except Exception as e:
        print(f"Database initialization error: {e}")
        print("Continuing anyway (tables may already exist)...")

    # Ensure homeserver is registered (only one per bridge manager instance)
    print("Ensuring homeserver registration...")
    try:
        existing_homeservers = HomeserverRepository.list_all()
        if len(existing_homeservers) > 1:
            raise RuntimeError(
                "Multiple homeservers found for this bridge manager instance. "
                "Only one homeserver is supported."
            )

        homeserver = HomeserverRepository.get_or_create(
            id=BRIDGE_MANAGER_CONFIG.HOMESERVER_ID,
            name=BRIDGE_MANAGER_CONFIG.HOMESERVER_NAME,
            url=BRIDGE_MANAGER_CONFIG.HOMESERVER_URL,
            hs_token=BRIDGE_MANAGER_CONFIG.HOMESERVER_HS_TOKEN,
        )

        if existing_homeservers and existing_homeservers[0].id != homeserver.id:
            raise RuntimeError(
                "Existing homeserver does not match configured HOMESERVER_ID. "
                "Please verify homeserver configuration."
            )

        print(
            f"✓ Homeserver registered: {homeserver.name} ({homeserver.id}) - {homeserver.url}"
        )
    except Exception as e:
        print(f"❌ Homeserver registration error: {e}")
        print("Exiting - homeserver must be registered before accepting requests")
        sys.exit(1)

    # Start the appservice
    print(
        f"Starting Bridge Manager Appservice on {BRIDGE_MANAGER_CONFIG.HOST}:{BRIDGE_MANAGER_CONFIG.PORT}..."
    )
    uvicorn.run(
        app,  # Pass the app object directly instead of string
        host=BRIDGE_MANAGER_CONFIG.HOST,
        port=BRIDGE_MANAGER_CONFIG.PORT,
        log_level="info",
        reload=False,  # Set to True for development
    )
