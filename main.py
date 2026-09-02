import json
import logging
from pathlib import Path
import sys
from typing import Any
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def get_all_versions(timeout: int = 10) -> list[str] | None:
    """
    Fetches all available versions from DataDragon.
    :param timeout: Timeout for the HTTP request in seconds.
    :return: List of all version strings, or None if the request failed.
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


def get_latest_patch(timeout: int = 10) -> str | None:
    """
    Fetches the latest version patch from the available versions.
    :param timeout: Timeout for the HTTP request in seconds.
    :return: The latest patch version string, or None if unavailable.
    """
    versions = get_all_versions(timeout)
    if not versions:
        logging.error("Versions list is empty or unavailable.")
        return None
    return versions[0]


def get_champion_data(patch_version: str, language: str = "en_US", timeout: int = 10) -> dict[str, Any] | None:
    """
    Fetches patch data from DataDragon for a specific patch version.
    :param patch_version: Version of the patch.
    :param language: Language code for the champion data.
    :param timeout: Timeout for the HTTP request in seconds.
    :return: Dictionary containing the champion data, or None if failed.
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f"Failed to fetch champion data: {error}")
    except ValueError as error:
        logging.error(f"Failed to parse champion data JSON: {error}")
    return None


def save_json_file(data: Any, filepath: str | Path) -> bool:
    """
    Saves data to a JSON file.
    :param data: The data to be saved.
    :param filepath: Target path where the file will be saved.
    :return: True if saved successfully, False otherwise.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        return True
    except OSError as error:
        logging.error(f"Failed to save JSON file to '{filepath}': {error}")
        return False


def main() -> None:
    print("League Data Dragon Fetcher\n")

    latest_patch = get_latest_patch()
    if not latest_patch:
        sys.exit(1)
    print(f"Latest patch version: {latest_patch}")

    print(f"Downloading champion data for patch {latest_patch}...")
    champions_raw = get_champion_data(latest_patch)
    if not champions_raw:
        sys.exit(1)

    target_file = Path("champions.json")
    if save_json_file(champions_raw, target_file):
        print(f"Champion data saved to '{target_file}'")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
