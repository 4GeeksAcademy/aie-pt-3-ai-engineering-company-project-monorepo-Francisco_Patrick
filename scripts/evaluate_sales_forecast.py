#!/usr/bin/env python3
"""CLI runner and orchestrator for TrackFlow regression model evaluation pipeline.

Executes 5-fold expanding-window temporal cross-validation on the 96-month training
partition (2016-01 to 2023-12) while keeping the 24-month hold-out test set (2024-01
to 2025-12) untouched, renders the learning curve (data/eval/learning_curve.png),
generates the technical fit diagnosis report (data/eval/evaluation_report.md),
writes the business metric cost justification (docs/model-eval.md), and exports
the structured CV metrics JSON (data/eval/cv_metrics.json).

Adheres strictly to specs/025-regression-model-evaluation/contracts/cli-contract.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

# Ensure monorepo root is on sys.path
MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

try:
    import numpy as np
    from data.pipelines.sales_forecast.dataset import (
        DataLeakageError,
        DatasetValidationError,
        create_temporal_partition,
        load_and_validate_sales_data,
    )
    from data.pipelines.sales_forecast.evaluator import (
        classify_model_fit,
        compute_learning_curve,
        evaluate_temporal_cv,
        export_cv_metrics_json,
        generate_business_metric_doc,
        generate_evaluation_report,
    )
    from data.pipelines.sales_forecast.visualizer import render_learning_curve
except ImportError as err:
    sys.stderr.write(f"Environment / Dependency error: Failed to import evaluation modules: {err}\n")
    sys.exit(3)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments according to specs/025-regression-model-evaluation/contracts/cli-contract.md.

    Args:
        argv: Optional sequence of command-line argument strings.

    Returns:
        argparse.Namespace: Parsed CLI configuration.
    """
    parser = argparse.ArgumentParser(
        description="TrackFlow Regression Model Evaluation Pipeline (5-Fold Temporal CV & Fit Diagnosis).",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("data/raw/trackflow_sales.csv"),
        help="Path to the raw TrackFlow sales CSV dataset (default: data/raw/trackflow_sales.csv).",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of chronological expanding cross-validation folds (>= 5, default: 5).",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for deterministic Random Forest execution (default: 42).",
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=Path("data/eval"),
        help="Output directory for learning_curve.png, evaluation_report.md, and cv_metrics.json (default: data/eval).",
    )
    parser.add_argument(
        "--docs-path",
        type=Path,
        default=Path("docs/model-eval.md"),
        help="Output path for the business cost metric justification document (default: docs/model-eval.md).",
    )
    return parser.parse_args(argv)


