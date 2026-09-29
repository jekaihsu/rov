"""JSON-lines TCP client used by the mock ``qysea`` package to reach the simulator.

One persistent connection per (host, port) is shared by every manage object in
the process. Calls are serialised with a lock, so the client is safe to use from
several threads (status pollers, camera loops, GUI callbacks).

Environment:
    QYSIM_HOST       simulator host            (default 127.0.0.1)
    QYSIM_RPC_PORT   simulator SDK RPC port    (default 9760)
    QYSIM_TIMEOUT    per-call reply timeout, s (default 3.0)
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import threading


class SimUnavailable(Exception):
    """The simulator could not be reached. ``kind`` is 'ConnectTimeout' or 'ReceiveTimeout'."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


class SimError(Exception):
    """The simulator answered ``ok: false`` (a server-side exception)."""


def endpoint() -> tuple[str, int]:
    return os.environ.get("QYSIM_HOST", "127.0.0.1"), int(os.environ.get("QYSIM_RPC_PORT", "9760"))


class RpcClient:
    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.host, self.port = host, port
        self.timeout = float(timeout if timeout is not None else os.environ.get("QYSIM_TIMEOUT", "3.0"))
        self._sock: socket.socket | None = None
        self._rfile = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    # ── connection management ─────────────────────────────────────────────
    def _open(self) -> None:
        try:
            s = socket.create_connection((self.host, self.port), timeout=min(self.timeout, 2.0))
        except OSError as e:
            raise SimUnavailable("ConnectTimeout", f"simulator not reachable at {self.host}:{self.port} ({e})")
        s.settimeout(self.timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = s
        self._rfile = s.makefile("rb")

    def close(self) -> None:
        with self._lock:
            self._drop()

    def _drop(self) -> None:
        for obj in (self._rfile, self._sock):
            try:
                if obj is not None:
                    obj.close()
            except OSError:
                pass
        self._sock = self._rfile = None

    # ── request/response ─────────────────────────────────────────────────
    def _roundtrip(self, payload: dict):
        """One attempt. Returns the response dict, or None if the connection turned out dead
        before the server could have seen the request (safe to retry)."""
        if self._sock is None:
            self._open()
        rid = payload["id"]
        try:
            self._sock.sendall((json.dumps(payload) + "\n").encode())
        except OSError:
            self._drop()
            return None
        while True:
            try:
                line = self._rfile.readline()
            except socket.timeout:
                self._drop()           # a late reply must not be read by the next call
                raise SimUnavailable("ReceiveTimeout", f"no reply from simulator within {self.timeout:.1f}s")
            except OSError:
                self._drop()
                return None
            if not line:               # server closed the connection (e.g. it restarted)
                self._drop()
                return None
            try:
                resp = json.loads(line)
            except ValueError:
                continue
            if resp.get("id") == rid:
                return resp

    def request(self, payload: dict):
        """Send one request (``type`` and fields) and return ``result``."""
        with self._lock:
            payload = {**payload, "id": next(self._ids)}
            resp = self._roundtrip(payload)
            if resp is None:           # stale socket: reconnect once and retry
                resp = self._roundtrip(payload)
            if resp is None:
                raise SimUnavailable("ConnectTimeout", "connection to simulator lost")
        if not resp.get("ok", False):
            raise SimError(resp.get("error", "unknown simulator error"))
        return resp.get("result")

    def sdk(self, cls: str, method: str, args=(), kwargs=None):
        return self.request({"type": "sdk", "cls": cls, "method": method,
                             "args": list(args), "kwargs": dict(kwargs or {})})

    def camera_view(self, file_path: str | None = None) -> dict:
        req = {"type": "camera_view"}
        if file_path:
            req["file_path"] = file_path
        return self.request(req)

    def ping(self) -> bool:
        try:
            return self.request({"type": "ping"}) == "pong"
        except (SimUnavailable, SimError):
            return False


_clients: dict[tuple[str, int], RpcClient] = {}
_clients_lock = threading.Lock()


def get_client() -> RpcClient:
    """Shared client for the endpoint currently configured in the environment."""
    key = endpoint()
    with _clients_lock:
        c = _clients.get(key)
        if c is None:
            c = _clients[key] = RpcClient(*key)
        return c


def _jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    try:                               # numpy scalars and the like
        return v.item()
    except AttributeError:
        return str(v)


def sdk_error(text: str, code: str = "408", **extra) -> dict:
    return {"status": "error", "status_code": code, "text": text, **extra}


def call(cls: str, method: str, args=(), kwargs=None, on_fail=None):
    """Forward one SDK call. Transport failures never raise: they are turned into the
    SDK's own error value via ``on_fail(text, code)`` (default: an error dict)."""
    on_fail = on_fail or (lambda text, code: sdk_error(text, code))
    try:
        return get_client().sdk(cls, method, _jsonable(list(args)), _jsonable(kwargs or {}))
    except SimUnavailable as e:
        return on_fail(e.kind, "408")
    except SimError as e:
        return on_fail(f"SimulatorError: {e}", "500")
