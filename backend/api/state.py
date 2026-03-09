from backend.orchestrator import CoreOrchestrator
from backend.config import settings
from backend.runtime import DbRunStore
from backend.runtime.service import RuntimeService
from backend.runtime.heartbeat import HeartbeatService
from backend.runtime.conversation_maintenance import ConversationMaintenanceService
from backend.runtime.scheduler import SchedulerService

orchestrator = CoreOrchestrator()

run_store = DbRunStore()

runtime_service = RuntimeService(
    orchestrator=orchestrator,
    orchestrator_factory=lambda: CoreOrchestrator(user_id=orchestrator.user_id),
    orchestration_max_workers=settings.runtime_orchestration_max_workers,
    run_store=run_store,
)

heartbeat_service = HeartbeatService()
conversation_maintenance_service = ConversationMaintenanceService(orchestrator=orchestrator)
scheduler_service = SchedulerService(runtime_service=runtime_service)
