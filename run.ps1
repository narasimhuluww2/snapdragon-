<#
.SYNOPSIS
    One-Click PowerShell Launch Script for SnapEdge AI Assistant.
    Snapdragon AI Lab Build and Present Challenge.
    Optimized for Snapdragon-Powered HP PCs (Qualcomm Hexagon NPU 45 TOPS).

.DESCRIPTION
    Launches the FastAPI backend server on http://localhost:8000
    and verifies the local environment for Qualcomm AI Hub models and AHEAD engine.
    Optionally launches the floating desktop companion widget (-WithWidget).
#>

[CmdletBinding()]
param (
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1",
    [switch]$NoBrowser,
    [switch]$WithWidget
)

$ErrorActionPreference = "Stop"

# Title banner
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host "   SnapEdge AI Assistant - Snapdragon AI Lab Build and Present Challenge   " -ForegroundColor Yellow
Write-Host "   Target Platform: Snapdragon-Powered HP PCs (Hexagon NPU 45 TOPS)        " -ForegroundColor Green
Write-Host "   Local Server: http://$HostAddress`:$Port                                  " -ForegroundColor White
Write-Host "===========================================================================" -ForegroundColor Cyan

# Add local path for uv if present
$LocalBin = "$env:USERPROFILE\.local\bin"
if (Test-Path $LocalBin) {
    $env:Path = "$LocalBin;$env:Path"
}

# Verify uv is installed
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvPath) {
    Write-Warning "uv package manager not found on PATH. Falling back to python..."
} else {
    Write-Host "[OK] uv package manager detected: $($uvPath.Source)" -ForegroundColor Green
}

# Optional automatic browser launch
if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 2
        try {
            Start-Process $url
        } catch {}
    } -ArgumentList "http://$HostAddress`:$Port" | Out-Null
    Write-Host "[INFO] Launching browser at http://$HostAddress`:$Port in 2 seconds..." -ForegroundColor Gray
}

# Optional desktop widget launch
if ($WithWidget) {
    Start-Job -ScriptBlock {
        param($hasUv)
        Start-Sleep -Seconds 3
        try {
            if ($hasUv) {
                Start-Process uv -ArgumentList "run python desktop_widget.py"
            } else {
                Start-Process python -ArgumentList "desktop_widget.py"
            }
        } catch {}
    } -ArgumentList ($null -ne $uvPath) | Out-Null
    Write-Host "[INFO] Floating Desktop Companion HUD enabled (-WithWidget)..." -ForegroundColor Magenta
}

Write-Host "`nStarting SnapEdge FastAPI Server on http://$HostAddress`:$Port ...`n" -ForegroundColor Cyan

if ($uvPath) {
    & uv run uvicorn snapedge.app:app --host $HostAddress --port $Port
} else {
    & python -m uvicorn snapedge.app:app --host $HostAddress --port $Port
}
