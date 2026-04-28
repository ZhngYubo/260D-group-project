#!/usr/bin/env python3
"""Train pointwise arrival autoencoders separately by runway."""

from __future__ import annotations

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
import joblib
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split


def wrap_to_180(angle_deg: np.ndarray) -> np.ndarray:
    return ((angle_deg + 180.0) % 360.0) - 180.0


def interp_series(values: np.ndarray, n_samples: int) -> np.ndarray:
    if len(values) == 1:
        return np.repeat(values, n_samples)
    src = np.linspace(0.0, 1.0, len(values))
    dst = np.linspace(0.0, 1.0, n_samples)
    return np.interp(dst, src, values)


def compute_track_angle(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    lat_rad = np.deg2rad(lat_deg)
    lon_rad = np.deg2rad(lon_deg)
    dlon = np.diff(lon_rad, prepend=lon_rad[0])
    dlat = np.diff(lat_rad, prepend=lat_rad[0])
    mean_lat = (lat_rad + np.roll(lat_rad, 1)) / 2.0
    mean_lat[0] = lat_rad[0]
    x = dlon * np.cos(mean_lat)
    y = dlat
    heading = np.rad2deg(np.arctan2(x, y))
    heading = (heading + 360.0) % 360.0
    if len(heading) > 1:
        heading[0] = heading[1]
    return heading


def build_features(df: pd.DataFrame, n_samples: int) -> tuple[pd.DataFrame, np.ndarray]:
    rows = []
    feats = []
    df = df.sort_values(["trajectory_id", "time"]).copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)

    for traj_id, g in df.groupby("trajectory_id", sort=False):
        g = g.sort_values("time")
        if len(g) < 10 or g["runway"].isna().all():
            continue
        lat = g["lat"].astype(float).to_numpy()
        lon = g["lon"].astype(float).to_numpy()
        track = compute_track_angle(lat, lon)
        runway_bearing = float(g["runway_true_bearing_deg"].dropna().iloc[0]) if g["runway_true_bearing_deg"].notna().any() else track[-1]
        heading_rel = wrap_to_180(track - runway_bearing)
        heading_rel = interp_series(heading_rel, n_samples)

        alt_col = "baroaltitude" if g["baroaltitude"].notna().any() else "geoaltitude"
        alt = g[alt_col].astype(float).interpolate(limit_direction="both").bfill().ffill().to_numpy()
        alt = interp_series(alt, n_samples)
        alt = alt - alt[-1]

        feat = np.concatenate([heading_rel, alt])
        feats.append(feat)
        rows.append(
            {
                "trajectory_id": traj_id,
                "flight_id": g["flight_id"].iloc[0],
                "segment_start_time": g["segment_start_time"].iloc[0],
                "segment_end_time": g["segment_end_time"].iloc[0],
                "callsign": g["callsign"].iloc[0],
                "runway": g["runway"].iloc[0],
                "arrival_corridor": g["arrival_corridor"].iloc[0] if "arrival_corridor" in g else None,
                "arrival_mode": g["arrival_mode"].iloc[0] if "arrival_mode" in g else None,
                "n_points": len(g),
            }
        )
    return pd.DataFrame(rows), np.asarray(feats)


