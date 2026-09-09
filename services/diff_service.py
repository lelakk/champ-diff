import logging


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