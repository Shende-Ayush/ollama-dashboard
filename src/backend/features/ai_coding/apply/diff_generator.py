"""Generate unified diffs from AI-suggested code changes."""
import difflib
from dataclasses import dataclass


@dataclass
class FileDiff:
    """A diff for a single file."""
    file_path: str
    original_content: str
    new_content: str
    diff_text: str
    insertions: int
    deletions: int


def generate_diff(original: str, modified: str, file_path: str = "file") -> FileDiff:
    """Generate a unified diff between original and modified content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    ))

    diff_text = "\n".join(diff_lines)
    insertions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    return FileDiff(
        file_path=file_path,
        original_content=original,
        new_content=modified,
        diff_text=diff_text,
        insertions=insertions,
        deletions=deletions,
    )


def extract_code_from_response(response: str, language: str = "") -> list[dict]:
    """Extract code blocks from AI response text.
    
    Returns list of {language, code, file_path (if mentioned)}.
    """
    import re
    blocks = []
    pattern = r'```(\w*)\n([\s\S]*?)```'
    
    for match in re.finditer(pattern, response):
        lang = match.group(1) or language
        code = match.group(2).strip()
        
        # Look for file path hint in the line before the code block
        start_pos = match.start()
        prefix_text = response[:start_pos].rstrip()
        file_path = None
        
        # Common patterns: "--- path/to/file.py ---" or "# path/to/file.py" or "File: path/to/file.py"
        path_patterns = [
            r'---\s*(.+?)\s*---\s*$',
            r'(?:File|file|Path|path):\s*(.+?)\s*$',
            r'#\s*(.+\.\w+)\s*$',
            r'`(.+\.\w+)`\s*$',
        ]
        last_line = prefix_text.split('\n')[-1] if prefix_text else ""
        for pp in path_patterns:
            m = re.search(pp, last_line)
            if m:
                file_path = m.group(1).strip()
                break
        
        blocks.append({
            "language": lang,
            "code": code,
            "file_path": file_path,
        })
    
    return blocks