def train_per_runway(
    meta: pd.DataFrame,
    feats: np.ndarray,
    min_samples: int,
    seed: int,
    holdout_fraction: float,
    model_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    holdout_frames = []
    train_frames = []
    stats_rows = []
    trained_runways = []

    if model_dir is not None:
        model_dir.mkdir(parents=True, exist_ok=True)

    for runway, group in meta.groupby("runway"):
        if len(group) < min_samples:
            continue
        idx = group.index.to_numpy()
        X = feats[idx]
        local_meta = group.reset_index(drop=True).copy()
        local_idx = np.arange(len(local_meta))

        train_idx, holdout_idx = train_test_split(
            local_idx,
            test_size=holdout_fraction,
            random_state=seed,
            shuffle=True,
        )
        train_meta = local_meta.iloc[train_idx].reset_index(drop=True)
        holdout_meta = local_meta.iloc[holdout_idx].reset_index(drop=True)
        X_train = X[train_idx]
        X_holdout = X[holdout_idx]

        scaler = MinMaxScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_holdout_s = scaler.transform(X_holdout)
        input_dim = X_train_s.shape[1]
        hidden_a = min(64, max(16, input_dim // 2))
        hidden_b = min(24, max(6, input_dim // 6))
        model = MLPRegressor(
            hidden_layer_sizes=(hidden_a, hidden_b, hidden_a),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            random_state=seed,
            max_iter=1200,
            early_stopping=True,
            validation_fraction=0.15,
        )
        model.fit(X_train_s, X_train_s)
        train_recon = model.predict(X_train_s)
        holdout_recon = model.predict(X_holdout_s)
        train_mse = ((train_recon - X_train_s) ** 2).mean(axis=1)
        holdout_mse = ((holdout_recon - X_holdout_s) ** 2).mean(axis=1)
        q95 = float(np.quantile(train_mse, 0.95))
        q99 = float(np.quantile(train_mse, 0.99))

        train_frame = train_meta.copy()
        train_frame["dataset_split"] = "train"
        train_frame["anomaly_score"] = train_mse
        train_frame["is_top_5pct_anomaly"] = train_mse >= q95
        train_frame["is_top_1pct_anomaly"] = train_mse >= q99
        train_frames.append(train_frame)

        holdout_frame = holdout_meta.copy()
        holdout_frame["dataset_split"] = "holdout"
        holdout_frame["anomaly_score"] = holdout_mse
        holdout_frame["is_top_5pct_anomaly"] = holdout_mse >= q95
        holdout_frame["is_top_1pct_anomaly"] = holdout_mse >= q99
        holdout_frames.append(holdout_frame)
        trained_runways.append(str(runway))
        stats_rows.append(
            {
                "runway": runway,
                "n_trajectories": len(local_meta),
                "n_train": len(train_meta),
                "n_holdout": len(holdout_meta),
                "train_loss": float(model.loss_),
                "train_score_mean": float(train_mse.mean()),
                "train_score_std": float(train_mse.std()),
                "train_score_p95": q95,
                "train_score_p99": q99,
                "holdout_score_mean": float(holdout_mse.mean()),
                "holdout_score_std": float(holdout_mse.std()),
                "holdout_score_p95": float(np.quantile(holdout_mse, 0.95)),
                "holdout_score_p99": float(np.quantile(holdout_mse, 0.99)),
                "best_train_score": float(train_mse.min()),
                "worst_train_score": float(train_mse.max()),
                "best_holdout_score": float(holdout_mse.min()),
                "worst_holdout_score": float(holdout_mse.max()),
            }
        )
        if model_dir is not None:
            joblib.dump(
                {
                    "runway": runway,
                    "scaler": scaler,
                    "model": model,
                    "n_samples": int(X_train_s.shape[1] // 2),
                    "feature_order": ["relative_heading", "relative_altitude"],
                    "input_dim": int(X_train_s.shape[1]),
                    "hidden_layer_sizes": list(model.hidden_layer_sizes),
                    "seed": int(seed),
                    "holdout_fraction": float(holdout_fraction),
                    "train_q95": q95,
                    "train_q99": q99,
                },
                model_dir / f"runway_{runway}_autoencoder.joblib",
            )
    if model_dir is not None:
        metadata = {
            "model_family": "runway-conditioned pointwise autoencoder",
            "estimator": "sklearn.neural_network.MLPRegressor",
            "trained_runways": trained_runways,
            "min_samples": int(min_samples),
            "seed": int(seed),
            "holdout_fraction": float(holdout_fraction),
        }
        (model_dir / "model_metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
    return (
        pd.concat(holdout_frames, ignore_index=True).sort_values("anomaly_score", ascending=False),
        pd.concat(train_frames, ignore_index=True).sort_values("anomaly_score", ascending=False),
        pd.DataFrame(stats_rows).sort_values("n_trajectories", ascending=False),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.csv)
    meta, feats = build_features(df, args.samples)
    model_dir = args.output_dir / "models"
    holdout_scores, train_scores, stats = train_per_runway(
        meta,
        feats,
        args.min_samples,
        args.seed,
        args.holdout_fraction,
        model_dir=model_dir,
    )
    holdout_scores.to_csv(args.output_dir / "runway_pointwise_anomaly_scores.csv", index=False)
    train_scores.to_csv(args.output_dir / "runway_pointwise_train_scores.csv", index=False)
    stats.to_csv(args.output_dir / "runway_pointwise_model_stats.csv", index=False)
    holdout_scores.head(50).to_csv(args.output_dir / "runway_pointwise_top_anomalies.csv", index=False)
    run_metadata = {
        "input_csv": str(args.csv),
        "output_dir": str(args.output_dir),
        "n_trajectories": int(len(meta)),
        "n_trained_runways": int(stats["runway"].nunique()),
        "samples_per_feature": int(args.samples),
        "feature_vector_dim": int(feats.shape[1]) if len(feats) else 0,
        "min_samples": int(args.min_samples),
        "seed": int(args.seed),
        "holdout_fraction": float(args.holdout_fraction),
    }
    (args.output_dir / "training_run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2),
        encoding="utf-8",
    )
    print(args.output_dir)


if __name__ == "__main__":
    main()
