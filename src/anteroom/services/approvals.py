from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass


@dataclass
class PendingApproval:
    fut: asyncio.Future[bool]
    message: str
    created_at: float
    owner: str


MAX_MESSAGE_CHARS = 10_000


class ApprovalManager:
    """In-process approval manager.

    Note: this is safe in the default single-process server mode used by `anteroom`.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending: dict[str, PendingApproval] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    def start_cleanup_task(
        self, *, expire_after_s: float = 600.0, interval_s: float = 60.0
    ) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(
            self._cleanup_expired(expire_after_s=expire_after_s, interval_s=interval_s)
        )

    async def stop_cleanup_task(self) -> None:
        task = self._cleanup_task
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup_task = None

    async def request(self, message: str, *, owner: str) -> str:
        approval_id = secrets.token_urlsafe(16)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        msg = (message or "")[:MAX_MESSAGE_CHARS]
        async with self._lock:
            self._pending[approval_id] = PendingApproval(
                fut=fut, message=msg, created_at=time.time(), owner=owner
            )
        return approval_id

    async def wait(self, approval_id: str, timeout_s: float = 300.0) -> bool:
        async with self._lock:
            pending = self._pending.get(approval_id)
        if not pending:
            return False
        try:
            return await asyncio.wait_for(pending.fut, timeout=timeout_s)
        except asyncio.TimeoutError:
            return False
        finally:
            async with self._lock:
                self._pending.pop(approval_id, None)

    async def resolve(self, approval_id: str, approved: bool, *, owner: str) -> bool:
        async with self._lock:
            pending = self._pending.get(approval_id)
            if not pending:
                return False
            if pending.owner != owner:
                return False
            if pending.fut.done():
                return False
            pending.fut.set_result(bool(approved))
            return True

    async def _cleanup_expired(
        self, *, expire_after_s: float, interval_s: float
    ) -> None:
        while True:
            await asyncio.sleep(interval_s)
            now = time.time()
            async with self._lock:
                expired = [
                    aid
                    for aid, pending in self._pending.items()
                    if now - pending.created_at > expire_after_s
                ]
                for aid in expired:
                    pending = self._pending.pop(aid, None)
                    if pending and not pending.fut.done():
                        pending.fut.set_result(False)

    async def get(self, approval_id: str) -> PendingApproval | None:
        async with self._lock:
            return self._pending.get(approval_id)
