# 尚未接入的文字模組

已擷取繁中基準，尚未翻譯／接入（prefs.display 的語言自稱刻意維持原文）。

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
- `procedure.index`
- `qysim.aquaculture.STRINGS`
- `qysim.debrief.STRINGS`
- `qysim.scenarios.INCIDENT_STRINGS`
- `qysim.scenarios.STRINGS`
- `qysim.sensors.STRINGS`
- `sonar.panel`
- `story.campaign`
- `tether.operations`
- `tether.snag_focus`
- `tether_reel`
- `vision.overlay`

## 合併 main（職涯、大片感選單、品牌）後新增、尚未接入

以下模組在 L1 分支之後才合併進 main；繁中基準已擷取（`i18n_extract.py`），尚未翻譯／接入。
括號內為含中文的字串數。

- `brand.chapters`（53）、`brand.licence_card`（18）、`brand.demo`（11）、`brand.demo_page`（8）、
  `brand.marks`（2）、`brand.menu_brand`（2）
- `career.contract_screen`（28）、`career.board`（27）、`career.results_panel`（23）、`career.shop`（22）、
  `career.dive`（19）、`career.deliverables`（14）、`career.summary`（7）、`career.rules`（5）、
  `career.shop_rules`（4）、`career.save`（3）、`career.settle`（3）、`career.fidelity_item`（2）
- `menu.big_picture`（2）
- `qysim.scenarios.PEN_VARIANT_STRINGS`（4）
- 不在 STRINGS 內、工具掃不到的資料檔：`viewer/career/contracts.json`、`licences.json`、`equipment.json`
  （工單標題、說明、交付項目、執照與裝備名稱），以及 `career/scoring.js`、`brand/chapter_card.js` 內的零星字串。
  需比照 PROTOCOL.md「前端依穩定 key 翻譯」的做法另定資料檔的 key。

另見 PROTOCOL.md 的伺服器／劇情／匯出快照盤點。
