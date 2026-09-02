import json
from typing import Any
import requests

BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"

def get_all_versions(timeout: int = 10) -> list[str]:
    """
    Fetches all available versions from DataDragon.
    :param timeout: timeout for the request
    :return: is all available versions from DataDragon.
    """
    url = f"{BASE_DDRAGON_URL}/api/versions.json"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()

def get_latest_patch(timeout: int = 10) -> str:
    """
    Fetches the latest version patch from the available versions.
    :param timeout: timeout for the request
    :return: is the latest patch version as a string.
    """
    versions = get_all_versions(timeout)
    return versions[0]

def get_champion_data(patch_version: str, language: str = "en_US", timeout: int = 10) -> dict:
    """
    Fetches patch data from DataDragon for a specific patch version.
    :param language: language of the champion data
    :param patch_version: version of the patch
    :param timeout: timeout for the request
    :return: is the dictionary containing the patch data
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def save_json_file(data: Any, filepath: str) -> None:
    """
    Saves data to a JSON file.
    :param data: The data to be saved in JSON format.
    :param filepath: The path where the JSON file will be created or overwritten.
    :return: None
    """
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    print("Downloading data from DataDragon")
    latest_patch = get_latest_patch()
    print(f"Latest patch version: {latest_patch}")

    print(f"Downloading champion data for patch version {latest_patch}")
    champions_raw = get_champion_data(latest_patch)
    save_json_file(champions_raw, "champions.json")
    print("Champion data saved to \'champions.json\'")
