"""
Centralized configuration for homeserver deployment

All configurable values for deploying Matrix homeserver instances.
"""

# ========================================
# Docker Images
# ========================================
POSTGRES_IMAGE = "postgres:15-alpine"
SYNAPSE_IMAGE = "matrixdotorg/synapse:latest"
REDIS_IMAGE = "redis:7-alpine"
NGINX_IMAGE = "nginx:alpine"
PROMETHEUS_IMAGE = "prom/prometheus:latest"
GRAFANA_IMAGE = "grafana/grafana:latest"

# ========================================
# Network Ports
# ========================================
# Synapse
SYNAPSE_HTTP_PORT = 8008  # Main HTTP API port
SYNAPSE_FEDERATION_PORT = 8448  # Federation port (TLS)
SYNAPSE_METRICS_PORT = 9000  # Metrics endpoint
SYNAPSE_REPLICATION_PORT = 9093  # Worker replication port

# Monitoring
GRAFANA_PORT = 3000  # Grafana web interface
PROMETHEUS_PORT = 9090  # Prometheus web interface

# Databases
POSTGRES_PORT = 5432  # PostgreSQL database
REDIS_PORT = 6379  # Redis (for workers)

# Nginx
NGINX_HTTP_PORT = 80  # Nginx load balancer
NGINX_STATUS_PORT = 8080  # Nginx metrics endpoint

# Workers
WORKER_BASE_PORT = 8081  # Starting port for worker HTTP endpoints

# ========================================
# Default Credentials
# ========================================
# Database
DB_USER = "synapse"
DB_PASSWORD = "password"  # TODO: Generate securely in production

# Grafana
GRAFANA_ADMIN_USER = "admin"
GRAFANA_ADMIN_PASSWORD = "admin"  # TODO: Generate securely in production

# Matrix Admin User
MATRIX_ADMIN_USERNAME = "admin"
MATRIX_ADMIN_PASSWORD = "admin"  # TODO: Generate securely in production

# ========================================
# Timeouts
# ========================================
SYNAPSE_STARTUP_TIMEOUT = 60  # Seconds to wait for Synapse to be ready
GRAFANA_STARTUP_TIMEOUT = 60  # Seconds to wait for Grafana to be ready

# ========================================
# Worker Configuration
# ========================================
WORKER_PORT_MAX_ATTEMPTS = 100  # Max attempts to find available port
WORKER_PORT_RANDOM_OFFSET = 50  # Random offset to avoid port collisions

# ========================================
# Database Connection Pool
# ========================================
DB_MIN_CONNECTIONS = 5  # Minimum connections in pool
DB_MAX_CONNECTIONS = 10  # Maximum connections in pool

# ========================================
# Nginx Configuration
# ========================================
NGINX_CLIENT_MAX_BODY_SIZE = "50M"  # Max upload size

# ========================================
# Prometheus Configuration
# ========================================
PROMETHEUS_SCRAPE_INTERVAL = "15s"  # How often to scrape metrics
PROMETHEUS_EVALUATION_INTERVAL = "15s"  # How often to evaluate rules

# ========================================
# Grafana Configuration
# ========================================
GRAFANA_ANONYMOUS_ACCESS = True  # Allow anonymous viewers
GRAFANA_ANONYMOUS_ROLE = "Viewer"  # Role for anonymous users
