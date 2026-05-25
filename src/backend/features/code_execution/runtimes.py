"""Language runtime registry for code execution sandbox."""
from backend.features.code_execution.schemas import RuntimeInfo

RUNTIMES: dict[str, dict] = {
    "python": {
        "image": "python:3.12-slim",
        "cmd": ["python", "-c"],
        "extension": ".py",
        "timeout": 30,
        "memory_mb": 128,
    },
    "javascript": {
        "image": "node:20-slim",
        "cmd": ["node", "-e"],
        "extension": ".js",
        "timeout": 30,
        "memory_mb": 128,
    },
    "typescript": {
        "image": "node:20-slim",
        "cmd": ["npx", "ts-node", "-e"],
        "extension": ".ts",
        "timeout": 45,
        "memory_mb": 256,
    },
    "bash": {
        "image": "bash:5",
        "cmd": ["bash", "-c"],
        "extension": ".sh",
        "timeout": 15,
        "memory_mb": 64,
    },
    "go": {
        "image": "golang:1.22-alpine",
        "cmd": ["go", "run", "/tmp/main.go"],
        "extension": ".go",
        "timeout": 60,
        "memory_mb": 256,
    },
}


def get_runtime(language: str) -> dict | None:
    """Get runtime configuration for a language."""
    return RUNTIMES.get(language.lower())


def list_runtimes() -> list[RuntimeInfo]:
    """List all supported runtime environments."""
    return [
        RuntimeInfo(
            name=lang,
            language=lang,
            docker_image=config["image"],
            max_timeout=config["timeout"],
            max_memory_mb=config["memory_mb"],
            is_active=True,
        )
        for lang, config in RUNTIMES.items()
    ]


def is_supported(language: str) -> bool:
    """Check if a language is supported."""
    return language.lower() in RUNTIMES
