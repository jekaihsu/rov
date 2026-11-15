# 配樂來源調查：錄音本身為公有領域或 CC0 的曲目

調查日期：2026-11-15。目標：古典與輕鬆風格的配樂，**錄音**（演奏）本身可自由使用，而不只是作曲已進入公有領域。
專案授權白名單（AGENTS.md）只接受 MIT／BSD／Apache／zlib／CC0；本文件另接受「公有領域標記（PDM）」的錄音，
因其效力等同無權利保留。CC-BY、CC-BY-SA、NC、「免版稅但須標示」一律不收。

## 判準

1. 授權必須針對**這一份錄音檔**，不是作曲者或樂譜。古典曲目作曲多已過期，但演奏錄音有獨立的鄰接權。
2. 以發布頁面上機器可讀的授權欄位為主要證據（archive.org 的 `licenseurl`／`rights`、OpenGameArt 的 License 欄），
   並盡量以第二來源佐證（維基百科、檔案內附 readme）。
3. 下載檔視為不可信資料：各存於獨立的空目錄，只用 ffmpeg 讀取，不執行其中任何內容。

## 採用曲目（6 首，共約 7.4 MB）

| 用途 | 檔案 | 曲目 | 演奏／作者 | 來源 | 授權證據（原文） | 原長 → 使用長度 |
|---|---|---|---|---|---|---|
| 標題／主選單 | `title_goldberg_aria.opus` | 巴哈《郭德堡變奏曲》BWV 988 詠嘆調 | Kimiko Ishizaka（Open Goldberg Variations, 2012） | [archive.org/details/OpenGoldbergVariations](https://archive.org/details/OpenGoldbergVariations) | `licenseurl: http://creativecommons.org/publicdomain/zero/1.0/`；維基百科 Kimiko Ishizaka 條目：“released the score and recordings into the public domain in May 2012.” | 4:59 → 2:27（前半段含反覆） |
| 簡報／機庫 | `briefing_wtc_prelude1.opus` | 巴哈《十二平均律》第一冊 第 1 號前奏曲 C 大調 BWV 846 | Kimiko Ishizaka（Open Well-Tempered Clavier, 2015） | [archive.org/details/bach-well-tempered-clavier-book-1](https://archive.org/details/bach-well-tempered-clavier-book-1)（同錄音另見 [OpenWell-TemperedClavier_Book_I](https://archive.org/details/OpenWell-TemperedClavier_Book_I)） | `rights: Released under CC0 1.0 Universal`；另一項目 `licenseurl: http://creativecommons.org/publicdomain/zero/1.0/`，描述：“Every part of it is free for you to use, share, and copy.”；維基百科：“The new recording was released into the public domain in March 2015.” | 2:43 → 2:42 |
| 下潛（主） | `dive_underwater_theme_ii.opus` | Underwater Theme II（無縫循環） | Cleyton Kauffman | [opengameart.org/content/underwater-theme-ii](https://opengameart.org/content/underwater-theme-ii) | 頁面 License(s)：`CC0`（連到 creativecommons.org/publicdomain/zero/1.0/）；壓縮檔內 readme：“[License] Creative Commons Zero (CC0)” | 1:45 → 1:45 |
| 下潛（輪替） | `dive_underwater_theme.opus` | Underwater Theme（2nd variation） | Spring Spring | [opengameart.org/content/underwater-theme-1](https://opengameart.org/content/underwater-theme-1) | 頁面 License(s)：`CC0`；說明：“Slow, minimalistic, ambient, reverby...” | 1:22 → 1:22 |
| 結算／成功 | `results_peer_gynt_morning.opus` | 葛利格《皮爾金》第一號組曲 I. 晨歌 | Musopen 2012 Kickstarter 錄音（捷克樂團；維基百科記為 “The Czech Philharmonic was commissioned to record the works”） | [archive.org/details/musopen-dvd-in-lossless-flac-format](https://archive.org/details/musopen-dvd-in-lossless-flac-format) | `licenseurl: http://creativecommons.org/publicdomain/mark/1.0/`；描述：“This project raised money to purchase and release music to the public domain.” | 3:49 → 0:30（4 秒淡出，不循環） |
| 事故緊張 | `tension_peer_gynt_aase.opus` | 葛利格《皮爾金》第一號組曲 II. 奧塞之死 | 同上 Musopen 錄音 | 同上 | 同上 | 4:34 → 1:06（第一樂句，在休止處切） |

處理方式：ffmpeg 擷取片段 → `loudnorm` 兩段式線性正規化至 −18 LUFS（真峰值 ≤ −1.3 dBFS）→ Ogg Opus。
鋼琴兩首用 80 kbps（96 kbps 時前奏曲 2.2 MB，超過單檔 2 MB），其餘 96 kbps VBR。每檔都小於 2 MB。

| 檔案 | 大小 | 長度 | 響度 |
|---|---|---|---|
| title_goldberg_aria.opus | 1 717 306 B | 147.2 s | −18.0 LUFS |
| briefing_wtc_prelude1.opus | 1 859 434 B | 161.7 s | −18.0 LUFS |
| dive_underwater_theme_ii.opus | 1 352 318 B | 104.7 s | −18.0 LUFS |
| dive_underwater_theme.opus | 1 283 393 B | 82.3 s | −18.2 LUFS |
| results_peer_gynt_morning.opus | 429 807 B | 29.9 s | −17.8 LUFS |
| tension_peer_gynt_aase.opus | 806 395 B | 66.3 s | −17.9 LUFS |
| **合計** | **7 448 653 B** | | |

## 排除的候選

| 候選 | 排除原因 |
|---|---|
| Kevin MacLeod 演奏的薩提《吉諾佩第》（Wikimedia Commons `Gymnopedie No. 1 (ISRC USUAN1100787).mp3` 等） | 錄音為 CC-BY 3.0（頁面原文：“This file is licensed under the Creative Commons Attribution 3.0 Unported license.”），不在白名單 |
| FreePD.com（Kevin MacLeod 的公有領域曲庫） | 網站已關閉（首頁標題 “FreePD.com - Site Closed”），無法取得檔案與授權頁 |
| musopen.org 原站授權頁 | 本環境連線回 403，無法直接引用；改以 archive.org 鏡像（Musopen 官方上傳、PDM 授權欄）與維基百科佐證 |
| archive.org `musopen-*-compressed` 系列（如 Tchaikovsky Pathétique、Suk Meditation） | 項目沒有授權欄位；同批錄音中只採用有 PDM 欄位的 `musopen-dvd-in-lossless-flac-format` 所含曲目 |
| archive.org `parso-*` 蕭邦夜曲等 | 雖標 CC0，但未列演奏者與錄音出處，無法確認上傳者有權釋出 |
| OpenGameArt “Underwater Ambient Pad”（isaiah658） | 標 CC0，但留言串質疑使用商用音色庫取樣，來源有疑慮 |
| 薩提／德布西的公有領域錄音 | 本次在可查證的來源中未找到演奏本身為 PD／CC0 的版本（Commons API 調查期間回 429 限流） |

## 待辦與疑慮

- Musopen 錄音的演奏樂團名稱各處說法不一（維基百科寫 Czech Philharmonic），但不影響授權。
- `dive_underwater_theme.opus` 原作者未明說可無縫循環；播放器用 `<audio loop>`，接縫可能有極短間隙。
- 若之後要加入薩提等曲目，必須重新確認**演奏**的授權，不能只看作曲者年代。
