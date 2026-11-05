"""Pytest root configuration and fixtures."""

import os

# Suppress Prefect API logging when running tasks outside flow contexts during tests
os.environ.setdefault("PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW", "ignore")

