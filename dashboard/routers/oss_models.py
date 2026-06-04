"""Pydantic v2 request/response models for OSS dashboard endpoints."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class FixRequestBody(BaseModel):
    apply: Annotated[
        bool,
        Field(description="If true, apply the fix; if false, return preview only."),
    ]


class AcceptRequestBody(BaseModel):
    finding_hash: Annotated[
        str,
        Field(min_length=1, description="SHA-256 hash of the finding to accept."),
    ]
    reason: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Justification for accepting the risk.",
        ),
    ]


class ApplyAllSafeBody(BaseModel):
    check_ids: Annotated[
        list[str],
        Field(
            min_length=1,
            description=("List of check_ids to apply. Must all have auto_apply_safe=True."),
        ),
    ]
