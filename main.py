import json
import sys
from typing import Any
import requests

BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def get_all_versions(timeout: int = 10) -> list[str] | None:
    """
    Fetches all available versions from DataDragon.
    :param timeout: timeout for the request
    :return: is all available versions from DataDragon.
    """
    url = f"{BASE_DDRAGON_URL}/api/versions.json"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        print(f"[Network Error]: Failed to fetch versions:\n{error}")
    except ValueError as error:
        print(f"[JSON Error]: Failed to parse versions:\n{error}")
    return None


def get_latest_patch(timeout: int = 10) -> str | None:
    """
    Fetches the latest version patch from the available versions.
    :param timeout: timeout for the request
    :return: is the latest patch version as a string.
    """
    versions = get_all_versions(timeout)

    if not versions:
        print("[Error]: Versions list is empty or unavailable")
        return None

    return versions[0]


def get_champion_data(patch_version: str, language: str = "en_US", timeout: int = 10) -> dict | None:
    """
    Fetches patch data from DataDragon for a specific patch version.
    :param language: language of the champion data
    :param patch_version: version of the patch
    :param timeout: timeout for the request
    :return: is the dictionary containing the patch data
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        print(f"[Network Error]: Failed to fetch champion data:\n{error}")
    except ValueError as error:
        print(f"[Value Error]: Failed to parse champion data:\n{error}")

    return None


def save_json_file(data: Any, filepath: str) -> bool:
    """
    Saves data to a JSON file.
    :param data: The data to be saved in JSON format.
    :param filepath: The path where the JSON file will be created or overwritten.
    :return: True if the file was saved successfully, False otherwise.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )
        return True
    except OSError as error:
        print(f"[File Error]: Failed to save JSON file to '{filepath}':\n{error}")
        return False


if __name__ == "__main__":
    print("League Data Dragon Fetcher\n")

    latest_patch = get_latest_patch()
    if not latest_patch:
        print("[Error]: Could not retrieve the latest patch version.")
        sys.exit(1)
    print(f"Latest patch version: {latest_patch}")

    print(f"Downloading champion data for patch version {latest_patch}")
    champions_raw = get_champion_data(latest_patch)
    if not champions_raw:
        print("[Error]: Could not retrieve champion data.")
        sys.exit(1)
    file_target = "champions.json"
    if save_json_file(champions_raw, file_target):
        print(f"Champion data saved to '{file_target}'")
    else:
        print("[Error]: Failed to save data to disk.")
        sys.exit(1)