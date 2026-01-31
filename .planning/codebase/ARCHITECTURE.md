# Architecture

**Analysis Date:** 2026-01-31

## Pattern Overview

**Overall:** Distributed GPU Cluster Manager with Server-Worker Architecture

GPUStack follows a **hybrid monolithic-microservices architecture** where:
- A central **Server** manages state and orchestrates GPU resources
- **Worker** nodes execute AI model inference workloads
- **Controllers** manage resource lifecycle using event-driven patterns
- **Schedulers** implement policy-based resource allocation

**Key Characteristics:**
- **Event-Driven Controllers**: Uses pub/sub event bus for resource state changes
- **Policy-Based Scheduling**: Pluggable scheduler with filters, scorers, and selectors
- **Multi-Backend Inference**: Supports vLLM, SGLang, TensorRT-LLM, MindIE, and custom backends
- **Multi-Cluster Support**: Can manage on-premises, cloud, and Kubernetes clusters
- **Async-First**: Built on asyncio with SQLModel for async database operations

## Layers

**API Layer:**
- Purpose: HTTP API surface for clients and OpenAI-compatible endpoints
- Location: `gpustack/routes/`, `gpustack/api/`
- Contains: FastAPI routers, middleware, authentication, exception handlers
- Depends on: Service layer, schemas
- Used by: External clients (CLI, UI, workers)

**Service Layer:**
- Purpose: Business logic and data access coordination
- Location: `gpustack/server/services.py`
- Contains: Service classes for CRUD operations on models, workers, instances
- Depends on: Database layer, schemas
- Used by: Controllers, routes

**Controller Layer:**
- Purpose: Event-driven resource lifecycle management
- Location: `gpustack/server/controllers.py`
- Contains: ModelController, ModelInstanceController, WorkerController, ClusterController, etc.
- Depends on: Event bus, services, schemas
- Used by: Server initialization

**Scheduler Layer:**
- Purpose: GPU resource allocation and model placement
- Location: `gpustack/scheduler/`, `gpustack/policies/`
- Contains: Scheduler, candidate selectors, worker filters, placement scorers
- Depends on: Worker status, model resource claims, policies
- Used by: Server

**Worker Layer:**
- Purpose: Node-level GPU management and inference execution
- Location: `gpustack/worker/`
- Contains: Worker class, backend managers, collectors, serve managers
- Depends on: Server API, inference backends
- Used by: GPU worker nodes

**Schema Layer:**
- Purpose: Data models and validation
- Location: `gpustack/schemas/`
- Contains: SQLModel-based entities (Model, Worker, ModelInstance, etc.)
- Depends on: SQLModel, Pydantic
- Used by: All other layers

**Backend Layer:**
- Purpose: Inference engine abstraction
- Location: `gpustack/worker/backends/`
- Contains: vLLM, SGLang, MindIE, VoxBox, Custom backend implementations
- Depends on: External inference engines
- Used by: ServeManager

**Config Layer:**
- Purpose: Configuration management
- Location: `gpustack/config/`
- Contains: Config class with Pydantic Settings, registration tokens
- Depends on: Environment variables, files
- Used by: All layers

## Data Flow

**Model Deployment Flow:**

1. **API Request**: Client POSTs to `/v2/models` → `gpustack/routes/models.py`
2. **Validation**: Pydantic schemas validate input (`gpustack/schemas/models.py`)
3. **Storage**: Service layer saves to database via SQLModel
4. **Event**: Event bus publishes `Model` created event
5. **Schedule**: Scheduler (`gpustack/scheduler/scheduler.py`) picks up unscheduled instances
6. **Filter Chain**: Worker filters (status, GPU match, cluster, labels) narrow candidates
7. **Candidate Selection**: Backend-specific selector calculates resource fits
8. **Score**: Placement scorer ranks candidates by policy (spread/binpack)
9. **Assign**: Scheduler assigns model instance to worker
10. **Deploy**: Worker receives assignment via heartbeat/websocket
11. **Serve**: Worker backend (`gpustack/worker/backends/*.py`) starts inference process
12. **Monitor**: Runtime metrics collected and reported back

