#!/usr/bin/env bash
# Build script for macOS and Linux.
# Usage: cd backend && ./build_backend.sh
set -euo pipefail

echo "==> Detecting Rust target triple..."
TRIPLE=$(rustc -Vv | grep host | cut -f2 -d' ')
echo "    Target: ${TRIPLE}"

PYTHON_BIN="${PYTHON:-python3}"
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

echo "==> Cleaning previous artifacts..."
rm -rf dist/ build/

echo "==> Installing PyInstaller and dependencies..."
"${PYTHON_BIN}" -m pip install pyinstaller
"${PYTHON_BIN}" -m pip install -e ".[full]"

echo "==> Building sidecar binary..."
"${PYTHON_BIN}" -m PyInstaller zt_ate_backend.spec

echo "==> Smoke-testing binary..."
./dist/zt-backend-sidecar &
BG_PID=$!
STATUS="000"
for _ in $(seq 1 10); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health || echo "000")
    [ "$STATUS" = "200" ] && break
    sleep 1
done
kill "$BG_PID" 2>/dev/null || true
wait "$BG_PID" 2>/dev/null || true
[ "$STATUS" != "200" ] && { echo "ERROR: health check failed (HTTP ${STATUS})"; exit 1; }
echo "    Health check passed."

echo "==> Copying to Tauri binaries..."
DEST="../src-tauri/binaries/zt-backend-sidecar-${TRIPLE}"
mkdir -p "../src-tauri/binaries"
cp dist/zt-backend-sidecar "${DEST}"
chmod +x "${DEST}"
echo "    Written: ${DEST}"
echo ""
echo "Done. Run 'cargo tauri build' from the project root."
