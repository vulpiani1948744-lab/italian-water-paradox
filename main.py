"""
The Italian Water Paradox: Rainfalls and Leaking Infrastructures.

Orchestrator: runs the full pipeline in order.
    1. Preprocessing  -> data/processed/merged_data.csv
    2. Visualisation  -> outputs/figures/*.png
    3. Reporting      -> outputs/report.md

Usage:
    python main.py
"""

import logging
import sys

from src import config, data_processing, report_generator, visualization


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    setup_logging()
    log = logging.getLogger("main")

    for path in (config.WATER_LOSSES_FILE, config.CLIMATE_FILE, config.ALTITUDE_FILE,
                 config.LOSS_SERIES_FILE, config.PRECIP_SERIES_FILE):
        if not path.exists():
            log.error("Missing input file: %s", path)
            return 1

    log.info("Step 1/3 - Preprocessing")
    merged, multiyear = data_processing.run()

    log.info("Step 2/3 - Visualisation")
    visualization.run(merged, multiyear)

    log.info("Step 3/3 - Reporting")
    insights = report_generator.run(merged, multiyear)

    log.info(
        "Done. %d cities | Pearson r = %.3f | worst loss: %s (%.1f%%)",
        insights["n_cities"], insights["pearson_r"],
        insights["worst_loss"][config.COL_CITY_LABEL], insights["worst_loss"][config.COL_LOSS],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
