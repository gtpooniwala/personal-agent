from backend.orchestrator import CoreOrchestrator
from backend.runtime import DbRunStore
from backend.runtime.service import RuntimeService

orchestrator = CoreOrchestrator()

run_store = DbRunStore()

runtime_service = RuntimeService(orchestrator=orchestrator, run_store=run_store)
