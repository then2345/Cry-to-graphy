"""
Thống kê + biểu đồ theo Experimental Design mục 5-6
Input : raw_measurements.csv
Output: summary.csv (18 dòng), fig_latency.png, fig_throughput.png

Chạy: pip install pandas matplotlib
      python analyze.py
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

T_CRIT = 2.045  # Student t, df = 29
ALGS = ["AES-256-GCM", "ChaCha20-Poly1305"]
TYPES = ["text", "image", "binary"]
COLORS = {"AES-256-GCM": "#2563eb", "ChaCha20-Poly1305": "#ea580c"}


def summarize(raw):
    rows = []
    for (alg, ds), g in raw.groupby(["algorithm", "dataset_id"], sort=False):
        B = int(g["actual_size_bytes"].iloc[0])
        r = {"session_id": g["session_id"].iloc[0], "protocol_version": g["protocol_version"].iloc[0],
             "scenario_id": f"{alg}|{ds}", "algorithm": alg, "dataset_id": ds,
             "data_type": g["data_type"].iloc[0], "actual_size_bytes": B, "n": len(g)}
        for op in ("enc", "dec"):
            ms = g[f"{op}_ns"] / 1e6
            mean, sd = ms.mean(), ms.std(ddof=1)
            half = T_CRIT * sd / math.sqrt(len(ms))
            r.update({f"{op}_mean_ms": mean, f"{op}_sd_ms": sd, f"{op}_median_ms": ms.median(),
                      f"{op}_ci95_low_ms": mean - half, f"{op}_ci95_high_ms": mean + half,
                      # tổng MB / tổng giây (không lấy trung bình các rate)
                      f"{op}_MB_s": (B * len(g) / 1e6) / (g[f"{op}_ns"].sum() / 1e9)})
        r["overhead_bytes"] = int(g["overhead_bytes"].iloc[0])
        r["overhead_pct"] = 100 * r["overhead_bytes"] / B
        rows.append(r)
    return pd.DataFrame(rows)


def plot_latency(s):
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
    fig.suptitle("Mean latency vs input size (error bars: 95% CI, n = 30)")
    fig.tight_layout()
    fig.savefig("fig_latency.png", dpi=200)


def plot_throughput(s):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    order = ["TXT01", "TXT05", "TXT10", "IMG01", "IMG05", "IMG10", "BIN01", "BIN05", "BIN10"]
    w = 0.38
    for ax, (op, label) in zip(axes, [("enc", "Encryption"), ("dec", "Decryption")]):
        for i, alg in enumerate(ALGS):
            d = s[s.algorithm == alg].set_index("dataset_id").loc[order]
            xs = [k + (i - 0.5) * w for k in range(len(order))]
            ax.bar(xs, d[f"{op}_MB_s"], width=w, label=alg, color=COLORS[alg])
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, rotation=45)
        ax.set_title(f"{label} throughput")
        ax.set_ylabel("Throughput (MB/s, 1 MB = 10^6 B)")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig("fig_throughput.png", dpi=200)


def main():
    raw = pd.read_csv("raw_measurements.csv")
    s = summarize(raw)
    s.to_csv("summary.csv", index=False)
    plot_latency(s)
    plot_throughput(s)

    # Bảng gọn cho báo cáo
    pd.set_option("display.width", 200)
    view = s[["algorithm", "dataset_id", "enc_mean_ms", "enc_sd_ms", "dec_mean_ms",
              "enc_MB_s", "dec_MB_s", "overhead_bytes"]].round(3)
    print(view.to_string(index=False))
    print(f"\nsummary.csv: {len(s)} rows (expected 18); figures: fig_latency.png, fig_throughput.png")


if __name__ == "__main__":
    main()
