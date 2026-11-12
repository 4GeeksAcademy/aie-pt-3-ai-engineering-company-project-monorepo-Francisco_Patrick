"""Visual forecast rendering module with uncertainty bands and seasonal callouts.

Generates high-resolution publication-quality PNG charts comparing ground-truth test revenue
against tree-ensemble predicted trajectories with 95% uncertainty envelopes.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend safe for CLI / CI environments
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from data.pipelines.sales_forecast.model import ForecastPredictionPoint

if TYPE_CHECKING:
    from data.pipelines.sales_forecast.evaluator import LearningCurvePoint, TemporalCVSummary


def render_forecast_visualization(
    predictions: Sequence[ForecastPredictionPoint],
    output_path: str | Path,
    dpi: int = 300,
) -> Path:
    """Render high-resolution visual forecast comparing actual vs. predicted revenue.

    Features:
        - Actual ground-truth revenue curve with circular markers.
        - Predicted forecast line from tree ensemble.
        - Semi-transparent shaded 95% uncertainty/variability envelope (±1.96σ).
        - Seasonal annotations highlighting November-December peaks and February dips.

    Args:
        predictions: Sequence of ForecastPredictionPoint objects for the hold-out test period.
        output_path: Target destination path for PNG file.
        dpi: Target image resolution (default: 300).

    Returns:
        Path: Resolved file path of the saved PNG image.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    dates = [pd.to_datetime(p.month) for p in predictions]
    actuals = np.array([p.actual_revenue_eur for p in predictions])
    preds = np.array([p.predicted_revenue_eur for p in predictions])
    lowers = np.array([p.lower_bound_eur for p in predictions])
    uppers = np.array([p.upper_bound_eur for p in predictions])

    fig, ax = plt.subplots(figsize=(14, 7), dpi=dpi)

    # 1. Uncertainty Envelope Ribbon
    ax.fill_between(
        dates,
        lowers,
        uppers,
        color="#3b82f6",
        alpha=0.20,
        label="95% Uncertainty / Variability Envelope (±1.96σ)",
        zorder=2,
    )

    # 2. Predicted Trajectory
    ax.plot(
        dates,
        preds,
        color="#2563eb",
        linestyle="--",
        linewidth=2.4,
        marker="s",
        markersize=5,
        label="Random Forest Predicted Revenue",
        zorder=3,
    )

    # 3. Ground Truth Actual Revenue
    ax.plot(
        dates,
        actuals,
        color="#0f172a",
        linestyle="-",
        linewidth=2.8,
        marker="o",
        markersize=6,
        label="Actual Ground Truth Revenue (2024–2025)",
        zorder=4,
    )

    # 4. Seasonal Callouts / Annotations
    for d, act in zip(dates, actuals):
        # Peak season: Nov and Dec
        if d.month == 11:
            ax.annotate(
                f"Peak Surge (Nov)\n€{act:,.0f}",
                xy=(d, act),
                xytext=(0, 28),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#047857",
                arrowprops=dict(arrowstyle="->", color="#047857", lw=1.2),
                zorder=5,
            )
        elif d.month == 12:
            ax.annotate(
                f"Holiday Surge (Dec)\n€{act:,.0f}",
                xy=(d, act),
                xytext=(0, 28),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#047857",
                arrowprops=dict(arrowstyle="->", color="#047857", lw=1.2),
                zorder=5,
            )
        # February seasonal dip
        elif d.month == 2:
            ax.annotate(
                f"Seasonal Dip (Feb)\n€{act:,.0f}",
                xy=(d, act),
                xytext=(0, -34),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#b91c1c",
                arrowprops=dict(arrowstyle="->", color="#b91c1c", lw=1.2),
                zorder=5,
            )

    # Styling and Labels
    ax.set_title(
        "TrackFlow Monthly Sales Forecast vs. Actual Revenue (2024–2025 Hold-Out Evaluation)\n"
        "Model: Random Forest Regressor (100 Trees) | Zero-Lookahead Causal Features",
        fontsize=13,
        fontweight="bold",
        pad=16,
        color="#0f172a",
    )
    ax.set_xlabel("Forecast Month (Chronological Out-of-Sample Hold-Out)", fontsize=11, labelpad=10)
    ax.set_ylabel("Monthly Revenue (EUR)", fontsize=11, labelpad=10)

    # Format Y-Axis with commas and Euro sign
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"€{x:,.0f}"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax.grid(True, linestyle=":", alpha=0.6, color="#94a3b8")
    ax.legend(loc="upper left", frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=10)

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    fig.savefig(path, dpi=dpi)
    plt.close(fig)

    return path


