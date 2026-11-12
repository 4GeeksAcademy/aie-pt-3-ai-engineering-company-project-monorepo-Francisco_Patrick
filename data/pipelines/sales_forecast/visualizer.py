"""Visual forecast rendering module with uncertainty bands and seasonal callouts.

Generates high-resolution publication-quality PNG charts comparing ground-truth test revenue
against tree-ensemble predicted trajectories with 95% uncertainty envelopes.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend safe for CLI / CI environments
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from data.pipelines.sales_forecast.model import ForecastPredictionPoint


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

