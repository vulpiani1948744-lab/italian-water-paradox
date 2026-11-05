"""
Task 3 - Automated reporting.

Gathers the results of `src/analysis.py` and writes them, with a narrative
that follows the numbers, into a Markdown report (`outputs/report.md`).
Nothing is hard-coded, so re-running the pipeline on new ISTAT data
refreshes every figure and every conclusion.
"""

import logging
from datetime import date

import numpy as np
import pandas as pd

from src import config
from src.analysis import (
    add_risk_classification,
    macro_area_regression,
    pearson_with_pvalue,
    summarise_dataset,
    terrain_regressions,
    top_critical_cities,
)

logger = logging.getLogger(__name__)


def describe_correlation(r: float, p: float) -> str:
    """Plain-language reading of a correlation coefficient."""
    strength = (
        "negligible" if abs(r) < 0.1 else
        "weak" if abs(r) < 0.3 else
        "moderate" if abs(r) < 0.5 else
        "strong"
    )
    direction = "positive" if r > 0 else "negative"
    significance = (
        "statistically significant at the 5% level"
        if p < 0.05 else "not statistically significant at the 5% level"
    )
    return f"a {strength} {direction} linear relationship, {significance}"


def interpret_correlation(r: float, p: float) -> str:
    """Narrative paragraph whose conclusion follows the sign and significance of r."""
    share = r ** 2 * 100
    text = (
        f"The Pearson coefficient indicates {describe_correlation(r, p)}. "
        f"Precipitation explains only about {share:.0f}% of the variance in "
        f"water losses (r² = {r ** 2:.3f}). "
    )
    if p >= 0.05 or abs(r) < 0.1:
        text += (
            "Network losses are therefore essentially independent of how much "
            "rain a city receives: they depend on how the network is built and "
            "managed, not on the climate. This is the *paradox* - the cities "
            "that can least afford to waste water are not, on average, any "
            "better at retaining it."
        )
    elif r > 0:
        text += (
            "The sign is the *paradox*: wetter cities tend to lose slightly "
            "*more* water, not less, and drier cities are not systematically "
            "better at retaining it. Section 4 checks whether this simply "
            "reflects the North-South divide. The correlation should not be "
            "read as causal."
        )
    else:
        text += (
            "Drier cities tend to lose *more* water: scarcity and inefficiency "
            "compound each other, which is exactly the scenario the critical "
            "quadrant is designed to isolate."
        )
    return text


def interpret_terrain(reg: dict) -> str:
    """Narrative for the altitude test, following the estimates of model B."""
    rain_a, rain_b, alt = reg["A"]["rain"], reg["B"]["rain"], reg["B"]["terrain"]
    shrink = (1 - rain_b["coef"] / rain_a["coef"]) * 100
    text = (
        f"Adding the altitude of the town centre changes the rainfall "
        f"coefficient from {rain_a['coef']:+.2f} to {rain_b['coef']:+.2f} "
        f"percentage points per 100 mm ({shrink:.0f}% smaller). "
    )
    if rain_b["p"] < 0.05:
        text += (
            "Rainfall **remains significant** (p ≈ {:.3f}), so altitude does "
            "**not** explain the rainfall-loss relationship: the terrain "
            "hypothesis is not supported as a full explanation. ".format(rain_b["p"])
        )
    else:
        text += (
            "Rainfall is **no longer significant** (p ≈ {:.3f}): once altitude "
            "is accounted for, the rainfall effect largely disappears, which "
            "supports the terrain hypothesis. ".format(rain_b["p"])
        )
    if alt["p"] < 0.05:
        text += (
            f"Altitude has its own effect: every 100 m of altitude is associated "
            f"with {alt['coef']:+.1f} percentage points of losses (p ≈ {alt['p']:.3f}), "
            f"independently of rainfall and macro-area."
        )
    else:
        text += (
            f"Altitude itself is not significant once rainfall and macro-area "
            f"are in the model (p ≈ {alt['p']:.3f})."
        )

    rain_c, relief = reg["C"]["rain"], reg["C"]["terrain"]
    if relief["p"] < 0.05:
        text += (
            f"\n\nTerrain relief tells a clearer story than altitude: towns with "
            f"more uneven terrain lose more water ({relief['coef']:+.1f} "
            f"percentage points per 100 m of standard deviation, p ≈ "
            f"{relief['p']:.3f}), consistent with the idea that height "
            f"differences within the network, rather than height itself, make "
            f"it harder to keep tight. With relief in the model the rainfall "
            f"coefficient falls to {rain_c['coef']:+.2f} "
            f"({(1 - rain_c['coef'] / rain_a['coef']) * 100:.0f}% smaller) but "
            + ("stays significant (p ≈ {:.3f}). Terrain explains part of the "
               "rainfall effect, not all of it.".format(rain_c["p"])
               if rain_c["p"] < 0.05 else
               "is no longer significant (p ≈ {:.3f}): terrain relief accounts "
               "for the rainfall effect.".format(rain_c["p"]))
        )
    else:
        text += (
            f"\n\nTerrain relief is not significant either (p ≈ {relief['p']:.3f})."
        )
    return text


