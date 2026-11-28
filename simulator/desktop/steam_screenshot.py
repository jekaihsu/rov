"""Register a locally generated JPEG using the Steam flat API bundled with steamworks.js."""
import ctypes
import sys


def register(library, jpeg, width, height):
    sdk = ctypes.CDLL(library)
    sdk.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]
    diagnostic = ctypes.create_string_buffer(1024)
    if sdk.SteamAPI_InitFlat(diagnostic) != 0:
        raise RuntimeError(diagnostic.value.decode(errors='replace'))
    try:
        sdk.SteamAPI_SteamScreenshots_v003.restype = ctypes.c_void_p
        interface = sdk.SteamAPI_SteamScreenshots_v003()
        add = sdk.SteamAPI_ISteamScreenshots_AddScreenshotToLibrary
        add.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        add.restype = ctypes.c_uint32
        if not interface or not add(interface, jpeg.encode('utf-8'), None, int(width), int(height)):
            raise RuntimeError('Steam screenshot registration failed')
    finally:
        sdk.SteamAPI_Shutdown()


if __name__ == '__main__':
    register(*sys.argv[1:])
