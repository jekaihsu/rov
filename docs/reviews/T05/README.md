# T05 音效验收资料

- `before.jpg`：origin/main，1600×900 主菜单。
- `after.jpg`：T05，1600×900 主菜单的音效设置。
- `audio-30s.webm`：约 30 秒实机画面及直接从 Web Audio 主混音捕获的 Opus 音轨。
  操作包括解锁、推力、灯光、机载视角与定深。使用自动画质的实际 WebGL canvas 捕获，
  因此录影解析度会低于页面截图。没有麦克风录音或外部取样。

生成：启动 8092/8792 功能版及 8093/8793 原始 main 版本后执行
`python simulator/tools/browser_audio_smoke.py`。

这些小型二进位仅作为任务书要求的 PR 审阅证据提交，不是游戏资源或建置输出。