def interpret_regression(reg: dict) -> str:
    """Narrative for the macro-area control, following the estimated coefficient."""
    text = (
        f"Macro-area alone explains {reg['r2_area_only'] * 100:.0f}% of the "
        f"variance in water losses; adding precipitation raises this to "
        f"{reg['r2_full'] * 100:.0f}%. Holding the macro-area constant, every "
        f"additional 100 mm of rain is associated with "
        f"{reg['coef_per_100mm']:+.1f} percentage points of losses "
        f"(t = {reg['t']:.2f}, p ≈ {reg['p']:.3f}; partial correlation "
        f"r = {reg['partial_r']:.2f}). "
    )
    if reg["p"] < 0.05:
        text += (
            "The rainfall-loss relationship therefore **persists within "
            "macro-areas**: it is not explained by the North-South divide. "
            "One plausible explanation is terrain: hill and mountain towns "
            "receive more rain and also run networks with steeper gradients "
            "and higher pressures, which are harder to keep tight. Section 5 "
            "tests this with ISTAT altitude data."
        )
    else:
        text += (
            "Once the macro-area is taken into account the relationship is no "
            "longer significant: the raw correlation mostly reflects the "
            "territorial divide in network performance."
        )
    return text


def interpret_robustness(single: dict, multi: dict) -> str:
    """Does the 2022 conclusion survive when both variables are averaged?"""
    same_sign = np.sign(single["r"]) == np.sign(multi["r"])
    rain_multi = multi["terrain"]["A"]["rain"]
    if same_sign and multi["p"] < 0.05 and single["p"] < 0.05:
        text = (
            f"The main result **holds**: with multi-year averages the correlation "
            f"is r = {multi['r']:.3f} (p ≈ {multi['p']:.3f}), the same sign as in "
            f"{config.CLIMATE_YEAR} (r = {single['r']:.3f}), so it is not an "
            f"artefact of the {config.CLIMATE_YEAR} drought. "
        )
    elif multi["p"] >= 0.05:
        text = (
            f"The national correlation **does not hold**: with multi-year "
            f"averages it is r = {multi['r']:.3f} and no longer significant "
            f"(p ≈ {multi['p']:.3f}). The {config.CLIMATE_YEAR} value was a "
            f"product of that year's unusual rainfall pattern. "
        )
    else:
        text = (
            f"The relationship **changes sign**: r = {multi['r']:.3f} on "
            f"multi-year averages (p ≈ {multi['p']:.3f}) against "
            f"r = {single['r']:.3f} in {config.CLIMATE_YEAR}. "
        )
    text += (
        f"\n\n**Why: two opposite patterns.** The national correlation mixes a "
        f"comparison *between* macro-areas with one *within* them. Between "
        f"macro-areas, the correlation of the five area averages is "
        f"r = {multi['between_r']:.2f} on multi-year data"
    )
    if multi["between_r"] < 0:
        text += (
            ": in a normal period the wetter North also has the most efficient "
            "networks, while the drier South and Islands lose the most water. "
            "At the national scale, scarcity and inefficiency therefore go "
            "together. "
        )
    else:
        text += ". "
    text += (
        f"Within macro-areas the relationship goes the other way (partial "
        f"r = {multi['within_r']:.2f}; rainfall coefficient "
        f"{rain_multi['coef']:+.2f} pp per 100 mm, p ≈ {rain_multi['p']:.3f}): "
        f"among cities of the same area, the wetter ones lose slightly more. "
        f"In {config.CLIMATE_YEAR} the drought made the North almost as dry as "
        f"the South (between-area r = {single['between_r']:.2f}), which hid the "
        f"first pattern and left only the second. The between-area figure "
        f"rests on five averages and is descriptive only.\n\n"
    )
    relief_single = single["terrain"]["C"]["terrain"]
    relief_multi = multi["terrain"]["C"]["terrain"]
    if relief_single["p"] < 0.05 and relief_multi["p"] >= 0.05:
        text += (
            f"The terrain-relief effect of Section 5 is **not robust**: on "
            f"multi-year averages it shrinks to {relief_multi['coef']:+.2f} pp "
            f"per 100 m (p ≈ {relief_multi['p']:.3f}), so it should be treated "
            f"as a {config.CLIMATE_YEAR}-specific finding. "
        )
    common = single["critical_cities"] & multi["critical_cities"]
    text += (
        f"The critical quadrant contains {multi['n_critical']} cities on "
        f"multi-year averages; {len(common)} of the {single['n_critical']} "
        f"critical cities of {config.CLIMATE_YEAR} are critical in both."
    )
    return text


