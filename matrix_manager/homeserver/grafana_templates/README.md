# Grafana Templates

This directory contains versioned Grafana configuration templates that are used during homeserver deployment.

## Files

- **datasources.yml** - Prometheus datasource configuration
- **dashboards.yml** - Dashboard provider configuration  
- **synapse-dashboard.json** - Synapse monitoring dashboard template

## Template Variables

Templates use `{{variable}}` placeholders that are replaced during deployment:

- `{{homeserver_id}}` - The homeserver ID (e.g., "hs-001")
- `{{prometheus_container}}` - Prometheus container name (e.g., "hs-001_prometheus")

## Updating Dashboards

### Method 1: Edit JSON directly
1. Edit `synapse-dashboard.json`
2. Use `{{homeserver_id}}` placeholders in queries
3. Commit changes
4. Next deployment will use updated dashboard

### Method 2: Export from Grafana UI
1. Make changes in Grafana UI
2. Export dashboard JSON via Grafana UI (Share > Export > Save to file)
3. Replace hardcoded homeserver IDs with `{{homeserver_id}}` placeholders
4. Save as `synapse-dashboard.json`
5. Commit changes

Example query replacement:
```
Before: synapse_http_server_requests_received_total{homeserver="hs-001"}
After:  synapse_http_server_requests_received_total{homeserver="{{homeserver_id}}"}
```

## Adding New Dashboards

1. Create new JSON file in this directory (e.g., `custom-dashboard.json`)
2. Use `{{homeserver_id}}` placeholders in Prometheus queries
3. Add filename to `DASHBOARD_TEMPLATES` list in `deploy.py`

## Notes

- These templates are version-controlled and shared across all deployments
- Provisioning files are marked as `readOnly` in Grafana to prevent UI modifications
- To allow UI edits, change `disableDeletion` and `allowUiUpdates` in `dashboards.yml`
