"""
Central configuration: file paths and shared constants.

Keeping every path in one place means the other modules never hard-code
locations, and the project can be moved or re-run from any working directory.
"""

from pathlib import Path

# Project root = parent of the `src/` folder that contains this file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Data folders ----------------------------------------------------------
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

WATER_LOSSES_FILE = RAW_DIR / "water_losses.csv"
CLIMATE_FILE = RAW_DIR / "climate_data.csv"
# ISTAT "Altimetria Comuni al 31 dicembre 2021" (Principali statistiche
# geografiche sui comuni). Header is on the second row of the first sheet.
ALTITUDE_FILE = RAW_DIR / "altimetria_comuni_2021.xlsx"
# ISTAT IstatData export (DCCV_URBANENV): total water losses 2012-2022.
LOSS_SERIES_FILE = RAW_DIR / "water_losses_2012_2022.csv"
# ISTAT "Tavole Dati Meteoclimatici Anno 2021", Tavola 1: annual
# precipitation in provincial capitals 2006-2021.
PRECIP_SERIES_FILE = RAW_DIR / "meteo_tavole_2021.xlsx"
PRECIP_SERIES_SHEET = "Tavola_1"
MERGED_FILE = PROCESSED_DIR / "merged_data.csv"
MULTIYEAR_FILE = PROCESSED_DIR / "multiyear_data.csv"

# --- Output folders --------------------------------------------------------
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORT_FILE = OUTPUTS_DIR / "report.md"

# --- Column names (single source of truth) ---------------------------------
COL_CITY = "City"
COL_CITY_LABEL = "City_Label"
COL_YEAR = "Year"
COL_LOSS = "Water_Loss_Percentage"
COL_PRECIP = "Total_Precipitation_mm"
COL_MACRO = "Macro_Area"
COL_ALTITUDE = "Altitude_Centre_m"      # altitude of the town-hall census section
COL_RELIEF = "Altitude_Std_m"           # std. dev. of altitude across the municipality
COL_PRECIP_VS_AVG = "Precip_pct_of_2006_2021_avg"  # 2022 rain as % of the city's 2006-2021 mean
COL_N_YEARS_LOSS = "N_Years_Loss"
COL_N_YEARS_PRECIP = "N_Years_Precip"

# Order used in legends and tables (ISTAT NUTS-1 macro-areas, north to south).
MACRO_AREA_ORDER = ["Nord-Ovest", "Nord-Est", "Centro", "Sud", "Isole"]

FIGURE_DPI = 300

# The precipitation file has no year column; its reference year is known
# from the ISTAT release it was downloaded from.
CLIMATE_YEAR = 2022

# Multi-year robustness check: the years for which ISTAT publishes water
# losses. Precipitation is averaged over the same years so that both
# variables cover the same period. A city enters the multi-year dataset only
# if it has at least MIN_YEARS valid years for both variables.
PANEL_YEARS = [2012, 2013, 2014, 2015, 2016, 2018, 2020, 2022]
MIN_YEARS = 6
PERIOD_LABEL = "2012-2022"
# Baseline for judging how unusual 2022 rainfall was.
BASELINE_YEARS = list(range(2006, 2022))
