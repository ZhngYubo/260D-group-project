#!/usr/bin/env python3
"""Merge pointwise segments with master runway labels by trajectory_id."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


MASTER_KEEP = [
    "trajectory_id",
    "runway",
    "runway_true_bearing_deg",
    "runway_threshold_lat",
    "runway_threshold_lon",
    "arrival_corridor",
    "runway_flow",
    "arrival_mode",
    "operational_flow_label",
    "entry_sector",
    "entry_lat",
    "entry_lon",
    "final_lat",
    "final_lon",
    "final_heading_deg",
    "match_score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", required=True, type=Path)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--airport", default="KLAX")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seg = pd.read_csv(args.segments)
    master = pd.read_csv(args.master, usecols=MASTER_KEEP)

    merged = seg.merge(master, on="trajectory_id", how="left", suffixes=("", "_master"))
    merged = merged[merged["airport_icao"] == args.airport].copy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)
    print(args.output)
    print("rows", len(merged))
    print("trajectory_ids", merged["trajectory_id"].nunique())


if __name__ == "__main__":
    main()
