// Expedition contract board data shared by the in-flight objective card and the pause menu: the active contract
// with its steps, or the contracts on offer with why one is unavailable. Pure functions over state.expedition
// (qysim/expedition.py); accepting and cancelling send the same operations as the drawer's expedition panel.

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.contracts', {
  help: {
    inspect: '穩定停靠三個站點，以機載相機完成巡檢。',
    recover: '拍攝目標，使用機械臂帶回交付區並釋放。',
    deploy: '從補給區取得感測器，放置到指定海床並拍照。',
  },
  hostOnly: '等待房主接案',
  offline: '目前離線，請等待重新連線。',
});

function distance(a, b) {
  if (!a || !b) return null;
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

export function contractBoard(state, host = true) {
  const expedition = state?.expedition;
  if (state?.mission?.mode !== 'expedition' || !expedition) return null;
  const active = expedition.active;
  if (active) {
    return {
      active: {
        id: active.id,
        label: active.label,
        steps: (active.steps || []).map(function step(entry) {
          const progress = entry.own_progress ?? entry.progress;
          return {
            id: entry.id,
            label: entry.label,
            done: !!entry.completed,
            progress: Number.isFinite(progress) ? progress : null,
            distance: entry.completed ? null : distance(entry.point, state.pos),
          };
        }),
      },
      offers: [],
      host,
    };
  }
  return {
    active: null,
    offers: (expedition.available || []).map(function offer(entry) {
      return {
        kind: entry.kind,
        label: entry.label,
        enabled: !!entry.enabled && host,
        reason: host ? entry.reason || '' : STRINGS.hostOnly,
        help: STRINGS.help[entry.kind] || '',
      };
    }),
    host,
  };
}

function requestId() {
  return globalThis.crypto?.randomUUID?.() || `request-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// send: app.js socket sender. Returns an error text when the command could not be sent.
export function acceptContract(send, kind) {
  const sent = send({ type: 'operation', action: 'expedition_start', request_id: requestId(), contract: kind });
  return sent ? '' : STRINGS.offline;
}

export function cancelContract(send) {
  const sent = send({ type: 'operation', action: 'expedition_cancel', request_id: requestId() });
  return sent ? '' : STRINGS.offline;
}
