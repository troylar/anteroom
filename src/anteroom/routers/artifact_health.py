"""Artifact health check API endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..services import artifact_health

router = APIRouter(tags=["artifact-health"])


@router.get("/artifacts/check")
async def check_artifacts(request: Request) -> dict[str, Any]:
    """Run artifact health check and return structured report."""
    db = request.app.state.db
    report = artifact_health.run_health_check(db)
    result = report.to_dict()
    for issue in result.get("issues", []):
        details = issue.get("details", {})
        details.pop("source_path", None)
    return result
