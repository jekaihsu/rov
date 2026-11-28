"""Check the desktop Steam screenshot bridge without requiring a signed-in Steam client."""
import unittest
from unittest.mock import Mock, patch

from desktop.steam_screenshot import register


class TestSteamScreenshot(unittest.TestCase):
    @patch('desktop.steam_screenshot.ctypes.CDLL')
    def test_adds_jpeg_at_its_actual_dimensions(self, load):
        sdk = load.return_value
        sdk.SteamAPI_InitFlat.return_value = 0
        sdk.SteamAPI_SteamScreenshots_v003.return_value = 123
        sdk.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary.return_value = 4
        register('library', '/tmp/水下.jpg', 800, 600)
        sdk.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary.assert_called_once_with(
            123, '/tmp/水下.jpg'.encode(), None, 800, 600)
        sdk.SteamAPI_Shutdown.assert_called_once()

    @patch('desktop.steam_screenshot.ctypes.CDLL')
    def test_invalid_handle_is_reported(self, load):
        sdk = Mock()
        load.return_value = sdk
        sdk.SteamAPI_InitFlat.return_value = 0
        sdk.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary.return_value = 0
        with self.assertRaises(RuntimeError):
            register('library', 'photo.jpg', 800, 600)
        sdk.SteamAPI_Shutdown.assert_called_once()
