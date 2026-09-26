import logging

from services.ddragon_client import get_champion_data, get_latest_and_previous_patch
from services.diff_service import get_champion_diff
from app.models import ChampionDiffResult

logger = logging.getLogger(__name__)


def compare_last_patch() -> ChampionDiffResult:
    """Compares the latest and previous patch versions and returns the differences.

    Returns:
        A ChampionDiffResult object containing the champion changes and new champions.
    """
    patches = get_latest_and_previous_patch()
    if not patches:
        raise RuntimeError("Failed to fetch patch versions")

    latest_patch, previous_patch = patches
    logger.info(f"Latest patch: {latest_patch}")
    logger.info(f"Previous patch: {previous_patch}")

    latest_champions = get_champion_data(latest_patch)
    previous_champions = get_champion_data(previous_patch)

    if not latest_champions or not previous_champions:
        raise RuntimeError("Failed to fetch champion data for patch versions")

    return get_champion_diff(latest_champions, previous_champions)
