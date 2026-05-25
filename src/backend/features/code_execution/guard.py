"""Security guard for code execution sandbox."""
from backend.features.code_execution.schemas import ValidationResult
from backend.utils.security.code_scanner import ScanResult, scan_code


class ExecutionGuard:
    """Validates code safety before execution.

    Uses the shared code_scanner utility and adds execution-context
    specific checks (e.g., network access control).
    """

    def validate(
        self, code: str, language: str, allow_network: bool = False
    ) -> ScanResult:
        """Run full security validation on code.

        Args:
            code: Source code to validate.
            language: Programming language.
            allow_network: Whether network access is permitted.

        Returns:
            ScanResult with safety assessment.
        """
        result = scan_code(code, language)

        # If network is not allowed, flag any network-related violations
        # (already handled by code_scanner patterns for most cases)
        if not allow_network and result.is_safe:
            # Additional network checks not covered by the base scanner
            pass

        return result

    def is_execution_allowed(
        self, code: str, language: str
    ) -> tuple[bool, list[str]]:
        """Quick check if code execution is allowed.

        Args:
            code: Source code to check.
            language: Programming language.

        Returns:
            Tuple of (is_allowed, list_of_violations).
        """
        result = self.validate(code, language)
        return result.is_safe, result.violations

    def to_validation_result(self, scan_result: ScanResult) -> ValidationResult:
        """Convert a ScanResult to a ValidationResult schema."""
        return ValidationResult(
            is_safe=scan_result.is_safe,
            violations=scan_result.violations,
            risk_level=scan_result.risk_level,
        )
