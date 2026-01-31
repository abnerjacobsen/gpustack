# External Integrations

**Analysis Date:** 2026-01-31

## APIs & External Services

**Model Registries:**
- Hugging Face Hub (`huggingface_hub`)
  - SDK: `huggingface-hub>=0.32.0`
  - Auth: `GPUSTACK_HUGGINGFACE_TOKEN` env var
  - Usage: Model download, file metadata, gated repo access
  - Files: `gpustack/worker/downloaders.py`, `gpustack/utils/hub.py`

- ModelScope (Chinese model hub)
  - SDK: `modelscope>=1.28`
  - Auth: Model-specific tokens
  - Usage: Alternative to Hugging Face for China region
  - Files: `gpustack/worker/downloaders.py`, `gpustack/utils/hub.py`

**Cloud Provider:**
- Digital Ocean
  - SDK: `pydo>=0.15.0` (Digital Ocean Python client)
  - Auth: `cloud_credentials` table, access tokens
  - Usage: GPU worker provisioning, droplet management
  - Files: `gpustack/cloud_providers/digital_ocean.py`, `gpustack/cloud_providers/abstract.py`

**Update Check:**
- GPUStack Update Server
  - Client: `httpx`
  - Endpoint: Configurable via `update_check_url` (default: GPUStack update server)
  - Usage: Version check, changelog retrieval
  - File: `gpustack/server/update_check.py`

**OpenAI API:**
- OpenAI Python SDK
  - SDK: `openai>=1.31.1`
  - Usage: OpenAI-compatible API types, NOT for external calls
  - Files: `gpustack/routes/openai.py`, `gpustack/api/middlewares.py`

## Data Storage

**Primary Database:**
- PostgreSQL (default embedded, or external)
  - Connection: `GPUSTACK_DATABASE_URL` env var
  - Async driver: `asyncpg`
  - Sync driver: `psycopg2-binary`
  - Default URL: `postgresql://root@127.0.0.1:5432/gpustack?sslmode=disable`

**Alternative Database:**
- MySQL/MariaDB
  - Connection: `mysql://` scheme in `GPUSTACK_DATABASE_URL`
  - Async driver: `asyncmy`
  - Sync driver: `pymysql`

- SQLite (async)
  - Driver: `aiosqlite`
  - Usage: Development/testing only

**File Storage:**
- Local filesystem (primary)
  - Data dir: `/var/lib/gpustack` (Linux) or `%APPDATA%/gpustack` (Windows)
  - Cache dir: `{data_dir}/cache`
  - Log dir: `{data_dir}/log`
  - Bin dir: `{data_dir}/bin` (versioned backends)

- Object Storage: Not directly integrated (relies on model registries)

**Caching:**
- aiocache (in-memory)
  - Library: `aiocache>=0.12.3`
  - Usage: Model metadata, hub file info
  - File: `gpustack/worker/downloaders.py`

## Authentication & Identity

**Auth Provider - Local:**
- Username/password with argon2 hashing
- JWT tokens (HS256 algorithm)
- API keys with `gpustack` prefix
- Files: `gpustack/security.py`, `gpustack/routes/auth.py`

**Auth Provider - OIDC:**
- OpenID Connect / OAuth2
  - Config: `GPUSTACK_OIDC_ISSUER`, `GPUSTACK_OIDC_CLIENT_ID`, `GPUSTACK_OIDC_CLIENT_SECRET`
  - Discovery: Auto-fetches `.well-known/openid-configuration`
  - Files: `gpustack/routes/auth.py`, `gpustack/config/config.py`

**Auth Provider - SAML:**
- SAML 2.0 SSO
  - Library: `python3-saml==1.16.0`
  - Config: `GPUSTACK_SAML_IDP_SERVER_URL`, `GPUSTACK_SAML_IDP_X509_CERT`, etc.
  - Dependencies: `lxml==5.2.1`, `xmlsec==1.3.14`
  - Files: `gpustack/routes/auth.py`

**Token Management:**
- JWT secret key auto-generated and stored in `{data_dir}/jwt_secret_key`
- Worker registration tokens in `{data_dir}/registration_token`
- API keys stored hashed with argon2

## Monitoring & Observability

