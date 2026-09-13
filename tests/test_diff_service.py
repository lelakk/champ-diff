from services.diff_service import get_champion_diff


def test_get_champion_diff_no_changes():
    """If stats are the same, the function should return empty dict and empty list"""
    patch = {"Garen": {"stats": {"hp": 1000}}}
    changes, new_champs = get_champion_diff(
        latest_patch_data=patch, previous_patch_data=patch
    )

    assert changes == {}
    assert new_champs == []


def test_get_champion_diff_stat_changes():
    """If two stats are changed, the function should return both buff and nerf."""
    latest_patch = {"Garen": {"stats": {"hp": 1000, "armor": 35}}}
    previous_patch = {"Garen": {"stats": {"hp": 900, "armor": 40}}}
    expected = {
        "Garen": {
            "hp": {"new": 1000, "old": 900},
            "armor": {"new": 35, "old": 40},
        }
    }

    changes, new_champs = get_champion_diff(
        latest_patch_data=latest_patch, previous_patch_data=previous_patch
    )

    assert changes == expected
    assert new_champs == []


def test_get_champion_diff_new_champion_only():
    """If only a new champion is added, changes should be empty and champion listed as new."""
    latest_patch = {"Garen": {"stats": {"hp": 1000}}}
    previous_patch = {}

    changes, new_champs = get_champion_diff(
        latest_patch_data=latest_patch, previous_patch_data=previous_patch
    )

    assert changes == {}
    assert new_champs == ["Garen"]


def test_get_champion_diff_stat_change_and_new_champion():
    """If one champion changed and one is new, there should be both outputs."""
    latest_patch = {"Garen": {"stats": {"hp": 1000}}, "Yasuo": {"stats": {"hp": 590}}}
    previous_patch = {"Garen": {"stats": {"hp": 900}}}
    expected = {"Garen": {"hp": {"new": 1000, "old": 900}}}

    changes, new_champs = get_champion_diff(
        latest_patch_data=latest_patch, previous_patch_data=previous_patch
    )

    assert changes == expected
    assert new_champs == ["Yasuo"]


def test_get_champion_diff_empty_latest_patch():
    """If latest patch data is empty, the function should return safe empty outputs."""
    changes, new_champs = get_champion_diff(
        latest_patch_data={}, previous_patch_data={"Garen": {"stats": {"hp": 1000}}}
    )

    assert changes == {}
    assert new_champs == []