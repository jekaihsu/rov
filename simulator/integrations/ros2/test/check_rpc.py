"""Smoke assertions on authoritative simulator state, separate from ROS feedback."""
import json
import socket
import sys
import time


def snapshot():
    with socket.create_connection(('127.0.0.1', 9760), timeout=2) as sock:
        sock.sendall(b'{"id":1,"type":"state"}\n')
        with sock.makefile('rb') as stream:
            response = json.loads(stream.readline())
    assert response['ok'], response
    return response['result']


def main():
    mode = sys.argv[1]
    state = snapshot()
    if mode == 'depth':
        # The simulator can run below real time; wait for convergence, not a fixed wall-clock delay.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert not state['locked'] and state['keep_depth'], state
            hold = state['depth_hold']
            if hold is not None and abs(hold - 3) < .3 and abs(state['pos'][2] - 3) < .3:
                break
            time.sleep(.1)
            state = snapshot()
    print(json.dumps({key: state[key] for key in
                      ('locked', 'input_latched', 'pos', 'vel', 'rc', 'depth_hold')}, sort_keys=True))
    if mode == 'locked':
        assert state['locked']
    elif mode == 'moving':
        assert not state['locked']
        assert state['vel'][0] > .03, state['vel']
        assert state['rc']['right_switch'] == 2
        assert state['rc']['right_ud'] > 1500
    elif mode == 'depth':
        assert not state['locked']
        assert state['keep_depth']
        assert state['depth_hold'] is not None
        assert abs(state['depth_hold'] - 3) < .3, state['depth_hold']
        assert abs(state['pos'][2] - 3) < .3, state['pos']
    print('PASS:', mode)


if __name__ == '__main__':
    main()
