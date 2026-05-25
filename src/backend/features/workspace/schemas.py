"""
Workspace & File System — Pydantic schemas.

Request/response models for workspace management, file operations, and git integration.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------
class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    git_url: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    root_path: str
    git_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# File System
# ---------------------------------------------------------------------------
class FileNode(BaseModel):
    name: str
    path: str
    is_directory: bool
    size_bytes: int = 0
    language: Optional[str] = None
    children: Optional[list[FileNode]] = None


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: Optional[str] = None
    size_bytes: int = 0


class WriteFileRequest(BaseModel):
    content: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    include_content: bool = False


class SearchResult(BaseModel):
    path: str
    line_number: Optional[int] = None
    match_text: str
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Git Integration
# ---------------------------------------------------------------------------
class GitStatusResponse(BaseModel):
    branch: str = ""
    clean: bool = True
    modified: list[str] = Field(default_factory=list)
    untracked: list[str] = Field(default_factory=list)
    staged: list[str] = Field(default_factory=list)


class GitCommitRequest(BaseModel):
    message: str = Field(..., min_length=1)
    files: Optional[list[str]] = None


class GitDiffResponse(BaseModel):
    diff_text: str = ""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
