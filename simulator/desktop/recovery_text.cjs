// Native launch and recovery UI also works before the viewer's dictionaries are available.
const rows = {
  en: ['Starting the local simulator…', 'Restart in safe mode', 'Retry', 'Open log folder', 'Copy error summary',
    'Quit', 'Verify the game files or check the Python installation.', 'Local port unavailable. Close other instances and retry.',
    'Allow the simulator to use localhost in your firewall, then retry.', 'The simulator stopped. Retry to restart.',
    'The display stopped responding. Restart in safe mode or update your graphics driver.'],
  ja: ['ローカルシミュレーターを起動中…', 'セーフモードで再起動', '再試行', 'ログフォルダーを開く', 'エラー概要をコピー',
    '終了', 'ゲームファイルの整合性または Python のインストールを確認してください。', 'ポートを使用できません。他のインスタンスを閉じて再試行してください。',
    'ファイアウォールで localhost への接続を許可して再試行してください。', 'シミュレーターが停止しました。再試行で再起動します。',
    '画面が応答しません。セーフモードで再起動するか、グラフィックスドライバーを更新してください。'],
  'zh-Hant': ['正在啟動本機模擬服務…', '以安全模式重新啟動', '重試', '開啟紀錄資料夾', '複製錯誤摘要',
    '結束', '請驗證遊戲檔案完整性，或檢查 Python 安裝。', '本機埠無法使用，請關閉其他執行中的模擬器後重試。',
    '請確認防火牆允許模擬器連線到 localhost，然後重試。', '模擬服務已停止，請重試以重新啟動。',
    '畫面停止回應，請以安全模式重新啟動或更新顯示驅動程式。'],
  'zh-Hans': ['正在启动本地模拟服务…', '以安全模式重新启动', '重试', '打开日志文件夹', '复制错误摘要',
    '退出', '请验证游戏文件完整性，或检查 Python 安装。', '本地端口不可用，请关闭其他运行中的模拟器后重试。',
    '请确认防火墙允许模拟器连接到 localhost，然后重试。', '模拟服务已停止，请重试以重新启动。',
    '画面停止响应，请以安全模式重新启动或更新显示驱动程序。'],
};
function nativeText(tag) {
  const lang = /^zh-(TW|HK|MO|Hant)/i.test(tag) ? 'zh-Hant' : /^zh/i.test(tag) ? 'zh-Hans' : tag.split('-')[0];
  const [starting, safe, retry, logs, copy, quit, missing, port, denied, backend, renderer] = rows[lang] || rows.en;
  const storage = {
    en: 'Check free disk space and write access to the game data folder, then verify the game files.',
    ja: '空き容量とゲームデータフォルダーの書き込み権限を確認し、ゲームファイルの整合性を確認してください。',
    'zh-Hant': '請檢查磁碟空間及遊戲資料夾的寫入權限，並驗證遊戲檔案。',
    'zh-Hans': '请检查磁盘空间及游戏文件夹的写入权限，并验证游戏文件。',
  };
  return { storage: storage[lang] || storage.en, starting, safe, retry, logs, copy, quit, missing, port, denied, timeout: denied, backend,
    renderer, unresponsive: renderer };
}
module.exports = { nativeText };
