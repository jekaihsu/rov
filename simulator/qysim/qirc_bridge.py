"""Attach this computer's USB controller to an existing online pilot seat.

    python -m qysim.qirc_bridge --config pairing.json [--adb path/to/adb]

Download the private pairing file from the pilot UI. Keep the browser open.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from .qirc import QircControls, QircReader
from .rc import RCState


class ControllerBridge:
    def __init__(self, config, reader):
        self.config = config
        self.reader = reader
        self.rc = RCState()
        self.controls = QircControls()
        self.ws = None
        self.seq = 0
        self.last_sample = 0.
        self.connected = False
        self.lock = asyncio.Lock()

    async def send(self, values):
        if self.ws is not None:
            async with self.lock:
                await self.ws.send(json.dumps({"type": "rc", "seq": self.seq, "rc": values}))
                self.seq += 1

    async def sample(self, axes, raw):
        self.last_sample = time.monotonic()
        if not self.connected:
            self.rc.centre_sticks()
            self.rc.rc_lock = 1
            self.controls.reset()
            self.connected = True
        values = self.controls.update(raw, self.rc)
        for key, value in values.items():
            setattr(self.rc, key, value)
        # Never hold the USB reader up while the network is reconnecting.
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.send(values)

    async def status(self, reason):
        self.connected = False
        self.controls.reset()
        self.rc.centre_sticks()
        self.rc.rc_lock = 1
        print(reason, flush=True)
        with contextlib.suppress(Exception):
            await self.send(self.rc.as_dict())

    async def watchdog(self):
        while True:
            if self.connected and time.monotonic() - self.last_sample >= .6:
                await self.status("USB 輸入逾時，已鎖定")
            await asyncio.sleep(.1)

    async def network(self):
        import websockets
        while True:
            try:
                async with websockets.connect(self.config["url"], max_size=2 ** 22) as ws:
                    await ws.send(json.dumps({"type": "attach_controller", "room_id": self.config["room_id"],
                                              "resume_token": self.config["resume_token"]}))
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") == "controller_session":
                            self.seq = 0
                            self.ws = ws
                            self.connected = False
                            self.controls.reset()
                            self.rc.rc_lock = 1
                            print("已配對遠端座席；請放開按鍵後再解鎖。", flush=True)
                        elif msg.get("type") == "state" and self.ws is ws:
                            for key, value in msg.get("rc", {}).items():
                                if hasattr(self.rc, key):
                                    setattr(self.rc, key, value)
                        elif msg.get("type") == "error":
                            raise RuntimeError(msg.get("message", msg.get("code", "Bridge rejected")))
            except (OSError, RuntimeError, websockets.exceptions.WebSocketException) as exc:
                print(f"橋接離線：{exc}；2 秒後重試", flush=True)
            finally:
                self.ws = None
                self.connected = False
                self.controls.reset()
            await asyncio.sleep(2.)

    async def run(self):
        tasks = [asyncio.create_task(self.reader.run(self.sample, self.status)),
                 asyncio.create_task(self.network()), asyncio.create_task(self.watchdog())]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="USB controller bridge for an online ROV pilot")
    parser.add_argument("--config", required=True, help="Private pairing JSON downloaded from the pilot UI")
    parser.add_argument("--adb", default=None)
    parser.add_argument("--serial", default=None)
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    if urlparse(config.get("url", "")).scheme not in ("ws", "wss"):
        parser.error("Pairing URL must use ws:// or wss://")
    if not config.get("resume_token") or not config.get("room_id"):
        parser.error("Pairing file needs room_id and resume_token")
    try:
        asyncio.run(ControllerBridge(config, QircReader(adb=args.adb, serial=args.serial)).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
