"""
Tests for Sprint 6: AI Chat + Diff Application.

Tests cover:
1. DiffGenerator — generate_diff, extract_code_from_response
2. EditorChatService — chat with mocked provider
3. DiffApplier — integration with workspace service
4. API endpoint tests — /api/ai-chat/* routes
"""
import os
import shutil
import tempfile
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.features.ai_coding.apply.diff_generator import (
    extract_code_from_response,
    generate_diff,
)
from backend.features.ai_coding.chat.schemas import ChatMessage, ChatRequest, ChatResponse
from backend.features.ai_coding.chat.service import EditorChatService
from backend.features.ai_coding.apply.diff_applier import DiffApplier
from backend.features.workspace.schemas import CreateWorkspaceRequest
from backend.features.workspace.service import WorkspaceService


# ===========================================================================
# Unit Tests: DiffGenerator
# ===========================================================================
class TestDiffGenerator:
    """Tests for diff generation utilities."""

    def test_generate_diff_with_additions(self):
        """Diff correctly shows added lines."""
        original = "line1\nline2\n"
        modified = "line1\nline2\nline3\nline4\n"
        diff = generate_diff(original, modified, "test.py")

        assert diff.file_path == "test.py"
        assert diff.insertions == 2
        assert diff.deletions == 0
        assert "+line3\n" in diff.diff_text
        assert "+line4\n" in diff.diff_text

    def test_generate_diff_with_deletions(self):
        """Diff correctly shows removed lines."""
        original = "line1\nline2\nline3\n"
        modified = "line1\n"
        diff = generate_diff(original, modified, "test.py")

        assert diff.insertions == 0
        assert diff.deletions == 2
        assert "-line2\n" in diff.diff_text
        assert "-line3\n" in diff.diff_text

    def test_generate_diff_identical_files(self):
        """Diff of identical content produces no diff."""
        content = "same content\nno changes\n"
        diff = generate_diff(content, content, "test.py")

        assert diff.diff_text == ""
        assert diff.insertions == 0
        assert diff.deletions == 0

    def test_generate_diff_mixed_changes(self):
        """Diff handles mixed additions and deletions."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nmodified_line2\nline3\nnew_line4\n"
        diff = generate_diff(original, modified, "app.py")

        assert diff.file_path == "app.py"
        assert diff.insertions >= 1
        assert diff.deletions >= 1
        assert "a/app.py" in diff.diff_text
        assert "b/app.py" in diff.diff_text

    def test_generate_diff_empty_original(self):
        """Diff from empty file (new file case)."""
        original = ""
        modified = "new content\nhere\n"
        diff = generate_diff(original, modified, "new_file.py")

        assert diff.insertions >= 1
        assert diff.deletions == 0
        assert diff.original_content == ""
        assert diff.new_content == modified

    def test_extract_code_single_block(self):
        """Extract a single code block from response."""
        response = "Here is the code:\n```python\ndef hello():\n    return 'world'\n```"
        blocks = extract_code_from_response(response)

        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"
        assert "def hello():" in blocks[0]["code"]
        assert "return 'world'" in blocks[0]["code"]

    def test_extract_code_multiple_blocks(self):
        """Extract multiple code blocks from response."""
        response = """Here are two files:

```python
def foo():
    pass
```

And another:

```javascript
function bar() {}
```
"""
        blocks = extract_code_from_response(response)

        assert len(blocks) == 2
        assert blocks[0]["language"] == "python"
        assert blocks[1]["language"] == "javascript"
        assert "def foo():" in blocks[0]["code"]
        assert "function bar()" in blocks[1]["code"]

    def test_extract_code_with_file_path_hints(self):
        """Extract code blocks with file path hints."""
        response = """File: src/main.py
```python
print('hello')
```
"""
        blocks = extract_code_from_response(response)

        assert len(blocks) == 1
        assert blocks[0]["file_path"] == "src/main.py"
        assert blocks[0]["code"] == "print('hello')"

    def test_extract_code_with_dashes_file_path(self):
        """Extract code blocks with --- file path --- pattern."""
        response = """--- utils/helper.py ---
