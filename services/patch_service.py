"""Select game patch versions for comparison."""

import logging

from services.ddragon_client import get_all_versions

logger = logging.getLogger(__name__)


def get_latest_and_previous_patch(timeout: int = 10) -> tuple[str, str] | None:
    """Fetches the latest and previous version patch from the available versions.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        A tuple containing the latest and previous patch version strings, or None if unavailable.
    """
    versions = get_all_versions(timeout)
    if not versions:
        logger.error("No versions returned from DataDragon")
        return None
    if not isinstance(versions, list) or len(versions) < 2:
        logger.error("Invalid versions response, expected at least 2 versions")
        return None
    if not all(isinstance(ver, str) for ver in versions):
        logger.error("Invalid version format, expected strings")
        return None
    return versions[0], versions[1]
