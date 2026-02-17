from __future__ import annotations

import asyncio

import pytest

from anteroom.services.approvals import ApprovalManager


@pytest.mark.asyncio
async def test_cleanup_task_expires_pending(monkeypatch) -> None:
    mgr = ApprovalManager()
    mgr.start_cleanup_task(expire_after_s=0.0, interval_s=0.01)
    try:
        approval_id = await mgr.request("Danger", owner="local")

        # It should be auto-expired quickly; wait should return False.
        res = await mgr.wait(approval_id, timeout_s=1.0)
        assert res is False
        assert await mgr.get(approval_id) is None
    finally:
        await mgr.stop_cleanup_task()


@pytest.mark.asyncio
async def test_resolve_wrong_owner_denied() -> None:
    mgr = ApprovalManager()
    approval_id = await mgr.request("Danger", owner="alice")

    ok = await mgr.resolve(approval_id, True, owner="bob")
    assert ok is False

    # Correct owner can resolve
    ok2 = await mgr.resolve(approval_id, True, owner="alice")
    assert ok2 is True
