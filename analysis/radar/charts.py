"""Shared matplotlib style for every chart in outputs/ (same colours as inspect_sample.py).

PRD section 11: every chart has a title, labelled axes, the sample size and a
one-line interpretation, and keeps observed facts apart from heuristic flags.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"     # categorical slots 1-3
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"  # status: genuine / mixed / suspicious
INK, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
SURFACE = "#fcfcfb"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def new_figure(width=7.0, height=4.2):
    fig, ax = plt.subplots(figsize=(width, height), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    return fig, ax


def style(ax, grid_axis="y"):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(BASE)
    ax.tick_params(colors=MUTED, length=0, labelsize=8.5)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def finish(fig, ax, title, caption, path):
    """Title on the left, interpretation + sample note underneath, then save."""
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    fig.text(0.01, 0.01, caption, fontsize=7.5, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)
