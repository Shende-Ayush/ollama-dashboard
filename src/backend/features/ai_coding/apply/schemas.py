"""Diff application schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class DiffPreviewRequest(BaseModel):
    workspace_id: str
    file_path: str
    new_content: str


class DiffPreviewResponse(BaseModel):
    file_path: str
    diff_text: str
    insertions: int
    deletions: int
    is_new_file: bool = False


class ApplyDiffRequest(BaseModel):
    workspace_id: str
    file_path: str
    new_content: str


class ApplyFromResponseRequest(BaseModel):
    workspace_id: str
    response_text: str = Field(..., min_length=1)
    target_file: Optional[str] = None
    language: str = Field(default="python")


class ApplyResult(BaseModel):
    status: str
    file_path: str
    insertions: int
    deletions: int
    diff_text: str
