#!/usr/bin/env python3
"""Create runway-specific anomaly-vs-typical comparison PNGs from merged pointwise data."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ANOM_COLOR = "#d1495b"
TYPICAL_COLORS = ["#2a9d8f", "#457b9d", "#6d597a"]
BG_COLOR = "#9aa0a6"
RUNWAY_BG_COLOR = "#6b7280"


def pick_typicals(scores: pd.DataFrame, runway: str, n: int = 3) -> pd.DataFrame:
    return scores[scores["runway"] == runway].sort_values("anomaly_score", ascending=True).head(n).reset_index(drop=True)


def plot_panel(
    ax: plt.Axes,
    airport_df: pd.DataFrame,
    runway_df: pd.DataFrame,
    anomaly_row: pd.Series,
    typical_rows: pd.DataFrame,
) -> None:
    for _, traj in airport_df.groupby("trajectory_id", sort=False):
        ax.plot(traj["lon"], traj["lat"], color=BG_COLOR, alpha=0.045, lw=0.7, zorder=1)

    for _, traj in runway_df.groupby("trajectory_id", sort=False):
        ax.plot(traj["lon"], traj["lat"], color=RUNWAY_BG_COLOR, alpha=0.14, lw=0.95, zorder=2)

    for idx, (_, row) in enumerate(typical_rows.iterrows()):
        traj = runway_df[runway_df["trajectory_id"] == row["trajectory_id"]]
        ax.plot(traj["lon"], traj["lat"], color=TYPICAL_COLORS[idx % len(TYPICAL_COLORS)], lw=2.0, ls="--", alpha=0.95, label=f"Typical #{idx+1} ({row['anomaly_score']:.3f})", zorder=3)

    anomaly_traj = runway_df[runway_df["trajectory_id"] == anomaly_row["trajectory_id"]]
    ax.plot(anomaly_traj["lon"], anomaly_traj["lat"], color=ANOM_COLOR, lw=2.7, alpha=0.98, label=f"Anomaly ({anomaly_row['anomaly_score']:.3f})", zorder=4)
    ax.scatter(anomaly_traj["lon"].iloc[-1], anomaly_traj["lat"].iloc[-1], s=160, marker="*", color="#f4a261", edgecolor="#54412d", linewidth=0.9, zorder=5)

    ax.set_title(f"Runway {anomaly_row['runway']} | Flight {anomaly_row['flight_id']}\nAnomalous vs Typical Approaches", fontsize=12, pad=10)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, alpha=0.14, linewidth=0.7, color="#c7cfdb")
    ax.set_facecolor("#ffffff")
    ax.tick_params(labelsize=9, colors="#374151")
    for spine in ax.spines.values():
        spine.set_color("#6b7280")
        spine.set_linewidth(0.9)
    notes = [
        f"Anomaly score: {anomaly_row['anomaly_score']:.4f}",
        f"Mode: {anomaly_row.get('arrival_mode', 'NA')}",
        f"Corridor: {anomaly_row.get('arrival_corridor', 'NA')}",
    ]
    ax.text(0.02, 0.02, "\n".join(notes), transform=ax.transAxes, va="bottom", ha="left", fontsize=8.2, color="#374151", bbox={"boxstyle": "round,pad=0.35", "fc": "#fffdf9", "ec": "#cfd6df", "alpha": 0.96})


def build_figure(df: pd.DataFrame, scores: pd.DataFrame, output_path: Path, n_anomalies: int = 4) -> None:
    anomalies = scores.sort_values("anomaly_score", ascending=False).head(n_anomalies).reset_index(drop=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 13), dpi=180)
    fig.patch.set_facecolor("#ffffff")
    legend_handles = [
        plt.Line2D([0], [0], color=BG_COLOR, lw=1.0, alpha=0.5, label="Airport-wide background trajectories"),
        plt.Line2D([0], [0], color=RUNWAY_BG_COLOR, lw=1.2, alpha=0.6, label="Same-runway background trajectories"),
        plt.Line2D([0], [0], color=TYPICAL_COLORS[0], lw=2.0, ls="--", label="Typical low-score trajectories"),
        plt.Line2D([0], [0], color=ANOM_COLOR, lw=2.6, label="Anomalous trajectory"),
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#f4a261", markeredgecolor="#54412d", markersize=12, lw=0, label="Arrival endpoint"),
    ]

    for ax, (_, anomaly_row) in zip(axes.flat, anomalies.iterrows()):
        runway = anomaly_row["runway"]
        runway_df = df[df["runway"] == runway]
        typical_rows = pick_typicals(scores, runway, n=3)
        plot_panel(ax, df, runway_df, anomaly_row, typical_rows)

    fig.suptitle("KLAX Runway-Conditioned Arrivals: Anomalous vs Typical Comparisons", fontsize=19, y=0.985)
    fig.legend(handles=legend_handles, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 0.952), fontsize=9.2, frameon=True, facecolor="#ffffff", edgecolor="#d7dde5")
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.925])
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--n-anomalies", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.csv)
    scores = pd.read_csv(args.scores)
    build_figure(df, scores, args.output, args.n_anomalies)
    print(args.output)


if __name__ == "__main__":
    main()
