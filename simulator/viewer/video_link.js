// Presentation rules for the simulated vehicle link (`state.link`, owned by the server).
// No imports: state_buffer.js receives this presenter as a parameter and both are unit-tested from data URLs.
// A healthy or absent link has no effect, so normal play and older servers are unchanged.

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

// What the onboard video and telemetry should do for one link report, or null when nothing changes.
export function linkEffect(link) {
  if (!link || typeof link !== 'object' || !link.state || link.state === 'healthy') return null;
  const lag = Number(link.video_lag_s);
  const artefact = Number(link.artefact);
  const telemetry = link.telemetry_hz;
  return {
    state: link.state,
    lost: link.state === 'lost',
    frozen: !!link.video_frozen,
    extraDelay: Number.isFinite(lag) ? clamp(lag, 0, 10) : 0,
    artefact: Number.isFinite(artefact) ? clamp(artefact, 0, 1) : 0,
    telemetryHz: Number.isFinite(telemetry) ? Math.max(0, telemetry) : null,
  };
}

// Holds the last telemetry packet and releases a new one at the link's telemetry rate (none while lost).
export function createTelemetryGate() {
  let held = null;
  let heldAt = -Infinity;
  return function gate(latest, effect, now) {
    if (!effect || effect.telemetryHz === null) {
      held = latest;
      heldAt = now;
      return null;
    }
    if (held === null) {
      held = latest;
      heldAt = now;
    }
    if (effect.telemetryHz > 0 && now - heldAt >= 1 / effect.telemetryHz) {
      held = latest;
      heldAt = now;
    }
    return held;
  };
}

// The object createRenderState() accepts as `link`.
export function createLinkPresenter() {
  return {effect: linkEffect, telemetry: createTelemetryGate()};
}
