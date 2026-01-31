# Technology Stack

**Analysis Date:** 2026-01-31

## Languages

**Primary:**
- Python 3.10-3.12 - Core application language (FastAPI backend, worker processes)
- Jinja2 - Kubernetes manifest templating (`gpustack/k8s/manifests.jinja`)
- YAML - Configuration, docker-compose, k8s manifests

**Secondary:**
- Shell/Bash - Build scripts (`hack/` directory)
- PowerShell - Windows build scripts (`hack/windows/`)
- Dockerfile - Multi-stage container builds (`pack/Dockerfile`)

## Runtime

**Environment:**
- Python 3.10-3.12 (requires-python: ">=3.10,<3.13")
- asyncio - Async/await throughout codebase
- multiprocessing - Worker process spawning

**Package Manager:**
- uv - Modern Python package installer and resolver (lockfile: `uv.lock`)
- pipx - Tool installation for versioned backends

**Build System:**
- Hatchling - Build backend (PEP 517)
- Makefile - Task runner with cross-platform support

## Frameworks

**Web/API:**
- FastAPI 0.115.0+ - Main web framework
- Uvicorn 0.32.0+ - ASGI server
- SQLModel 0.0.18+ - SQLAlchemy + Pydantic ORM
- Pydantic 2.11.5+ - Data validation and settings
- Pydantic-settings 2.2.1+ - Environment-based configuration

**Database:**
- SQLAlchemy 2.0.38+ (asyncio) - ORM with async support
- Alembic 1.13.2+ - Database migrations
- aiosqlite 0.20.0+ - Async SQLite
- asyncpg 0.29.0+ - Async PostgreSQL driver
- asyncmy 0.2.10+ - Async MySQL driver
- psycopg2-binary 2.9.10+ - Sync PostgreSQL driver
- PyMySQL 1.1.1+ - Sync MySQL driver

**Task Scheduling:**
- APScheduler 3.10.4+ (<4.0.0) - Background job scheduler

**Auth & Security:**
- PyJWT 2.8.0+ - JWT token handling
- argon2-cffi 23.1.0+ - Password hashing
- python3-saml 1.16.0 - SAML authentication
- lxml 5.2.1 - XML processing for SAML
- xmlsec 1.3.14 - XML security for SAML
- cryptography 43.0.0+ - Encryption utilities

**HTTP Clients:**
- httpx[socks] 0.27.0+ - Modern async HTTP client
- requests 2.32.3+ - Traditional HTTP client
- aiohttp 3.11.2+ - Async HTTP client/server

**ML/AI Libraries:**
- openai 1.31.1+ - OpenAI API client and types
- transformers 4.51.3+ (excluding 4.57.0) - Hugging Face transformers
- huggingface-hub 0.32.0+ - Hugging Face Hub utilities
- modelscope 1.28+ - ModelScope (Chinese model hub)
- vllm 0.10.1.1 (optional) - LLM inference engine

**Kubernetes:**
- kubernetes 33.1.0+ - Official K8s Python client
- kubernetes-asyncio 33.1.0+ - Async K8s client

**Monitoring:**
- prometheus-client 0.20.0+ - Prometheus metrics

**Caching:**
- aiocache 0.12.3+ - Async caching
- cachetools 6.0.0+ - General caching utilities

**Serialization:**
- msgpack 1.1.2+ - Binary serialization
- dataclasses-json 0.6.7+ - JSON serialization for dataclasses
- PyArrow 18.0.0-19.0.0 - Columnar data format
- pandas 2.3.0+ - Data manipulation

**Rate Limiting:**
- aiolimiter 1.2.1+ - Async rate limiting

**Utilities:**
- tenacity 9.0.0+ - Retry logic
- aiofiles 23.2.1+ - Async file operations
- psutil 7.0.0+ - System/process utilities
- colorama 0.4.6+ - Cross-platform colored terminal
- Jinja2 3.1.6+ - Templating

**GPU Vendor Support:**
- gpustack-runner 0.1.24.post4+ - GPUStack runner component
- gpustack-runtime 0.1.41.post3+ - GPUStack runtime component

## Key Dependencies

**Critical:**
- `fastapi` - Core web framework for API endpoints
- `sqlmodel` + `sqlalchemy` - Database ORM and models
- `pydantic` - Data validation, configuration management
- `kubernetes` + `kubernetes-asyncio` - Kubernetes cluster management
- `openai` - OpenAI-compatible API types and client
- `transformers` - Hugging Face model support

**Infrastructure:**
- `uvicorn` - ASGI server for FastAPI
- `alembic` - Database schema migrations
- `apscheduler` - Background task scheduling
- `prometheus-client` - Metrics exposition
- `aiocache` - Distributed caching
- `httpx` - Modern async HTTP client (preferred over requests)

**Security:**
- `pyjwt` - JWT authentication tokens
- `argon2-cffi` - Secure password hashing
- `python3-saml` - SAML SSO integration
- `cryptography` - Encryption and certificates

**Vendor Cloud:**
- `pydo` - Digital Ocean API client

## Configuration

**Environment:**
- Pydantic-settings with `GPUSTACK_` prefix
- Environment variables auto-mapped to Config class
- Key files:
  - `gpustack/config/config.py` - Main configuration class
  - `gpustack/config/registration.py` - Token management

**Build:**
- `pyproject.toml` - Project metadata, dependencies, tool configs
- `alembic.ini` - Database migration settings
- `pytest.ini` - Test markers
- `.pre-commit-config.yaml` - Pre-commit hooks (flake8, black, shellcheck)

**Key Configs Required:**
- `GPUSTACK_DATABASE_URL` - Database connection string (PostgreSQL or MySQL)
- `GPUSTACK_JWT_SECRET_KEY` - Auto-generated if not provided
- `GPUSTACK_BOOTSTRAP_PASSWORD` - Initial admin password
- `GPUSTACK_TOKEN` - Worker registration token

## Platform Requirements

**Development:**
- Python 3.10-3.12
- uv package manager
- make (GNU Make)
- git
- docker (optional, for container builds)

**Production:**
- Docker container runtime (primary deployment)
- PostgreSQL 17 (embedded) or external PostgreSQL/MySQL
- Kubernetes cluster (optional, for gateway mode)
- GPU drivers for target hardware (NVIDIA, AMD, Intel, Ascend, etc.)

**Supported GPU Vendors:**
- NVIDIA (via NVML)
- AMD (via ROCm/amd-smi)
- Intel (via Level Zero)
- Huawei Ascend (via CANN/DCMI)
- Cambricon
- Hygon
- Iluvatar
- MetaX
- MThreads
- T-Head

**Observability:**
- Prometheus (metrics collection)
- Grafana (visualization, optional)
- Higress API Gateway (embedded or external K8s)

---

*Stack analysis: 2026-01-31*
