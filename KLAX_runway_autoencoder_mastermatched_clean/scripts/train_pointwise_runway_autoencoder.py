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
    model_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_frames = []
    stats_rows = []
    trained_runways = []

    if model_dir is not None:
        model_dir.mkdir(parents=True, exist_ok=True)

    for runway, group in meta.groupby("runway"):
        if len(group) < min_samples:
            continue
        idx = group.index.to_numpy()
        X = feats[idx]
        scaler = MinMaxScaler()
        Xs = scaler.fit_transform(X)
        input_dim = Xs.shape[1]
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
        model.fit(Xs, Xs)
        recon = model.predict(Xs)
        sample_mse = ((recon - Xs) ** 2).mean(axis=1)
        q95 = float(np.quantile(sample_mse, 0.95))
        q99 = float(np.quantile(sample_mse, 0.99))
        frame = group.copy()
        frame["anomaly_score"] = sample_mse
        frame["is_top_5pct_anomaly"] = sample_mse >= q95
        frame["is_top_1pct_anomaly"] = sample_mse >= q99
        score_frames.append(frame)
        trained_runways.append(str(runway))
        stats_rows.append(
            {
                "runway": runway,
                "n_trajectories": len(group),
                "train_loss": float(model.loss_),
                "score_mean": float(sample_mse.mean()),
                "score_std": float(sample_mse.std()),
                "score_p95": q95,
                "score_p99": q99,
                "best_score": float(sample_mse.min()),
                "worst_score": float(sample_mse.max()),
            }
        )
        if model_dir is not None:
            joblib.dump(
                {
                    "runway": runway,
                    "scaler": scaler,
                    "model": model,
                    "n_samples": int(Xs.shape[1] // 2),
                    "feature_order": ["relative_heading", "relative_altitude"],
                    "input_dim": int(Xs.shape[1]),
                    "hidden_layer_sizes": list(model.hidden_layer_sizes),
                    "seed": int(seed),
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
        }
        (model_dir / "model_metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
    return (
        pd.concat(score_frames, ignore_index=True).sort_values("anomaly_score", ascending=False),
        pd.DataFrame(stats_rows).sort_values("n_trajectories", ascending=False),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.csv)
    meta, feats = build_features(df, args.samples)
    model_dir = args.output_dir / "models"
    scores, stats = train_per_runway(meta, feats, args.min_samples, args.seed, model_dir=model_dir)
    scores.to_csv(args.output_dir / "runway_pointwise_anomaly_scores.csv", index=False)
    stats.to_csv(args.output_dir / "runway_pointwise_model_stats.csv", index=False)
    scores.head(50).to_csv(args.output_dir / "runway_pointwise_top_anomalies.csv", index=False)
    run_metadata = {
        "input_csv": str(args.csv),
        "output_dir": str(args.output_dir),
        "n_trajectories": int(len(meta)),
        "n_trained_runways": int(stats["runway"].nunique()),
        "samples_per_feature": int(args.samples),
        "feature_vector_dim": int(feats.shape[1]) if len(feats) else 0,
        "min_samples": int(args.min_samples),
        "seed": int(args.seed),
    }
    (args.output_dir / "training_run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2),
        encoding="utf-8",
    )
    print(args.output_dir)


if __name__ == "__main__":
    main()
