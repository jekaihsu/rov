"""Q-iRC USB input for QY665 / RC_V001R003S001.

Uses authorized ADB and only ChannelValueGet queries. No robot, firmware
changes or calibration writes. Vendor apps release the port while we read.
"""
from __future__ import annotations
import asyncio
import contextlib
import shutil
import struct
import tempfile
import uuid
from pathlib import Path

CHANNEL_QUERY, CHANNEL_REPLY = 21168, 21169
QUERY_CRC, REPLY_CRC = 136, 178
AXES = ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave")
# Original CHANNEL_CONFIGS: S4(left X), S3(left Y), S1(right X),
# S2(right Y), T1, T2, W1, W2, ...; confirmed by RCTool StickValue(x, y).
AXIS_INDICES = (1, 0, 3, 2, 6, 7)
# Original app: T1 mode, T2 LED, C video, D photo, H lock, A depth.
CONTROL_INDICES = (4, 5, 8, 9, 14, 15)
VENDOR_APPS = ("org.qtproject.rctool", "com.qiyuansz.fifish")
VENDOR_MAIN = "com.qiyuansz.fifish/com.qiyuansz.fifish.ui.home.SplashActivity"


def crc_x25(data: bytes, extra: int) -> int:
    value = 0xffff
    for byte in data + bytes([extra]):
        tmp = byte ^ (value & 0xff)
        tmp ^= (tmp << 4) & 0xff
        value = (value >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)
    return value & 0xffff


def channel_query(seq: int = 0) -> bytes:
    body = bytes([1, 0, 0, seq & 255, 0, 0]) + CHANNEL_QUERY.to_bytes(3, "little") + b"\x01"
    return b"\xfd" + body + struct.pack("<H", crc_x25(body, QUERY_CRC))


class ChannelDecoder:
    """Reassemble MAVLink2 frames; ignore corrupt and unrelated responses."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, ...]]:
        self.buffer.extend(data)
        result = []
        while self.buffer:
            start = self.buffer.find(b"\xfd")
            if start < 0:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < 12:
                break
            length = self.buffer[1]
            if self.buffer[2] != 0:
                del self.buffer[0]
                continue
            size = length + 12
            if len(self.buffer) < size:
                break
            packet = bytes(self.buffer[:size])
            if int.from_bytes(packet[7:10], "little") != CHANNEL_REPLY:
                del self.buffer[:size]
                continue
            if length < 46 or crc_x25(packet[1:-2], REPLY_CRC) != int.from_bytes(packet[-2:], "little"):
                del self.buffer[0]
                continue
            values = struct.unpack("<23H", packet[10:56])
            if all(1000 <= values[i] <= 2000 for i in AXIS_INDICES + CONTROL_INDICES):
                result.append(values)
            del self.buffer[:size]
        return result


def axes_from_channels(values: tuple[int, ...]) -> dict[str, int]:
    return {name: values[index] for name, index in zip(AXES, AXIS_INDICES)}


class QircControls:
    """Translate physical edges using the current simulator toggle state.

    First/reconnected packets establish a baseline. A held button must be
    released before it can trigger; reconnecting cannot unlock or take a photo.
    Switch changes and browser buttons use the most recent deliberate action.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.previous = None
        self.blocked = set()

    @staticmethod
    def switch(value):
        return 0 if value < 1200 else 2 if value > 1800 else 1

    def update(self, raw, current):
        first = self.previous is None
        pressed = {name: raw[index] > 1800 for name, index in
                   (("record", 8), ("photo", 9), ("rc_lock", 14), ("keep_depth", 15))}
        if first:
            self.blocked = {name for name, down in pressed.items() if down}
        self.blocked.intersection_update(name for name, down in pressed.items() if down)
        values = axes_from_channels(raw)
        for name, index in (("left_switch", 4), ("right_switch", 5)):
            value = self.switch(raw[index])
            if first or value != self.switch(self.previous[index]):
                values[name] = value
        for name, index in (("rc_lock", 14), ("keep_depth", 15)):
            if not first and name not in self.blocked and pressed[name] and self.previous[index] <= 1800:
                values[name] = 1 - getattr(current, name)
        for name in ("record", "photo"):
            values[name] = int(pressed[name] and name not in self.blocked)
        self.previous = tuple(raw)
        return values


