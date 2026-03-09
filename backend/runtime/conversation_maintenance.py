from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from backend.config import agent_config
from backend.observability import increment_counter, observe_operation

logger = logging.getLogger(__name__)

_NAMING_CFG = agent_config.get("conversation_naming", {})
_NAMING_DELAY_MINUTES: int = _NAMING_CFG.get("delay_minutes", 5)
_NAMING_RETRY_DELAY_MINUTES: int = _NAMING_CFG.get("retry_delay_minutes", 2)
_NAMING_MAX_RETRIES: int = _NAMING_CFG.get("max_retries", 3)

_TITLE_SWEEP_LIMIT = 100
_EMPTY_SWEEP_LIMIT = 100
_EMPTY_CONVERSATION_MAX_AGE_DAYS = 1
_TITLE_LEASE_TTL_SECONDS = max(
    300,
    (_NAMING_RETRY_DELAY_MINUTES * 60 * max(_NAMING_MAX_RETRIES, 1)) + 300,
)
_DELETE_LEASE_TTL_SECONDS = 300


class ConversationMaintenanceService:
    """Background sweep that keeps conversation metadata tidy without read-side effects."""

    def __init__(self, orchestrator, poll_interval_seconds: int = 60, db_ops=None):
        self._orchestrator = orchestrator
        self._db_ops = db_ops
        self._poll_interval = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._background_tasks: set[asyncio.Task] = set()

    def _get_db_ops(self):
        if self._db_ops is not None:
            return self._db_ops
        from backend.database.operations import db_ops

        return db_ops

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        logger.info(
            "ConversationMaintenanceService starting",
            extra={"event": "conversation_maintenance.start"},
        )
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        logger.info(
            "ConversationMaintenanceService stopping",
            extra={"event": "conversation_maintenance.stop"},
        )
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        pending = list(self._background_tasks)
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _track_background_task(self, task: asyncio.Task) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _query_candidates_sync(self) -> tuple[list[dict], list[dict]]:
        db = self._get_db_ops()
        title_candidates = db.find_conversations_needing_title(
            delay_minutes=_NAMING_DELAY_MINUTES,
            limit=_TITLE_SWEEP_LIMIT,
        )
        empty_candidates = db.find_stale_empty_conversations(
            older_than_days=_EMPTY_CONVERSATION_MAX_AGE_DAYS,
            limit=_EMPTY_SWEEP_LIMIT,
        )
        return title_candidates, empty_candidates

    async def _acquire_lease(
        self,
        *,
        lease_key: str,
        owner_id: str,
        ttl_seconds: int,
    ):
        db = self._get_db_ops()
        return await asyncio.to_thread(
            db.acquire_lease,
            lease_key,
            owner_id,
            ttl_seconds,
        )

    async def _release_lease(self, *, lease_key: str, owner_id: str) -> None:
        db = self._get_db_ops()
        await asyncio.to_thread(db.release_lease, lease_key, owner_id)

    async def _loop(self) -> None:
        await self._sweep()
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._sweep()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "ConversationMaintenanceService sweep error",
                    extra={"event": "conversation_maintenance.sweep_error"},
                )

    async def _sweep(self) -> None:
        try:
            title_candidates, empty_candidates = await asyncio.to_thread(
                self._query_candidates_sync
            )
        except Exception:
            logger.exception(
                "ConversationMaintenanceService failed to query candidates",
                extra={"event": "conversation_maintenance.query_error"},
            )
            return

        for candidate in title_candidates:
            await self._schedule_title_generation(str(candidate["id"]))

        for candidate in empty_candidates:
            await self._schedule_empty_conversation_deletion(str(candidate["id"]))

    async def _schedule_title_generation(self, conversation_id: str) -> None:
        lease_key = f"conversation-maintenance:title:{conversation_id}"
        owner_id = f"title:{uuid.uuid4()}"
        lease = await self._acquire_lease(
            lease_key=lease_key,
            owner_id=owner_id,
            ttl_seconds=_TITLE_LEASE_TTL_SECONDS,
        )
        if lease is None:
            return

        increment_counter("maintenance.generate_title.scheduled_total")
        self._track_background_task(
            asyncio.create_task(
                self._generate_title_with_retry(
                    conversation_id=conversation_id,
                    lease_key=lease_key,
                    owner_id=owner_id,
                )
            )
        )

    async def _schedule_empty_conversation_deletion(self, conversation_id: str) -> None:
        lease_key = f"conversation-maintenance:delete:{conversation_id}"
        owner_id = f"delete:{uuid.uuid4()}"
        lease = await self._acquire_lease(
            lease_key=lease_key,
            owner_id=owner_id,
            ttl_seconds=_DELETE_LEASE_TTL_SECONDS,
        )
        if lease is None:
            return

        increment_counter("maintenance.delete_empty_conversation.scheduled_total")
        self._track_background_task(
            asyncio.create_task(
                self._delete_empty_conversation(
                    conversation_id=conversation_id,
                    lease_key=lease_key,
                    owner_id=owner_id,
                )
            )
        )

    async def _generate_title_with_retry(
        self,
        *,
        conversation_id: str,
        lease_key: str,
        owner_id: str,
    ) -> None:
        db = self._get_db_ops()
        try:
            with observe_operation(
                name="maintenance.generate_title",
                counter_prefix="maintenance.generate_title",
                as_type="chain",
                conversation_id=conversation_id,
                metadata={"component": "maintenance"},
            ):
                for attempt in range(1, _NAMING_MAX_RETRIES + 1):
                    try:
                        title = await self._orchestrator.generate_conversation_title(
                            conversation_id
                        )
                        if title:
                            return
                    except Exception:
                        logger.exception(
                            "Conversation title generation attempt failed",
                            extra={
                                "event": "conversation_maintenance.generate_title_error",
                                "conversation_id": conversation_id,
                                "attempt": attempt,
                            },
                        )
                        if attempt == _NAMING_MAX_RETRIES:
                            return

                    try:
                        still_untitled = await asyncio.to_thread(
                            db.is_conversation_untitled, conversation_id
                        )
                    except Exception:
                        logger.exception(
                            "Conversation title state check failed",
                            extra={
                                "event": "conversation_maintenance.generate_title_state_error",
                                "conversation_id": conversation_id,
                                "attempt": attempt,
                            },
                        )
                        return
                    if not still_untitled or attempt == _NAMING_MAX_RETRIES:
                        return

                    await asyncio.sleep(_NAMING_RETRY_DELAY_MINUTES * 60)
        finally:
            try:
                await self._release_lease(lease_key=lease_key, owner_id=owner_id)
            except Exception:
                logger.exception(
                    "Failed to release title maintenance lease",
                    extra={
                        "event": "conversation_maintenance.title_release_error",
                        "conversation_id": conversation_id,
                    },
                )

    async def _delete_empty_conversation(
        self,
        *,
        conversation_id: str,
        lease_key: str,
        owner_id: str,
    ) -> None:
        db = self._get_db_ops()
        try:
            with observe_operation(
                name="maintenance.delete_empty_conversation",
                counter_prefix="maintenance.delete_empty_conversation",
                as_type="span",
                conversation_id=conversation_id,
                metadata={"component": "maintenance"},
            ):
                messages = await asyncio.to_thread(
                    db.get_conversation_history, conversation_id
                )
                if messages:
                    logger.info(
                        "Skipping deletion for conversation that is no longer empty",
                        extra={
                            "event": "conversation_maintenance.delete_skip_nonempty",
                            "conversation_id": conversation_id,
                            "message_count": len(messages),
                        },
                    )
                    return
                await asyncio.to_thread(db.delete_conversation, conversation_id)
        except Exception:
            logger.exception(
                "Conversation cleanup failed",
                extra={
                    "event": "conversation_maintenance.delete_error",
                    "conversation_id": conversation_id,
                },
            )
        finally:
            try:
                await self._release_lease(lease_key=lease_key, owner_id=owner_id)
            except Exception:
                logger.exception(
                    "Failed to release delete maintenance lease",
                    extra={
                        "event": "conversation_maintenance.delete_release_error",
                        "conversation_id": conversation_id,
                    },
                )
