# Grafana Templates

Grafana configuration templates for homeserver monitoring.

## Files

- **datasources.yml** - Prometheus datasource configuration
- **dashboards.yml** - Dashboard provisioning configuration  
- **synapse-dashboard.json** - Pre-configured Synapse monitoring dashboard

## Template Variables

Templates use `{{variable}}` placeholders replaced during deployment:
- `{{homeserver_id}}` - Homeserver ID (e.g., "hs-001")
- `{{prometheus_container}}` - Prometheus container name (e.g., "hs-001_prometheus")

## Usage

These templates are automatically processed by `deploy.py`:
1. Variables are substituted based on deployment config
2. Datasource and dashboard configs are written to grafana provisioning directory
3. Dashboards are imported via Grafana API

## Updating Dashboards

To modify dashboards:
1. Edit `synapse-dashboard.json` directly, or
2. Export from Grafana UI and replace hardcoded IDs with `{{homeserver_id}}`

Example:
```
Before: homeserver="hs-001"
After:  homeserver="{{homeserver_id}}"
```
