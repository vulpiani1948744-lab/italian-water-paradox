"""
Task 2 - Data analysis and visualisation.

Produces three figures in `outputs/figures/` (dpi=300):
  1. risk_matrix_scatter.png  - precipitation vs. water loss, split into four
     quadrants by the national medians, with the critical quadrant highlighted;
  2. top_losses_bar.png       - the 15 cities with the highest water losses;
  3. macro_area_losses.png    - distribution of losses by ISTAT macro-area;
  4. risk_matrix_scatter_multiyear.png - the risk matrix on 2012-2022
     averages of both variables (robustness check).

Colour choices: one neutral hue for "context" cities and one accent hue for
cities in the critical quadrant. Text always uses neutral ink, never the
series colour, so the charts stay readable in greyscale prints.
"""

import logging

import matplotlib

matplotlib.use("Agg")  # headless backend: no window needed to save files

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src import config
from src.analysis import add_risk_classification, top_critical_cities

logger = logging.getLogger(__name__)

# --- Palette (validated reference palette, light mode) ----------------------
COLOR_BASE = "#2a78d6"      # blue  - all non-critical cities
COLOR_CRITICAL = "#eb6834"  # orange - critical quadrant
COLOR_SURFACE = "#fcfcfb"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#52514e"
COLOR_GRID = "#e4e3df"


def _apply_style() -> None:
    """Shared, quiet styling: light grid, no top/right spines."""
    sns.set_theme(style="whitegrid", font_scale=1.0)
    plt.rcParams.update({
        "figure.facecolor": COLOR_SURFACE,
        "axes.facecolor": COLOR_SURFACE,
        "axes.edgecolor": COLOR_GRID,
        "axes.labelcolor": COLOR_TEXT,
        "axes.titlecolor": COLOR_TEXT,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": COLOR_GRID,
        "grid.linewidth": 0.8,
        "xtick.color": COLOR_TEXT_MUTED,
        "ytick.color": COLOR_TEXT_MUTED,
        "legend.frameon": False,
    })


def _save(fig: plt.Figure, filename: str) -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / filename
    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figure %s", path)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _label_points(fig: plt.Figure, ax: plt.Axes, rows: pd.DataFrame) -> None:
    """Name the given cities without letting labels overlap.

    Greedy placement: for each city (highest loss first) try a few positions
    around the point and keep the first whose box does not collide with an
    earlier label, cover another labelled point, or leave the axes.
    """
    # (dx, dy) in points, horizontal alignment
    candidates = [(10, 0, "left"), (-10, 0, "right"), (0, -15, "center"),
                  (0, 15, "center"), (10, -15, "left"), (10, 15, "left"),
                  (-10, -15, "right"), (-10, 15, "right"), (10, -30, "left"),
                  (-10, -30, "right")]
    renderer = fig.canvas.get_renderer()
    axes_box = ax.get_window_extent(renderer)
    points = ax.transData.transform(rows[[config.COL_PRECIP, config.COL_LOSS]].to_numpy())
    placed = []

    for i, (_, row) in sorted(enumerate(rows.iterrows()),
                              key=lambda item: -item[1][1][config.COL_LOSS]):
        for dx, dy, ha in candidates:
            ann = ax.annotate(
                row[config.COL_CITY_LABEL],
                xy=(row[config.COL_PRECIP], row[config.COL_LOSS]),
                xytext=(dx, dy), textcoords="offset points", ha=ha, va="center",
                fontsize=9.5, fontweight="bold", color=COLOR_TEXT,
                arrowprops=dict(arrowstyle="-", color=COLOR_TEXT_MUTED, lw=0.8),
                zorder=4,
            )
            box = ann.get_window_extent(renderer).expanded(1.08, 1.25)
            others = [p for j, p in enumerate(points) if j != i]
            clear = (
                not any(box.overlaps(b) for b in placed)
                and not any(box.contains(px, py) for px, py in others)
                and axes_box.contains(box.x0, box.y0) and axes_box.contains(box.x1, box.y1)
            )
            if clear:
                break
            ann.remove()
        else:
            # Every position collides: fall back to the first one.
            dx, dy, ha = candidates[0]
            ann = ax.annotate(
                row[config.COL_CITY_LABEL],
                xy=(row[config.COL_PRECIP], row[config.COL_LOSS]),
                xytext=(dx, dy), textcoords="offset points", ha=ha, va="center",
                fontsize=9.5, fontweight="bold", color=COLOR_TEXT,
                arrowprops=dict(arrowstyle="-", color=COLOR_TEXT_MUTED, lw=0.8),
                zorder=4,
            )
            box = ann.get_window_extent(renderer)
        placed.append(box)


