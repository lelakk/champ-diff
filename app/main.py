import logging

from app.use_cases import compare_last_patch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        result = compare_last_patch()
    except RuntimeError as error_message:
        logger.error(f"Error occurred while comparing last patch: {error_message}")
        raise SystemExit(1)

    champion_changes, new_champions = result
    logger.info(f"Champion changes: {champion_changes}")
    logger.info(f"New champion: {new_champions}" if new_champions else "No new champions")


if __name__ == "__main__":
    main()
