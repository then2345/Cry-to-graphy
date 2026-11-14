"""
Thống kê + biểu đồ theo Experimental Design mục 5-6
Input : raw_measurements.csv (+ config.json để biết số lần đo mỗi scenario)
Output: summary.csv (18 dòng), fig_latency.png, fig_throughput.png

Chạy: pip install pandas matplotlib
      python analyze.py

Chương trình dừng với exit code 1 nếu dữ liệu thô hoặc bảng tổng hợp không khớp
18 scenario (2 thuật toán × 9 dataset) hoặc không khớp measured_pairs trong config.json.
"""
import argparse
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ALGS = ["AES-256-GCM", "ChaCha20-Poly1305"]
TYPES = ["text", "image", "binary"]
DATASET_ORDER = ["TXT01", "TXT05", "TXT10", "IMG01", "IMG05", "IMG10",
                 "BIN01", "BIN05", "BIN10"]
EXPECTED_SCENARIOS = len(ALGS) * len(DATASET_ORDER)
COLORS = {"AES-256-GCM": "#2563eb", "ChaCha20-Poly1305": "#ea580c"}


def t_critical(df: int) -> float:
    """95% two-sided Student t critical value, rounded to 3 decimals.

    df < 10 uses tabulated values; larger df uses the Cornish-Fisher expansion,
    which reproduces the published table to <0.001 for df >= 8 (df=29 -> 2.045).
    """
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
             6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
    if df in table:
        return table[df]
    if df < 1:
        raise ValueError("df must be >= 1")
    z = 1.959963984540054
    z2 = z * z
    z3 = z2 * z
    z5 = z3 * z2
    z7 = z5 * z2
    z9 = z7 * z2
    value = (z
             + (z3 + z) / (4 * df)
             + (5 * z5 + 16 * z3 + 3 * z) / (96 * df ** 2)
             + (3 * z7 + 19 * z5 + 17 * z3 - 15 * z) / (384 * df ** 3)
             + (79 * z9 + 776 * z7 + 1482 * z5 - 1920 * z3 - 945 * z) / (92160 * df ** 4))
    return round(value, 3)


def summarize(raw):
    rows = []
    for (alg, ds), g in raw.groupby(["algorithm", "dataset_id"], sort=False):
        B = int(g["actual_size_bytes"].iloc[0])
        r = {"session_id": g["session_id"].iloc[0], "protocol_version": g["protocol_version"].iloc[0],
             "scenario_id": f"{alg}|{ds}", "algorithm": alg, "dataset_id": ds,
             "data_type": g["data_type"].iloc[0], "actual_size_bytes": B, "n": len(g)}
        tcrit = t_critical(len(g) - 1)
        for op in ("enc", "dec"):
            ms = g[f"{op}_ns"] / 1e6
            mean, sd = ms.mean(), ms.std(ddof=1)
            half = tcrit * sd / math.sqrt(len(ms))
            r.update({f"{op}_mean_ms": mean, f"{op}_sd_ms": sd, f"{op}_median_ms": ms.median(),
                      f"{op}_ci95_low_ms": mean - half, f"{op}_ci95_high_ms": mean + half,
                      # tổng MB / tổng giây (không lấy trung bình các rate)
                      f"{op}_MB_s": (B * len(g) / 1e6) / (g[f"{op}_ns"].sum() / 1e9)})
        r["overhead_bytes"] = int(g["overhead_bytes"].iloc[0])
        r["overhead_pct"] = 100 * r["overhead_bytes"] / B
        rows.append(r)
    return pd.DataFrame(rows)


def plot_latency(s, runs):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    for row, (op, label) in enumerate([("enc", "Encryption"), ("dec", "Decryption")]):
        for col, t in enumerate(TYPES):
            ax = axes[row][col]
            for alg in ALGS:
                d = s[(s.algorithm == alg) & (s.data_type == t)].sort_values("actual_size_bytes")
                x = d["actual_size_bytes"] / 1e6
                err = d[f"{op}_mean_ms"] - d[f"{op}_ci95_low_ms"]
                ax.errorbar(x, d[f"{op}_mean_ms"], yerr=err, marker="o", capsize=4,
                            label=alg, color=COLORS[alg])
            ax.set_title(f"{label} – {t}")
            ax.set_xlabel("Input size (MB)")
            ax.set_ylabel("Mean latency (ms)")
            ax.grid(alpha=0.3)
    axes[0][0].legend()
    fig.suptitle(f"Mean latency vs input size (error bars: 95% CI, n = {runs})")
    fig.tight_layout()
    fig.savefig("fig_latency.png", dpi=200)


