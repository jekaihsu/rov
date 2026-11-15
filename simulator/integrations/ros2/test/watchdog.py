"""Prove a frozen bridge cannot bypass the simulator's own input watchdog."""
import os
from pathlib import Path
import signal
import time

from check_rpc import snapshot


def main():
    candidates = []
    for process in Path('/proc').glob('[0-9]*'):
        try:
            args = (process / 'cmdline').read_bytes().split(b'\0')
        except (OSError, ProcessLookupError):
            continue
        if any(arg.endswith(b'/lib/rov_sim_bridge/bridge') for arg in args):
            candidates.append(int(process.name))
    assert len(candidates) == 1, candidates
    pid = candidates[0]
    before = snapshot()
    assert not before['locked'], 'Run with continuous ROS command and explicit arm first'
    try:
        os.kill(pid, signal.SIGSTOP)
        time.sleep(1.0)
        frozen = snapshot()
        assert frozen['locked'] and frozen['input_latched'], frozen
        print('PASS: bridge frozen 1.0 s -> server locked=True, input_latched=True')
    finally:
        os.kill(pid, signal.SIGCONT)
    time.sleep(1.0)
    resumed = snapshot()
    assert resumed['locked'] and not resumed['input_latched'], resumed
    print('PASS: resumed with live ROS command -> locked=True, input_latched=False; explicit arm required')


if __name__ == '__main__':
    main()
