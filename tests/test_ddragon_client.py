import unittest
from unittest.mock import MagicMock, patch

import requests
import ddragon_client

class TestDdragonClient(unittest.TestCase):
    @patch("ddragon_client.requests.get")
    def test_get_champion_data_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": {
            "data": {"Garen": {"stats": {}}}}
        }


if __name__ == '__main__':
    unittest.main()