**Worker Registration Flow:**

1. **Start**: Worker process starts via `gpustack/cmd/start.py`
2. **Discover**: Worker auto-detects GPUs using detectors (`gpustack/detectors/`)
3. **Register**: Worker POSTs to `/v2/workers` with token authentication
4. **Heartbeat**: Periodic heartbeats update worker status and GPU metrics
5. **Sync**: WorkerSyncer reconciles expected vs. actual state

## Key Abstractions

**Controller Pattern:**
- Purpose: Event-driven state machine for resources
- Examples: `gpustack/server/controllers.py` (ModelController, WorkerController)
- Pattern: Watches event bus, reacts to CREATE/UPDATE/DELETE events

**Policy-Based Scheduling:**
- Purpose: Flexible GPU resource allocation
- Examples: `gpustack/policies/candidate_selectors/`, `gpustack/policies/worker_filters/`
- Pattern: Chain of responsibility - filters reduce candidates, selectors score

**Backend Abstraction:**
- Purpose: Pluggable inference engines
- Examples: `gpustack/worker/backends/base.py`, `vllm.py`, `sglang.py`
- Pattern: Template method - base class defines lifecycle, subclasses implement specifics

**Schema-First Design:**
- Purpose: Single source of truth for data models
- Examples: `gpustack/schemas/models.py`, `gpustack/schemas/workers.py`
- Pattern: SQLModel = SQLAlchemy + Pydantic, supports both ORM and validation

**Bus/Event System:**
- Purpose: Decoupled communication between components
- Examples: `gpustack/server/bus.py`
- Pattern: Pub/sub with async event handlers

## Entry Points

**CLI Entry:**
- Location: `gpustack/main.py`
- Triggers: `python -m gpustack` or `gpustack` command
- Responsibilities: Argument parsing, subcommand dispatch

**Server Start:**
- Location: `gpustack/cmd/start.py`
- Triggers: `gpustack start` with server configuration
- Responsibilities: Initialize database, start scheduler, start API server, spawn worker (if embedded)

**Worker Start:**
- Location: `gpustack/worker/worker.py`
- Triggers: `gpustack start` with worker-only mode, or embedded worker
- Responsibilities: Register with server, collect metrics, manage inference processes

**API Server:**
- Location: `gpustack/server/app.py` → `create_app()`
- Triggers: Server.start() initializes FastAPI app
- Responsibilities: Route registration, middleware stack, lifecycle management

**Migration:**
- Location: `gpustack/cmd/db_migration.py`
- Triggers: `gpustack migrate` or server start with migrations
- Responsibilities: Alembic database migrations

## Error Handling

**Strategy:** Layer-specific with centralized exception handlers

**Patterns:**
- **API Layer**: `gpustack/api/exceptions.py` defines error responses, handlers registered in app
- **Service Layer**: Raises domain-specific exceptions, caught by controllers/routes
- **Controller Layer**: Retries with tenacity for transient failures, event error handling
- **Worker Layer**: Process supervision with automatic restarts, error reporting to server

## Cross-Cutting Concerns

**Logging:**
- Location: `gpustack/logging.py`
- Pattern: Structured JSON logging with python-json-logger, per-module loggers

**Authentication:**
- Location: `gpustack/api/auth.py`, `gpustack/security.py`
- Pattern: JWT tokens for users, API keys for external access, worker tokens for registration

**Database Access:**
- Location: `gpustack/server/db.py`, `gpustack/server/deps.py`
- Pattern: Async SQLModel with dependency-injected sessions

**Metrics:**
- Location: `gpustack/server/metrics_collector.py`, `gpustack/exporter/`
- Pattern: Prometheus-compatible metrics with custom collectors

**Configuration:**
- Location: `gpustack/config/config.py`
- Pattern: Pydantic Settings with environment variable and file support

---

*Architecture analysis: 2026-01-31*