**Metrics - Prometheus:**
- Prometheus client library
  - SDK: `prometheus-client>=0.20.0`
  - Endpoint: `/metrics` (configurable port, default 10161)
  - Files: `gpustack/exporter/exporter.py`, `gpustack/routes/metrics.py`

**Gateway Metrics:**
- Higress/Envoy stats endpoint
  - URL: `http://127.0.0.1:{gateway_metrics_port}/stats/prometheus`
  - Parsing: Custom Prometheus text format parser
  - File: `gpustack/server/metrics_collector.py`

**Runtime Metrics:**
- Backend metrics aggregation (vLLM, llama.cpp, etc.)
  - Prometheus parser: `prometheus_client.parser.text_string_to_metric_families`
  - Files: `gpustack/worker/runtime_metrics_client.py`, `gpustack/worker/runtime_metrics_aggregator.py`

**Logging:**
- Python logging with structured JSON output
  - Library: `python-json-logger>=3.3.0`
  - File: `gpustack/logging.py`

**Distributed Tracing:**
- Not currently integrated

## CI/CD & Deployment

**Container Images:**
- Base: Ubuntu 22.04
- Python: 3.11 (configurable)
- Registry: Docker Hub (`gpustack/gpustack`)
- File: `pack/Dockerfile`

**Docker Compose:**
- Services: GPUStack server, Prometheus, Grafana
- Files: `docker-compose/docker-compose.server.yaml`, `docker-compose/docker-compose.observability.yaml`

**Kubernetes:**
- In-cluster deployment support
- Higress API Gateway integration
- Service discovery via DNS
- Files: `gpustack/k8s/manifests.jinja`, `gpustack/k8s/manifest_template.py`

**Build Tools:**
- ORAS - OCI registry client (for WASM plugins)
- Skopeo - Container image mirroring
- s6-overlay - Process supervision in containers

**Documentation:**
- MkDocs with Material theme
  - Tools: `mkdocs>=1.6.0`, `mkdocs-material>=9.5.27`
  - File: `mkdocs.yml`

## Environment Configuration

**Required env vars for server:**
- `GPUSTACK_DATABASE_URL` - Database connection (auto-configured if using embedded PostgreSQL)
- `GPUSTACK_BOOTSTRAP_PASSWORD` - Initial admin password (if not set, auto-generated)

**Required env vars for worker:**
- `GPUSTACK_SERVER_URL` - Server URL to connect to
- `GPUSTACK_TOKEN` - Worker registration token

**Optional but common:**
- `GPUSTACK_HUGGINGFACE_TOKEN` - Hugging Face access token
- `GPUSTACK_DATA_DIR` - Override default data directory
- `GPUSTACK_LOG_DIR` - Override default log directory
- `GPUSTACK_SSL_KEYFILE` / `GPUSTACK_SSL_CERTFILE` - TLS configuration
- `GPUSTACK_OIDC_ISSUER` - OIDC provider URL
- `GPUSTACK_SAML_IDP_SERVER_URL` - SAML IdP URL

**Secrets location:**
- Filesystem: `{data_dir}/` (jwt_secret_key, registration_token, worker_token)
- Database: Hashed passwords, API keys, cloud credentials
- Kubernetes Secrets: TLS certificates (when in K8s mode)

## Webhooks & Callbacks

**Incoming:**
- None currently

**Outgoing:**
- None currently (synchronous API only)

**Reverse Proxy / Gateway:**
- Higress (Envoy-based) for model routing
- Routes OpenAI-compatible requests to model instances
- Files: `gpustack/gateway/`, `gpustack/http_proxy/`

## Third-Party Tools Downloaded at Runtime

**Inference Backends:**
- llama.cpp (downloaded via `gpustack download-tools`)
- vLLM (via pipx for versioned installs)
- Various vendor-specific backends (downloaded from GitHub releases)

**Tools:**
- pipx - Python tool installer
- uv - Package installer
- oras - OCI registry operations
- skopeo - Container image operations (with fallback source build)

**Container Runtime Support:**
- Docker socket mounting (`/var/run/docker.sock`)
- CDI (Container Device Interface) specs
- Various GPU device plugins (NVIDIA, AMD, Ascend, etc.)

---

*Integration audit: 2026-01-31*
