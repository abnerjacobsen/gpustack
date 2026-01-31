# Codebase Structure

**Analysis Date:** 2026-01-31

## Directory Layout

```
gpustack/
├── api/                    # API infrastructure (middleware, auth, exceptions, types)
├── assets/                 # Static assets (metrics configs, chat templates)
├── client/                 # Generated API clients for internal use
├── cloud_providers/        # Cloud provider integrations (DigitalOcean)
├── cmd/                    # CLI command implementations (start, migrate, etc.)
├── codegen/                # Code generation templates
├── config/                 # Configuration management
├── detectors/              # GPU/runtime detection (fastfetch, custom)
├── envs/                   # Environment variable constants
├── exporter/               # Prometheus metrics exporter
├── gateway/                # Kubernetes gateway and plugins
├── http_proxy/             # HTTP proxy utilities
├── k8s/                    # Kubernetes-specific code
├── mixins/                 # Shared model mixins
├── policies/               # Scheduling policies
│   ├── candidate_selectors/  # Backend-specific resource selectors
│   ├── event_recorder/       # Event recording
│   ├── scorers/              # Placement scoring algorithms
│   └── worker_filters/       # Worker filtering logic
├── routes/                 # FastAPI route handlers
│   └── worker/               # Worker-specific routes
├── scheduler/              # Model scheduling logic
├── schemas/                # SQLModel/Pydantic schemas
├── server/                 # Server implementation
├── third_party/            # Third-party bundled dependencies
├── utils/                  # Utility modules
└── worker/                 # Worker implementation
    ├── backends/             # Inference engine backends
    ├── benchmark/            # Benchmarking tools
    └── schemas/              # Worker-specific schemas

tests/                      # Test suite
├── api/                    # API tests
├── cloud_providers/        # Cloud provider tests
├── controller/             # Controller tests
├── fixtures/               # Test fixtures
├── gateway/                # Gateway tests
├── policies/               # Policy tests
├── pretrained_config/      # Config tests
├── routers/                # Router tests
├── scheduler/              # Scheduler tests
├── server/                 # Server tests
└── utils/                  # Utility tests
docs/                       # Documentation (MkDocs)
hack/                       # Development scripts
pack/                       # Packaging scripts
benchmarks/                 # Performance benchmarks
static/                     # Static UI assets
docker-compose/             # Docker compose configurations
```

## Directory Purposes

**`gpustack/api/`:**
- Purpose: API infrastructure shared across routes
- Contains: Middleware, authentication, exceptions, response types
- Key files: `gpustack/api/middlewares.py`, `gpustack/api/auth.py`, `gpustack/api/exceptions.py`

**`gpustack/routes/`:**
- Purpose: HTTP route handlers
- Contains: FastAPI routers for each resource (models, workers, auth, etc.)
- Key files: `gpustack/routes/routes.py` (main router aggregation), `gpustack/routes/models.py`

**`gpustack/server/`:**
- Purpose: Server orchestration and business logic
- Contains: Controllers, services, database init, system monitoring
- Key files: `gpustack/server/server.py`, `gpustack/server/controllers.py`, `gpustack/server/services.py`

**`gpustack/scheduler/`:**
- Purpose: Model placement scheduling
- Contains: Scheduler implementation, model registry, resource calculator
- Key files: `gpustack/scheduler/scheduler.py`, `gpustack/scheduler/calculator.py`

**`gpustack/policies/`:**
- Purpose: Scheduling policy implementations
- Contains: Filters, scorers, candidate selectors for different backends
- Key files: `gpustack/policies/candidate_selectors/vllm_resource_fit_selector.py`

**`gpustack/worker/`:**
- Purpose: Worker node implementation
- Contains: Worker process, backend managers, collectors, serve manager
- Key files: `gpustack/worker/worker.py`, `gpustack/worker/serve_manager.py`

**`gpustack/schemas/`:**
- Purpose: Data models and validation
- Contains: SQLModel-based database entities
- Key files: `gpustack/schemas/models.py`, `gpustack/schemas/workers.py`, `gpustack/schemas/common.py`

**`gpustack/cmd/`:**
- Purpose: CLI command implementations
- Contains: Start, migrate, download-tools, reset-password commands
- Key files: `gpustack/cmd/start.py`, `gpustack/cmd/db_migration.py`

**`gpustack/config/`:**
- Purpose: Configuration management
- Contains: Config classes, registration token handling
- Key files: `gpustack/config/config.py`

**`gpustack/utils/`:**
- Purpose: Shared utilities
- Contains: Network, GPU, hub, command, file utilities
- Key files: `gpustack/utils/gpu.py`, `gpustack/utils/hub.py`, `gpustack/utils/network.py`

**`gpustack/client/`:**
- Purpose: Generated internal API clients
- Contains: Auto-generated clients for server-worker communication
- Pattern: Generated from OpenAPI spec

**`gpustack/gateway/`:**
- Purpose: Kubernetes gateway and ingress management
- Contains: K8s integration, plugins, pull logic
- Key files: `gpustack/gateway/plugins.py`

**`gpustack/migrations/`:**
- Purpose: Database migrations
- Contains: Alembic migration scripts
- Pattern: Auto-generated via `alembic revision`

