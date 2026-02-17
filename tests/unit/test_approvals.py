from __future__ import annotations

import asyncio

import pytest

from anteroom.services.approvals import ApprovalManager


@pytest.mark.asyncio
async def test_request_wait_resolve_approved() -> None:
    mgr = ApprovalManager()
    approval_id = await mgr.request("Dangerous: rm -rf /", owner="local")

    async def _resolver() -> None:
        await asyncio.sleep(0)
        ok = await mgr.resolve(approval_id, True, owner="local")
        assert ok is True

    task = asyncio.create_task(_resolver())
    approved = await mgr.wait(approval_id, timeout_s=1.0)
    await task

    assert approved is True


@pytest.mark.asyncio
async def test_wait_times_out_and_cleans_up() -> None:
    mgr = ApprovalManager()
    approval_id = await mgr.request("Danger", owner="local")

    approved = await mgr.wait(approval_id, timeout_s=0.01)
    assert approved is False

    # Should be cleaned up after wait (even on timeout)
    assert await mgr.get(approval_id) is None


@pytest.mark.asyncio
async def test_resolve_unknown_id_returns_false() -> None:
    mgr = ApprovalManager()
    assert await mgr.resolve("nope", True, owner="local") is False


@pytest.mark.asyncio
async def test_resolve_after_timeout_returns_false() -> None:
    mgr = ApprovalManager()
    approval_id = await mgr.request("Danger", owner="local")
    _ = await mgr.wait(approval_id, timeout_s=0.01)
    assert await mgr.resolve(approval_id, True, owner="local") is False
