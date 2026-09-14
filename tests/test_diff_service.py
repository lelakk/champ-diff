from app.models import ChampionEntry, ChampionDiffStat
from services.diff_service import get_champion_diff


def test_get_champion_diff_no_changes():
    """If stats are the same, the function should return empty dict and empty list"""
    patch = {"Garen": ChampionEntry(stats={"hp": 1000})}
    result = get_champion_diff(latest_patch_data=patch, previous_patch_data=patch)

    assert result.champion_changes == {}
    assert result.new_champions == []


def test_get_champion_diff_stat_changes():
    """If two stats are changed, the function should return both buff and nerf."""
    latest_patch = {"Garen": ChampionEntry(stats={"hp": 1000, "armor": 35})}
    previous_patch = {"Garen": ChampionEntry(stats={"hp": 900, "armor": 40})}
    expected_changes = {
        "Garen": {
            "hp": ChampionDiffStat(new=1000, old=900),
            "armor": ChampionDiffStat(new=35, old=40),
        }
    }

    result = get_champion_diff(latest_patch_data=latest_patch, previous_patch_data=previous_patch)

    assert result.champion_changes == expected_changes
    assert result.new_champions == []


def test_get_champion_diff_new_champion_only():
    """If only a new champion is added, changes should be empty and champion listed as new."""
    latest_patch = {"Garen": ChampionEntry(stats={"hp": 1000})}
    previous_patch = {}

    result = get_champion_diff(latest_patch_data=latest_patch, previous_patch_data=previous_patch)

    assert result.champion_changes == {}
    assert result.new_champions == ["Garen"]


def test_get_champion_diff_stat_change_and_new_champion():
    """If one champion changed and one is new, there should be both outputs."""
    latest_patch = {
        "Garen": ChampionEntry(stats={"hp": 1000}),
        "Yasuo": ChampionEntry(stats={"hp": 590})
    }
    previous_patch = {"Garen": ChampionEntry(stats={"hp": 900})}
    expected_changes = {"Garen": {"hp": ChampionDiffStat(new=1000, old=900)}}

    result = get_champion_diff(latest_patch_data=latest_patch, previous_patch_data=previous_patch)

    assert result.champion_changes == expected_changes
    assert result.new_champions == ["Yasuo"]


def test_get_champion_diff_empty_latest_patch():
    """If latest patch data is empty, the function should return safe empty outputs."""
    result = get_champion_diff(
        latest_patch_data={},
        previous_patch_data={"Garen": ChampionEntry(stats={"hp": 1000})}
    )

    assert result.champion_changes == {}
    assert result.new_champions == []