def compute_insights(df: pd.DataFrame) -> dict:
    """Calculate every metric injected into the report."""
    scored = add_risk_classification(df)
    worst_loss = df.loc[df[config.COL_LOSS].idxmax()]
    best_loss = df.loc[df[config.COL_LOSS].idxmin()]
    driest = df.loc[df[config.COL_PRECIP].idxmin()]
    r, p, n = pearson_with_pvalue(df[config.COL_LOSS], df[config.COL_PRECIP])
    # Spearman rho = Pearson r computed on ranks (avoids a SciPy dependency).
    rho = df[config.COL_LOSS].rank().corr(df[config.COL_PRECIP].rank())

    by_area = (
        df.groupby(config.COL_MACRO)
        .agg(
            Cities=(config.COL_CITY, "count"),
            Median_Loss=(config.COL_LOSS, "median"),
            Mean_Loss=(config.COL_LOSS, "mean"),
            Median_Precip=(config.COL_PRECIP, "median"),
        )
        .reindex([a for a in config.MACRO_AREA_ORDER if a in set(df[config.COL_MACRO])])
    )
    critical_by_area = scored[scored["Is_Critical"]][config.COL_MACRO].value_counts()
    by_area["Critical_Cities"] = critical_by_area.reindex(by_area.index).fillna(0).astype(int)
    by_area["Within_r"] = (
        df.groupby(config.COL_MACRO)[[config.COL_LOSS, config.COL_PRECIP]]
        .apply(lambda g: g[config.COL_LOSS].corr(g[config.COL_PRECIP]))
        .reindex(by_area.index)
    )

    return {
        "year": int(df[config.COL_YEAR].max()),
        "n_cities": n,
        "worst_loss": worst_loss,
        "best_loss": best_loss,
        "driest": driest,
        "median_loss": df[config.COL_LOSS].median(),
        "median_precip": df[config.COL_PRECIP].median(),
        "pearson_r": r,
        "pearson_p": p,
        "spearman_rho": rho,
        "n_critical": int(scored["Is_Critical"].sum()),
        "top_critical": top_critical_cities(df, 5),
        "by_area": by_area,
        "regression": macro_area_regression(df),
        "terrain": terrain_regressions(df),
        "precip_vs_avg": df[config.COL_PRECIP_VS_AVG].median(),
        "precip_vs_avg_by_area": df.groupby(config.COL_MACRO)[config.COL_PRECIP_VS_AVG]
        .median().reindex(by_area.index),
        "driest_vs_avg": df.nsmallest(5, config.COL_PRECIP_VS_AVG),
    }


