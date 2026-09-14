import logging

from app.models import ChampionDiffResult, ChampionDiffStat, ChampionEntry

logger = logging.getLogger(__name__)


def get_champion_diff(
    latest_patch_data: dict[str, ChampionEntry],
    previous_patch_data: dict[str, ChampionEntry]
) -> ChampionDiffResult:
    """Compares champion stats between two patch datasets.

    Args:
        latest_patch_data: Dictionary mapping champion names to their newer patch data models.
        previous_patch_data: Dictionary mapping champion names to their older patch data models.

    Returns:
        A ChampionDiffResult object containing the calculated stat differences and newly added champions.
    """

    champion_changes = {}
    new_champions = []

    for champion_name, new_champ_data in latest_patch_data.items():
        previous_champ_data = previous_patch_data.get(champion_name)

        if previous_champ_data is None:
            logger.warning(f"Champion {champion_name} added...")
            new_champions.append(champion_name)
            continue

        previous_stats = previous_champ_data.stats
        new_stats = new_champ_data.stats

        if previous_stats == new_stats:
            continue

        current_champ_diff = {}
        for stat, new_value in new_stats.items():
            previous_value = previous_stats.get(stat)

            if previous_value != new_value:
                current_champ_diff[stat] = ChampionDiffStat(
                    new = new_value,
                    old = previous_value
                )

        if current_champ_diff:
            champion_changes[champion_name] = current_champ_diff

    return ChampionDiffResult(
        champion_changes=champion_changes,
        new_champions=new_champions
    )
