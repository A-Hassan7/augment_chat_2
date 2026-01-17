"""
Utility to export Grafana dashboards back to templates

This tool is useful when you've made changes to dashboards in the Grafana UI
and want to save them back to version-controlled template files.

Note: With the new provisioning system, dashboards and datasources are
automatically configured on deployment. This tool is only needed if you want
to export modified dashboards from the UI back to templates.
"""

import json
import re
import requests
from pathlib import Path


def export_dashboard(
    homeserver_id: str,
    dashboard_uid: str = None,
    grafana_url: str = "http://localhost:3000",
    output_file: str = None,
):
    """
    Export a dashboard from Grafana and save as a template

    Args:
        homeserver_id: The homeserver ID (used for placeholder substitution)
        dashboard_uid: Dashboard UID to export (if None, lists available dashboards)
        grafana_url: URL to Grafana instance
        output_file: Output filename (defaults to slug-based name)
    """
    auth = ("admin", "admin")
    templates_dir = Path(__file__).parent / "grafana_templates"

    # If no UID provided, list available dashboards
    if not dashboard_uid:
        print("Available dashboards:")
        try:
            response = requests.get(f"{grafana_url}/api/search?type=dash-db", auth=auth)
            dashboards = response.json()
            for dash in dashboards:
                print(f"  UID: {dash['uid']}")
                print(f"  Title: {dash['title']}")
                print(f"  URL: {dash['url']}")
                print()
            print("Usage: python setup_grafana.py <homeserver_id> <dashboard_uid>")
        except Exception as e:
            print(f"Error listing dashboards: {e}")
        return

    # Export the dashboard
    print(f"Exporting dashboard {dashboard_uid}...")
    try:
        response = requests.get(
            f"{grafana_url}/api/dashboards/uid/{dashboard_uid}", auth=auth
        )
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return

        dashboard_data = response.json()
        dashboard = dashboard_data["dashboard"]

        # Remove Grafana metadata
        dashboard.pop("id", None)
        dashboard.pop("uid", None)
        dashboard.pop("version", None)

        # Convert dashboard JSON to string for replacement
        dashboard_str = json.dumps(dashboard, indent=2)

        # Replace homeserver_id with template placeholder
        dashboard_str = dashboard_str.replace(
            f'"{homeserver_id}"', '"{{homeserver_id}}"'
        )
        dashboard_str = dashboard_str.replace(
            f'homeserver=\\"{homeserver_id}\\"',
            'homeserver=\\"{{homeserver_id}}\\"',
        )
        dashboard_str = dashboard_str.replace(
            f"homeserver='{homeserver_id}'", "homeserver='{{homeserver_id}}'"
        )

        # Determine output filename
        if not output_file:
            slug = dashboard.get("title", "dashboard").lower()
            slug = re.sub(r"[^a-z0-9]+", "-", slug)
            slug = slug.strip("-")
            output_file = f"{slug}.json"

        output_path = templates_dir / output_file

        # Write the template
        with open(output_path, "w") as f:
            f.write(dashboard_str)

        print(f"✓ Dashboard exported to: {output_path}")
        print(f"  Title: {dashboard.get('title')}")
        print(f"  Template placeholders have been substituted")
        print(f"\nNext deployment will use the updated dashboard.")

    except Exception as e:
        print(f"Error exporting dashboard: {e}")


def list_datasources(grafana_url: str = "http://localhost:3000"):
    """List all configured datasources"""
    auth = ("admin", "admin")
    try:
        response = requests.get(f"{grafana_url}/api/datasources", auth=auth)
        datasources = response.json()
        print("Configured datasources:")
        for ds in datasources:
            print(f"  Name: {ds['name']}")
            print(f"  Type: {ds['type']}")
            print(f"  URL: {ds['url']}")
            print(f"  Default: {ds.get('isDefault', False)}")
            print()
    except Exception as e:
        print(f"Error listing datasources: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Grafana Dashboard Export Utility")
        print("=" * 50)
        print("\nUsage:")
        print("  List dashboards:")
        print("    python setup_grafana.py <homeserver_id>")
        print("\n  Export dashboard:")
        print(
            "    python setup_grafana.py <homeserver_id> <dashboard_uid> [output_file]"
        )
        print("\n  List datasources:")
        print("    python setup_grafana.py --datasources")
        print("\nExample:")
        print("  python setup_grafana.py hs-001")
        print("  python setup_grafana.py hs-001 abc123def456")
        print("  python setup_grafana.py hs-001 abc123def456 my-custom-dashboard.json")
        sys.exit(1)

    if sys.argv[1] == "--datasources":
        list_datasources()
    elif len(sys.argv) == 2:
        # List dashboards
        export_dashboard(sys.argv[1])
    elif len(sys.argv) == 3:
        # Export with auto-generated filename
        export_dashboard(sys.argv[1], sys.argv[2])
    else:
        # Export with custom filename
        export_dashboard(sys.argv[1], sys.argv[2], output_file=sys.argv[3])