def reader_script() -> str:
    escaped = "".join("\\%03o" % b for b in channel_query())
    # PID + session token allow explicit cleanup even if the Windows parent dies.
    # Only terminate our own helper after verifying its Android command line.
    return f"""#!/system/bin/sh
pid_file=/data/local/tmp/qysim-qirc-reader.pid
old_pid=
old_token=
if [ -r "$pid_file" ]; then read -r old_pid old_token < "$pid_file"; fi
if [ "$1" = stop ] && [ "$old_token" != "$2" ]; then exit 0; fi
case "$old_pid" in
  ''|*[!0-9]*) ;;
  *) if [ -r "/proc/$old_pid/cmdline" ] && tr '\\000' ' ' < "/proc/$old_pid/cmdline" | grep -Fq '/data/local/tmp/qysim-qirc-read.sh run '; then
         kill "$old_pid" 2>/dev/null
     fi ;;
esac
if [ "$1" = stop ]; then exit 0; fi
if [ "$1" != run ] || [ -z "$2" ]; then exit 1; fi
sleep 0.1
echo "$$ $2" > "$pid_file"
exec 3<>/dev/ttyHS3 || exit 1
cat <&3 &
reader_pid=$!
trap 'kill "$reader_pid" 2>/dev/null; exec 3>&-' EXIT
trap 'exit 0' HUP INT TERM
count=0
while [ "$count" -lt 90000 ] && kill -0 "$reader_pid" 2>/dev/null; do
    printf '{escaped}' >&3 || break
    count=$((count + 1))
    sleep 0.04
done
exit 0
"""


class QircReader:
    def __init__(self, adb: str | None = None, serial: str | None = None, port: int = 5038):
        bundled = Path(__file__).resolve().parents[2] / ".runtime/android/platform-tools/adb.exe"
        self.adb = adb or (str(bundled) if bundled.exists() else shutil.which("adb"))
        self.serial = serial
        self.port = port
        self.process = None
        self.apps_stopped = False
        self.stream_token = None

    def command(self, *args, device=True):
        if not self.adb:
            raise RuntimeError("找不到 adb，請安裝 Android Platform Tools")
        cmd = [self.adb, "-P", str(self.port)]
        if device:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    async def call(self, *args, device=True, timeout=8):
        proc = await asyncio.create_subprocess_exec(*self.command(*args, device=device),
                                                  stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except BaseException:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise RuntimeError(err.decode(errors="replace").strip() or "ADB 指令失敗")
        return out.decode(errors="replace")

    async def prepare(self):
        if not self.serial:
            output = await self.call("devices", "-l", device=False)
            matches = [line.split()[0] for line in output.splitlines()
                       if len(line.split()) > 1 and line.split()[1] == "device" and "model:Q_iRC" in line]
            if len(matches) != 1:
                raise RuntimeError("請接上 Q-iRC USB，選 Local Data Transfer 並允許 USB 偵錯")
            self.serial = matches[0]
        await self.call("shell", "test", "-r", "/dev/ttyHS3")
        with tempfile.TemporaryDirectory(prefix="qysim-qirc-") as folder:
            script = Path(folder) / "qysim-qirc-read.sh"
            script.write_text(reader_script(), encoding="ascii", newline="\n")
            await self.call("push", str(script), "/data/local/tmp/qysim-qirc-read.sh")
        self.apps_stopped = True
        for package in VENDOR_APPS:
            await self.call("shell", "am", "force-stop", package)

    async def stop_stream(self):
        if self.stream_token is not None:
            token, self.stream_token = self.stream_token, None
            with contextlib.suppress(Exception):
                await self.call("shell", "sh", "/data/local/tmp/qysim-qirc-read.sh", "stop", token, timeout=3)
        if self.process is not None:
            if self.process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    self.process.kill()
                await self.process.wait()
            self.process = None

    async def run(self, on_sample, on_status):
        """Callbacks run in the simulator loop; no extra network listener."""
        try:
            while True:
                try:
                    await on_status("正在連接 USB 遙控器")
                    await self.prepare()
                    decoder = ChannelDecoder()
                    self.stream_token = uuid.uuid4().hex
                    self.process = await asyncio.create_subprocess_exec(
                        *self.command("exec-out", "sh", "/data/local/tmp/qysim-qirc-read.sh", "run", self.stream_token),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                    while True:
                        data = await asyncio.wait_for(self.process.stdout.read(4096), timeout=3)
                        if not data:
                            raise RuntimeError("USB 遙控器已中斷")
                        for values in decoder.feed(data):
                            await on_sample(axes_from_channels(values), values)
                except (OSError, RuntimeError, asyncio.TimeoutError) as exc:
                    await on_status(str(exc) or "USB 搖桿資料逾時")
                finally:
                    await self.stop_stream()
                await asyncio.sleep(2)
        finally:
            await self.stop_stream()
            if self.apps_stopped:
                with contextlib.suppress(Exception):
                    await self.call("shell", "am", "start", "-n", VENDOR_MAIN)
