import logging
from app.use_cases import compare_last_patch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    try:
        result = compare_last_patch()
    except RuntimeError as error_message:
        logging.error(f"Error occurred while comparing last patch: {error_message}")
        raise SystemExit(1)

    champion_changes, new_champions = result
    logging.info(f"Amount of champion changes: {len(champion_changes)}")
    logging.info(f"New champion: {new_champions}" if new_champions else "No new champions")

if __name__ == "__main__":
    main()
