@echo off
title SnapEdge AI Assistant - Snapdragon HP PC Launch
echo ===========================================================================
echo   Starting SnapEdge AI Assistant (Snapdragon AI Lab Build & Present)
echo   Target Platform: Snapdragon-Powered HP PCs (Hexagon NPU 45 TOPS)
echo   Local URL: http://localhost:8000
echo ===========================================================================
set Path=C:\Users\naras\.local\bin;%Path%

if "%1"=="--widget" (
    echo [INFO] Launching SnapEdge Desktop Companion HUD in background...
    start uv run python desktop_widget.py
)
if "%1"=="/widget" (
    echo [INFO] Launching SnapEdge Desktop Companion HUD in background...
    start uv run python desktop_widget.py
)

uv run uvicorn snapedge.app:app --host 127.0.0.1 --port 8000
pause