def plot_risk_matrix(df: pd.DataFrame, filename: str = "risk_matrix_scatter.png",
                     period: str = None, averaged: bool = False) -> None:
    """Scatterplot of precipitation vs. water loss split into four quadrants.

    `averaged=True` labels the axes as multi-year averages; `period` defaults
    to the dataset's year.
    """
    if period is None:
        period = str(df[config.COL_YEAR].max())
    df = add_risk_classification(df)
    med_precip = df[config.COL_PRECIP].median()
    med_loss = df[config.COL_LOSS].median()

    fig, ax = plt.subplots(figsize=(11, 7.5))

    # Axis limits with padding, fixed before shading so the quadrant fills them.
    x_pad = 0.05 * np.ptp(df[config.COL_PRECIP])
    y_pad = 0.08 * np.ptp(df[config.COL_LOSS])
    x_min, x_max = df[config.COL_PRECIP].min() - x_pad, df[config.COL_PRECIP].max() + x_pad
    y_min, y_max = max(0, df[config.COL_LOSS].min() - y_pad), df[config.COL_LOSS].max() + y_pad
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    # Critical quadrant: low precipitation (left) AND high losses (top).
    ax.fill_between(
        [x_min, med_precip], med_loss, y_max,
        color=COLOR_CRITICAL, alpha=0.08, zorder=0, linewidth=0,
    )

    # National median reference lines.
    ax.axvline(med_precip, color=COLOR_TEXT_MUTED, linestyle="--", linewidth=1.2, zorder=1)
    ax.axhline(med_loss, color=COLOR_TEXT_MUTED, linestyle="--", linewidth=1.2, zorder=1)

    # Points: context cities first, critical cities on top.
    for is_critical, color, label in [
        (False, COLOR_BASE, "Other provincial capitals"),
        (True, COLOR_CRITICAL, "Critical quadrant"),
    ]:
        subset = df[df["Is_Critical"] == is_critical]
        ax.scatter(
            subset[config.COL_PRECIP], subset[config.COL_LOSS],
            s=60, color=color, edgecolor=COLOR_SURFACE, linewidth=1.5,
            alpha=0.9, zorder=3, label=f"{label} (n={len(subset)})",
        )

    # Quadrant captions in the corners.
    corner_style = dict(fontsize=9, color=COLOR_TEXT_MUTED, style="italic")
    ax.text(x_min + x_pad * 0.3, y_max - y_pad * 0.3,
            "CRITICAL\nlow rainfall · high losses",
            ha="left", va="top", fontweight="bold", **{**corner_style, "color": COLOR_TEXT})
    ax.text(x_max - x_pad * 0.3, y_max - y_pad * 0.3,
            "Wet but leaky\nhigh rainfall · high losses", ha="right", va="top", **corner_style)
    ax.text(x_min + x_pad * 0.3, y_min + y_pad * 0.3,
            "Dry but efficient\nlow rainfall · low losses", ha="left", va="bottom", **corner_style)
    ax.text(x_max - x_pad * 0.3, y_min + y_pad * 0.3,
            "Low risk\nhigh rainfall · low losses", ha="right", va="bottom", **corner_style)

    # Median values next to the reference lines.
    ax.text(med_precip, y_min, f" median {med_precip:.0f} mm",
            rotation=90, va="bottom", ha="right", fontsize=8, color=COLOR_TEXT_MUTED)
    ax.text(x_max, med_loss, f"median {med_loss:.1f}% ",
            va="bottom", ha="right", fontsize=8, color=COLOR_TEXT_MUTED)

    _label_points(fig, ax, top_critical_cities(df, 5))

    prefix = "Average " if averaged else ""
    ax.set_xlabel(f"{prefix}{'t' if averaged else 'T'}otal annual precipitation (mm)")
    ax.set_ylabel(f"{prefix}{'w' if averaged else 'W'}ater losses in distribution network (%)")
    ax.set_title(f"The Italian Water Paradox: rainfall vs. network losses ({period})", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)
    fig.text(0.01, -0.04, "Source: ISTAT - water losses in distribution networks; "
             "Rilevazione dati meteoclimatici ed idrologici. Dashed lines = national medians.",
             fontsize=8, color=COLOR_TEXT_MUTED)
    _save(fig, filename)


