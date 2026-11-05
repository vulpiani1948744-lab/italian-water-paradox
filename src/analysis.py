"""
Statistical analysis shared by the charts and the report.

Everything that computes a number lives here: the risk-quadrant
classification, correlations and the OLS regressions. `visualization.py`
draws these results and `report_generator.py` turns them into text, so
neither module has to depend on the other.
"""

import math

import numpy as np
import pandas as pd

from src import config


def add_risk_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Flag the critical quadrant and compute a criticality score.

    Critical quadrant: precipitation BELOW the national median AND water loss
    ABOVE the national median - cities that both receive little water and
    waste much of what they distribute.

    Criticality score = z(loss) - z(precipitation): standardising both
    variables puts them on a comparable scale, so a city scores high when it
    is far above typical losses and/or far below typical rainfall.
    """
    df = df.copy()
    loss, precip = df[config.COL_LOSS], df[config.COL_PRECIP]
    df["Is_Critical"] = (precip < precip.median()) & (loss > loss.median())
    df["Criticality_Score"] = (
        (loss - loss.mean()) / loss.std() - (precip - precip.mean()) / precip.std()
    )
    return df


def top_critical_cities(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """The n critical-quadrant cities with the highest criticality score."""
    scored = add_risk_classification(df)
    return scored[scored["Is_Critical"]].nlargest(n, "Criticality_Score")


def pearson_with_pvalue(x: pd.Series, y: pd.Series) -> tuple:
    """Pearson r and an approximate two-sided p-value for H0: rho = 0.

    t = r * sqrt((n-2) / (1-r^2)) follows a Student t with n-2 degrees of
    freedom. For n > ~30 it is well approximated by a standard normal, which
    avoids a SciPy dependency: p = erfc(|t| / sqrt(2)).
    """
    n = len(x)
    r = x.corr(y, method="pearson")
    t = r * math.sqrt((n - 2) / (1 - r ** 2))
    p = math.erfc(abs(t) / math.sqrt(2))
    return r, p, n


def _ols(df: pd.DataFrame, terms: dict) -> dict:
    """OLS of water loss on the given terms plus macro-area dummies.

    `terms` maps a name to a numeric column (already rescaled). Fitted with
    numpy least squares; standard errors are the classical OLS ones and
    p-values use the same normal approximation as pearson_with_pvalue.
    Returns {"r2": ..., name: {"coef", "se", "t", "p"} for each term}.
    """
    loss = df[config.COL_LOSS].to_numpy(dtype=float)
    dummies = pd.get_dummies(df[config.COL_MACRO], drop_first=True, dtype=float)
    X = np.column_stack(
        [np.ones(len(df))]
        + [np.asarray(values, dtype=float) for values in terms.values()]
        + [dummies.to_numpy()]
    )
    beta, *_ = np.linalg.lstsq(X, loss, rcond=None)
    resid = loss - X @ beta
    dof = len(df) - X.shape[1]
    se = np.sqrt(np.diag(resid @ resid / dof * np.linalg.inv(X.T @ X)))

    result = {"r2": 1 - (resid @ resid) / ((loss - loss.mean()) ** 2).sum()}
    for i, name in enumerate(terms, start=1):
        t = beta[i] / se[i]
        result[name] = {"coef": beta[i], "se": se[i], "t": t,
                        "p": math.erfc(abs(t) / math.sqrt(2))}
    return result


def macro_area_regression(df: pd.DataFrame) -> dict:
    """OLS of water loss on precipitation, controlling for macro-area.

    Model: loss = b0 + b1 * (precipitation / 100 mm) + macro-area dummies + e.
    If b1 stays significant once the macro-areas are in the model, the
    rainfall-loss relationship is not just a by-product of the territorial
    divide.
    """
    fit = _ols(df, {"rain": df[config.COL_PRECIP] / 100})
    loss = df[config.COL_LOSS]
    area_mean = df.groupby(config.COL_MACRO)[config.COL_LOSS].transform("mean")
    # Partial correlation: correlate the deviations from each macro-area mean.
    demeaned = df[[config.COL_LOSS, config.COL_PRECIP]] - (
        df.groupby(config.COL_MACRO)[[config.COL_LOSS, config.COL_PRECIP]].transform("mean")
    )
    return {
        "coef_per_100mm": fit["rain"]["coef"],
        "se": fit["rain"]["se"],
        "t": fit["rain"]["t"],
        "p": fit["rain"]["p"],
        "r2_full": fit["r2"],
        "r2_area_only": 1 - ((loss - area_mean) ** 2).sum() / ((loss - loss.mean()) ** 2).sum(),
        "partial_r": demeaned[config.COL_LOSS].corr(demeaned[config.COL_PRECIP]),
    }


def terrain_regressions(df: pd.DataFrame) -> dict:
    """Test the terrain hypothesis: does altitude explain the rainfall effect?

    If hill and mountain towns both receive more rain and lose more water,
    adding altitude to the model should shrink the rainfall coefficient
    towards zero. Three nested specifications, all with macro-area dummies:
      A. rain
      B. rain + altitude of the town centre       (per 100 m)
      C. rain + relief, i.e. std. dev. of altitude (per 100 m)
    """
    rain = df[config.COL_PRECIP] / 100
    return {
        "corr_alt_loss": df[config.COL_ALTITUDE].corr(df[config.COL_LOSS]),
        "corr_alt_rain": df[config.COL_ALTITUDE].corr(df[config.COL_PRECIP]),
        "corr_relief_loss": df[config.COL_RELIEF].corr(df[config.COL_LOSS]),
        "A": _ols(df, {"rain": rain}),
        "B": _ols(df, {"rain": rain, "terrain": df[config.COL_ALTITUDE] / 100}),
        "C": _ols(df, {"rain": rain, "terrain": df[config.COL_RELIEF] / 100}),
    }


def summarise_dataset(df: pd.DataFrame) -> dict:
    """The headline statistics used to compare the 2022 and multi-year results."""
    r, p, n = pearson_with_pvalue(df[config.COL_LOSS], df[config.COL_PRECIP])
    scored = add_risk_classification(df)
    area_means = df.groupby(config.COL_MACRO)[[config.COL_LOSS, config.COL_PRECIP]].mean()
    return {
        "n": n,
        # Correlation between the 5 macro-area means: descriptive only (n = 5).
        "between_r": area_means[config.COL_LOSS].corr(area_means[config.COL_PRECIP]),
        "within_r": macro_area_regression(df)["partial_r"],
        "median_loss": df[config.COL_LOSS].median(),
        "median_precip": df[config.COL_PRECIP].median(),
        "r": r,
        "p": p,
        "rho": df[config.COL_LOSS].rank().corr(df[config.COL_PRECIP].rank()),
        "terrain": terrain_regressions(df),
        "n_critical": int(scored["Is_Critical"].sum()),
        "critical_cities": set(scored.loc[scored["Is_Critical"], config.COL_CITY]),
        "top5": top_critical_cities(df, 5)[config.COL_CITY_LABEL].tolist(),
    }
