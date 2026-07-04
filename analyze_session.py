"""
analyze_session.py  –  Post-process an OpenMATB session CSV.

Usage:
    python3 analyze_session.py <path_to_session_csv>

No third-party packages required (stdlib only).
"""

import csv
import math
import sys
from pathlib import Path

# Quantitative rubric thresholds for Cognitive Control Strategy classification
TRACKING_RMSE_THRESHOLD = 35.0  # Pixels: above → Reactive
RESMAN_DEV_THRESHOLD = 150.0    # Fuel units: above → Reactive
BIN_SIZE_SEC = 30


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _rmse(values: list[float]) -> float:
    if not values:
        return float("nan")
    return math.sqrt(sum(v ** 2 for v in values) / len(values))


def _mean_abs(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(abs(v) for v in values) / len(values)


def parse_session_file(file_path: str) -> None:
    p = Path(file_path)
    if not p.exists():
        print(f"Error: file not found – {file_path}")
        sys.exit(1)

    print(f"Analyzing: {file_path}")

    rows: list[dict[str, str]] = []
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})

    # Parse scenario_time
    valid_rows: list[tuple[float, dict[str, str]]] = []
    for row in rows:
        t = _safe_float(row.get("scenario_time", ""))
        if t is not None:
            valid_rows.append((t, row))

    if not valid_rows:
        print("Error: no valid scenario_time found in log.")
        sys.exit(1)

    max_time = max(t for t, _ in valid_rows)
    num_bins = math.ceil(max_time / BIN_SIZE_SEC)

    bins_data: list[dict] = []

    for i in range(num_bins):
        t_start = i * BIN_SIZE_SEC
        t_end = (i + 1) * BIN_SIZE_SEC

        bin_rows = [(t, r) for t, r in valid_rows if t_start <= t < t_end]

        # Tracking RMSE (centre_deviation performance entries)
        track_devs: list[float] = []
        for t, r in bin_rows:
            if r.get("module") == "track" and r.get("address") == "center_deviation":
                v = _safe_float(r.get("value", ""))
                if v is not None:
                    track_devs.append(v)
        tracking_rmse = _rmse(track_devs)

        # Resman mean absolute deviation of tanks A and B from target (2500)
        resman_a: list[float] = []
        resman_b: list[float] = []
        for t, r in bin_rows:
            if r.get("module") == "resman":
                addr = r.get("address", "")
                v = _safe_float(r.get("value", ""))
                if v is None:
                    continue
                if addr == "a_deviation":
                    resman_a.append(v)
                elif addr == "b_deviation":
                    resman_b.append(v)

        mean_a = _mean_abs(resman_a)
        mean_b = _mean_abs(resman_b)

        if not math.isnan(mean_a) and not math.isnan(mean_b):
            resman_dev = (mean_a + mean_b) / 2.0
        elif not math.isnan(mean_a):
            resman_dev = mean_a
        elif not math.isnan(mean_b):
            resman_dev = mean_b
        else:
            resman_dev = float("nan")

        # Classify control mode
        is_proactive = True
        if not math.isnan(tracking_rmse) and tracking_rmse >= TRACKING_RMSE_THRESHOLD:
            is_proactive = False
        if not math.isnan(resman_dev) and resman_dev >= RESMAN_DEV_THRESHOLD:
            is_proactive = False

        bins_data.append(
            {
                "bin_index": i + 1,
                "time_range": f"{t_start}s-{t_end}s",
                "tracking_rmse": tracking_rmse,
                "resman_dev": resman_dev,
                "status": "Proactive" if is_proactive else "Reactive",
            }
        )

    # Survey responses (genericscales performance entries)
    surveys: dict[str, str] = {}
    for _t, r in valid_rows:
        if r.get("module") == "genericscales" and r.get("type") == "performance":
            addr = r.get("address", "")
            val = r.get("value", "")
            if addr and _safe_float(val) is not None:
                surveys[addr] = val  # last value wins (final slider position)

    # ─── Print results ───────────────────────────────────────────────────────
    total_bins = len(bins_data)
    proactive_bins = sum(1 for b in bins_data if b["status"] == "Proactive")
    proactive_pct = (proactive_bins / total_bins * 100) if total_bins > 0 else 0.0

    SEP = "=" * 62
    sep = "-" * 62
    print()
    print(SEP)
    print("          OPENMATB COGNITIVE CONTROL ANALYSIS")
    print(SEP)
    print(f"  Session file      : {Path(file_path).name}")
    print(f"  Total 30s bins    : {total_bins}")
    print(f"  Proactive bins    : {proactive_bins}  ({proactive_pct:.1f}%)")
    print(f"  Reactive  bins    : {total_bins - proactive_bins}  ({100 - proactive_pct:.1f}%)")
    print(sep)
    print(f"  Rubric thresholds : Track RMSE < {TRACKING_RMSE_THRESHOLD} px  |  Resman Dev < {RESMAN_DEV_THRESHOLD} units")
    print(sep)
    print(f"  {'Bin':<4}  {'Interval':<13}  {'Track RMSE':>10}  {'Resman Dev':>10}  {'Mode':<10}")
    print(sep)
    for b in bins_data:
        rmse_s = f"{b['tracking_rmse']:>10.2f}" if not math.isnan(b["tracking_rmse"]) else f"{'N/A':>10}"
        rdev_s = f"{b['resman_dev']:>10.2f}" if not math.isnan(b["resman_dev"]) else f"{'N/A':>10}"
        print(f"  {b['bin_index']:<4}  {b['time_range']:<13}  {rmse_s}  {rdev_s}  {b['status']:<10}")

    print()
    print(SEP)
    print("          POST-EXPERIMENT SURVEY RESPONSES")
    print(SEP)
    if surveys:
        for question, score in surveys.items():
            print(f"  {question:<30} : {score}")
    else:
        print("  No survey responses found in this session.")
    print(SEP)
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_session.py <path_to_session_csv>")
        sys.exit(1)
    parse_session_file(sys.argv[1])

