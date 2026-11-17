# 尚未接入的文字模組

已擷取繁中基準，尚未翻譯／接入（prefs.display 的語言自稱刻意維持原文）。

N4 已接入：`brand.*`、`career.*`（含 `career.copy` 對應 contracts／licences／equipment JSON）、
`procedure.index`／`deck_steps`／`crew_radio`／`deck_stage`／`fidelity_item`、`menu.big_picture`。
鍵值方案見 `simulator/viewer/career/copy.js` 與 `localize_data.js`（`career.copy.<bucket>.<id>.<field>`）。

仍待接入：

- `asset_config`
- `audio.engine`
- `audio.fidelity`
- `audio.music_fidelity`
- `camera_rig`
- `control_layout`
- `debrief.strings`
- `fidelity`
- `fidelity_panel`
- `fleet_names`
- `fx.beautify`
- `fx.silt`
- `input.bindings`
- `input.calibrate`
- `input.haptics_fidelity`
- `input.hints`
- `input.settings`
- `instructor.strings`
- `pilot_station`
- `prefs.display`
- `qysim.aquaculture.STRINGS`
- `qysim.debrief.STRINGS`
- `qysim.scenarios.INCIDENT_STRINGS`
- `qysim.scenarios.PEN_VARIANT_STRINGS`
- `qysim.scenarios.STRINGS`
- `qysim.sensors.STRINGS`
- `sonar.panel`
- `story.campaign`
- `tether.operations`
- `tether.snag_focus`
- `tether_reel`
- `vision.overlay`

另見 PROTOCOL.md 的伺服器／劇情／匯出快照盤點。
