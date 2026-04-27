from __future__ import annotations

import os
import re
from pathlib import Path


class SecretScannerService:
    _patterns = {
        "gemini_api_key": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        "openai_api_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    }

    def __init__(self, root: Path) -> None:
        self.root = root

    def scan(self) -> list[str]:
        findings: list[str] = []
        skipped_dirs = {".pytest_cache", ".ruff_cache", "__pycache__", "node_modules", ".next"}
        skipped_suffixes = {
            ".db",
            ".sqlite",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".pyc",
            ".wal",
            ".shm",
            ".zip",
            ".pdf",
        }

        for current_root, dirnames, filenames in os.walk(self.root, topdown=True, onerror=lambda _error: None):
            dirnames[:] = [name for name in dirnames if name not in skipped_dirs]
            root_path = Path(current_root)
            for filename in filenames:
                path = root_path / filename
                if path.suffix.lower() in skipped_suffixes:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for label, pattern in self._patterns.items():
                    if pattern.search(text):
                        findings.append(f"{label}:{path}")
        return findings

    def enforce_clean_startup(self) -> None:
        findings = self.scan()
        if findings:
            raise RuntimeError(
                "startup refused because hardcoded credentials were detected: "
                + ", ".join(findings)
            )
