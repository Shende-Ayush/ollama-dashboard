from datetime import datetime, timedelta, timezone


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_after_seconds: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after = timedelta(seconds=reset_after_seconds)
        self.failures = 0
        self.open_until: datetime | None = None

    def allow(self) -> bool:
        if self.open_until is None:
            return True
        if datetime.now(timezone.utc) >= self.open_until:
            self.failures = 0
            self.open_until = None
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.open_until = datetime.now(timezone.utc) + self.reset_after


circuit_breaker = CircuitBreaker()
