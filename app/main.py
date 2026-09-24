"""Main entry point for the application."""

import logging

from app.use_cases import compare_last_patch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Runs the patch comparison workflow and logs the results."""
    try:
        result = compare_last_patch()
    except RuntimeError as error_message:
        logger.error("Error occurred while comparing last patch: %s", error_message)
        raise SystemExit(1) from error_message

    logger.info("Champion changes: %s", result.champion_changes)
    if result.new_champions:
        logger.info("New champions: %s", result.new_champions)
    else:
        logger.info("No new champions")


if __name__ == "__main__":
    main()
