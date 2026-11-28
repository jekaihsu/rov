"""Loopback HTTP interface for the internal editor's local mission folder."""

import json
from urllib.parse import urlsplit
from . import custom


def reply(handler, status, body):
    data = json.dumps(body, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def handle(handler):
    path = urlsplit(handler.path).path
    if path not in ("/api/missions", "/api/missions/validate", "/api/missions/sites"):
        return False
    host = handler.headers.get("Host", "")
    local = {"127.0.0.1", "localhost"}
    if not custom.enabled() or handler.client_address[0] not in local or host.split(":")[0] not in local:
        reply(handler, 403, {"error": "local"})
    elif handler.command == "GET" and path.endswith("/sites"):
        from ..scenarios import LIBRARY

        sites = []
        for key, build in LIBRARY.items():
            site = build()
            world = dict(
                current=dict(surface_kn=site.current.surface_kn, surface_dir=site.current.surface_dir),
                start_pos=site.start_pos,
                spool=site.spool_pos,
                scenario=site.summary(),
                seabed_depth=site.seabed_depth,
                obstacles=[o.as_dict() for o in site.obstacles],
            )
            sites.append(dict(key=key, name=site.name, world=world))
        reply(handler, 200, sites)
    elif handler.command == "GET":
        reply(handler, 200, list(custom.courses()))
    elif handler.headers.get("Origin") != "http://" + host:
        reply(handler, 403, {"error": "origin"})
    else:
        try:
            size = int(handler.headers.get("Content-Length", 0))
            if not 0 < size <= 262144:
                raise ValueError("$: 1..262144 bytes")

            def reject(value):
                raise ValueError(f"$: {value}")

            script = json.loads(handler.rfile.read(size), parse_constant=reject)
            if path.endswith("/validate"):
                custom.check(script)
            else:
                custom.save(script)
            reply(handler, 200, {"id": script["id"]})
        except (ValueError, RecursionError) as error:
            reply(handler, 400, {"error": str(error)})
        except OSError as error:
            reply(handler, 500, {"error": str(error)})
    return True