```python
def helper():
    pass
```
"""
        blocks = extract_code_from_response(response)

        assert len(blocks) == 1
        assert blocks[0]["file_path"] == "utils/helper.py"

    def test_extract_code_no_code_blocks(self):
        """Extract returns empty list when no code blocks present."""
        response = "This is just plain text explaining something without any code."
        blocks = extract_code_from_response(response)

        assert len(blocks) == 0

    def test_extract_code_uses_default_language(self):
        """Code blocks without language marker use provided default."""
        response = "```\nsome code here\n```"
        blocks = extract_code_from_response(response, language="python")

        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"

    def test_extract_code_with_backtick_path(self):
        """Extract code blocks with backtick file path pattern."""
        response = """`src/config.ts`
```typescript
export const config = {};
```
"""
        blocks = extract_code_from_response(response)

        assert len(blocks) == 1
        assert blocks[0]["file_path"] == "src/config.ts"


# ===========================================================================
# Unit Tests: EditorChatService
# ===========================================================================
class TestEditorChatService:
    """Tests for the editor chat service with mocked provider."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """Chat returns a valid ChatResponse with mock provider."""
        service = EditorChatService()

        async def mock_chat_stream(*args, **kwargs):
            yield "Hello "
            yield "World!"

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_chat_stream())

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi there")],
        )

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            mock_session = AsyncMock()
            result = await service.chat(request, mock_session)

        assert isinstance(result, ChatResponse)
        assert result.response == "Hello World!"
        assert result.model_used == "llama3.2:3b"
        assert result.tokens_used > 0
        assert result.latency_ms >= 0
        assert result.has_code_blocks is False

    @pytest.mark.asyncio
    async def test_chat_includes_file_context(self):
        """Chat includes file context in messages sent to provider."""
        service = EditorChatService()
        captured_messages = []

        async def mock_chat_stream(model, messages, options=None):
            captured_messages.extend(messages)
            yield "response"

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(side_effect=mock_chat_stream)

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Explain this code")],
            file_context=[
                {"path": "main.py", "content": "print('hello')", "language": "python"}
            ],
        )

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            mock_session = AsyncMock()
            await service.chat(request, mock_session)

        # Should have system prompt, file context, and user message
        assert len(captured_messages) == 3
        assert captured_messages[0]["role"] == "system"
        assert captured_messages[1]["role"] == "system"
        assert "main.py" in captured_messages[1]["content"]
        assert "print('hello')" in captured_messages[1]["content"]
        assert captured_messages[2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_handles_provider_error(self):
        """Chat handles provider errors gracefully."""
        service = EditorChatService()

        async def mock_chat_stream_error(*args, **kwargs):
            raise ConnectionError("Provider unavailable")
            yield  # noqa: unreachable - makes it an async generator

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_chat_stream_error())

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
        )

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            mock_session = AsyncMock()
            result = await service.chat(request, mock_session)

        assert "Error:" in result.response
        assert result.model_used == "llama3.2:3b"

    @pytest.mark.asyncio
    async def test_chat_detects_code_blocks(self):
        """Chat correctly detects code blocks in response."""
        service = EditorChatService()

        async def mock_chat_stream(*args, **kwargs):
            yield "Here is the code:\n```python\nprint('hi')\n```"

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_chat_stream())

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Write a hello world")],
        )

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            mock_session = AsyncMock()
            result = await service.chat(request, mock_session)

        assert result.has_code_blocks is True

    @pytest.mark.asyncio
    async def test_chat_uses_specified_model(self):
        """Chat uses the model specified in request."""
        service = EditorChatService()
        used_model = []

        async def mock_chat_stream(model, messages, options=None):
            used_model.append(model)
            yield "ok"

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(side_effect=mock_chat_stream)

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model="mistral:7b",
        )

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            mock_session = AsyncMock()
            result = await service.chat(request, mock_session)

        assert result.model_used == "mistral:7b"
        assert used_model[0] == "mistral:7b"


# ===========================================================================
# Integration Tests: DiffApplier (with workspace)
# ===========================================================================
@pytest.fixture
def tmp_workspace_dir():
    """Create a temporary workspace directory."""
    path = tempfile.mkdtemp(prefix="test_ai_chat_ws_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest_asyncio.fixture
async def workspace_with_file(db_session, tmp_workspace_dir):
    """Create a workspace with an existing file for diff tests."""
    svc = WorkspaceService()
    svc.WORKSPACE_BASE = tmp_workspace_dir

    ws = await svc.create_workspace(
        CreateWorkspaceRequest(name="DiffTestWS"), db_session
    )
    # Write a test file
    await svc.write_file(ws.id, "main.py", "def hello():\n    return 'world'\n", db_session)
    return ws


class TestDiffApplier:
    """Integration tests for DiffApplier with workspace."""

    @pytest.mark.asyncio
    async def test_preview_changes_existing_file(self, workspace_with_file, db_session):
        """Preview changes on an existing file shows diff."""
        ws = workspace_with_file
        applier = DiffApplier()

        diff = await applier.preview_changes(
            workspace_id=ws.id,
            file_path="main.py",
            new_content="def hello():\n    return 'universe'\n",
            session=db_session,
        )

        assert diff.file_path == "main.py"
        assert diff.insertions >= 1
        assert diff.deletions >= 1
        assert "universe" in diff.diff_text
        assert "world" in diff.diff_text

    @pytest.mark.asyncio
    async def test_preview_changes_new_file(self, workspace_with_file, db_session):
        """Preview changes for a new file (original is empty)."""
        ws = workspace_with_file
        applier = DiffApplier()

        diff = await applier.preview_changes(
            workspace_id=ws.id,
            file_path="new_file.py",
            new_content="print('new')\n",
            session=db_session,
        )

        assert diff.file_path == "new_file.py"
        assert diff.original_content == ""
        assert diff.insertions >= 1
        assert diff.deletions == 0

    @pytest.mark.asyncio
    async def test_apply_change_writes_file(self, workspace_with_file, db_session):
        """Apply a change writes the new content to the file."""
        ws = workspace_with_file
        applier = DiffApplier()

        result = await applier.apply_change(
            workspace_id=ws.id,
            file_path="main.py",
            new_content="def hello():\n    return 'updated'\n",
            session=db_session,
        )

        assert result["status"] == "applied"
        assert result["file_path"] == "main.py"
        assert result["insertions"] >= 1

        # Verify the file was actually written
        svc = WorkspaceService()
        svc.WORKSPACE_BASE = os.path.dirname(ws.root_path)
        file_content = await svc.read_file(ws.id, "main.py", db_session)
        assert "updated" in file_content.content

    @pytest.mark.asyncio
    async def test_apply_from_response_extracts_and_applies(self, workspace_with_file, db_session):
        """apply_from_response extracts code and applies to target file."""
        ws = workspace_with_file
        applier = DiffApplier()

        ai_response = """Here's the updated code:
