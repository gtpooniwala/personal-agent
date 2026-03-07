from backend.orchestrator import CoreOrchestrator
from backend.runtime import InMemoryRunStore
from backend.runtime.service import RuntimeService

orchestrator = CoreOrchestrator()

# TODO(#15): Replace temporary in-memory run store with durable runs/run_events persistence.
run_store = InMemoryRunStore()

# TODO(postgres-migration): Implement Postgres-backed RunStore using DATABASE_URL and migration tables.
runtime_service = RuntimeService(orchestrator=orchestrator, run_store=run_store)
