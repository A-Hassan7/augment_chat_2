"""
Configure Grafana with Prometheus datasource and Synapse dashboard
"""

import time
import requests
from pathlib import Path


def setup_grafana(homeserver_id: str, grafana_url: str = "http://localhost:3000"):
    """
    Set up Grafana with Prometheus datasource and Synapse dashboard

    Args:
        homeserver_id: The homeserver ID
        grafana_url: URL to Grafana instance
    """
    print(f"Setting up Grafana for {homeserver_id}...")

    # Wait for Grafana to be ready
    print("  Waiting for Grafana to be ready...")
    for i in range(30):
        try:
            response = requests.get(f"{grafana_url}/api/health")
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)

    # Grafana credentials
    auth = ("admin", "admin")

    # Add Prometheus datasource
    print("  Adding Prometheus datasource...")
    datasource = {
        "name": "Prometheus",
        "type": "prometheus",
        "access": "proxy",
        "url": "http://prometheus:9090",
        "isDefault": True,
        "jsonData": {"timeInterval": "15s"},
    }

    try:
        response = requests.post(
            f"{grafana_url}/api/datasources",
            json=datasource,
            auth=auth,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code in [200, 409]:  # 409 = already exists
            print("  ✓ Prometheus datasource configured")
        else:
            print(f"  Warning: Failed to add datasource: {response.text}")
    except Exception as e:
        print(f"  Warning: Could not configure datasource: {e}")

    # Create Synapse dashboard
    print("  Creating Synapse dashboard...")
    dashboard = create_synapse_dashboard(homeserver_id)

    try:
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            json={"dashboard": dashboard, "overwrite": True},
            auth=auth,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code == 200:
            print("  ✓ Synapse dashboard created")
        else:
            print(f"  Warning: Failed to create dashboard: {response.text}")
    except Exception as e:
        print(f"  Warning: Could not create dashboard: {e}")

    print(f"✓ Grafana setup complete")
    print(f"  Access Grafana at: {grafana_url}")
    print(f"  Username: admin")
    print(f"  Password: admin")


def create_synapse_dashboard(homeserver_id: str) -> dict:
    """Create a Synapse monitoring dashboard"""
    return {
        "title": f"Synapse Homeserver - {homeserver_id}",
        "tags": ["synapse", homeserver_id],
        "timezone": "browser",
        "schemaVersion": 16,
        "panels": [
            {
                "id": 1,
                "title": "Request Rate",
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": f'rate(synapse_http_server_requests_received_total{{homeserver="{homeserver_id}"}}[5m])',
                        "legendFormat": "{{instance}} - {{method}} {{servlet}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "reqps", "label": "Requests/sec"},
                    {"format": "short"},
                ],
            },
            {
                "id": 2,
                "title": "Response Time (p95)",
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": f'histogram_quantile(0.95, rate(synapse_http_server_response_time_seconds_bucket{{homeserver="{homeserver_id}"}}[5m]))',
                        "legendFormat": "{{instance}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "s", "label": "Response Time"},
                    {"format": "short"},
                ],
            },
            {
                "id": 3,
                "title": "Active Connections",
                "type": "graph",
                "gridPos": {"x": 0, "y": 8, "w": 8, "h": 8},
                "targets": [
                    {
                        "expr": f'synapse_http_server_active_requests{{homeserver="{homeserver_id}"}}',
                        "legendFormat": "{{instance}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "short", "label": "Connections"},
                    {"format": "short"},
                ],
            },
            {
                "id": 4,
                "title": "Database Connections",
                "type": "graph",
                "gridPos": {"x": 8, "y": 8, "w": 8, "h": 8},
                "targets": [
                    {
                        "expr": f'synapse_storage_connections{{homeserver="{homeserver_id}"}}',
                        "legendFormat": "{{instance}} - {{state}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "short", "label": "Connections"},
                    {"format": "short"},
                ],
            },
            {
                "id": 5,
                "title": "Memory Usage",
                "type": "graph",
                "gridPos": {"x": 16, "y": 8, "w": 8, "h": 8},
                "targets": [
                    {
                        "expr": f'process_resident_memory_bytes{{homeserver="{homeserver_id}"}}',
                        "legendFormat": "{{instance}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [{"format": "bytes", "label": "Memory"}, {"format": "short"}],
            },
            {
                "id": 6,
                "title": "Event Processing Rate",
                "type": "graph",
                "gridPos": {"x": 0, "y": 16, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": f'rate(synapse_storage_events_persisted_events_total{{homeserver="{homeserver_id}"}}[5m])',
                        "legendFormat": "{{instance}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "ops", "label": "Events/sec"},
                    {"format": "short"},
                ],
            },
            {
                "id": 7,
                "title": "Federation Outbound",
                "type": "graph",
                "gridPos": {"x": 12, "y": 16, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": f'rate(synapse_federation_client_sent_transactions_total{{homeserver="{homeserver_id}"}}[5m])',
                        "legendFormat": "{{instance}}",
                        "refId": "A",
                    }
                ],
                "yaxes": [
                    {"format": "ops", "label": "Transactions/sec"},
                    {"format": "short"},
                ],
            },
        ],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python setup_grafana.py <homeserver_id>")
        sys.exit(1)

    homeserver_id = sys.argv[1]
    setup_grafana(homeserver_id)
