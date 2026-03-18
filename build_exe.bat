@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  LumaEXR-Viewer.spec

echo.
echo Build complete. Output: dist\LumaEXR-Viewer_v_1_0.exe
