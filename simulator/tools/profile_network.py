"""Reproducible serialization and local transport measurements; excludes physics and WAN."""
import json
import statistics
import socket
import threading
import time
from pathlib import Path
from qysim.engine import Simulator
from qysim.server import SimHost, _json_default


def local_transport_ms(payloads):
    """Measure local socket transport only; excludes WebSocket framing and WAN latency."""
    data = ''.join(payloads).encode('utf8')
    sender, receiver = socket.socketpair()

    def drain():
        remaining = len(data)
        while remaining:
            chunk = receiver.recv(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    worker = threading.Thread(target=drain)
    try:
        worker.start()
        start = time.perf_counter()
        sender.sendall(data)
        worker.join()
        return (time.perf_counter() - start) * 1000
    finally:
        sender.close()
        receiver.close()


def benchmark():
    report = {}
    for marks in (0, 128):
        host = SimHost(Simulator('coral_reef', 42))
        players = [host.room.join('Pilot '+str(i), model_id=m)
                   for i, m in enumerate(('x1', 'falcon', 'bluerov2_heavy'))]
        host.sim.world.paint_marks = [
            {'id': i, 'pos': [i*.03, 1.5, 9.2], 'normal': [0., 0., -1.],
             'color': '#f4c430', 'vehicle_id': 'v1'} for i in range(marks)]
        before, after, snapshots, payloads = [], [], [], []
        for cycle in range(80):
            host.room.tick += 1
            start = time.perf_counter()
            states = [host.viewer_state(host.room, p) for p in players]
            snapshots.append((time.perf_counter()-start)*1000)
            start = time.perf_counter()
            baseline = [json.dumps({'type': 'state', **s}, default=_json_default,
                                   ensure_ascii=False) for s in states]
            before.append((time.perf_counter()-start)*1000)
            if hasattr(host, 'viewer_payload'):
                start = time.perf_counter()
                payloads = [host.viewer_payload(host.room, p) for p in players]
                after.append((time.perf_counter()-start)*1000)
                for a, b in zip(baseline, payloads):
                    assert json.loads(a) == json.loads(b), 'Wire state changed'
        row = {'clients': 3, 'state_hz_per_client': host.view_hz,
               'before_bytes_per_second': sum(len(s.encode()) for s in baseline)*host.view_hz,
               'before_serialization_ms': statistics.median(before),
               'snapshot_ms': statistics.median(snapshots),
               'before_total_bytes': sum(len(s.encode()) for s in baseline)}
        if after:
            row.update(after_payload_ms=statistics.median(after),
                       after_total_bytes=sum(len(s.encode()) for s in payloads),
                       semantic_equality=True,
                       after_bytes_per_second=sum(len(s.encode()) for s in payloads)*host.view_hz)
            # Senders are independent: they can land on different physics ticks.
            # Include snapshot creation for BOTH paths in this pessimistic case.
            staggered_before, staggered_after = [], []
            for cycle in range(30):
                tick = host.room.tick
                start = time.perf_counter()
                baseline = []
                for player in players:
                    host.room.tick += 1
                    baseline.append(json.dumps({'type': 'state', **host.viewer_state(host.room, player)},
                                               default=_json_default, ensure_ascii=False))
                staggered_before.append((time.perf_counter()-start)*1000)
                host.room.tick = tick
                start = time.perf_counter()
                payloads = []
                for player in players:
                    host.room.tick += 1
                    payloads.append(host.viewer_payload(host.room, player))
                staggered_after.append((time.perf_counter()-start)*1000)
                assert all(json.loads(a) == json.loads(b) for a, b in zip(baseline, payloads))
            row.update(staggered_before_snapshot_and_payload_ms=statistics.median(staggered_before),
                       staggered_after_snapshot_and_payload_ms=statistics.median(staggered_after))
        row['local_socket_transport_ms'] = statistics.median(
            local_transport_ms(payloads) for _ in range(30))
        row['transport_scope'] = 'local socketpair; excludes WebSocket framing, WAN and scheduling'
        report[str(marks)+'_paint_marks'] = row
    target = Path(__file__).resolve().parents[1]/'output'/'network-validation'
    target.mkdir(parents=True, exist_ok=True)
    (target/'serialization.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    benchmark()
