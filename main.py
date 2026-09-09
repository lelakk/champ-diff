import json
import logging
from pathlib import Path
import sys
from typing import Any
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def get_all_versions(timeout: int = 10) -> list[str] | None:
    """Fetches all available versions from DataDragon.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        List of all version strings, or None if the request failed.
    """
    url = f"{BASE_DDRAGON_URL}/api/versions.json"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f"Failed to fetch versions: {error}")
    except ValueError as error:
        logging.error(f"Failed to parse versions JSON: {error}")
    return None


def get_latest_and_previous_patch(timeout: int = 10) -> tuple[str, str] | None:
    """Fetches the latest and previous version patch from the available versions.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        A tuple containing the latest and previous patch version strings, or None if unavailable.
    """
    versions = get_all_versions(timeout)
    if not versions:
        logging.error("No versions returned from DataDragon")
        return None
    if not isinstance(versions, list) or len(versions)<2:
        logging.error("Invalid versions response, expected at least 2 versions")
        return None
    if not all(isinstance(v, str) for v in versions):
        logging.error("Invalid version format, expected strings")
        return None
    return versions[0], versions[1]

def get_champion_data(patch_version: str, language: str = "en_US", timeout: int = 10) -> dict[str, Any] | None:
    """Fetches patch data from DataDragon for a specific patch version.

    Args:
        patch_version: Version of the patch.
        language: Language code for the champion data.
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        Dictionary containing the champion data, or None if failed.
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        patch_data = response.json()
        return patch_data.get("data")
    except requests.exceptions.RequestException as error:
        logging.error(f"Failed to fetch champion data: {error}")
    except ValueError as error:
        logging.error(f"Failed to parse champion data JSON: {error}")
    return None


def save_json_file(data: Any, filepath: str | Path) -> bool:
    """Saves data to a JSON file.

    Args:
        data: The data to be saved.
        filepath: Target path where the file will be saved.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        return True
    except OSError as error:
        logging.error(f"Failed to save JSON file to '{filepath}': {error}")
        return False


def get_champion_diff(latest_patch_data: dict, previous_patch_data: dict) -> tuple[dict, list]:
    """Compares champion stats between two patch datasets.

    Args:
        latest_patch_data: Champion data from the newer patch.
        previous_patch_data: Champion data from the older patch.

    Returns:
        A tuple where:
            - First element is a dictionary of changed champions and their stat diffs.
            - Second element is a list of champions that were not present in the previous patch.
    """

    champion_changes = {}
    new_champions = []

    for champion, new_data in latest_patch_data.items():
        previous_data = previous_patch_data.get(champion)
        current_champ_diff = {}
        if previous_data is None:
            logging.warning(f"Champion {champion} added...")
            new_champions.append(champion)
        else:
            previous_stats = previous_data.get("stats", {})
            new_stats = new_data.get("stats", {})

            if previous_stats == new_stats:
                continue

            for stat, new_value in new_stats.items():
                previous_value = previous_stats.get(stat)
                if previous_value != new_value:
                    current_champ_diff[stat] = {"new": new_value, "old": previous_value}
            champion_changes[champion] = current_champ_diff


    return champion_changes, new_champions

def main() -> None:

    patches = get_latest_and_previous_patch()
    if not patches:
        sys.exit(1)
    latest_patch, previous_patch = patches

    logging.info(f"Latest patch version: {latest_patch}")
    logging.info(f"Previous patch version: {previous_patch}")

    logging.info(f"Downloading champion data for patch {latest_patch} and patch {previous_patch} ...")

    latest_champions = get_champion_data(latest_patch)
    previous_champions = get_champion_data(previous_patch)
    if not latest_champions or not previous_champions:
        logging.error("Failed to fetch champion data for patch versions")
        sys.exit(1)

    get_champion_diff(latest_champions, previous_champions)

if __name__ == "__main__":
    main()
