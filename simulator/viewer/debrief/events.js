/* Extract debrief timeline markers from replay frames or a stored debrief block. */
import {SEEK_LEAD_S, SILT_WHITEOUT} from './strings.js';

function rising(prev, now) {
  return !prev && !!now;
}

function eventRow(kind, t, detail, extra) {
  const row = {kind, t: Number(t) || 0, detail: detail || ''};
  if (extra) Object.assign(row, extra);
  return row;
}

export function seekTime(eventT, leadS = SEEK_LEAD_S, startT = 0) {
  return Math.max(startT, Number(eventT) - leadS);
}

export function extractEventsFromFrames(frames, injections) {
  const events = [];
  for (const item of injections || []) {
    const start = item.start ?? item.t;
    if (start == null) continue;
    events.push(eventRow('instructor_inject', start, String(item.kind || 'inject'), {
      injection: item.kind,
      vehicle_id: item.vehicle_id,
    }));
  }
  let prevBroken = false;
  let prevWarn = false;
  let prevWrap = false;
  let prevSilt = false;
  let prevDvlLost = false;
  let prevComms = false;
  const prevDone = new Map();
  const seenCollision = new Set();
  const seenPenalty = new Set();
  for (const frame of frames || []) {
    const t = Number(frame.t) || 0;
    for (const contact of frame.events || []) {
      if (!contact || typeof contact !== 'object') continue;
      const key = `${contact.t}|${contact.obstacle}|${contact.severity}|${contact.where}`;
      if (seenCollision.has(key)) continue;
      seenCollision.add(key);
      const detail = [contact.obstacle, contact.severity].filter(Boolean).join(' · ');
      events.push(eventRow('collision', contact.t ?? t, detail, {
        severity: contact.severity,
        obstacle: contact.obstacle,
      }));
    }
    const tether = frame.tether || {};
    const wraps = tether.wraps || {};
    const snagged = Object.keys(wraps).length > 0 || (tether.snagged_on || []).length > 0;
    const warn = !!tether.warn;
    const broken = !!tether.broken;
    if (rising(prevWarn, warn)) {
      events.push(eventRow('tether_warn', t, tether.tension_max != null ? `${tether.tension_max} N` : ''));
    }
    if (rising(prevWrap, snagged)) {
      const names = Object.keys(wraps);
      events.push(eventRow('tether_snag', t, names.join(', ') || 'snag'));
    }
    if (rising(prevBroken, broken)) events.push(eventRow('tether_break', t, ''));
    prevWarn = warn;
    prevWrap = snagged;
    prevBroken = broken;
    const silt = Number(frame.silt) || 0;
    const white = silt >= SILT_WHITEOUT;
    if (rising(prevSilt, white)) events.push(eventRow('silt_whiteout', t, `silt=${silt.toFixed(2)}`));
    prevSilt = white;
    const dvl = frame.sensors?.dvl || {};
    const dvlLost = dvl.status === 'lost';
    if (rising(prevDvlLost, dvlLost)) events.push(eventRow('dvl_lost', t, dvl.reason || ''));
    prevDvlLost = dvlLost;
    const link = frame.link || {};
    const lost = link.state === 'lost';
    if (rising(prevComms, lost)) events.push(eventRow('comms_loss', t, link.cause || ''));
    prevComms = lost;
    const score = frame.score || {};
    (score.objectives || []).forEach(function trackObjective(objective, index) {
      const done = !!objective.done;
      if (rising(prevDone.get(index), done)) {
        events.push(eventRow('objective_done', t, objective.label || String(index)));
      }
      prevDone.set(index, done);
    });
    for (const penalty of score.penalties || []) {
      const key = `${penalty.t}|${penalty.reason}|${penalty.points}`;
      if (seenPenalty.has(key)) continue;
      seenPenalty.add(key);
      events.push(eventRow('penalty', penalty.t ?? t, penalty.reason || '', {points: penalty.points}));
    }
  }
  events.sort((a, b) => a.t - b.t || a.kind.localeCompare(b.kind));
  return events;
}

export function eventsForRecording(recording, clipIndex = 0) {
  const stored = recording?.debrief?.events;
  if (Array.isArray(stored) && stored.length) return stored.slice();
  const clip = recording?.clips?.[clipIndex];
  if (!clip) return [];
  const clipStored = clip.debrief?.events;
  if (Array.isArray(clipStored) && clipStored.length) return clipStored.slice();
  const injections = clip.debrief?.injections || recording?.debrief?.injections;
  return extractEventsFromFrames(clip.frames || [], injections);
}