def _markdown_table(rows: list, headers: list) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _robustness_section(ins: dict) -> str:
    """Markdown comparing the 2022 results with the multi-year averages."""
    single, multi = ins["single"], ins["multi"]
    years = ", ".join(str(y) for y in config.PANEL_YEARS)

    def stars(term: dict) -> str:
        bold = "**" if term["p"] < 0.05 else ""
        return f"{bold}{term['coef']:+.2f}{bold} (p ≈ {term['p']:.3f})"

    rows = [
        ("Cities", single["n"], multi["n"]),
        ("Median water loss", f"{single['median_loss']:.1f}%", f"{multi['median_loss']:.1f}%"),
        ("Median precipitation (mm)", f"{single['median_precip']:.0f}", f"{multi['median_precip']:.0f}"),
        ("Pearson r (loss vs. rain)", f"{single['r']:.3f} (p ≈ {single['p']:.3f})",
         f"{multi['r']:.3f} (p ≈ {multi['p']:.3f})"),
        ("Spearman ρ", f"{single['rho']:.3f}", f"{multi['rho']:.3f}"),
        ("Rain, pp per 100 mm (model A)", stars(single["terrain"]["A"]["rain"]),
         stars(multi["terrain"]["A"]["rain"])),
        ("Altitude, pp per 100 m (model B)", stars(single["terrain"]["B"]["terrain"]),
         stars(multi["terrain"]["B"]["terrain"])),
        ("Terrain relief, pp per 100 m (model C)", stars(single["terrain"]["C"]["terrain"]),
         stars(multi["terrain"]["C"]["terrain"])),
        ("Rain once relief is included (model C)", stars(single["terrain"]["C"]["rain"]),
         stars(multi["terrain"]["C"]["rain"])),
        ("Cities in critical quadrant", single["n_critical"], multi["n_critical"]),
        ("Top 5 critical cities", ", ".join(single["top5"]), ", ".join(multi["top5"])),
    ]
    table = _markdown_table([list(r) for r in rows],
                            ["", f"{config.CLIMATE_YEAR} only", f"Average {config.PERIOD_LABEL}"])
    return f"""
### Multi-year averages ({config.PERIOD_LABEL})

Water losses and precipitation are both averaged over the {len(config.PANEL_YEARS)}
years for which ISTAT publishes water losses ({years}), so the two
variables cover exactly the same period. Cities need at least
{config.MIN_YEARS} valid years for each variable; {multi['n']} of
{single['n']} qualify.

![Risk matrix, multi-year averages](figures/risk_matrix_scatter_multiyear.png)

{table}

*Models include macro-area dummies; bold = significant at the 5% level.*

{interpret_robustness(single, multi)}
"""


