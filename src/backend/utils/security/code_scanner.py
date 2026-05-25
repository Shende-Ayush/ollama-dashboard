"""
Shared dangerous code detection utility.
Used by: code_execution, autonomous.
"""
import re
from dataclasses import dataclass


@dataclass
class ScanResult:
    """Result of code security scan."""
    is_safe: bool
    violations: list[str]
    risk_level: str  # low, medium, high, critical


# Per-language dangerous patterns
PYTHON_DANGEROUS = [
    (r'\bos\.system\b', "os.system() - shell execution"),
    (r'\bsubprocess\b', "subprocess module - process spawning"),
    (r'\bos\.exec', "os.exec*() - process replacement"),
    (r'\b__import__\b', "__import__() - dynamic import"),
    (r'\beval\b\s*\(', "eval() - arbitrary code execution"),
    (r'\bexec\b\s*\(', "exec() - arbitrary code execution"),
    (r'\bcompile\b\s*\(', "compile() - code compilation"),
    (r'\bctypes\b', "ctypes - low-level memory access"),
    (r'\bsocket\b', "socket module - network access"),
    (r'\burllib\b', "urllib - network access"),
    (r'\brequests\b', "requests - network access"),
    (r'\bhttpx\b', "httpx - network access"),
    (r'\bopen\s*\(\s*["\']\/(?:etc|proc|sys|dev)', "reading system files"),
    (r'\bshutil\.rmtree\b', "shutil.rmtree - recursive deletion"),
]

JAVASCRIPT_DANGEROUS = [
    (r'\bchild_process\b', "child_process - shell execution"),
    (r'\bexec\b\s*\(', "exec() - shell execution"),
    (r'\bspawn\b\s*\(', "spawn() - process spawning"),
    (r'\beval\b\s*\(', "eval() - arbitrary code execution"),
    (r'\bFunction\b\s*\(', "Function() constructor - code execution"),
    (r'\brequire\s*\(\s*["\']fs', "fs module - filesystem access"),
    (r'\brequire\s*\(\s*["\']net', "net module - network access"),
    (r'\brequire\s*\(\s*["\']http', "http module - network access"),
    (r'\bprocess\.env\b', "process.env - environment access"),
    (r'\bprocess\.exit\b', "process.exit - process termination"),
]

BASH_DANGEROUS = [
    (r'\brm\s+-rf\s+/', "rm -rf / - recursive root deletion"),
    (r'\b(mkfs|fdisk|dd)\b', "disk manipulation commands"),
    (r'\b(chmod|chown)\s+.*\s+/', "permission changes on system files"),
    (r'\bcurl\b.*\|\s*bash', "curl pipe to bash - remote execution"),
    (r'\bwget\b.*\|\s*bash', "wget pipe to bash - remote execution"),
    (r'\b(iptables|ufw)\b', "firewall manipulation"),
    (r'\b(useradd|userdel|passwd)\b', "user management"),
]

PATTERNS = {
    "python": PYTHON_DANGEROUS,
    "javascript": JAVASCRIPT_DANGEROUS,
    "typescript": JAVASCRIPT_DANGEROUS,
    "bash": BASH_DANGEROUS,
    "shell": BASH_DANGEROUS,
}


def scan_code(code: str, language: str) -> ScanResult:
    """
    Scan code for dangerous patterns.
    Returns ScanResult with safety assessment.
    """
    patterns = PATTERNS.get(language.lower(), [])
    violations = []

    for pattern, description in patterns:
        if re.search(pattern, code, re.IGNORECASE):
            violations.append(description)

    if not violations:
        return ScanResult(is_safe=True, violations=[], risk_level="low")

    # Determine risk level
    critical_keywords = ["shell execution", "recursive deletion", "arbitrary code"]
    has_critical = any(
        any(kw in v.lower() for kw in critical_keywords) 
        for v in violations
    )

    if has_critical:
        risk_level = "critical"
    elif len(violations) >= 3:
        risk_level = "high"
    elif len(violations) >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return ScanResult(
        is_safe=False,
        violations=violations,
        risk_level=risk_level,
    )
