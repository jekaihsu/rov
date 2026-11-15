// Restarting the current run from the pause menu or the results screen, with the commands the drawer already
// sends: a chapter restarts with campaign_start; anything else resets the scene (reset) and, because a reset
// scene comes back in scenario training, sets the play mode again (mission_mode). Host only on the server.

const SCENE_MODES = new Set(['free_explore', 'expedition', 'inspection_coop']);

// The messages that restart what `state` is running, in order.
export function restartMessages(state) {
  const campaign = state?.campaign;
  if (campaign?.status === 'active' && campaign.chapter) {
    return [{ type: 'operation', action: 'campaign_start', chapter: campaign.chapter }];
  }
  const messages = [{ type: 'reset' }];
  const mode = state?.mission?.mode;
  if (SCENE_MODES.has(mode)) messages.push({ type: 'operation', action: 'mission_mode', mode });
  return messages;
}

export function restartRun(send, state) {
  return restartMessages(state).every(function sendOne(message) {
    return send(message);
  });
}