**`tests/`:**
- Purpose: Test suite
- Structure: Mirrors `gpustack/` structure where applicable
- Key files: `tests/conftest.py` (pytest fixtures)

## Key File Locations

**Entry Points:**
- `gpustack/main.py`: CLI entry point
- `gpustack/cmd/start.py`: Server/worker start command
- `gpustack/server/app.py`: FastAPI app factory (`create_app()`)

**Configuration:**
- `gpustack/config/config.py`: Main configuration class
- `pyproject.toml`: Package metadata and dependencies
- `alembic.ini`: Database migration configuration

**Core Logic:**
- `gpustack/server/server.py`: Server orchestration
- `gpustack/worker/worker.py`: Worker orchestration
- `gpustack/scheduler/scheduler.py`: Scheduling engine
- `gpustack/server/controllers.py`: Event-driven controllers

**API Layer:**
- `gpustack/routes/routes.py`: Router aggregation
- `gpustack/api/middlewares.py`: Request/response middleware
- `gpustack/api/auth.py`: Authentication logic

**Data Models:**
- `gpustack/schemas/models.py`: Model, ModelInstance schemas
- `gpustack/schemas/workers.py`: Worker, GPU device schemas
- `gpustack/schemas/common.py`: Shared base classes

**Testing:**
- `tests/conftest.py`: Pytest fixtures and configuration
- `tests/fixtures/`: Test data fixtures

## Naming Conventions

**Files:**
- Python modules: `snake_case.py`
- Test files: `test_*.py` or `*_test.py` (uses `test_` prefix)
- Generated files: `generated_*.py` (client files)

**Directories:**
- Package directories: `snake_case`
- Test directories mirror source structure

**Classes:**
- Controllers: `*Controller` (e.g., `ModelController`, `WorkerController`)
- Services: `*Service` (e.g., `ModelService`, `WorkerService`)
- Schemas: PascalCase matching entity (e.g., `Model`, `Worker`, `ModelInstance`)
- Backends: `*Backend` or backend-specific (e.g., `VLLMBackend`, `SGLangBackend`)
- Selectors: `*ResourceFitSelector` (e.g., `VLLMResourceFitSelector`)
- Filters: `*Filter` (e.g., `StatusFilter`, `GPUMatchingFilter`)

**Functions:**
- Routes: HTTP method + resource (e.g., `get_models`, `create_worker`)
- Utils: `snake_case` descriptive verbs
- Private: `_leading_underscore`

**Variables:**
- Constants: `UPPER_CASE` (in `gpustack/envs/`)
- Config: `lowercase` matching CLI args
- Enums: `PascalCase` with `Enum` suffix

## Where to Add New Code

**New API Endpoint:**
- Route handler: `gpustack/routes/{resource}s.py`
- Add to router: `gpustack/routes/routes.py`
- Schema: `gpustack/schemas/{resource}s.py`
- Tests: `tests/routers/test_{resource}s.py`

**New Inference Backend:**
- Backend implementation: `gpustack/worker/backends/{backend_name}.py`
- Candidate selector: `gpustack/policies/candidate_selectors/{backend_name}_resource_fit_selector.py`
- Schema updates: `gpustack/schemas/inference_backend.py`
- Tests: `tests/policies/candidate_selectors/{backend_name}/`

**New Scheduling Policy:**
- Worker filter: `gpustack/policies/worker_filters/{filter_name}_filter.py`
- Scorer: `gpustack/policies/scorers/{scorer_name}_scorer.py`
- Add to scheduler: `gpustack/scheduler/scheduler.py`
- Tests: `tests/policies/worker_filters/` or `tests/policies/scorers/`

**New Model Schema:**
- Schema definition: `gpustack/schemas/{resource}s.py`
- Use SQLModel for database entities
- Add ListParams subclass if paginated
- Tests: Co-located or in `tests/server/`

**Utilities:**
- Shared helpers: `gpustack/utils/{category}.py`
- Category examples: `gpu.py`, `network.py`, `hub.py`, `command.py`
- Tests: `tests/utils/test_{category}.py`

## Special Directories

**`gpustack/migrations/versions/`:**
- Purpose: Alembic database migrations
- Generated: Yes (via `make generate-migration` or `alembic revision`)
- Committed: Yes

**`gpustack/codegen/templates/`:**
- Purpose: Templates for code generation
- Generated: No
- Committed: Yes

**`gpustack/client/`:**
- Purpose: Auto-generated API clients
- Generated: Yes (from OpenAPI spec)
- Committed: Yes (checked into repo)
- Note: Regenerated when API changes

**`gpustack/third_party/`:**
- Purpose: Bundled third-party tools
- Generated: Yes (downloaded during build)
- Committed: Partial (some binaries included)

**`gpustack/assets/`:**
- Purpose: Static configuration templates
- Generated: No
- Committed: Yes
- Contains: Metrics configs, chat templates, profile configs

**`docs/`:**
- Purpose: MkDocs documentation
- Generated: No (except performance lab)
- Committed: Yes
- Build command: `mkdocs serve` or `mkdocs build`

---

*Structure analysis: 2026-01-31*
