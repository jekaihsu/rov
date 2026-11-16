"""Hold flight inputs until a condition holds, budgeted in simulated seconds rather than wall time.

On a loaded host the server's fixed-step simulation and the software-rendered page both slow down, so a
wall-clock wait measures the machine, not the vehicle. A wait fails once the simulation itself has run its
budget without the condition holding; the scaled wall timeout is only a stalled-server watchdog.

A page starved for longer than the accepted heartbeat hold (AGENTS.md: about 2.6 s) is locked by the
server's failsafe. That is correct product behaviour, so on a host declared slow (ROV_BROWSER_TIMEOUT_SCALE
above 1) the driver does what a pilot does: release the input, unlock again and repeat it. Each relock is
printed. At the default scale (CI, an idle host) no relock is tolerated, so a spontaneous lock still fails.
"""
from _browser import timeout, without_render

SIM_BUDGET_S = 20.0
# The simulated-time budget is the pass criterion; this cap only stops a wait that makes no progress at all.
MAX_RELOCKS = 0 if timeout(1000) <= 1000 else 40

# `condition` is a function body evaluated with `v = window.__viewer`; it returns true once the goal is met.
PROGRESS = """({condition, start, budget, watchLock}) => {
  const viewer = window.__viewer;
  const state = viewer?.S;
  if (!state) return false;
  if (new Function('v', condition)(viewer)) return {status: 'done'};
  const detail = {t: state.t, locked: state.locked, latched: state.input_latched, pos: state.pos, vel: state.vel,
                  rc: state.rc};
  if (watchLock && (state.locked || state.input_latched)) return {status: 'locked', ...detail};
  if (state.t - start > budget) return {status: 'expired', ...detail};
  return false;
}"""


def wait_condition(page, condition, watch_lock=False, budget=SIM_BUDGET_S):
    """Wait until condition holds or the simulated budget runs out; returns the page-side status dictionary."""
    start = page.evaluate('window.__viewer.S.t')
    arg = {'condition': condition, 'start': start, 'budget': budget, 'watchLock': watch_lock}
    handle = page.wait_for_function(PROGRESS, arg=arg, timeout=timeout(240000) + int(budget * 4000))
    return handle.json_value()


LOCK_DETAIL = '({generation: window.__viewer.S.control_generation, pageLock: window.__viewer.rc.rc_lock})'


def unlock_again(page, unlock):
    """Unlock (a key name or a callable) until the server reports the vehicle unlocked and resynchronised."""
    before = page.evaluate(LOCK_DETAIL)
    for _ in range(3):
        if callable(unlock):
            unlock()
        else:
            page.keyboard.press(unlock)
        try:
            page.wait_for_function('!window.__viewer.S.locked && !window.__viewer.S.input_latched',
                                   timeout=timeout(15000))
            return
        except Exception:
            continue
    after = page.evaluate(LOCK_DETAIL)
    # A rising control_generation means the server kept failsafe-locking while we tried to unlock.
    raise AssertionError(f'vehicle did not unlock after a failsafe lock: before {before}, after {after}')


def hold_until(page, key, condition, unlock, label, budget=SIM_BUDGET_S, watch_lock=True, allies=()):
    """Hold key until condition holds; recover from failsafe locks caused by host load. Returns the relock count.

    WebGL draws are skipped on the page and its allies while waiting (the viewer's own __skipRender flag):
    software rendering is what starves the input heartbeat on a busy host, and nothing drawn is asserted
    during the wait. Input sampling, the socket and the animation loop keep running.
    """
    relocks = 0
    with without_render(page, *allies):
        while True:
            page.keyboard.down(key)
            result = wait_condition(page, condition, watch_lock=watch_lock, budget=budget)
            page.keyboard.up(key)
            if result['status'] == 'done':
                return relocks
            if result['status'] == 'expired':
                raise AssertionError(f'{label} did not complete within {budget} simulated s: {result}')
            relocks += 1
            print(f'failsafe lock during {label} (relock {relocks}): {result}', flush=True)
            if relocks > MAX_RELOCKS:
                raise AssertionError(f'{label}: more than {MAX_RELOCKS} failsafe locks: {result}')
            unlock_again(page, unlock)


def left_node(node_id):
    return f'return v.S.campaign.node?.id !== {node_id!r};'


def hold_until_advanced(page, node_id, key, unlock_key):
    """Hold key until the story leaves node_id. The unlock node is a key tap confirmed by the server."""
    if key != unlock_key:
        return hold_until(page, key, left_node(node_id), unlock_key, node_id)
    with without_render(page):
        if page.evaluate('window.__viewer.S.locked'):
            unlock_again(page, unlock_key)
        wait_left(page, node_id)
    return 0


def wait_left(page, node_id):
    """Wait for a node the driver has already acted on (dialogue, checkpoint) to be left."""
    result = wait_condition(page, left_node(node_id))
    if result['status'] != 'done':
        raise AssertionError(f'{node_id} did not advance within {SIM_BUDGET_S} simulated s: {result}')