def plot_throughput(s):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    order = DATASET_ORDER
    w = 0.38
    error_bars_drawn = True
    for ax, (op, label) in zip(axes, [("enc", "Encryption"), ("dec", "Decryption")]):
        for i, alg in enumerate(ALGS):
            d = s[s.algorithm == alg].set_index("dataset_id").loc[order]
            xs = [k + (i - 0.5) * w for k in range(len(order))]
            mean = d[f"{op}_MB_s"]
            # B/mean(t) chỉ đổi được thành khoảng tin cậy hữu hạn khi cận dưới CI của
            # latency > 0; với ít lần đo, CI có thể chạm 0 và cận trên throughput là vô hạn.
            ci_low = d[f"{op}_ci95_low_ms"]
            if (ci_low <= 0).any():
                bad = ", ".join(d.index[ci_low <= 0])
                print(f"WARNING: {label} throughput error bars omitted: "
                      f"95% CI lower latency <= 0 for {bad}")
                error_bars_drawn = False
                ax.bar(xs, mean, width=w, label=alg, color=COLORS[alg])
            else:
                mb = d["actual_size_bytes"] / 1e6
                lo = mb / (d[f"{op}_ci95_high_ms"] / 1e3)   # throughput ứng với cận trên latency
                hi = mb / (ci_low / 1e3)                    # throughput ứng với cận dưới latency
                yerr = [mean - lo, hi - mean]
                ax.bar(xs, mean, width=w, label=alg, color=COLORS[alg],
                       yerr=yerr, capsize=3, error_kw={"elinewidth": 1})
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, rotation=45)
        ax.set_title(f"{label} throughput")
        ax.set_ylabel("Throughput (MB/s, 1 MB = 10^6 B)")
        ax.grid(axis="y", alpha=0.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    note = ("Error bars: throughput at the 95% CI bounds of mean latency" if error_bars_drawn
            else "Error bars omitted where the 95% CI of mean latency includes 0")
    fig.text(0.5, 0.015, note, ha="center", fontsize=9)
    fig.savefig("fig_throughput.png", dpi=200)


def validate_raw(raw, measured_pairs=None):
    """Fail fast on incomplete or inconsistent measurements."""
    if raw["algorithm"].nunique() != len(ALGS):
        sys.exit(f"ERROR: expected {len(ALGS)} algorithms, found {raw['algorithm'].nunique()}")
    if raw["dataset_id"].nunique() != len(DATASET_ORDER):
        sys.exit(f"ERROR: expected {len(DATASET_ORDER)} datasets, "
                 f"found {raw['dataset_id'].nunique()}")
    counts = raw.groupby(["algorithm", "dataset_id"], observed=True).size()
    if len(counts) != EXPECTED_SCENARIOS:
        sys.exit(f"ERROR: expected {EXPECTED_SCENARIOS} scenarios, found {len(counts)}")
    n = int(counts.iloc[0])
    if counts.nunique() != 1:
        sys.exit("ERROR: scenarios have different run counts: "
                 + ", ".join(f"{k}={v}" for k, v in counts.items() if v != n))
    if measured_pairs is not None and n != measured_pairs:
        sys.exit(f"ERROR: raw data has {n} runs per scenario, "
                 f"config.json measured_pairs = {measured_pairs}")
    if n < 2:
        sys.exit(f"ERROR: need at least 2 measured runs per scenario for SD/CI, found {n}")
    if len(raw) != EXPECTED_SCENARIOS * n:
        sys.exit(f"ERROR: expected {EXPECTED_SCENARIOS * n} raw rows, found {len(raw)}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw_measurements.csv")
    ap.add_argument("--summary", default="summary.csv")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    raw = pd.read_csv(args.raw)
    measured_pairs = None
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            measured_pairs = int(json.load(f)["measured_pairs"])
    runs = validate_raw(raw, measured_pairs)

    s = summarize(raw)
    if len(s) != EXPECTED_SCENARIOS:
        sys.exit(f"ERROR: expected {EXPECTED_SCENARIOS} summary rows, found {len(s)}")
    s.to_csv(args.summary, index=False)
    plot_latency(s, runs)
    plot_throughput(s)

    # Bảng gọn cho báo cáo
    pd.set_option("display.width", 200)
    view = s[["algorithm", "dataset_id", "enc_mean_ms", "enc_sd_ms", "dec_mean_ms",
              "enc_MB_s", "dec_MB_s", "overhead_bytes"]].round(3)
    print(view.to_string(index=False))
    print(f"\n{args.summary}: {len(s)} rows (n = {runs} per scenario); "
          f"{len(raw)} raw rows; figures: fig_latency.png, fig_throughput.png")


if __name__ == "__main__":
    main()
