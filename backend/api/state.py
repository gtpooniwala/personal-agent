from backend.orchestrator import CoreOrchestrator
from backend.runtime import DbRunStore
from backend.runtime.service import RuntimeService
from backend.runtime.heartbeat import HeartbeatService
from backend.runtime.scheduler import SchedulerService

orchestrator = CoreOrchestrator()

run_store = DbRunStore()

runtime_service = RuntimeService(orchestrator=orchestrator, run_store=run_store)

heartbeat_service = HeartbeatService(run_store=run_store)
scheduler_service = SchedulerService(runtime_service=runtime_service)
