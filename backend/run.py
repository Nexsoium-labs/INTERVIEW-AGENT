"""
ZT-ATE Backend PyInstaller entry point.
Run as: python run.py in dev, or as compiled zt-backend-sidecar under Tauri.
"""
from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    _bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=False,
        loop="asyncio",
    )
