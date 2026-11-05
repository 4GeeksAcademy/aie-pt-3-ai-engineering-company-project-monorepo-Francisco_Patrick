<#
.SYNOPSIS
    Convenience test runner executing pytest with the canonical virtual environment.
.DESCRIPTION
    Executes pytest targeting the monorepo's virtual environment in services/api/.venv
    via uv or directly using the virtualenv python binary.
.EXAMPLE
    .\scripts\test_runner.ps1 tests/unit/jobs/test_nightly_export_runner.py -v
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$VenvPython = Join-Path $RepoRoot "services\api\.venv\Scripts\python.exe"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    if ($PytestArgs.Count -gt 0) {
        uv run --project "$RepoRoot\services\api" pytest @PytestArgs
    } else {
        uv run --project "$RepoRoot\services\api" pytest
    }
} elseif (Test-Path $VenvPython) {
    if ($PytestArgs.Count -gt 0) {
        & $VenvPython -m pytest @PytestArgs
    } else {
        & $VenvPython -m pytest
    }
} else {
    Write-Error "Neither 'uv' nor virtual environment at services/api/.venv was found. Please install uv or set up the virtualenv."
    exit 1
}

