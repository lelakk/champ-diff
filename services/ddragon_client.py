"""Fetch champion data and patch versions from Riot DataDragon API."""

import logging
from typing import Any
import requests
from pydantic import ValidationError

from app.models import ChampionPayload, ChampionEntry

logger = logging.getLogger(__name__)
BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def _fetch_json(url: str, timeout: int = 10) -> dict[str, Any] | None:
    """Fetches and parses JSON data from a given URL.

    Args:
        url: The URL to fetch the JSON data from.
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        Parsed JSON data or None if the request fails.
        or the response contains invalid JSON.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as error_message:
        logger.error("Request failed for %s: %s", url, error_message)
        return None
    try:
        return response.json()
    except ValueError as error_message:
        logger.error("Failed to parse JSON from %s: %s", url, error_message)
        return None


def get_champion_data(
    patch_version: str, language: str = "en_US", timeout: int = 10
) -> dict[str, ChampionEntry] | None:
    """Fetches patch data from DataDragon for a specific patch version.

    Args:
        patch_version: Version of the patch.
        language: Language code for the champion data.
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        Dictionary containing the champion data, or None if failed.
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"
    logger.info("Downloading champion data for patch %s ...", patch_version)

    data = _fetch_json(url, timeout)
    if not isinstance(data, dict):
        return None

    try:
        champ_payload = ChampionPayload.model_validate(data)
    except ValidationError as error_message:
        logger.error(
            "Invalid champion payload format for patch %s: %s",
            patch_version, error_message,
        )
        return None

    if not champ_payload.data:
        return None

    return champ_payload.data


def get_all_versions(timeout: int = 10) -> list[str] | None:
    """Fetches all available versions from DataDragon.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        List of all version strings, or None if the request failed.
    """
    url = f"{BASE_DDRAGON_URL}/api/versions.json"
    data = _fetch_json(url, timeout)
    if isinstance(data, list):
        return data
    return None
