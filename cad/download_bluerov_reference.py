"""Fetch the official R3 mesh by ZIP byte ranges, without the unused CAD files.

Reference-only output under .runtime; does not replace any release asset.
"""
import datetime
import hashlib
import json
from pathlib import Path
import struct
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime" / "bluerov-reference"
URL = "https://cad.bluerobotics.com/BLUEROV2-R3.zip"


def get_range(first, count):
    req = urllib.request.Request(URL, headers={"Range": f"bytes={first}-{first+count-1}", "User-Agent": "ROV-Reference-Inspection/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status != 206:
            raise RuntimeError("Server did not honor the bounded byte range")
        data = response.read()
    if len(data) != count:
        raise RuntimeError("Incomplete CAD byte range")
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(URL, method="HEAD"), timeout=30) as response:
        length = int(response.headers["Content-Length"])
    tail = get_range(length-65536, 65536)
    at = 0
    while True:
        at = tail.find(b"PK\x01\x02", at)
        if at < 0:
            raise RuntimeError("Official ZIP has no STL entry")
        entry = struct.unpack_from("<4s6H3I5H2I", tail, at)
        name = tail[at+46:at+46+entry[10]].decode("utf-8")
        if name.lower().endswith(".stl"):
            break
        at += 46 + entry[10] + entry[11] + entry[12]
    compressed, raw, crc_expected, offset = entry[8], entry[9], entry[7], entry[16]
    local = struct.unpack("<4s5H3I2H", get_range(offset, 30))
    start = offset + 30 + local[9] + local[10]
    path = OUT / "bluerov2-r3-official.stl"
    metadata = OUT / "source.json"
    if path.exists() and path.stat().st_size == raw and metadata.exists():
        print("Already fetched", path, flush=True)
        return
    decoder = zlib.decompressobj(-15) if entry[4] == 8 else None
    if entry[4] not in (0, 8):
        raise RuntimeError("Unsupported ZIP compression")
    digest, crc, total = hashlib.sha256(), 0, 0
    print(f"Official mesh: {name}; compressed {compressed:,}; STL {raw:,}", flush=True)
    with path.open("wb") as target:
        for used in range(0, compressed, 2*1024*1024):
            chunk = get_range(start+used, min(2*1024*1024, compressed-used))
            data = decoder.decompress(chunk) if decoder is not None else chunk
            target.write(data)
            digest.update(data)
            crc = zlib.crc32(data, crc)
            total += len(data)
            print(f"Downloaded {min(compressed,used+len(chunk)):,}/{compressed:,} bytes", flush=True)
    if crc != crc_expected or total != raw:
        raise RuntimeError("Official STL checksum/size mismatch")
    metadata.write_text(json.dumps(dict(url=URL, member=name, bytes=raw, compressed_bytes=compressed,
        sha256=digest.hexdigest(), crc32=f"{crc:08x}", downloaded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose="Local reference inspection only; commercial redistribution license not verified."), indent=2), encoding="utf-8")
    print("VERIFIED", path, digest.hexdigest(), flush=True)


if __name__ == "__main__":
    main()
