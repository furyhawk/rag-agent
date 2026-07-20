"""Base connector interface and registry.

Extracted and generalized from agent_alpha/backend/rag/connectors.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {}


class BaseConnector(ABC):
    """Abstract base for document source connectors."""

    CONNECTOR_TYPE: str = ""
    DISPLAY_NAME: str = ""
    CONFIG_SCHEMA: dict[str, Any] = {}

    @classmethod
    def register(cls) -> None:
        """Register this connector in the global registry."""
        CONNECTOR_REGISTRY[cls.CONNECTOR_TYPE] = cls

    @classmethod
    @abstractmethod
    def validate_config(
        cls, config: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate connector configuration."""
        ...

    @classmethod
    @abstractmethod
    async def list_files(
        cls, config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """List available files from the source."""
        ...

    @classmethod
    @abstractmethod
    async def download_file(
        cls, config: dict[str, Any], file_path: str
    ) -> bytes:
        """Download a file from the source."""
        ...


class LocalFilesystemConnector(BaseConnector):
    """Local filesystem connector."""

    CONNECTOR_TYPE = "local"
    DISPLAY_NAME = "Local Filesystem"
    CONFIG_SCHEMA = {
        "path": {"type": "string", "description": "Local directory path"}
    }

    @classmethod
    def validate_config(
        cls, config: dict[str, Any]
    ) -> tuple[bool, str | None]:
        path = config.get("path")
        if not path:
            return False, "Missing 'path' in config"
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            return False, f"Path does not exist: {path}"
        if not p.is_dir():
            return False, f"Path is not a directory: {path}"
        return True, None

    @classmethod
    async def list_files(
        cls, config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        from pathlib import Path

        path = Path(config["path"])
        allowed = {".txt", ".md", ".docx", ".pdf"}
        files = []
        for f in path.rglob("*"):
            if f.is_file() and f.suffix.lower() in allowed:
                files.append(
                    {
                        "path": str(f),
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                    }
                )
        return files

    @classmethod
    async def download_file(
        cls, config: dict[str, Any], file_path: str
    ) -> bytes:
        from pathlib import Path

        return Path(file_path).read_bytes()


LocalFilesystemConnector.register()
