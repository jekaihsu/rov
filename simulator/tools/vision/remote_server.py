"""Minimal external inference protocol server (empty results, not a trained model)."""
import asyncio
import json
import websockets


async def handle(socket):
    async for message in socket:
        request = json.loads(message)
        # Decode request['image'] and call your permissively licensed model here.
        await socket.send(json.dumps({"id": request["id"], "detections": []}))


async def main():
    async with websockets.serve(handle, "127.0.0.1", 8766, max_size=4 * 1024 * 1024):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
