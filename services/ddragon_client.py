import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)
BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def get_champion_data(
    patch_version: str, language: str = "en_US", timeout: int = 10
) -> dict[str, Any] | None:
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
        logger.info(f"Downloading champion data for patch {patch_version} ...")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        patch_data = response.json()
        return patch_data.get("data")
    except requests.exceptions.RequestException as error_message:
        logger.error(f"Failed to fetch champion data: {error_message}")
    except ValueError as error_message:
        logger.error(f"Failed to parse champion data JSON: {error_message}")
    return None


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
    except requests.exceptions.RequestException as error_message:
        logger.error(f"Failed to fetch versions: {error_message}")
    except ValueError as error_message:
        logger.error(f"Failed to parse versions JSON: {error_message}")
    return None
