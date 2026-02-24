"""Plan mode endpoints: read, approve, reject plans."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..cli.plan import delete_plan, get_plan_file_path, read_plan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["plan"])


def _validate_conversation_id(conversation_id: str) -> None:
    """Reject obviously invalid conversation IDs."""
    if not conversation_id or len(conversation_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    import re

    if not re.match(r"^[A-Za-z0-9_\-]+$", conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")


class PlanRejectRequest(BaseModel):
    reason: str = Field(default="", max_length=4096)


@router.get("/conversations/{conversation_id}/plan")
async def get_plan(conversation_id: str, request: Request) -> dict:
    _validate_conversation_id(conversation_id)
    data_dir = request.app.state.config.app.data_dir
    try:
        plan_path = get_plan_file_path(data_dir, conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    content = read_plan(plan_path)
    if content is None:
        return {"exists": False, "content": None}
    return {"exists": True, "content": content}


@router.post("/conversations/{conversation_id}/plan/approve")
async def approve_plan(conversation_id: str, request: Request) -> dict:
    ct = request.headers.get("content-type", "")
    if ct and not ct.startswith("application/json"):
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")

    _validate_conversation_id(conversation_id)
    data_dir = request.app.state.config.app.data_dir
    try:
        plan_path = get_plan_file_path(data_dir, conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    content = read_plan(plan_path)
    if content is None:
        raise HTTPException(status_code=404, detail="No plan found for this conversation")
    delete_plan(plan_path)
    logger.info("Plan approved for conversation %s", conversation_id)
    return {"status": "approved", "content": content}


@router.post("/conversations/{conversation_id}/plan/reject")
async def reject_plan(conversation_id: str, request: Request) -> dict:
    ct = request.headers.get("content-type", "")
    if ct and not ct.startswith("application/json"):
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")

    _validate_conversation_id(conversation_id)
    data_dir = request.app.state.config.app.data_dir
    try:
        plan_path = get_plan_file_path(data_dir, conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    content = read_plan(plan_path)
    if content is None:
        raise HTTPException(status_code=404, detail="No plan found for this conversation")
    delete_plan(plan_path)
    logger.info("Plan rejected for conversation %s", conversation_id)
    return {"status": "rejected"}