```python
def hello():
    return 'from_ai'
```
"""
        results = await applier.apply_from_response(
            workspace_id=ws.id,
            response_text=ai_response,
            target_file="main.py",
            language="python",
            session=db_session,
        )

        assert len(results) == 1
        assert results[0]["status"] == "applied"
        assert results[0]["file_path"] == "main.py"

        # Verify file content
        svc = WorkspaceService()
        svc.WORKSPACE_BASE = os.path.dirname(ws.root_path)
        file_content = await svc.read_file(ws.id, "main.py", db_session)
        assert "from_ai" in file_content.content

    @pytest.mark.asyncio
    async def test_apply_from_response_no_target_no_path(self, workspace_with_file, db_session):
        """apply_from_response with no target file and no path in response applies nothing."""
        ws = workspace_with_file
        applier = DiffApplier()

        ai_response = """Here's some code:
```python
x = 1
```
"""
        results = await applier.apply_from_response(
            workspace_id=ws.id,
            response_text=ai_response,
            target_file=None,
            language="python",
            session=db_session,
        )

        assert len(results) == 0


# ===========================================================================
# API Endpoint Tests
# ===========================================================================
@pytest_asyncio.fixture
async def ai_chat_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with AI chat router included."""
    from backend.main import app
    from backend.api.routes.ai_chat import router as ai_chat_router
    from backend.common.db.session import get_db_session
    from tests.conftest import override_get_db_session

    # Include the AI chat router for tests
    app.include_router(ai_chat_router, prefix="/api")

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestAIChatAPI:
    """API endpoint tests for AI Chat."""

    @pytest.mark.asyncio
    async def test_chat_message_endpoint(self, ai_chat_client):
        """POST /api/ai-chat/message returns AI response."""
        async def mock_chat_stream(*args, **kwargs):
            yield "Hello from AI!"

        mock_model = MagicMock()
        mock_model.name = "llama3.2:3b"

        mock_provider = MagicMock()
        mock_provider.list_models = AsyncMock(return_value=[mock_model])
        mock_provider.chat_stream = MagicMock(return_value=mock_chat_stream())

        with patch(
            "backend.features.ai_coding.chat.service.model_registry"
        ) as mock_registry:
            mock_registry.get.return_value = mock_provider
            response = await ai_chat_client.post("/api/ai-chat/message", json={
                "messages": [{"role": "user", "content": "Hello"}],
            })

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello from AI!"
        assert data["model_used"] == "llama3.2:3b"
        assert "tokens_used" in data
        assert "latency_ms" in data
        assert data["has_code_blocks"] is False

    @pytest.mark.asyncio
    async def test_chat_message_validation(self, ai_chat_client):
        """POST /api/ai-chat/message validates required fields."""
        # Empty messages array
        response = await ai_chat_client.post("/api/ai-chat/message", json={
            "messages": [],
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_diff_preview_endpoint(self, ai_chat_client, db_session):
        """POST /api/ai-chat/diff/preview returns diff."""
        # Create a workspace for the test
        svc = WorkspaceService()
        tmp_dir = tempfile.mkdtemp(prefix="test_api_diff_")
        svc.WORKSPACE_BASE = tmp_dir

        try:
            ws = await svc.create_workspace(
                CreateWorkspaceRequest(name="APITestWS"), db_session
            )
            await svc.write_file(ws.id, "test.py", "old content\n", db_session)

            with patch(
                "backend.features.ai_coding.apply.diff_applier.workspace_service",
                svc,
            ):
                response = await ai_chat_client.post("/api/ai-chat/diff/preview", json={
                    "workspace_id": ws.id,
                    "file_path": "test.py",
                    "new_content": "new content\n",
                })

            assert response.status_code == 200
            data = response.json()
            assert data["file_path"] == "test.py"
            assert data["insertions"] >= 1
            assert data["deletions"] >= 1
            assert "diff_text" in data
            assert data["is_new_file"] is False
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_diff_apply_endpoint(self, ai_chat_client, db_session):
        """POST /api/ai-chat/diff/apply applies changes."""
        svc = WorkspaceService()
        tmp_dir = tempfile.mkdtemp(prefix="test_api_apply_")
        svc.WORKSPACE_BASE = tmp_dir

        try:
            ws = await svc.create_workspace(
                CreateWorkspaceRequest(name="ApplyTestWS"), db_session
            )
            await svc.write_file(ws.id, "app.py", "x = 1\n", db_session)

            with patch(
                "backend.features.ai_coding.apply.diff_applier.workspace_service",
                svc,
            ):
                response = await ai_chat_client.post("/api/ai-chat/diff/apply", json={
                    "workspace_id": ws.id,
                    "file_path": "app.py",
                    "new_content": "x = 2\ny = 3\n",
                })

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "applied"
            assert data["file_path"] == "app.py"
            assert data["insertions"] >= 1

            # Verify file was updated
            file_content = await svc.read_file(ws.id, "app.py", db_session)
            assert "x = 2" in file_content.content
            assert "y = 3" in file_content.content
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_diff_apply_from_response_endpoint(self, ai_chat_client, db_session):
        """POST /api/ai-chat/diff/apply-from-response extracts and applies."""
        svc = WorkspaceService()
        tmp_dir = tempfile.mkdtemp(prefix="test_api_from_resp_")
        svc.WORKSPACE_BASE = tmp_dir

        try:
            ws = await svc.create_workspace(
                CreateWorkspaceRequest(name="FromRespWS"), db_session
            )
            await svc.write_file(ws.id, "main.py", "old code\n", db_session)

            ai_response = "Here is the fix:\n```python\nnew code from AI\n```"

            with patch(
                "backend.features.ai_coding.apply.diff_applier.workspace_service",
                svc,
            ):
                response = await ai_chat_client.post("/api/ai-chat/diff/apply-from-response", json={
                    "workspace_id": ws.id,
                    "response_text": ai_response,
                    "target_file": "main.py",
                    "language": "python",
                })

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["applied"]) == 1
            assert data["applied"][0]["status"] == "applied"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_diff_preview_invalid_workspace(self, ai_chat_client):
        """POST /api/ai-chat/diff/preview with invalid workspace treats as new file."""
        # The workspace_service raises ValueError for unknown workspace_id
        # but preview_changes catches it and treats as new file (original="")
        fake_id = str(uuid.uuid4())
        response = await ai_chat_client.post("/api/ai-chat/diff/preview", json={
            "workspace_id": fake_id,
            "file_path": "test.py",
            "new_content": "content",
        })
        # The preview_changes method catches ValueError and treats as new file
        # so the response is 200 with is_new_file=True
        assert response.status_code == 200
        data = response.json()
        assert data["is_new_file"] is True
