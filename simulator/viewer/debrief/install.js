/* Wire debrief timeline, viewpoint and report export into an active replay session.
   RC must stay silent: this module never opens a socket or sends commands. */
import {STRINGS} from './strings.js';
import {eventsForRecording} from './events.js';
import {installTimeline} from './timeline.js';
import {installViewpoint, VIEW_STUDENT, studentDisplayTime} from './viewpoint.js';
import {buildDebriefHtml, downloadDebriefHtml} from './report.js';

function el(tag, className, parent, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  if (parent) parent.append(node);
  return node;
}

function nearestFrame(frames, time) {
  if (!frames?.length) return null;
  let best = frames[0];
  let bestDist = Math.abs((frames[0].t || 0) - time);
  for (const frame of frames) {
    const dist = Math.abs((frame.t || 0) - time);
    if (dist < bestDist) {
      best = frame;
      bestDist = dist;
    }
  }
  return best;
}

export function installDebrief({
  replayBar,
  getReplay,
  setReplayTime,
  setCam,
  sampleSnapshots,
  onFeed,
  captureScreenshot,
}) {
  if (!replayBar) return null;
  document.body.classList.add('debriefing');

  const panel = el('div', 'debrief-panel', replayBar);
  const viewpoint = installViewpoint({
    host: panel,
    setCam,
    onChange() {
      refreshFeed();
    },
  });
  const details = el('details', 'debrief-details', panel);
  el('summary', '', details, STRINGS.notes);
  const notes = el('textarea', 'debrief-notes', details);
  notes.rows = 2;
  notes.placeholder = STRINGS.notesPlaceholder;
  notes.setAttribute('aria-label', STRINGS.notes);
  const exportBtn = el('button', 'debrief-export', panel, STRINGS.exportReport);
  exportBtn.type = 'button';

  const seekRow = replayBar.querySelector('.rp-row') || replayBar;
  const timelineHost = el('div', 'debrief-timeline', seekRow);
  const seek = replayBar.querySelector('#rpSeek');
  if (seek) timelineHost.append(seek);

  function clip() {
    const rep = getReplay();
    return rep?.data?.clips?.[rep.ci] || null;
  }

  function events() {
    const rep = getReplay();
    if (!rep?.data) return [];
    return eventsForRecording(rep.data, rep.ci);
  }

  const timeline = installTimeline({
    bar: timelineHost,
    getDuration() {
      const current = clip();
      return current?.dur || Math.max(0.01, (current?.frames?.at?.(-1)?.t || 0) - (current?.frames?.[0]?.t || 0));
    },
    getTime() {
      return getReplay()?.t || 0;
    },
    setTime(t, options) {
      setReplayTime(t, options);
      refreshFeed();
    },
    getEvents: events,
  });

  function displayTime() {
    const rep = getReplay();
    if (!rep) return 0;
    const current = clip();
    if (!current) return rep.t;
    if (viewpoint.mode !== VIEW_STUDENT) return rep.t;
    const absolute = (current.frames?.[0]?.t || 0) + rep.t;
    const frame = nearestFrame(current.frames, absolute);
    const delayed = studentDisplayTime(absolute, frame);
    return Math.max(0, delayed - (current.frames?.[0]?.t || 0));
  }

  function refreshFeed() {
    const rep = getReplay();
    const current = clip();
    if (!rep || !current || !sampleSnapshots || !onFeed) return null;
    const time = (current.frames?.[0]?.t || 0) + displayTime();
    const snapshot = sampleSnapshots(current.frames, time);
    const state = {...snapshot, type: 'state', paused: false};
    onFeed(state);
    viewpoint.updateCompare(state);
    timeline.paint();
    return state;
  }

  exportBtn.addEventListener('click', async function exportReport() {
    const rep = getReplay();
    const current = clip();
    const eventList = events();
    const screenshots = [];
    if (captureScreenshot && eventList.length) {
      const previous = rep.t;
      const previousPlaying = rep.playing;
      for (const event of eventList.slice(0, 4)) {
        const target = Math.max(0, event.t - (current?.frames?.[0]?.t || 0) - 5);
        setReplayTime(target, {pause: true});
        refreshFeed();
        await new Promise(function waitFrame(resolve) {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        });
        const src = await captureScreenshot();
        if (src) {
          screenshots.push({
            t: event.t,
            caption: `${STRINGS[event.kind] || event.kind} @ ${event.t.toFixed(1)}s`,
            src,
          });
        }
      }
      setReplayTime(previous, {pause: !previousPlaying});
      if (previousPlaying) rep.playing = true;
      refreshFeed();
    }
    const score = current?.frames?.at?.(-1)?.score || {};
    const html = buildDebriefHtml({
      report: {
        vehicle_id: current?.frames?.[0]?.vehicle_id || 'replay',
        elapsed: current?.dur || rep?.t || 0,
        completion: score,
        debrief: {notes: notes.value},
      },
      events: eventList,
      notes: notes.value,
      screenshots,
    });
    downloadDebriefHtml('debrief-report.html', html);
  });

  timeline.renderEvents();
  timeline.paint();
  refreshFeed();

  return {
    viewpoint,
    timeline,
    refreshFeed,
    displayTime,
    events,
    paint() {
      timeline.paint();
      viewpoint.updateCompare(getReplay() && refreshFeed());
    },
    strings: STRINGS,
  };
}
