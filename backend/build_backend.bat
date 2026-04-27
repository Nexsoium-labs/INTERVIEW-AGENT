@echo off
setlocal enabledelayedexpansion

echo =^> Detecting Rust target triple...
for /f "tokens=2" %%i in ('rustc -Vv ^| findstr /c:"host"') do set TRIPLE=%%i
if "%TRIPLE%"=="" (
    echo ERROR: Could not detect Rust target triple.
    echo        Rust/rustc is likely not installed or not on PATH.
    echo        Install Rust from https://rustup.rs then re-run this script.
    echo        If you are on a standard 64-bit Windows machine you can bypass
    echo        this check by setting TRIPLE manually:
    echo          set TRIPLE=x86_64-pc-windows-msvc
    echo          build_backend.bat
    exit /b 1
)
echo     Target: %TRIPLE%

set PYTHON_BIN=python
if exist .venv\Scripts\python.exe set PYTHON_BIN=.venv\Scripts\python.exe

echo =^> Cleaning previous artifacts...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo =^> Installing PyInstaller and dependencies...
%PYTHON_BIN% -m pip install pyinstaller
%PYTHON_BIN% -m pip install -e ".[full]"

echo =^> Building sidecar binary...
%PYTHON_BIN% -m PyInstaller zt_ate_backend.spec
if %ERRORLEVEL% neq 0 ( echo ERROR: PyInstaller failed. & exit /b 1 )

echo =^> Copying to Tauri binaries...
if not exist ..\src-tauri\binaries mkdir ..\src-tauri\binaries
set DEST=..\src-tauri\binaries\zt-backend-sidecar-%TRIPLE%.exe
copy dist\zt-backend-sidecar.exe "%DEST%"
if %ERRORLEVEL% neq 0 ( echo ERROR: Copy failed. & exit /b 1 )
echo     Written: %DEST%

echo.
echo Done. Run 'cargo tauri build' from the project root.
