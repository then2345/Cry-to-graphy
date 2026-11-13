"""
Vẽ sơ đồ luồng chương trình benchmark -> fig_flow.png
Chạy: python flow_diagram.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

steps = [
    ("Input", "Load dataset\n(TXT / IMG / BIN)\nverify SHA-256"),
    ("Setup", "Fresh 256-bit key\ncipher object\nnonce counter"),
    ("Warm-up", "5 encrypt–decrypt\npairs (not timed)"),
    ("Encrypt", "t0 → encrypt() → t1\nperf_counter_ns"),
    ("Decrypt", "t2 → decrypt() → t3\nperf_counter_ns"),
    ("Validate", "plaintext == input?\n(outside timer)"),
    ("Output", "raw_measurements.csv\n→ summary.csv, plots"),
]
timed = {"Encrypt", "Decrypt"}

fig, ax = plt.subplots(figsize=(15, 3.4))
ax.set_xlim(0, len(steps) * 2.1)
ax.set_ylim(-0.6, 3.4)
ax.axis("off")
for i, (title, body) in enumerate(steps):
    x = i * 2.1 + 0.1
    color = "#fde68a" if title in timed else "#dbeafe"
    ax.add_patch(FancyBboxPatch((x, 0.6), 1.75, 2.0, boxstyle="round,pad=0.05",
                                fc=color, ec="#1e3a8a", lw=1.4))
    ax.text(x + 0.875, 2.25, title, ha="center", va="center", fontsize=11, weight="bold")
    ax.text(x + 0.875, 1.35, body, ha="center", va="center", fontsize=8.5)
    if i < len(steps) - 1:
        ax.annotate("", xy=(x + 2.05, 1.6), xytext=(x + 1.85, 1.6),
                    arrowprops=dict(arrowstyle="->", lw=1.6))
# vòng lặp 30 lần
x0, x1 = 3 * 2.1 + 0.5, 5 * 2.1 + 1.4
ax.annotate("", xy=(x0, 0.55), xytext=(x1, 0.55),
            arrowprops=dict(arrowstyle="->", lw=1.3, connectionstyle="arc3,rad=-0.25", color="#b91c1c"))
ax.text((x0 + x1) / 2, -0.45, "repeat 30 rounds × 2 algorithms (alternating order), 9 datasets",
        ha="center", fontsize=9, color="#b91c1c")
ax.text(0.1, 3.1, "Yellow = timed region (only the API call)", fontsize=9, color="#92400e")
fig.tight_layout()
fig.savefig("fig_flow.png", dpi=200)
print("fig_flow.png saved")
