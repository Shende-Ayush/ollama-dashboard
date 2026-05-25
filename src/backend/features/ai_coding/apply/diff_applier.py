"""Apply diffs to workspace files."""
import logging
from typing import Optional

from backend.features.ai_coding.apply.diff_generator import FileDiff, generate_diff, extract_code_from_response
from backend.features.workspace.service import workspace_service

logger = logging.getLogger(__name__)


class DiffApplier:
    """Applies AI-generated code changes to workspace files."""

    async def preview_changes(
        self,
        workspace_id: str,
        file_path: str,
        new_content: str,
        session,
    ) -> FileDiff:
        """Generate a diff preview without applying changes."""
        try:
            file_response = await workspace_service.read_file(workspace_id, file_path, session)
            original = file_response.content
        except (ValueError, FileNotFoundError):
            original = ""  # New file

        return generate_diff(original, new_content, file_path)

    async def apply_change(
        self,
        workspace_id: str,
        file_path: str,
        new_content: str,
        session,
    ) -> dict:
        """Apply a code change to a workspace file."""
        # Generate diff for logging
        try:
            file_response = await workspace_service.read_file(workspace_id, file_path, session)
            original = file_response.content
        except (ValueError, FileNotFoundError):
            original = ""

        diff = generate_diff(original, new_content, file_path)

        # Write the new content
        await workspace_service.write_file(workspace_id, file_path, new_content, session)

        return {
            "status": "applied",
            "file_path": file_path,
            "insertions": diff.insertions,
            "deletions": diff.deletions,
            "diff_text": diff.diff_text,
        }

    async def apply_from_response(
        self,
        workspace_id: str,
        response_text: str,
        target_file: Optional[str],
        language: str,
        session,
    ) -> list[dict]:
        """Extract code from AI response and apply to workspace.
        
        If target_file is specified, applies first code block to that file.
        Otherwise, uses file paths from response.
        """
        blocks = extract_code_from_response(response_text, language)
        results = []

        for block in blocks:
            file_path = block.get("file_path") or target_file
            if not file_path:
                continue

            code = block["code"]
            result = await self.apply_change(workspace_id, file_path, code, session)
            results.append(result)

        return results


diff_applier = DiffApplier()
