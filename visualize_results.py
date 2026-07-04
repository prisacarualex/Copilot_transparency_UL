"""
visualize_results.py  –  Multi-session analysis for the Copilot Transparency study.

Loads all labeled session CSVs, computes per-session and per-30s-bin metrics,
classifies cognitive control modes, and saves a figure to sessions/analysis.png.

Usage:
    python visualize_results.py [sessions_dir]     (default: ./sessions)
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless – no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Tunable thresholds (from the study rubric) ───────────────────────────────
TRACKING_RMSE_THRESHOLD = 35.0   # px  – above = Reactive
RESMAN_DEV_THRESHOLD    = 150.0  # units – above = Reactive
BIN_SIZE_SEC            = 30

COLORS = {"transparent": "#2196F3", "opaque": "#F44336"}


# ── I/O helpers ──────────────────────────────────────────────────────────────

def _safe_float(v: str) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def load_session(path: Path) -> dict:
    """Parse a single session CSV into a structured dict."""
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})

    # Detect condition
    condition = "unknown"
    for r in rows:
        if r.get("module") == "copilot" and r.get("address") == "transparency":
            condition = r.get("value", "unknown")
            break

    # Collect timed rows
    timed: list[tuple[float, dict]] = []
    for r in rows:
        t = _safe_float(r.get("scenario_time", ""))
        if t is not None:
            timed.append((t, r))

    return {"path": path, "condition": condition, "timed": timed}


MAX_SESSION_MB = 50  # skip files larger than this (e.g. runaway debug logs)


def load_all_sessions(sessions_dir: Path) -> list[dict]:
    labeled = []
    for csv_path in sorted(sessions_dir.rglob("*.csv")):
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_SESSION_MB:
            print(f"  Skipping {csv_path.name} ({size_mb:.0f} MB, exceeds {MAX_SESSION_MB} MB limit)")
            continue
        s = load_session(csv_path)
        if s["condition"] in ("transparent", "opaque"):
            labeled.append(s)
    return labeled


# ── Per-session metric computation ───────────────────────────────────────────

def _rmse(values: list[float]) -> float:
    if not values:
        return float("nan")
    return math.sqrt(sum(v ** 2 for v in values) / len(values))


def _mean_abs(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(abs(v) for v in values) / len(values)


def compute_session_metrics(session: dict) -> dict:
    timed = session["timed"]
    if not timed:
        return {}

    max_t = max(t for t, _ in timed)
    n_bins = math.ceil(max_t / BIN_SIZE_SEC) if max_t > 0 else 1

    bins: list[dict] = []
    track_ts:  list[float] = []
    track_rmse_series: list[float] = []

    for i in range(n_bins):
        t0, t1 = i * BIN_SIZE_SEC, (i + 1) * BIN_SIZE_SEC
        bin_rows = [(t, r) for t, r in timed if t0 <= t < t1]

        devs: list[float] = []
        ra, rb = [], []
        sdt_hits = sdt_misses = sdt_fa = 0

        for t, r in bin_rows:
            m, addr, val = r.get("module"), r.get("address"), r.get("value", "")
            rtype = r.get("type")

            if rtype == "performance":
                if m == "track" and addr == "center_deviation":
                    v = _safe_float(val)
                    if v is not None:
                        devs.append(v)
                elif m == "resman" and addr == "a_deviation":
                    v = _safe_float(val)
                    if v is not None:
                        ra.append(v)
                elif m == "resman" and addr == "b_deviation":
                    v = _safe_float(val)
                    if v is not None:
                        rb.append(v)
                elif m == "sysmon" and addr == "signal_detection":
                    if val == "HIT":
                        sdt_hits += 1
                    elif val == "MISS":
                        sdt_misses += 1
                    elif val == "FA":
                        sdt_fa += 1

        tracking_rmse = _rmse(devs)
        mean_a = _mean_abs(ra)
        mean_b = _mean_abs(rb)

        valid_res = [x for x in [mean_a, mean_b] if not math.isnan(x)]
        resman_dev = sum(valid_res) / len(valid_res) if valid_res else float("nan")

        is_reactive = False
        if not math.isnan(tracking_rmse) and tracking_rmse >= TRACKING_RMSE_THRESHOLD:
            is_reactive = True
        if not math.isnan(resman_dev) and resman_dev >= RESMAN_DEV_THRESHOLD:
            is_reactive = True

        bins.append({
            "bin": i + 1,
            "t_mid": (t0 + t1) / 2,
            "tracking_rmse": tracking_rmse,
            "resman_dev": resman_dev,
            "is_reactive": is_reactive,
            "sdt_hits": sdt_hits,
            "sdt_misses": sdt_misses,
            "sdt_fa": sdt_fa,
        })

        track_ts.append((t0 + t1) / 2)
        track_rmse_series.append(tracking_rmse)

    valid_bins = [b for b in bins if not (math.isnan(b["tracking_rmse"]) and math.isnan(b["resman_dev"]))]
    proactive_pct = (
        sum(1 for b in valid_bins if not b["is_reactive"]) / len(valid_bins) * 100
        if valid_bins else float("nan")
    )
    total_hits   = sum(b["sdt_hits"]   for b in bins)
    total_misses = sum(b["sdt_misses"] for b in bins)
    total_fa     = sum(b["sdt_fa"]     for b in bins)
    total_det    = total_hits + total_misses
    hit_rate     = total_hits / total_det if total_det > 0 else float("nan")

    all_track = [b["tracking_rmse"] for b in bins if not math.isnan(b["tracking_rmse"])]
    mean_track_rmse = sum(all_track) / len(all_track) if all_track else float("nan")

    all_res = [b["resman_dev"] for b in bins if not math.isnan(b["resman_dev"])]
    mean_resman_dev = sum(all_res) / len(all_res) if all_res else float("nan")

    return {
        "session_id": session["path"].stem.split("_")[0],
        "condition": session["condition"],
        "n_bins": len(valid_bins),
        "proactive_pct": proactive_pct,
        "mean_track_rmse": mean_track_rmse,
        "mean_resman_dev": mean_resman_dev,
        "hit_rate": hit_rate,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "total_fa": total_fa,
        "bins": bins,
        "track_ts": track_ts,
        "track_rmse_series": track_rmse_series,
    }


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_results(metrics: list[dict], out_path: Path) -> None:
    transparent = [m for m in metrics if m["condition"] == "transparent"]
    opaque      = [m for m in metrics if m["condition"] == "opaque"]

    def _vals(group: list[dict], key: str) -> list[float]:
        return [m[key] for m in group if not math.isnan(m.get(key, float("nan")))]

    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(
        "Co-Pilot Transparency Study — Preliminary Results\n"
        f"(Transparent n={len(transparent)}, Opaque n={len(opaque)}; "
        f"{len(metrics)} total labeled sessions)",
        fontsize=14, fontweight="bold", y=0.98,
    )

    gs = fig.add_gridspec(3, 3, hspace=0.50, wspace=0.38)

    ax_pp  = fig.add_subplot(gs[0, 0])   # Proactive % bar
    ax_tr  = fig.add_subplot(gs[0, 1])   # Mean tracking RMSE bar
    ax_rd  = fig.add_subplot(gs[0, 2])   # Mean resman dev bar
    ax_hr  = fig.add_subplot(gs[1, 0])   # Hit-rate bar
    ax_ts  = fig.add_subplot(gs[1, 1:])  # Tracking RMSE time-series
    ax_rm  = fig.add_subplot(gs[2, 0:2]) # Resman dev time-series
    ax_sdt = fig.add_subplot(gs[2, 2])   # SDT stacked bar

    # ── Helper: simple group bar ──────────────────────────────────────────
    def _bar2(ax, t_vals, o_vals, title, ylabel, lower_better=False):
        t_mean = np.nanmean(t_vals) if t_vals else 0
        o_mean = np.nanmean(o_vals) if o_vals else 0
        bars = ax.bar(
            ["Transparent", "Opaque"],
            [t_mean, o_mean],
            color=[COLORS["transparent"], COLORS["opaque"]],
            edgecolor="black", linewidth=0.7, width=0.5,
        )
        # Individual dots
        for j, (grp, col) in enumerate(zip([t_vals, o_vals], COLORS.values())):
            ax.scatter(
                [j] * len(grp), grp,
                color="black", zorder=5, s=30, alpha=0.6,
            )
        ax.set_title(title, fontsize=10, pad=6)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Transparent", "Opaque"], fontsize=9)
        ax.tick_params(axis="y", labelsize=8)
        # Annotate with values
        for bar, v in zip(bars, [t_mean, o_mean]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ax.get_ylim()[1] * 0.01,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=8)

    # ── 1. Proactive % ────────────────────────────────────────────────────
    _bar2(ax_pp,
          _vals(transparent, "proactive_pct"),
          _vals(opaque,      "proactive_pct"),
          "% Time in Proactive Mode", "Proactive %")
    ax_pp.set_ylim(0, 110)
    ax_pp.axhline(50, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)

    # ── 2. Mean tracking RMSE ─────────────────────────────────────────────
    _bar2(ax_tr,
          _vals(transparent, "mean_track_rmse"),
          _vals(opaque,      "mean_track_rmse"),
          "Mean Tracking RMSE (px)", "RMSE (px)", lower_better=True)
    ax_tr.axhline(TRACKING_RMSE_THRESHOLD, color="orange", linestyle="--",
                  linewidth=0.9, alpha=0.7, label=f"Reactive threshold ({TRACKING_RMSE_THRESHOLD})")
    ax_tr.legend(fontsize=7)

    # ── 3. Mean resman deviation ──────────────────────────────────────────
    _bar2(ax_rd,
          _vals(transparent, "mean_resman_dev"),
          _vals(opaque,      "mean_resman_dev"),
          "Mean ResMan Tank Deviation", "Deviation (units)", lower_better=True)
    ax_rd.axhline(RESMAN_DEV_THRESHOLD, color="orange", linestyle="--",
                  linewidth=0.9, alpha=0.7, label=f"Threshold ({RESMAN_DEV_THRESHOLD})")
    ax_rd.legend(fontsize=7)

    # ── 4. Sysmon hit rate ────────────────────────────────────────────────
    _bar2(ax_hr,
          [m["hit_rate"] for m in transparent if not math.isnan(m["hit_rate"])],
          [m["hit_rate"] for m in opaque      if not math.isnan(m["hit_rate"])],
          "SysMon Hit Rate", "Hit Rate (0–1)")
    ax_hr.set_ylim(0, 1.15)

    # ── 5. Tracking RMSE time-series per session ──────────────────────────
    for m in transparent:
        ts = m["track_ts"]
        rs = m["track_rmse_series"]
        valid = [(t, r) for t, r in zip(ts, rs) if not math.isnan(r)]
        if valid:
            tx, rx = zip(*valid)
            ax_ts.plot(tx, rx, color=COLORS["transparent"], alpha=0.55, linewidth=1.2)
    for m in opaque:
        ts = m["track_ts"]
        rs = m["track_rmse_series"]
        valid = [(t, r) for t, r in zip(ts, rs) if not math.isnan(r)]
        if valid:
            tx, rx = zip(*valid)
            ax_ts.plot(tx, rx, color=COLORS["opaque"], alpha=0.55, linewidth=1.2,
                       linestyle="--")

    ax_ts.axhline(TRACKING_RMSE_THRESHOLD, color="orange", linestyle=":", linewidth=1.0,
                  label=f"Reactive threshold ({TRACKING_RMSE_THRESHOLD} px)")
    ax_ts.set_title("Tracking RMSE over Time (per session)", fontsize=10)
    ax_ts.set_xlabel("Scenario time (s)", fontsize=9)
    ax_ts.set_ylabel("RMSE (px)", fontsize=9)
    ax_ts.legend(
        handles=[
            mpatches.Patch(color=COLORS["transparent"], label="Transparent"),
            mpatches.Patch(color=COLORS["opaque"],      label="Opaque (dashed)"),
            plt.Line2D([0], [0], color="orange", linestyle=":", label=f"Threshold ({TRACKING_RMSE_THRESHOLD})"),
        ],
        fontsize=8,
    )

    # ── 6. Resman deviation time-series ───────────────────────────────────
    for m in transparent:
        ts = [b["t_mid"]     for b in m["bins"] if not math.isnan(b["resman_dev"])]
        rs = [b["resman_dev"] for b in m["bins"] if not math.isnan(b["resman_dev"])]
        if ts:
            ax_rm.plot(ts, rs, color=COLORS["transparent"], alpha=0.55, linewidth=1.2)
    for m in opaque:
        ts = [b["t_mid"]     for b in m["bins"] if not math.isnan(b["resman_dev"])]
        rs = [b["resman_dev"] for b in m["bins"] if not math.isnan(b["resman_dev"])]
        if ts:
            ax_rm.plot(ts, rs, color=COLORS["opaque"], alpha=0.55, linewidth=1.2,
                       linestyle="--")
    ax_rm.axhline(RESMAN_DEV_THRESHOLD, color="orange", linestyle=":", linewidth=1.0)
    ax_rm.set_title("ResMan Deviation over Time (per session)", fontsize=10)
    ax_rm.set_xlabel("Scenario time (s)", fontsize=9)
    ax_rm.set_ylabel("Mean |deviation| (units)", fontsize=9)
    ax_rm.legend(
        handles=[
            mpatches.Patch(color=COLORS["transparent"], label="Transparent"),
            mpatches.Patch(color=COLORS["opaque"],      label="Opaque (dashed)"),
            plt.Line2D([0], [0], color="orange", linestyle=":", label=f"Threshold ({RESMAN_DEV_THRESHOLD})"),
        ],
        fontsize=8,
    )

    # ── 7. SDT stacked bar ────────────────────────────────────────────────
    groups = ["Transparent", "Opaque"]
    hits   = [sum(m["total_hits"]   for m in g) for g in [transparent, opaque]]
    misses = [sum(m["total_misses"] for m in g) for g in [transparent, opaque]]
    fas    = [sum(m["total_fa"]       for m in m_list) for m_list in [transparent, opaque]]
    x = np.arange(len(groups))
    ax_sdt.bar(x, hits,   label="HIT",  color="#4CAF50", edgecolor="black", linewidth=0.7)
    ax_sdt.bar(x, misses, label="MISS", color="#FF9800", bottom=hits,
               edgecolor="black", linewidth=0.7)
    fa_bottom = [h + m for h, m in zip(hits, misses)]
    ax_sdt.bar(x, fas,   label="FA",   color="#9C27B0", bottom=fa_bottom,
               edgecolor="black", linewidth=0.7)
    ax_sdt.set_xticks(x)
    ax_sdt.set_xticklabels(groups, fontsize=9)
    ax_sdt.set_title("SysMon Signal Detection\n(total across sessions)", fontsize=10)
    ax_sdt.set_ylabel("Count", fontsize=9)
    ax_sdt.legend(fontsize=8)

    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    print(f"Figure saved → {out_path}")


# ── Console summary ───────────────────────────────────────────────────────────

def print_summary(metrics: list[dict]) -> None:
    SEP = "=" * 72
    sep = "-" * 72
    print()
    print(SEP)
    print("       CO-PILOT TRANSPARENCY STUDY — SESSION SUMMARY")
    print(SEP)
    print(f"  {'ID':<5} {'Condition':<13} {'Proactive%':>10} {'Trk RMSE':>10} "
          f"{'Res Dev':>10} {'HitRate':>9} {'Hits':>6} {'Miss':>6} {'FA':>6}")
    print(sep)
    for m in sorted(metrics, key=lambda x: (x["condition"], x["session_id"])):
        pp  = f"{m['proactive_pct']:.1f}" if not math.isnan(m['proactive_pct'])  else "N/A"
        tr  = f"{m['mean_track_rmse']:.1f}" if not math.isnan(m['mean_track_rmse']) else "N/A"
        rd  = f"{m['mean_resman_dev']:.1f}" if not math.isnan(m['mean_resman_dev']) else "N/A"
        hr  = f"{m['hit_rate']:.2f}" if not math.isnan(m['hit_rate']) else "N/A"
        fa = m.get('total_fa', 0)
        print(f"  {m['session_id']:<5} {m['condition']:<13} {pp:>10} {tr:>10} "
              f"{rd:>10} {hr:>9} {m['total_hits']:>6} {m['total_misses']:>6} {fa:>6}")
    print(sep)

    for cond in ("transparent", "opaque"):
        grp = [m for m in metrics if m["condition"] == cond]
        if not grp:
            continue
        pp_vals  = [m["proactive_pct"]  for m in grp if not math.isnan(m["proactive_pct"])]
        tr_vals  = [m["mean_track_rmse"] for m in grp if not math.isnan(m["mean_track_rmse"])]
        rd_vals  = [m["mean_resman_dev"] for m in grp if not math.isnan(m["mean_resman_dev"])]
        hr_vals  = [m["hit_rate"]        for m in grp if not math.isnan(m["hit_rate"])]
        print(f"  {cond.upper()} (n={len(grp)})")
        print(f"    Proactive %   mean={np.mean(pp_vals):.1f}  sd={np.std(pp_vals):.1f}"  if pp_vals else "    Proactive % N/A")
        print(f"    Tracking RMSE mean={np.mean(tr_vals):.1f}  sd={np.std(tr_vals):.1f}" if tr_vals else "    Tracking RMSE N/A")
        print(f"    ResMan Dev    mean={np.mean(rd_vals):.1f}  sd={np.std(rd_vals):.1f}"  if rd_vals else "    ResMan Dev N/A")
        print(f"    Hit rate      mean={np.mean(hr_vals):.2f}  sd={np.std(hr_vals):.2f}" if hr_vals else "    Hit rate N/A")
        print()
    print(SEP)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    sessions_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sessions")
    if not sessions_dir.exists():
        print(f"Error: sessions directory not found – {sessions_dir}")
        sys.exit(1)

    print(f"Loading sessions from {sessions_dir} …")
    sessions = load_all_sessions(sessions_dir)
    print(f"Found {len(sessions)} labeled session(s).")

    if not sessions:
        print("No labeled sessions found (need copilot;transparency;transparent/opaque events).")
        sys.exit(0)

    metrics = [compute_session_metrics(s) for s in sessions]
    metrics = [m for m in metrics if m]

    print_summary(metrics)

    out = sessions_dir / "analysis.png"
    plot_results(metrics, out)


if __name__ == "__main__":
    main()
