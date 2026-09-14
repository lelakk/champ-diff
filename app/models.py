from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ChampionEntry(BaseModel):
    """Represents a single champion fetched from the DataDragon API.

    Attributes:
        id: The unique identifier of the champion.
        name: The display name of the champion.
        stats: A dictionary containing the champion's base statistics.
    """
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    stats: dict[str, float | int] = Field(default_factory=dict)


class ChampionPayload(BaseModel):
    """Represents the main payload structure of the champion.json file from DataDragon.

    Attributes:
        data: A dictionary mapping champion names to their ChampionEntry models.
    """
    model_config = ConfigDict(extra="allow")
    data: dict[str, ChampionEntry] = Field(default_factory=dict)


class ChampionDiffStat(BaseModel):
    """Stores the old and new values of a single changed champion statistic.

    Attributes:
        new: The new value of the statistic in the latest patch.
        old: The previous value of the statistic in the older patch.
    """
    new: Any = None
    old: Any = None


class ChampionDiffResult(BaseModel):
    """Stores the differences between two patch versions.

    Attributes:
        champion_changes: A nested dictionary mapping champion names to their changed stats.
        new_champions: A list of champion names that were introduced in the latest patch.
    """
    champion_changes: dict[str, dict[str, ChampionDiffStat]] = Field(default_factory=dict)
    new_champions: list[str] = Field(default_factory=list)