def plot_top_losses(df: pd.DataFrame, n: int = 15, filename: str = "top_losses_bar.png") -> None:
    """Horizontal bar chart of the n cities with the highest water losses."""
    df = add_risk_classification(df)
    top = df.nlargest(n, config.COL_LOSS)
    national_median = df[config.COL_LOSS].median()

    fig, ax = plt.subplots(figsize=(10, 7.5))
    colors = [COLOR_CRITICAL if c else COLOR_BASE for c in top["Is_Critical"]]
    # Horizontal bars keep city names readable; worst city at the top.
    bars = ax.barh(
        top[config.COL_CITY_LABEL], top[config.COL_LOSS],
        color=colors, height=0.72, edgecolor=COLOR_SURFACE, linewidth=2,
    )
    ax.invert_yaxis()

    for bar, value in zip(bars, top[config.COL_LOSS]):
        ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}%", va="center", fontsize=9, color=COLOR_TEXT)

    ax.axvline(national_median, color=COLOR_TEXT_MUTED, linestyle="--", linewidth=1.2)
    ax.text(national_median, -0.6, f" national median {national_median:.1f}%",
            fontsize=8.5, color=COLOR_TEXT_MUTED, va="bottom")

    ax.set_xlim(0, top[config.COL_LOSS].max() * 1.12)
    ax.set_xlabel("Water losses in distribution network (%)")
    ax.set_ylabel("")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Top {n} provincial capitals by water losses", loc="left")

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOR_CRITICAL),
        plt.Rectangle((0, 0), 1, 1, color=COLOR_BASE),
    ]
    ax.legend(handles, ["Also below-median rainfall (critical)", "Above-median rainfall"],
              loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
    _save(fig, filename)


def plot_macro_area_losses(df: pd.DataFrame, filename: str = "macro_area_losses.png") -> None:
    """Box plot + individual cities: how losses vary across ISTAT macro-areas."""
    order = [a for a in config.MACRO_AREA_ORDER if a in set(df[config.COL_MACRO])]

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.boxplot(
        data=df, x=config.COL_MACRO, y=config.COL_LOSS, order=order, ax=ax,
        color="#d6e4f5", width=0.55, fliersize=0, linewidth=1.2,
        medianprops=dict(color=COLOR_TEXT, linewidth=2),
    )
    sns.stripplot(
        data=df, x=config.COL_MACRO, y=config.COL_LOSS, order=order, ax=ax,
        color=COLOR_BASE, size=6, jitter=0.18, alpha=0.8,
        edgecolor=COLOR_SURFACE, linewidth=1,
    )

    counts = df[config.COL_MACRO].value_counts()
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([f"{a}\n(n={counts[a]})" for a in order])
    ax.axhline(df[config.COL_LOSS].median(), color=COLOR_TEXT_MUTED, linestyle="--", linewidth=1.2)
    ax.set_xlabel("")
    ax.set_ylabel("Water losses in distribution network (%)")
    ax.set_title("Water losses by ISTAT macro-area (dashed = national median)", loc="left")
    _save(fig, filename)


def run(df: pd.DataFrame, multiyear: pd.DataFrame = None) -> None:
    """Generate every figure for the project."""
    _apply_style()
    plot_risk_matrix(df)
    plot_top_losses(df)
    plot_macro_area_losses(df)
    if multiyear is not None:
        plot_risk_matrix(multiyear, "risk_matrix_scatter_multiyear.png",
                         period=f"average of {len(config.PANEL_YEARS)} years, "
                                f"{config.PERIOD_LABEL}",
                         averaged=True)