def build_report(ins: dict) -> str:
    """Render the insights as Markdown."""
    L, P, LBL, MA = config.COL_LOSS, config.COL_PRECIP, config.COL_CITY_LABEL, config.COL_MACRO
    worst, best, driest = ins["worst_loss"], ins["best_loss"], ins["driest"]

    critical_table = _markdown_table(
        [
            [i, row[LBL], row[MA], f"{row[L]:.1f}%", f"{row[P]:.1f}", f"{row['Criticality_Score']:.2f}"]
            for i, (_, row) in enumerate(ins["top_critical"].iterrows(), start=1)
        ],
        ["#", "City", "Macro-area", "Water loss", "Precipitation (mm)", "Criticality score"],
    )
    area_table = _markdown_table(
        [
            [area, int(r.Cities), f"{r.Median_Loss:.1f}%", f"{r.Mean_Loss:.1f}%",
             f"{r.Median_Precip:.0f}", int(r.Critical_Cities), f"{r.Within_r:+.2f}"]
            for area, r in ins["by_area"].iterrows()
        ],
        ["Macro-area", "Cities", "Median loss", "Mean loss", "Median precip. (mm)",
         "Critical cities", "r (loss vs. rain) within area"],
    )
    terrain = ins["terrain"]

    def _cell(term: dict) -> str:
        stars = "**" if term["p"] < 0.05 else ""
        return f"{stars}{term['coef']:+.2f}{stars} (t = {term['t']:.2f})"

    terrain_table = _markdown_table(
        [
            [label, _cell(terrain[key]["rain"]),
             _cell(terrain[key]["terrain"]) if "terrain" in terrain[key] else "-",
             f"{terrain[key]['r2']:.3f}"]
            for key, label in [
                ("A", "A. Rain + macro-area"),
                ("B", "B. A + altitude of town centre"),
                ("C", "C. A + terrain relief (std. dev. of altitude)"),
            ]
        ],
        ["Model", "Rain (pp per 100 mm)", "Terrain (pp per 100 m)", "R²"],
    )
    year = ins["year"]

    anomaly_table = _markdown_table(
        [[area, f"{v:.0f}%"] for area, v in ins["precip_vs_avg_by_area"].items()]
        + [["**Italy (all capitals)**", f"**{ins['precip_vs_avg']:.0f}%**"]],
        ["Macro-area", f"Median {year} rainfall, % of 2006-2021 average"],
    )
    driest_table = _markdown_table(
        [[row[LBL], row[MA], f"{row[P]:.0f}", f"{row[config.COL_PRECIP_VS_AVG]:.0f}%"]
         for _, row in ins["driest_vs_avg"].iterrows()],
        ["City", "Macro-area", f"{year} rainfall (mm)", "% of 2006-2021 average"],
    )
    robustness = _robustness_section(ins) if ins.get("multi") else ""
    caveat = ""
    if ins.get("multi") and ins["multi"]["p"] >= 0.05:
        caveat = (
            f"\n> **Caveat.** This national correlation is specific to {year}: "
            f"on {config.PERIOD_LABEL} averages it disappears "
            f"(r = {ins['multi']['r']:.3f}, p ≈ {ins['multi']['p']:.3f}). "
            f"Section 6 explains why.\n"
        )

    return f"""# The Italian Water Paradox: Rainfalls and Leaking Infrastructures

*Automated report generated on {date.today():%d/%m/%Y} from ISTAT official data
(reference year {ins['year']}, {ins['n_cities']} provincial capitals).*

## 1. Key findings

| Indicator | Result |
|---|---|
| Highest water loss | **{worst[LBL]}** ({worst[MA]}): **{worst[L]:.1f}%** of water put into the network is not delivered to users |
| Lowest water loss | {best[LBL]} ({best[MA]}): {best[L]:.1f}% |
| Lowest precipitation (highest drought risk) | **{driest[LBL]}** ({driest[MA]}): **{driest[P]:.1f} mm** in {year} |
| National median water loss | {ins['median_loss']:.1f}% |
| National median precipitation | {ins['median_precip']:.1f} mm |
| Pearson correlation (loss vs. precipitation) | **r = {ins['pearson_r']:.3f}** (p ≈ {ins['pearson_p']:.3f}, n = {ins['n_cities']}) |
| Spearman rank correlation (robustness check) | ρ = {ins['spearman_rho']:.3f} |
| Cities in the critical quadrant | {ins['n_critical']} of {ins['n_cities']} |

> **What "water losses" measures.** The ISTAT indicator is *total* losses in
> the distribution network: the share of water put into the network that is
> not delivered to final users. It includes **real losses** (physical leaks
> from pipes and joints) and **apparent losses** (meter under-registration,
> unauthorised connections). The indicator should therefore be read as a
> measure of the **overall inefficiency of the network**, not of pipe
> failures alone: "leaking infrastructures" describes only part of it.

> **Precipitation refers to a single year.** The values describe the weather
> of {year}, not the long-run climate. {year} was an exceptionally dry year:
> the median capital received only **{ins['precip_vs_avg']:.0f}%** of its
> 2006-2021 average rainfall, and the North-West just
> {ins['precip_vs_avg_by_area'].get('Nord-Ovest', float('nan')):.0f}%. Section 6 repeats the
> analysis on multi-year averages to check that the conclusions survive.

**Interpretation of the correlation.** {interpret_correlation(ins['pearson_r'], ins['pearson_p'])}
{caveat}
## 2. The risk matrix

![Risk matrix](figures/risk_matrix_scatter.png)

The dashed lines are the national medians ({ins['median_precip']:.0f} mm and
{ins['median_loss']:.1f}%), which split cities into four quadrants. The
**critical quadrant** (top-left) contains cities with below-median rainfall
*and* above-median losses: {ins['n_critical']} cities.

The five most critical cities are ranked by a criticality score,
`z(water loss) − z(precipitation)`, which standardises both variables so that
distance from the national average counts equally on each axis:

{critical_table}

## 3. The worst-performing networks

![Top 15 water losses](figures/top_losses_bar.png)

Orange bars mark cities that also fall in the critical quadrant.

## 4. The territorial divide

![Losses by macro-area](figures/macro_area_losses.png)

{area_table}

**Does the territorial divide explain the correlation?** To check, water
losses were regressed on precipitation together with the macro-area
(ordinary least squares, with the five macro-areas entered as dummy variables).
{interpret_regression(ins['regression'])}

## 5. Does altitude explain it?

If the rainfall effect were really a terrain effect, adding altitude to the
model should make it disappear. Altitude is the height of the town centre
(the census section hosting the town hall), which is where the urban network
sits; terrain relief is the standard deviation of altitude across the
municipality, a measure of how hilly it is.

Simple correlations: altitude vs. losses r = {terrain['corr_alt_loss']:.2f};
altitude vs. rainfall r = {terrain['corr_alt_rain']:.2f}; relief vs. losses
r = {terrain['corr_relief_loss']:.2f}.

{terrain_table}

*Coefficients in percentage points of water loss; all models include
macro-area dummies; bold = significant at the 5% level.*

{interpret_terrain(terrain)}

## 6. Robustness: was {year} representative?

### How unusual was {year} rainfall?

Each city's {year} rainfall is compared with its own 2006-2021 average
(ISTAT, Tavole Dati Meteoclimatici 2021):

{anomaly_table}

The five capitals furthest below their usual rainfall:

{driest_table}

Because the drought hit the North much harder than the South, the {year}
ranking of "dry" cities is distorted. A more reliable comparison averages
both variables over the same years.
{robustness}
## 7. Methodological notes

- **Sources**: ISTAT, total water losses in the municipal distribution
  networks of provincial capitals; ISTAT, *Rilevazione dati meteoclimatici ed
  idrologici* for total annual precipitation; ISTAT, *Altimetria Comuni al
  31 dicembre 2021* (Principali statistiche geografiche sui comuni) for
  altitude; ISTAT IstatData (water losses 2012-2022) and ISTAT *Tavole Dati
  Meteoclimatici Anno 2021*, Tavola 1 (precipitation 2006-2021) for the
  multi-year check.
- **Multi-year averages**: simple means over {', '.join(str(y) for y in config.PANEL_YEARS)}
  (precipitation for the earlier years from the 2021 edition of the ISTAT
  tables, {config.CLIMATE_YEAR} from the {config.CLIMATE_YEAR} release; ISTAT
  occasionally revises past values in later editions). Missing years are
  skipped; cities with fewer than {config.MIN_YEARS} valid years for either
  variable are excluded. The {config.CLIMATE_YEAR} water losses in the series
  match the cross-section exactly.
- **Indicator**: total water losses in distribution (% of the volume put into
  the network) = real losses + apparent losses. The two components cannot be
  separated with this dataset, so the indicator measures the overall
  inefficiency of the network rather than physical leakage only.
- **Reference year**: both datasets refer to {year}.
- **Altitude**: the town-centre altitude refers to the census section of the
  town hall; terrain relief is computed over the whole municipal territory,
  which may include uninhabited mountain areas far from the network. Both are
  2021 values, adequate for 2022 since terrain does not change.
- **Unit of analysis**: provincial capital municipalities. ISTAT aggregate rows
  ("Capoluoghi di provincia", "Capoluoghi di città metropolitana") were removed.
- **Missing data**: cities flagged by ISTAT with the missing-value marker
  `....`, and cities present in only one source, are excluded by the inner
  merge (see the pipeline log for the list).
- **Thresholds**: quadrants use medians rather than means because both
  distributions are skewed and medians are robust to outliers.
- **Limitations**: precipitation comes from one year ({year}, an exceptional
  drought year) and one station per city, so it captures that year's weather
  rather than long-run climate; multi-year averages or ISTAT climate normals
  would be a sounder measure. Correlation and regression do not imply causation.
"""


def run(df: pd.DataFrame, multiyear: pd.DataFrame = None,
        output_path=config.REPORT_FILE) -> dict:
    """Compute the insights and write the Markdown report."""
    insights = compute_insights(df)
    if multiyear is not None:
        insights["single"] = summarise_dataset(df)
        insights["multi"] = summarise_dataset(multiyear)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_report(insights), encoding="utf-8")
    logger.info("Saved report to %s", output_path)
    return insights