def render_learning_curve(
    learning_curve: Sequence["LearningCurvePoint"],
    output_path: str | Path = Path("data/eval/learning_curve.png"),
    cv_summary: "TemporalCVSummary | None" = None,
    dpi: int = 300,
) -> Path:
    """Render high-resolution learning curve comparing Training vs. Validation MAE and RMSE.

    Plots Training Error and Validation Error across increasing chronological training sample
    sizes (N = 16, 32, 48, 64, 80 months) in a two-panel diagnostic layout (RMSE primary panel
    and MAE secondary panel) with generalization gap shading and mean +/- std callouts.

    Args:
        learning_curve: Sequence of LearningCurvePoint objects ordered by increasing train_size.
        output_path: Destination file path for the PNG chart (default: data/eval/learning_curve.png).
        cv_summary: Optional TemporalCVSummary for displaying aggregate mean +/- std bands in title/legend.
        dpi: Image resolution in dots per inch (default: 300).

    Returns:
        Path: Resolved path of the saved PNG image.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    train_sizes = np.array([pt.train_size for pt in learning_curve], dtype=int)
    train_rmse = np.array([pt.train_rmse_eur for pt in learning_curve], dtype=float)
    val_rmse = np.array([pt.val_rmse_eur for pt in learning_curve], dtype=float)
    train_mae = np.array([pt.train_mae_eur for pt in learning_curve], dtype=float)
    val_mae = np.array([pt.val_mae_eur for pt in learning_curve], dtype=float)

    fig, (ax_rmse, ax_mae) = plt.subplots(1, 2, figsize=(15, 6.5), dpi=dpi, sharex=True)

    eur_formatter = ticker.FuncFormatter(lambda x, p: f"€{x:,.0f}")

    # Panel 1: RMSE Learning Curve (Primary Decision Metric)
    ax_rmse.fill_between(
        train_sizes,
        train_rmse,
        val_rmse,
        color="#f97316",
        alpha=0.16,
        label="Generalization Gap (Val RMSE − Train RMSE)",
        zorder=2,
    )
    ax_rmse.plot(
        train_sizes,
        val_rmse,
        color="#dc2626",
        linestyle="-",
        linewidth=2.6,
        marker="o",
        markersize=7,
        label="Validation RMSE (Out-of-Sample Fold)",
        zorder=4,
    )
    ax_rmse.plot(
        train_sizes,
        train_rmse,
        color="#2563eb",
        linestyle="--",
        linewidth=2.4,
        marker="s",
        markersize=6,
        label="Training RMSE (In-Sample Fold)",
        zorder=3,
    )

    for sz, tr, vr in zip(train_sizes, train_rmse, val_rmse):
        ax_rmse.annotate(
            f"€{vr:,.0f}",
            xy=(sz, vr),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color="#991b1b",
        )
        ax_rmse.annotate(
            f"€{tr:,.0f}",
            xy=(sz, tr),
            xytext=(0, -15),
            textcoords="offset points",
            ha="center",
            fontsize=8.0,
            color="#1e40af",
        )

    ax_rmse.set_title(
        "Primary Metric: RMSE vs. Chronological Training Size",
        fontsize=11.5,
        fontweight="bold",
        color="#0f172a",
        pad=12,
    )
    ax_rmse.set_xlabel("Chronological Training Window Size (Months)", fontsize=10.5, labelpad=8)
    ax_rmse.set_ylabel("Root Mean Squared Error — RMSE (EUR)", fontsize=10.5, labelpad=8)
    ax_rmse.set_xticks(train_sizes)
    ax_rmse.set_xticklabels([f"{s}m\n(Fold {i + 1})" for i, s in enumerate(train_sizes)])
    ax_rmse.yaxis.set_major_formatter(eur_formatter)
    ax_rmse.set_ylim(bottom=0, top=float(np.max(val_rmse)) * 1.22)
    ax_rmse.grid(True, linestyle=":", alpha=0.6, color="#94a3b8")
    ax_rmse.legend(loc="upper right", frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=9)

    # Panel 2: MAE Learning Curve (Linear Executive Interpretation Metric)
    ax_mae.fill_between(
        train_sizes,
        train_mae,
        val_mae,
        color="#eab308",
        alpha=0.16,
        label="Generalization Gap (Val MAE − Train MAE)",
        zorder=2,
    )
    ax_mae.plot(
        train_sizes,
        val_mae,
        color="#d97706",
        linestyle="-",
        linewidth=2.6,
        marker="o",
        markersize=7,
        label="Validation MAE (Out-of-Sample Fold)",
        zorder=4,
    )
    ax_mae.plot(
        train_sizes,
        train_mae,
        color="#059669",
        linestyle="--",
        linewidth=2.4,
        marker="s",
        markersize=6,
        label="Training MAE (In-Sample Fold)",
        zorder=3,
    )

    for sz, tm, vm in zip(train_sizes, train_mae, val_mae):
        ax_mae.annotate(
            f"€{vm:,.0f}",
            xy=(sz, vm),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color="#92400e",
        )
        ax_mae.annotate(
            f"€{tm:,.0f}",
            xy=(sz, tm),
            xytext=(0, -15),
            textcoords="offset points",
            ha="center",
            fontsize=8.0,
            color="#065f46",
        )

    ax_mae.set_title(
        "Secondary Metric: MAE vs. Chronological Training Size",
        fontsize=11.5,
        fontweight="bold",
        color="#0f172a",
        pad=12,
    )
    ax_mae.set_xlabel("Chronological Training Window Size (Months)", fontsize=10.5, labelpad=8)
    ax_mae.set_ylabel("Mean Absolute Error — MAE (EUR)", fontsize=10.5, labelpad=8)
    ax_mae.set_xticks(train_sizes)
    ax_mae.set_xticklabels([f"{s}m\n(Fold {i + 1})" for i, s in enumerate(train_sizes)])
    ax_mae.yaxis.set_major_formatter(eur_formatter)
    ax_mae.set_ylim(bottom=0, top=float(np.max(val_mae)) * 1.22)
    ax_mae.grid(True, linestyle=":", alpha=0.6, color="#94a3b8")
    ax_mae.legend(loc="upper right", frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=9)

    subtitle = (
        f"5-Fold Summary — Train RMSE: {cv_summary.formatted_train_rmse} | Val RMSE: {cv_summary.formatted_val_rmse} | "
        f"Train MAE: {cv_summary.formatted_train_mae} | Val MAE: {cv_summary.formatted_val_mae}"
        if cv_summary is not None
        else "5-Fold Expanding-Window Chronological Cross-Validation (96-Month Training Partition, 2016–2023)"
    )

    fig.suptitle(
        "TrackFlow Sales Forecasting — Temporal Learning Curve & Fit Diagnosis (Overfitting Gap Analysis)\n"
        + subtitle,
        fontsize=12.5,
        fontweight="bold",
        color="#0f172a",
        y=0.98,
    )

    plt.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)

    return path