def run_evaluation(args: argparse.Namespace) -> int:
    """Execute the end-to-end 5-fold temporal cross-validation and reporting pipeline.

    Args:
        args: Parsed CLI options.

    Returns:
        int: Process exit code:
            - 0: Success
            - 1: Dataset Validation Failure
            - 2: Temporal / Fold Leakage Error
            - 3: Runtime / Environment Error
    """
    try:
        # Step 1: Load and validate consolidated dataset
        df = load_and_validate_sales_data(args.data_path, market="consolidated")

        # Step 2: Verify 8y train (96m) / 2y test (24m) partition boundaries
        partition = create_temporal_partition(df, train_months=96, test_months=24)
        mean_train_rev = float(np.mean(partition.train_df["revenue_eur"].values))
        avg_rev_per_shipment = float(
            np.mean(partition.train_df["avg_revenue_per_shipment_eur"].values)
        )

        # Step 3: Run leak-free expanding-window temporal cross-validation on 96-month training partition
        cv_summary = evaluate_temporal_cv(
            partition.train_df,
            n_splits=args.n_splits,
            random_seed=args.random_seed,
            n_estimators=100,
        )

        # Step 4: Extract learning curve progression and classify model fit
        learning_curve = compute_learning_curve(cv_summary)
        diagnosis = classify_model_fit(
            cv_summary=cv_summary,
            learning_curve=learning_curve,
            mean_train_revenue_eur=mean_train_rev,
        )

        # Step 5: Generate output artifacts
        args.eval_dir.mkdir(parents=True, exist_ok=True)
        lc_png_path = args.eval_dir / "learning_curve.png"
        eval_report_path = args.eval_dir / "evaluation_report.md"
        cv_json_path = args.eval_dir / "cv_metrics.json"

        render_learning_curve(
            learning_curve=learning_curve,
            output_path=lc_png_path,
            cv_summary=cv_summary,
            dpi=300,
        )
        generate_evaluation_report(
            cv_summary=cv_summary,
            learning_curve=learning_curve,
            diagnosis=diagnosis,
            output_path=eval_report_path,
        )
        generate_business_metric_doc(
            cv_summary=cv_summary,
            diagnosis=diagnosis,
            output_path=args.docs_path,
            avg_revenue_per_shipment_eur=avg_rev_per_shipment,
        )
        export_cv_metrics_json(
            cv_summary=cv_summary,
            diagnosis=diagnosis,
            output_path=cv_json_path,
            model_type="random_forest",
            random_seed=args.random_seed,
            train_partition_months=partition.train_count,
        )

        # Step 6: Print structured executive stdout summary per cli-contract.md
        print("======================================================================")
        print(f" TRACKFLOW REGRESSION MODEL EVALUATION — {cv_summary.n_splits}-FOLD TEMPORAL CV SUMMARY")
        print("======================================================================")
        print(
            f"Dataset: {args.data_path.as_posix()} "
            f"(Training Partition: {partition.train_count} months, {partition.train_start} to {partition.train_end})"
        )
        print(
            f"Hold-Out Test Partition: {partition.test_count} months "
            f"({partition.test_start} to {partition.test_end}) [ISOLATED / UNTOUCHED]"
        )
        print(
            f"Cross-Validation Strategy: Expanding Window ({cv_summary.n_splits} Chronological Folds, Zero Leakage)\n"
        )
        print("Per-Fold Metrics (EUR):")
        for f in cv_summary.folds:
            print(
                f"  Fold {f.fold_index} (Train: {f.train_size}m, Val: {f.val_size}m) | "
                f"Train MAE: €{f.train_mae_eur:,.2f} | Val MAE: €{f.val_mae_eur:,.2f} | "
                f"Train RMSE: €{f.train_rmse_eur:,.2f} | Val RMSE: €{f.val_rmse_eur:,.2f}"
            )
        print(f"\nCross-Validation Summary (mean ± std across {cv_summary.n_splits} folds):")
        print(f"  - Training MAE    : {cv_summary.formatted_train_mae}")
        print(f"  - Validation MAE  : {cv_summary.formatted_val_mae}")
        print(f"  - Training RMSE   : {cv_summary.formatted_train_rmse}")
        print(f"  - Validation RMSE : {cv_summary.formatted_val_rmse}\n")
        print(f"Model Fit Diagnosis : {diagnosis.fit_classification}")
        print(f"Primary Metric      : {diagnosis.primary_metric} (Root Mean Squared Error)")
        print(f"Staging Decision    : {diagnosis.staging_readiness_decision}\n")
        print("Artifacts Generated:")
        print(f"  - Learning Curve Plot       : {lc_png_path.as_posix()}")
        print(f"  - Technical Eval Report     : {eval_report_path.as_posix()}")
        print(f"  - Business Metric Doc       : {args.docs_path.as_posix()}")
        print(f"  - Structured CV Metrics JSON: {cv_json_path.as_posix()}")
        print("======================================================================")

        return 0

    except DatasetValidationError as exc:
        sys.stderr.write(f"Dataset Validation Failure: {exc}\n")
        return 1
    except DataLeakageError as exc:
        sys.stderr.write(f"Temporal / Fold Leakage Error: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"Runtime / Environment Error: {exc}\n")
        return 3


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    exit_code = run_evaluation(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

