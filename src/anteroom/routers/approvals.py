from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter()


class ApprovalResponse(BaseModel):
    approval_id: str = Field(..., max_length=64)
    approved: bool


@router.post("/approvals/respond")
async def respond_approval(payload: ApprovalResponse, request: Request):
    mgr = getattr(request.app.state, "approval_manager", None)
    if mgr is None:
        return {"ok": False, "detail": "approval manager not configured"}

    resolved = await mgr.resolve(payload.approval_id, payload.approved, owner="local")
    return {"ok": True, "resolved": resolved}
