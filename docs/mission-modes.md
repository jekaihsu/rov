# Gameplay mission modes

The launch menu selects a shared mode for the room. Vehicle dynamics, physical damage, currents and tether behavior remain active in every mode.

| Mode ID | Behavior |
| --- | --- |
| `free_explore` | No mission countdown, score or penalties. Dive, take photos and use tools freely. |
| `inspection_coop` | Shared 12-minute survey. Normally three observation stations, chosen from valid scene objectives and clear fallback locations. Any pilot may finish any station. |
| `scenario_training` | Original ordered scene objectives and scoring, retained for existing scenarios and clients. Backend default. |

For a cooperative observation, stay within 1.5 m of the station and below 0.35 m/s ground speed for three uninterrupted seconds, then take a photo. Scene targets that specify an inspected object also require heading within 35 degrees of it. A broken tether cannot complete a station. Leaving the station or moving too fast resets that pilot's dwell. One player's dwell cannot be consumed by another player. Completion is counted once and credited to a vehicle ID. The clock is shared, so three pilots do not consume it three times as quickly.

The photograph check is a pose-based training criterion, not image recognition or proof that a real photograph contains an object. The existing synthetic camera record stores pose metadata; the browser may also export its rendered view.

Commands use the existing WebSocket operation envelope:

```json
{"type":"operation","action":"mission_mode","mode":"inspection_coop"}
{"type":"operation","action":"mission_photo"}
```

Only the room host may change the shared mode. The mode command starts a fresh run; selecting a scene/reset preserves the selected mode but resets progress. Existing SDK and RC camera buttons also count as mission photographs. A photo taken without meeting the criteria still succeeds as a photograph, with the reason in `mission.last_photo.message`.

`S.mission` includes `mode`, `label`, `status`, `elapsed`, `time_limit`, `remaining`, `completed`, `total`, `score`, `ready_target`, `targets`, and `last_photo`. Target fields are `id`, `label`, `point` (NED), `face_point`, `radius`, `hold_s`, `progress` (best team dwell), `own_progress`, `ready`, `completed`, `completed_by`, and `completed_at`. Free exploration has an empty target array and null score/time limit/remaining. Training has status `training`; use the original `S.score` objectives. Cooperative terminal states are `completed` and `expired`.

Free/cooperative `S.score` remains structurally compatible with old HUD rendering but derives from this mission run. The original scorer remains internal for compatibility; its hidden legacy penalties do not affect free/cooperative mission scores. Only scenario-training mode exposes those original penalties.
