import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Optional

# Ensure repository root is on sys.path when invoked directly as a script
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from services.jobs.models import JobStatus
from services.jobs.runner import NightlyExportRunner


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure structured console logging to stdout and stderr."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("scripts.nightly_export")
    logger.setLevel(log_level)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Standard / Info / Debug stream -> stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    logger.addHandler(stdout_handler)

    # Error stream -> stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    return logger


def parse_arguments(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI command line flags."""
    parser = argparse.ArgumentParser(
        description="Autonomous nightly telemetry export and executive KPI pipeline orchestrator.",
    )
    parser.add_argument(
        "--date",
        dest="date",
        type=str,
        default=None,
        help="Target date override in YYYY-MM-DD UTC format. Precedes TARGET_DATE env var.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Resolve date and check locks/idempotency without writing snapshots or running pipeline.",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable verbose DEBUG logging.",
    )
    return parser.parse_args(args)


def main(args: Optional[list[str]] = None) -> int:
    """Main execution routine for nightly export CLI."""
    parsed = parse_arguments(args)
    logger = setup_logging(verbose=parsed.verbose)

    try:
        runner = NightlyExportRunner()
        result = runner.execute(
            target_date_override=parsed.date,
            dry_run=parsed.dry_run,
        )

        if result.status == JobStatus.FAILED:
            return 1

        # Clean success or clean skip (concurrency lock or idempotency) -> exit code 0
        return 0

    except ValueError as val_err:
        logger.error("Validation error: %s", val_err)
        return 1
    except Exception as exc:
        logger.error("Unhandled execution failure: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
