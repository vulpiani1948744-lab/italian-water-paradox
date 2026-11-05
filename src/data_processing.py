"""
Task 1 - Data preprocessing.

Loads the two ISTAT extracts, cleans them, assigns each city to its ISTAT
macro-area, merges them on the city name and writes the result to
`data/processed/merged_data.csv`.

Cleaning issues handled (all observed in the raw ISTAT exports):
  * footer rows with source notes ("Fonte: Istat, ...", "a) I dati ...");
  * national aggregate rows ("Capoluoghi di provincia", ...) that are not cities;
  * the ISTAT missing-value marker "...." in numeric columns;
  * quoting artefacts in names with apostrophes ('L"'Aquila' -> L'Aquila);
  * different spellings of the same city across the two files
    (e.g. "Bolzano/Bozen" vs "Bolzano", "Massa" vs "Massa Carrara").
"""

import logging

import pandas as pd

from src import config

logger = logging.getLogger(__name__)

# Rows that are national totals rather than individual cities.
AGGREGATE_ROWS = {
    "capoluoghi di provincia",
    "capoluoghi di città metropolitana",
    "italia",
}

# Spelling variants -> canonical (standardised) key.
CITY_ALIASES = {
    "bolzano/bozen": "bolzano",
    "massa carrara": "massa",
    "pesaro urbino": "pesaro",
    "reggio emilia": "reggio nell'emilia",
    "reggio calabria": "reggio di calabria",
}

# Provincial capitals -> ISTAT macro-area (NUTS-1). Keys are standardised names.
_MACRO_AREAS = {
    "Nord-Ovest": [
        # Piemonte
        "torino", "vercelli", "novara", "cuneo", "asti", "alessandria",
        "biella", "verbania",
        # Valle d'Aosta
        "aosta",
        # Liguria
        "imperia", "savona", "genova", "la spezia",
        # Lombardia
        "varese", "como", "sondrio", "milano", "bergamo", "brescia", "pavia",
        "cremona", "mantova", "lecco", "lodi", "monza",
    ],
    "Nord-Est": [
        # Trentino-Alto Adige
        "bolzano", "trento",
        # Veneto
        "verona", "vicenza", "belluno", "treviso", "venezia", "padova", "rovigo",
        # Friuli-Venezia Giulia
        "udine", "gorizia", "trieste", "pordenone",
        # Emilia-Romagna
        "piacenza", "parma", "reggio nell'emilia", "modena", "bologna",
        "ferrara", "ravenna", "forlì", "cesena", "rimini",
    ],
    "Centro": [
        # Toscana
        "massa", "lucca", "pistoia", "firenze", "livorno", "pisa", "arezzo",
        "siena", "grosseto", "prato",
        # Umbria
        "perugia", "terni",
        # Marche
        "pesaro", "urbino", "ancona", "macerata", "ascoli piceno", "fermo",
        # Lazio
        "viterbo", "rieti", "roma", "latina", "frosinone",
    ],
    "Sud": [
        # Abruzzo
        "l'aquila", "teramo", "pescara", "chieti",
        # Molise
        "campobasso", "isernia",
        # Campania
        "caserta", "benevento", "napoli", "avellino", "salerno",
        # Puglia
        "foggia", "bari", "taranto", "brindisi", "lecce", "andria", "barletta",
        "trani",
        # Basilicata
        "potenza", "matera",
        # Calabria
        "cosenza", "catanzaro", "reggio di calabria", "crotone", "vibo valentia",
    ],
    "Isole": [
        # Sicilia
        "trapani", "palermo", "messina", "agrigento", "caltanissetta", "enna",
        "catania", "ragusa", "siracusa",
        # Sardegna
        "sassari", "nuoro", "cagliari", "oristano", "carbonia",
        "sanluri", "iglesias", "olbia", "tempio pausania", "lanusei",
        "tortolì", "villacidro",
    ],
}
CITY_TO_MACRO_AREA = {
    city: area for area, cities in _MACRO_AREAS.items() for city in cities
}


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------
def clean_city_label(names: pd.Series) -> pd.Series:
    """Fix quoting artefacts and whitespace, keeping the original casing.

    ISTAT exports escape apostrophes oddly, e.g. 'L"'Aquila' for L'Aquila.
    """
    return (
        names.astype(str)
        .str.replace("’", "'", regex=False)  # typographic apostrophe
        .str.replace("\"'", "'", regex=False)     # 'L"'Aquila' -> 'L''Aquila'
        .str.replace('"', "", regex=False)
        .str.strip()
        .str.strip("'")                           # 'L'Aquila' -> L'Aquila
        .str.replace(r"\s+", " ", regex=True)
    )


