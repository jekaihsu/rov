/* Wire debrief timeline, viewpoint and report export into an active replay session.
   RC must stay silent: this module never opens a socket or sends commands.
   Public demo replays stay on the plain replay bar; only instructor / training records open this panel. */
import {STRINGS, SEEK_LEAD_S} from './strings.js';
import {eventsForRecording, seekTime} from './events.js';
import {installTimeline} from './timeline.js';
import {installViewpoint, VIEW_GOD, VIEW_STUDENT, studentDisplayTime} from './viewpoint.js';
import {buildDebriefHtml, downloadDebriefHtml} from './report.js';
import {installDebriefControls} from './controls.js';
import {getFidelity} from '../fidelity.js';

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

/** Public showcase demos stay on the plain replay chrome; training / instructor clips open debrief. */
export function shouldInstallDebrief(url, data) {
  const source = String(url || '');
  if (/(^|[/?#&=])demo_recording\.json(\b|$)/i.test(source)) return false;
  if (source.endsWith('demo_recording.json')) return false;
  if (data?.debrief || data?.clips?.some((clip) => clip?.debrief)) return true;
  // local: training imports and unnamed fixtures without a demo basename still get the panel.
  return !/demo_recording/i.test(source);
}

export function installDebrief({
  replayBar,
  getReplay,
  setReplayTime,
  setCam,
  feed,
  capture,
  fidelity = getFidelity(),
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

  function clipStart() {
    return Number(clip()?.frames?.[0]?.t) || 0;
  }

  function events() {
    const rep = getReplay();
    if (!rep?.data) return [];
    return eventsForRecording(rep.data, rep.ci);
  }

  function baseVideoDelaySec() {
    const ms = Number(fidelity?.get?.('videoDelayMs'));
    return Number.isFinite(ms) && ms > 0 ? ms / 1000 : 0;
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
    getStart: clipStart,
  });

  function displayTime() {
    const rep = getReplay();
    if (!rep) return 0;
    const current = clip();
    if (!current) return rep.t;
    if (viewpoint.mode !== VIEW_STUDENT) return rep.t;
    const absolute = (current.frames?.[0]?.t || 0) + rep.t;
    const frame = nearestFrame(current.frames, absolute);
    const delayed = studentDisplayTime(absolute, frame, baseVideoDelaySec());
    return Math.max(0, delayed - (current.frames?.[0]?.t || 0));
  }

  // The app's own replay feed samples at displayTime() and then calls afterFeed with the state it showed.
  function refreshFeed() {
    if (!getReplay() || !clip()) return;
    feed?.();
  }

  function afterFeed(state) {
    viewpoint.updateCompare(state);
    timeline.paint();
  }

  function captureScreenshot() {
    const canvas = capture?.();
    if (!canvas?.toBlob) return Promise.resolve(null);
    return new Promise(function blobToDataUrl(resolve) {
      canvas.toBlob(function read(blob) {
        if (!blob) {
          resolve(null);
          return;
        }
        const reader = new FileReader();
        reader.onload = function loaded() {
          resolve(reader.result);
        };
        reader.readAsDataURL(blob);
      }, 'image/jpeg', 0.72);
    });
  }

  exportBtn.addEventListener('click', async function exportReport() {
    const rep = getReplay();
    const current = clip();
    const eventList = events();
    const screenshots = [];
    const captureMode = viewpoint.mode;
    if (capture && eventList.length) {
      const previous = rep.t;
      const previousPlaying = rep.playing;
      for (const event of eventList.slice(0, 4)) {
        const target = seekTime(event.t, SEEK_LEAD_S, clipStart()) - clipStart();
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
            view: captureMode,
          });
        }
      }
      setReplayTime(previous, {pause: !previousPlaying});
      if (previousPlaying) rep.playing = true;
      refreshFeed();
    }
    const score = current?.frames?.at?.(-1)?.score || {};
    const showBanner = captureMode === VIEW_GOD
      || screenshots.some(function godShot(shot) { return shot.view === VIEW_GOD; });
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
      showViewpointBanner: showBanner,
    });
    downloadDebriefHtml('debrief-report.html', html);
  });

  timeline.renderEvents();
  timeline.paint();
  installDebriefControls({panel, viewpoint}).catch(function ignore() {});

  return {
    viewpoint,
    timeline,
    refreshFeed,
    afterFeed,
    displayTime,
    events,
    paint() {
      timeline.paint();
    },
    strings: STRINGS,
  };
}
