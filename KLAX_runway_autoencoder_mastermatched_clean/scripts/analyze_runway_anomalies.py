#!/usr/bin/env python3
"""Analyze runway-conditioned anomaly scores and generate summary artifacts."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def haversine_nm(lat1, lon1, lat2, lon2):
    r_km = 6371.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    km = r_km * c
    return km * 0.539957


def wrap_to_180(angle):
    return ((angle + 180.0) % 360.0) - 180.0


def build_traj_metrics(point_df: pd.DataFrame) -> pd.DataFrame:
    point_df = point_df.sort_values(["trajectory_id", "time"]).copy()
    point_df["time"] = pd.to_datetime(point_df["time"], utc=True)

    rows = []
    for traj_id, g in point_df.groupby("trajectory_id", sort=False):
        g = g.sort_values("time")
        lat = g["lat"].to_numpy(dtype=float)
        lon = g["lon"].to_numpy(dtype=float)
        hdg = g["heading"].to_numpy(dtype=float)
        runway_bearing = float(g["runway_true_bearing_deg"].dropna().iloc[0]) if g["runway_true_bearing_deg"].notna().any() else np.nan
        thresh_lat = float(g["runway_threshold_lat"].dropna().iloc[0]) if g["runway_threshold_lat"].notna().any() else np.nan
        thresh_lon = float(g["runway_threshold_lon"].dropna().iloc[0]) if g["runway_threshold_lon"].notna().any() else np.nan

        seg_len = haversine_nm(lat[:-1], lon[:-1], lat[1:], lon[1:]) if len(g) > 1 else np.array([0.0])
        path_len = float(np.nansum(seg_len))
        direct_len = float(haversine_nm(lat[0], lon[0], lat[-1], lon[-1]))
        tort = path_len / direct_len if direct_len > 1e-6 else np.nan

        hdg_diff = np.abs(wrap_to_180(hdg - runway_bearing)) if not np.isnan(runway_bearing) else np.full_like(hdg, np.nan)
        max_hdg_diff = float(np.nanmax(hdg_diff)) if len(hdg_diff) else np.nan

        if not np.isnan(thresh_lat) and not np.isnan(thresh_lon):
            d_to_thresh = haversine_nm(lat, lon, thresh_lat, thresh_lon)
            aligned_idx = np.where(hdg_diff <= 15.0)[0]
            aligned_dist = float(d_to_thresh[aligned_idx[0]]) if len(aligned_idx) else np.nan
        else:
            aligned_dist = np.nan

        rows.append(
            {
                "trajectory_id": traj_id,
                "path_len_nm": path_len,
                "direct_len_nm": direct_len,
                "tortuosity": tort,
                "max_heading_diff_deg": max_hdg_diff,
                "first_alignment_dist_nm": aligned_dist,
            }
        )
    return pd.DataFrame(rows)


def runway_summary(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for runway, g in scores.groupby("runway"):
        rows.append(
            {
                "runway": runway,
                "n_trajectories": len(g),
                "mean_score": g["anomaly_score"].mean(),
                "median_score": g["anomaly_score"].median(),
                "p95_score": g["anomaly_score"].quantile(0.95),
                "p99_score": g["anomaly_score"].quantile(0.99),
                "top5_count": int(g["is_top_5pct_anomaly"].sum()),
                "top5_rate": g["is_top_5pct_anomaly"].mean(),
                "top1_count": int(g["is_top_1pct_anomaly"].sum()),
                "top1_rate": g["is_top_1pct_anomaly"].mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("n_trajectories", ascending=False)


def daily_summary(scores: pd.DataFrame) -> pd.DataFrame:
    g = scores.copy()
    g["sample_day"] = pd.to_datetime(g["segment_start_time"], utc=True).dt.strftime("%Y-%m-%d")
    out = (
        g.groupby("sample_day")
        .agg(
            n_trajectories=("trajectory_id", "size"),
            mean_score=("anomaly_score", "mean"),
            median_score=("anomaly_score", "median"),
            p95_score=("anomaly_score", lambda s: s.quantile(0.95)),
            top5_count=("is_top_5pct_anomaly", "sum"),
            top1_count=("is_top_1pct_anomaly", "sum"),
        )
        .reset_index()
    )
    out["top5_rate"] = out["top5_count"] / out["n_trajectories"]
    out["top1_rate"] = out["top1_count"] / out["n_trajectories"]
    return out.sort_values("sample_day")


def explain_cases(scores: pd.DataFrame, traj_metrics: pd.DataFrame) -> pd.DataFrame:
    top6 = scores.head(6).merge(traj_metrics, on="trajectory_id", how="left")

    # runway-local medians for comparison
    local = scores[["trajectory_id", "runway", "n_points", "arrival_corridor", "arrival_mode"]].merge(traj_metrics, on="trajectory_id", how="left")
    med = local.groupby("runway").agg(
        med_points=("n_points", "median"),
        med_path=("path_len_nm", "median"),
        med_tort=("tortuosity", "median"),
        med_align=("first_alignment_dist_nm", "median"),
    )

    explanations = []
    for _, row in top6.iterrows():
        rmed = med.loc[row["runway"]]
        parts = []
        if row.get("arrival_mode") == "VECTORED_FINAL":
            parts.append("classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final")
        if pd.notna(row["tortuosity"]) and pd.notna(rmed["med_tort"]) and row["tortuosity"] > rmed["med_tort"] * 1.15:
            parts.append("its flown path is noticeably less direct than the typical trajectory in the same runway group")
        if pd.notna(row["path_len_nm"]) and pd.notna(rmed["med_path"]) and row["path_len_nm"] > rmed["med_path"] * 1.15:
            parts.append("the trajectory is longer than the runway-specific median, consistent with a widened or delayed turn-in")
        if pd.notna(row["first_alignment_dist_nm"]) and pd.notna(rmed["med_align"]) and row["first_alignment_dist_nm"] < rmed["med_align"] * 0.8:
            parts.append("it appears to align with runway heading later than typical traffic in the same group")
        if pd.notna(row["n_points"]) and pd.notna(rmed["med_points"]) and row["n_points"] < rmed["med_points"] * 0.6:
            parts.append("the segment is shorter than the runway-group median, so partial observation may also contribute to the score")
        if pd.notna(row["max_heading_diff_deg"]) and row["max_heading_diff_deg"] > 60:
            parts.append("the track approaches from a substantially different heading before merging onto final")
        if not parts:
            parts.append("the trajectory departs from the local nominal shape in a moderate but not single-factor way, suggesting a combination of geometry and timing differences")
        explanations.append(" ; ".join(parts))

    top6["explanation"] = explanations
    return top6[
        [
            "runway",
            "flight_id",
            "segment_start_time",
            "arrival_corridor",
            "arrival_mode",
            "n_points",
            "anomaly_score",
            "path_len_nm",
            "tortuosity",
            "first_alignment_dist_nm",
            "max_heading_diff_deg",
            "explanation",
        ]
    ]


def plot_runway_distribution(scores: pd.DataFrame, out_path: Path):
    order = scores.groupby("runway")["trajectory_id"].size().sort_values(ascending=False).index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), dpi=220)
    fig.patch.set_facecolor("white")

    data = [scores.loc[scores["runway"] == rw, "anomaly_score"].values for rw in order]
    bp = axes[0].boxplot(data, tick_labels=order, patch_artist=True, showfliers=False)
    for patch in bp["boxes"]:
        patch.set(facecolor="#dbeafe", edgecolor="#4a6fa5", alpha=0.9)
    for med in bp["medians"]:
        med.set(color="#1f2937", linewidth=1.4)
    axes[0].set_title("Runway-wise Anomaly Score Distribution")
    axes[0].set_xlabel("Runway")
    axes[0].set_ylabel("Anomaly score")
    axes[0].grid(True, alpha=0.15)

    summary = runway_summary(scores)
    axes[1].bar(summary["runway"], summary["top5_rate"], color="#94a3b8", label="Top 5% rate")
    axes[1].bar(summary["runway"], summary["top1_rate"], color="#334155", width=0.45, label="Top 1% rate")
    axes[1].set_title("Runway-wise High-Anomaly Rate")
    axes[1].set_xlabel("Runway")
    axes[1].set_ylabel("Rate")
    axes[1].legend(frameon=True)
    axes[1].grid(True, axis="y", alpha=0.15)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_daily_summary(daily: pd.DataFrame, out_path: Path):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), dpi=220, sharex=True)
    fig.patch.set_facecolor("white")
    x = np.arange(len(daily))
    labels = daily["sample_day"].tolist()

    axes[0].bar(x, daily["top5_count"], color="#64748b", alpha=0.85, label="Top 5% anomaly count")
    axes[0].plot(x, daily["top1_count"], color="#b91c1c", marker="o", linewidth=1.8, label="Top 1% anomaly count")
    axes[0].set_title("Daily Anomaly Count")
    axes[0].set_ylabel("Count")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.15)

    axes[1].plot(x, daily["mean_score"], color="#0f766e", marker="o", linewidth=1.8, label="Mean score")
    axes[1].plot(x, daily["p95_score"], color="#7c3aed", marker="s", linewidth=1.8, label="95th percentile score")
    axes[1].set_title("Daily Anomaly Intensity")
    axes[1].set_ylabel("Score")
    axes[1].set_xlabel("Sample day")
    axes[1].legend()
    axes[1].grid(True, axis="y", alpha=0.15)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_markdown(runway_df: pd.DataFrame, daily_df: pd.DataFrame, top6_df: pd.DataFrame, out_path: Path):
    highest_runway = runway_df.sort_values("mean_score", ascending=False).iloc[0]
    highest_rate = runway_df.sort_values("top5_rate", ascending=False).iloc[0]
    highest_day = daily_df.sort_values("top5_count", ascending=False).iloc[0]
    strongest_day = daily_df.sort_values("p95_score", ascending=False).iloc[0]

    lines = [
        "# KLAX Runway-Conditioned Anomaly Analysis",
        "",
        "## 1. Runway-level score distribution and anomaly rate",
        "",
        runway_df.to_string(index=False),
        "",
        f"Interpretation: Runway {highest_runway['runway']} has the highest mean anomaly score ({highest_runway['mean_score']:.4f}), while runway {highest_rate['runway']} has the highest top-5% anomaly rate ({highest_rate['top5_rate']:.2%}). Smaller runway groups such as 25R and 07L show higher average anomaly levels, which suggests either more irregular approach structure or greater sensitivity to limited sample size.",
        "",
        "## 2. Daily anomaly count and intensity",
        "",
        daily_df.to_string(index=False),
        "",
        f"Interpretation: The largest anomaly count occurs on {highest_day['sample_day']} with {int(highest_day['top5_count'])} top-5% anomalies, while the strongest anomaly intensity appears on {strongest_day['sample_day']} with a 95th-percentile score of {strongest_day['p95_score']:.4f}. Count and intensity should be read together, since some days may have fewer anomalies but more severe individual outliers.",
        "",
        "## 3. Top-6 anomaly interpretation",
        "",
    ]

    for i, row in top6_df.iterrows():
        lines.append(
            f"{i+1}. `Runway {row['runway']}` | `{row['flight_id']}` | score `{row['anomaly_score']:.4f}`: {row['explanation']}."
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--pointwise", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(args.scores)
    pointwise = pd.read_csv(args.pointwise)

    traj_metrics = build_traj_metrics(pointwise)
    runway_df = runway_summary(scores)
    daily_df = daily_summary(scores)
    top6_df = explain_cases(scores, traj_metrics)

    runway_df.to_csv(args.output_dir / "runway_anomaly_summary.csv", index=False)
    daily_df.to_csv(args.output_dir / "daily_anomaly_summary.csv", index=False)
    top6_df.to_csv(args.output_dir / "top6_anomaly_explanations.csv", index=False)

    plot_runway_distribution(scores, args.output_dir / "runway_score_distribution.png")
    plot_daily_summary(daily_df, args.output_dir / "daily_anomaly_trends.png")
    build_markdown(runway_df, daily_df, top6_df, args.output_dir / "ANALYSIS_SUMMARY.md")
    print(args.output_dir)


if __name__ == "__main__":
    main()