def standardize_city(names: pd.Series) -> pd.Series:
    """Build the merge key: cleaned, lower-case, with known aliases resolved."""
    key = clean_city_label(names).str.lower()
    return key.replace(CITY_ALIASES)


def to_numeric(values: pd.Series) -> pd.Series:
    """Convert to float, turning ISTAT markers such as '....' into NaN."""
    return pd.to_numeric(
        values.astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _drop_non_city_rows(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Remove national aggregates and footer/note rows."""
    is_aggregate = df[config.COL_CITY].isin(AGGREGATE_ROWS)
    # Footer notes are long free-text sentences, never a city name.
    is_note = df[config.COL_CITY].str.len() > 40
    dropped = df.loc[is_aggregate | is_note, config.COL_CITY].tolist()
    if dropped:
        logger.info("%s: dropped %d non-city rows: %s", name, len(dropped), dropped)
    return df.loc[~(is_aggregate | is_note)]


def _drop_missing(df: pd.DataFrame, column: str, name: str) -> pd.DataFrame:
    """Drop rows whose value is missing, logging which cities are affected."""
    missing = df[column].isna()
    if missing.any():
        logger.warning(
            "%s: %d cities have no valid '%s' and are excluded: %s",
            name, missing.sum(), column, df.loc[missing, config.COL_CITY].tolist(),
        )
    return df.loc[~missing]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_water_losses(path=config.WATER_LOSSES_FILE) -> pd.DataFrame:
    """Load and clean the water losses dataset (one row per city)."""
    df = pd.read_csv(path, dtype=str)
    df[config.COL_CITY_LABEL] = clean_city_label(df[config.COL_CITY])
    df[config.COL_CITY] = standardize_city(df[config.COL_CITY])
    df[config.COL_YEAR] = to_numeric(df[config.COL_YEAR]).astype("Int64")
    df[config.COL_LOSS] = to_numeric(df[config.COL_LOSS])

    df = _drop_non_city_rows(df, "water_losses")
    df = _drop_missing(df, config.COL_LOSS, "water_losses")

    # If several years are present, keep the most recent observation per city.
    df = (
        df.sort_values(config.COL_YEAR)
        .drop_duplicates(subset=config.COL_CITY, keep="last")
        .reset_index(drop=True)
    )
    logger.info("water_losses: %d cities loaded", len(df))
    return df[[config.COL_CITY, config.COL_CITY_LABEL, config.COL_YEAR, config.COL_LOSS]]


def load_climate(path=config.CLIMATE_FILE) -> pd.DataFrame:
    """Load and clean the precipitation dataset (one row per city)."""
    df = pd.read_csv(path, dtype=str)
    if config.COL_YEAR not in df.columns:
        logger.info("climate_data has no '%s' column: using reference year %d",
                    config.COL_YEAR, config.CLIMATE_YEAR)
    df[config.COL_CITY] = standardize_city(df[config.COL_CITY])
    df[config.COL_PRECIP] = to_numeric(df[config.COL_PRECIP])

    df = _drop_non_city_rows(df, "climate_data")
    df = _drop_missing(df, config.COL_PRECIP, "climate_data")
    df = df.drop_duplicates(subset=config.COL_CITY, keep="first").reset_index(drop=True)
    logger.info("climate_data: %d cities loaded", len(df))
    return df[[config.COL_CITY, config.COL_PRECIP]]


def load_altitude(path=config.ALTITUDE_FILE) -> pd.DataFrame:
    """Load ISTAT municipal altimetry (one row per municipality).

    Keeps the altitude of the town centre ("ALT CENTR MUN": centroid of the
    census section hosting the town hall), which is where the urban water
    network actually sits, and the standard deviation of altitude across the
    municipal territory as a measure of how hilly it is.
    """
    df = pd.read_excel(path, sheet_name=0, header=1)
    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    df = df.rename(columns={"ALT CENTR MUN": config.COL_ALTITUDE, "STD": config.COL_RELIEF})
    df[config.COL_CITY] = standardize_city(df["COMUNE"])
    for col in (config.COL_ALTITUDE, config.COL_RELIEF):
        df[col] = to_numeric(df[col])
    logger.info("altitude: %d municipalities loaded", len(df))
    return df[[config.COL_CITY, config.COL_ALTITUDE, config.COL_RELIEF]]


def load_loss_series(path=config.LOSS_SERIES_FILE) -> pd.DataFrame:
    """Load the IstatData water-loss series as a City x Year table.

    The export is in long format (one row per territory and year). It also
    contains national and macro-area aggregates; these are dropped later
    simply because they do not match any city of the merged dataset.
    ISTAT marks years before a city entered the survey with "..".
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df[config.COL_CITY] = standardize_city(df["Territorio"])
    df[config.COL_YEAR] = to_numeric(df["TIME_PERIOD"]).astype("Int64")
    df[config.COL_LOSS] = to_numeric(df["Osservazione"])
    wide = df.pivot_table(index=config.COL_CITY, columns=config.COL_YEAR,
                          values=config.COL_LOSS, aggfunc="first")
    logger.info("loss series: %d territories, years %s", len(wide), list(wide.columns))
    return wide


def load_precip_series(path=config.PRECIP_SERIES_FILE,
                       sheet=config.PRECIP_SERIES_SHEET) -> pd.DataFrame:
    """Load annual precipitation per provincial capital as a City x Year table.

    The ISTAT table puts temperature and precipitation side by side under two
    merged headers, with the years on the row below. The precipitation block
    is located by its header rather than by fixed column numbers, so a future
    edition with more years is read the same way.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header_row, start_col = next(
        (r, c) for r in range(10) for c in range(raw.shape[1])
        # startswith, not "in": the table title also mentions precipitation.
        if str(raw.iat[r, c]).strip().upper().startswith("PRECIPITAZ")
    )
    years = {}
    for c in range(start_col, raw.shape[1]):
        year = to_numeric(pd.Series([raw.iat[header_row + 1, c]])).iloc[0]
        if pd.isna(year):
            break
        years[c] = int(year)

    body = raw.iloc[header_row + 2:]
    body = body[body[0].notna() & ~body[0].astype(str).str.startswith(("Fonte", "("))]
    wide = pd.DataFrame(
        {year: to_numeric(body[c]).to_numpy() for c, year in years.items()},
        index=standardize_city(body[0]).to_numpy(),
    )
    wide.index.name = config.COL_CITY
    logger.info("precipitation series: %d cities, years %d-%d",
                len(wide), min(years.values()), max(years.values()))
    return wide


# ---------------------------------------------------------------------------
# Enrichment and merge
# ---------------------------------------------------------------------------
def add_macro_area(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the ISTAT macro-area; unmapped cities are labelled 'Unknown'."""
    df = df.copy()
    df[config.COL_MACRO] = df[config.COL_CITY].map(CITY_TO_MACRO_AREA)
    unmapped = df.loc[df[config.COL_MACRO].isna(), config.COL_CITY].tolist()
    if unmapped:
        logger.warning("No macro-area mapping for: %s", unmapped)
    df[config.COL_MACRO] = df[config.COL_MACRO].fillna("Unknown")
    return df


def merge_datasets(water: pd.DataFrame, climate: pd.DataFrame) -> pd.DataFrame:
    """Inner-merge on the standardised city key and report what was lost."""
    only_water = sorted(set(water[config.COL_CITY]) - set(climate[config.COL_CITY]))
    only_climate = sorted(set(climate[config.COL_CITY]) - set(water[config.COL_CITY]))
    if only_water:
        logger.warning("In water_losses only (excluded by inner merge): %s", only_water)
    if only_climate:
        logger.warning("In climate_data only (excluded by inner merge): %s", only_climate)

    merged = water.merge(climate, on=config.COL_CITY, how="inner", validate="one_to_one")
    logger.info("Merged dataset: %d cities", len(merged))
    return merged


def add_altitude(df: pd.DataFrame, altitude: pd.DataFrame) -> pd.DataFrame:
    """Attach altitude to the merged cities; every city must find a match.

    The altimetry file covers all ~7,900 Italian municipalities, so names are
    only matched against our capitals. Municipalities sharing a name with a
    capital elsewhere would make the match ambiguous, hence the check.
    """
    candidates = altitude[altitude[config.COL_CITY].isin(df[config.COL_CITY])]
    duplicated = candidates.loc[candidates[config.COL_CITY].duplicated(), config.COL_CITY]
    if not duplicated.empty:
        raise ValueError(f"Ambiguous municipality names in altitude file: {sorted(set(duplicated))}")

    out = df.merge(candidates, on=config.COL_CITY, how="left", validate="one_to_one")
    missing = out.loc[out[config.COL_ALTITUDE].isna(), config.COL_CITY].tolist()
    if missing:
        raise ValueError(f"No altitude found for: {missing}")
    return out


def add_precip_vs_average(df: pd.DataFrame, precip_series: pd.DataFrame) -> pd.DataFrame:
    """2022 precipitation as a percentage of each city's 2006-2021 average.

    Below 100 means 2022 was drier than usual for that city. The average
    requires at least 10 valid years, otherwise the value is left missing.
    """
    baseline = precip_series.reindex(columns=config.BASELINE_YEARS)
    average = baseline.mean(axis=1).where(baseline.notna().sum(axis=1) >= 10)
    out = df.copy()
    out[config.COL_PRECIP_VS_AVG] = (
        out[config.COL_PRECIP] / out[config.COL_CITY].map(average) * 100
    )
    return out


def build_multiyear(df: pd.DataFrame, loss_series: pd.DataFrame,
                    precip_series: pd.DataFrame) -> pd.DataFrame:
    """Average losses and precipitation over the same years (PANEL_YEARS).

    The 2022 precipitation comes from the 2022 dataset already merged in
    `df`; earlier years come from the ISTAT 2006-2021 table. The output keeps
    the same column names as the 2022 dataset (COL_LOSS, COL_PRECIP now hold
    multi-year averages), so every analysis and chart can be reused unchanged.
    """
    cities = df.set_index(config.COL_CITY)
    precip = precip_series.reindex(index=cities.index, columns=config.PANEL_YEARS)
    precip[config.CLIMATE_YEAR] = cities[config.COL_PRECIP]
    loss = loss_series.reindex(index=cities.index, columns=config.PANEL_YEARS)

    out = cities[[config.COL_CITY_LABEL, config.COL_MACRO,
                  config.COL_ALTITUDE, config.COL_RELIEF]].copy()
    out[config.COL_LOSS] = loss.mean(axis=1)
    out[config.COL_PRECIP] = precip.mean(axis=1)
    out[config.COL_N_YEARS_LOSS] = loss.notna().sum(axis=1)
    out[config.COL_N_YEARS_PRECIP] = precip.notna().sum(axis=1)

    enough = ((out[config.COL_N_YEARS_LOSS] >= config.MIN_YEARS)
              & (out[config.COL_N_YEARS_PRECIP] >= config.MIN_YEARS))
    if (~enough).any():
        logger.warning(
            "Multi-year: %d cities have fewer than %d of %d years and are excluded: %s",
            (~enough).sum(), config.MIN_YEARS, len(config.PANEL_YEARS),
            out.index[~enough].tolist(),
        )
    out = out[enough].reset_index()
    logger.info("Multi-year dataset (%s): %d cities", config.PERIOD_LABEL, len(out))
    return out


def validate(df: pd.DataFrame) -> None:
    """Sanity checks on the merged dataset; raise instead of writing bad data.

    Explicit exceptions rather than `assert`, which Python skips when run
    with the -O flag.
    """
    key_columns = [config.COL_LOSS, config.COL_PRECIP]
    missing = df.loc[df[key_columns].isna().any(axis=1), config.COL_CITY].tolist()
    if missing:
        raise ValueError(f"Missing loss or precipitation after merge for: {missing}")
    out_of_range = df.loc[~df[config.COL_LOSS].between(0, 100), config.COL_CITY].tolist()
    if out_of_range:
        raise ValueError(f"Water loss outside 0-100% for: {out_of_range}")
    negative_rain = df.loc[df[config.COL_PRECIP] < 0, config.COL_CITY].tolist()
    if negative_rain:
        raise ValueError(f"Negative precipitation for: {negative_rain}")
    if df[config.COL_CITY].duplicated().any():
        raise ValueError("Duplicate cities in merged dataset")


def run(output_path=config.MERGED_FILE, multiyear_path=config.MULTIYEAR_FILE) -> tuple:
    """Full preprocessing step: load, clean, merge, enrich, export.

    Returns (merged, multiyear): the 2022 cross-section and the multi-year
    averages used as a robustness check.
    """
    water = load_water_losses()
    climate = load_climate()
    precip_series = load_precip_series()
    merged = add_macro_area(merge_datasets(water, climate))
    merged = add_altitude(merged, load_altitude())
    merged = add_precip_vs_average(merged, precip_series)

    years = set(merged[config.COL_YEAR].dropna().astype(int))
    if years != {config.CLIMATE_YEAR}:
        logger.warning("Water-loss years %s differ from precipitation year %d",
                       sorted(years), config.CLIMATE_YEAR)

    columns = [
        config.COL_CITY, config.COL_CITY_LABEL, config.COL_MACRO,
        config.COL_YEAR, config.COL_LOSS, config.COL_PRECIP,
        config.COL_ALTITUDE, config.COL_RELIEF, config.COL_PRECIP_VS_AVG,
    ]
    merged = merged[columns].sort_values(config.COL_CITY).reset_index(drop=True)

    validate(merged)

    multiyear = build_multiyear(merged, load_loss_series(), precip_series)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    multiyear.to_csv(multiyear_path, index=False)
    logger.info("Saved merged dataset to %s", output_path)
    logger.info("Saved multi-year dataset to %s", multiyear_path)
    return merged, multiyear
