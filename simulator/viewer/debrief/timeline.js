/* Compact debrief markers over the existing seek control. Click seeks to t − lead. */
import {STRINGS, SEEK_LEAD_S} from './strings.js';
import {seekTime} from './events.js';

function el(tag, className, parent) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (parent) parent.append(node);
  return node;
}

// Event times are absolute recording times; the seek bar and setTime are relative to the clip start.
export function installTimeline({bar, getDuration, getTime, setTime, getEvents, getStart, onSelect}) {
  let rail = bar.querySelector('.debrief-rail');
  if (!rail) {
    rail = el('div', 'debrief-rail', bar);
    rail.setAttribute('aria-label', STRINGS.timeline);
  }
  const markers = el('div', 'debrief-markers', rail);
  // Event chips live on the compact toolbar (sibling of the seek row), not inside .rp-row.
  const chipHost = bar.closest('.replay') || bar;
  let list = chipHost.querySelector('.debrief-event-list');
  if (!list) list = el('ol', 'debrief-event-list', chipHost);

  function duration() {
    return Math.max(0.01, Number(getDuration()) || 0.01);
  }

  function start() {
    return Number(getStart?.()) || 0;
  }

  function jumpTo(event) {
    const target = seekTime(event.t, SEEK_LEAD_S, start()) - start();
    setTime(target, {pause: true});
    onSelect?.(event, target);
  }

  function paint() {
    // Progress fill is the native range input; markers only need a re-layout hook.
    rail.dataset.t = String(Math.round(Number(getTime()) || 0));
  }

  function renderEvents() {
    markers.replaceChildren();
    list.replaceChildren();
    const dur = duration();
    const events = getEvents() || [];
    if (!events.length) {
      list.textContent = STRINGS.emptyEvents;
      return;
    }
    for (const event of events) {
      const marker = el('button', `debrief-marker kind-${event.kind}`, markers);
      marker.type = 'button';
      const offset = Math.max(0, Math.min(1, (event.t - start()) / dur));
      marker.style.left = `${offset * 100}%`;
      marker.title = `${STRINGS[event.kind] || event.kind} · ${event.t.toFixed(1)}${STRINGS.seconds}`;
      marker.setAttribute('aria-label', marker.title);
      marker.addEventListener('click', function jump(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        jumpTo(event);
      });
      const row = el('li', `debrief-event kind-${event.kind}`, list);
      const time = el('button', 'debrief-event-time', row);
      time.type = 'button';
      time.textContent = `${event.t.toFixed(1)}${STRINGS.seconds}`;
      time.addEventListener('click', function jump() {
        jumpTo(event);
      });
      const label = el('span', 'debrief-event-label', row);
      label.textContent = STRINGS[event.kind] || event.kind;
    }
  }

  return {
    renderEvents,
    paint,
    root: rail,
    list,
  };
}
