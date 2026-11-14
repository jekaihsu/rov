## 做了什么
T03 将状态插值与镜头逻辑移到 `state_buffer.js` / `camera_rig.js`，包含共同服务器渲染时间、自适应远端缓冲、本机零等待预测、临界阻尼镜头、雲台/硬连结切换、250 ms 镜头过渡和真实机载观测照姿态。不改后端、SDK、物理或协定。

## 最新审查逐条处理
1. **合并 main**：先执行 `git fetch origin && git merge --no-edit origin/main`，以 merge commit `6cf822c` 并入 `origin/main` `4065ba5`；收尾又以 merge commit `f5a739d` 并入新合并的 T05 `006a061`，没有 rebase。冲突仅为 app.js 的 import，保留两边功能。`updateFlightHUD(S, W, dt)` 仍直接读取权威状态 `S`；未把 HUD 接到渲染状态。`browser_camera_smoke.py`、`browser_hud_smoke.py` 均通过。
2. **延迟**：每版独立执行 7 次，最终中位数差 **+9.3 ms**，通过“不高于改动前 +30 ms”的审查标准，详见下表。正常收包不再走 8 m/s 修正限速；限速仅在超过 150 ms 的断包恢复后短暂启用。本机采样在实际执行时取时钟，不再使用可能已经过时的 rAF 时间戳。
3. **整份状态复制**：移除 `structuredClone` 和遍历全部字段的通用插值。只分配位置、姿态、速度、纜线节点、载具、工作物件与鱼群的运动字段；其他遥测/任务资料共享只读引用，上一帧渲染输出也直接保留。新增测试证明 opaque telemetry 不被复制、输入位置不被改写。三载具 CPU 采样比较如下。
4. **本机旋转阶梯（自动审查）**：以最近两个服务器姿态推算 shortest-arc 角运动，外插最多 100 ms、角速度最多 8 rad/s；新增连续旋转与外插时间上限测试。
5. **app.js 编排与程式风格（自动审查）**：`createRenderState` 收纳双缓冲选择、姿态应用、fleet/tether 更新，app.js 只留初始化、ingest 和 update 呼叫。拆开新加入的多语句行与相机恢复函数。
6. **同时间戳暂停状态（自动审查）**：保留等时间戳替换、暂停不外插、恢复重设时钟；对应回归测试通过。

## 延迟：各 7 次，原始资料保留
实际命令：
```bash
python simulator/tools/camera_latency.py --runs 7 --output /tmp/t03-review-latency-final
```
两个服务器分别运行最新 main `006a061`（8093/8793/9761）与本分支（8092/8792/9760）。浏览器 1600×900、机载；每次 reset、关闭洋流/湍流，等待 3 秒，再采 8 个中立帧估计漂移，随后在同一个 JS task 解锁并送 ArrowUp。量测到相对中立漂移预测的水平渲染位移超过 20 mm。使用相同脚本/条件，先完成前版 7 次、再完成后版 7 次；最终量测时没有其他浏览器测试并行。

| 版本 | 7 次实际输出（ms） | 中位数 | 最小 | 最大 |
|---|---|---:|---:|---:|
| main | 373.9, 370.6, 369.5, 305.0, 385.3, 356.9, 352.5 | **369.5** | 305.0 | 385.3 |
| 本分支 | 379.3, 388.0, 378.8, 359.5, 390.8, 352.9, 357.7 | **378.8** | 352.9 | 390.8 |

`378.8 <= 369.5 + 30`，差 +9.3 ms。这里只声称通过该代理量测门槛，不声称改善，也不是实体手把/输入到光子的仪器测量。

最初使用未扣中立漂移的方法也跑过 7 次（前中位数 370.5、后 564.5 ms），出现 8.6/12 ms 即触发的样本，无法区分原有漂移与输入，故不用于合并判断。最终统一修正方法后整组重跑，没有挑选或剔除最终 7 次中的任何样本。旧单组 405/531 ms 同样被本次资料取代。

原始记录：`docs/validation/T03/review/{before,after}-[1-7].json` 与 `*-summary.json`。

## 三载具性能：实际命令与结果
使用从服务器三人房间捕获的同一份 **19,565 bytes** 状态 `docs/validation/T03/review/fleet-state.json`。保留原本 `browser_fleet_perf.py` 的 cable/画质断言，并增加双缓冲采样计时；先 warmup 60 帧，再计 600 帧，每 3 帧发一包。比较对象是此次修正前的 merge commit `6cf822c`（静态端口 8094）与本次修正后（8092），此微基准使用同一个 T04 基底；新增音效不进入缓冲 CPU 计时。
```bash
cd simulator
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_fleet_perf.py --url http://127.0.0.1:8094/ --snapshot ../docs/validation/T03/review/fleet-state.json
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_fleet_perf.py --url http://127.0.0.1:8092/ --snapshot ../docs/validation/T03/review/fleet-state.json
```
两次均 exit 0，包含原有 geometry/dirty/dispose/adaptive-resolution 断言。每帧 local+remote 缓冲 CPU 时间：

| 版本 | 平均 ms/帧 | 中位数 ms/帧 | P95 ms/帧 |
|---|---:|---:|---:|
| 修正前 | 2.198 | 1.800 | 4.500 |
| 修正后 | 0.117 | 0.100 | 0.200 |

这是三载具快照的浏览器 CPU 缓冲微基准，**不是含 GPU 的整帧 FPS**。完整结果见 `review/perf-before.json`、`review/perf-after.json`。也曾跑合成压力快照，结果不用于此表。

## 本机测试（本月 CI 额度已用完）
```text
cd simulator && python -m unittest discover -s tests
Ran 119 tests in 107.982s
OK

node --test simulator/tests/*.mjs
# tests 15, pass 15, fail 0, skipped 0

node simulator/desktop/test_collection_store.cjs
Collection storage passed: serialized writes, reopen, covers, export/import, collisions, validation and failed-write rollback.

for f in simulator/viewer/*.js $(find simulator/viewer -mindepth 2 -name '*.js' -not -path '*/vendor/*') simulator/desktop/*.cjs; do node --check "$f" || exit; done
# exit 0

git diff --check
# exit 0

cd simulator
python tools/browser_camera_smoke.py
Five camera modes, finite poses, gimbal roll lock and physical capture restore passed

python tools/browser_hud_smoke.py
HUD geometry, tap timeout, hold/release, drawer persistence passed.
```
服务启动命令：`python -m qysim.server --http-port 8092 --ws-port 8792`；main 比较服务额外使用 `--http-port 8093 --ws-port 8793 --rpc-port 9761`。系统缺 Chrome 的旧脚本使用临时 `/tmp/t03-browser/sitecustomize.py`，仅移除 launch 的 `channel='chrome'` 而使用 Playwright Chromium；未改既有断言、超时或跳过测试。

后端 119 项在第一次 merge 后执行；第二次 merge 的 T05 没有后端变更。最后一次 merge 后重新执行 Node（含音效测试）、语法、相机/HUD smoke 与两边各 7 次延迟。

本次不以旧 CI 成功纪录代表最新版本，也未手动触发 CI。没有删除、跳过或放宽既有测试。

## 画面证据与保守选择
![前](https://raw.githubusercontent.com/jekaihsu/rov/task/T03-camera/docs/validation/T03/before.png)
![后](https://raw.githubusercontent.com/jekaihsu/rov/task/T03-camera/docs/validation/T03/after.png)
![10 秒逐帧位移](https://raw.githubusercontent.com/jekaihsu/rov/task/T03-camera/docs/validation/T03/displacement.svg)
原始 1600×900 截图、10 秒逐帧图及本次审查量测为任务要求而提交，均小于 2 MB，未动 docs/showcase。截图是首次实现的视觉证据，不作为本轮性能统计。

G 切换训练硬连结，`?gimbal=0` 可直接关闭雲台；`[` / `]` 调俯仰（±0.65 rad）。T02 尚未合并，环绕维持鼠标。避障采用射线与 0.2 m 退让；服务器时间倒退超过 0.5 s 当作场景重置。这些是任务书模糊处的保守选择，不改权威物理。

## 未验证与后续
- 审查者已确认 `browser_smoke.py` 在 main 也失败，因此这项不阻挡本次合并；本轮重跑结果补于下方。
- 未生成完整 `render_movie.js` 影片、未验实体手把/硬件 GPU 的真实 30/60/144 fps 体验；解析弹簧帧率一致性由 Node 测试验证。
- T02 合并后的右摇杆相机动作、薄结构贴边避障体验留后续；HUD/菜单与既有品牌内容不在本任务范围。

## 其他实际重跑结果
```text
cd simulator
PYTHONPATH=/tmp/t03-browser:$PWD python tools/observation_smoke.py
17 real-browser observation cases passed.
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_menu_smoke.py
Menu flow passed: /workspace/rov/simulator/output/menu-validation
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_smoke.py
Locator.click: Timeout 30000ms exceeded.
# #closePip: waiting for element to be visible, enabled and stable
```
这三项在第二次音效 merge 前执行；已知的完整 smoke 超时如实保留，未改测试。最新 merge 后相机、HUD 与 15 项 Node 检查通过。

T05 合并前同方法的 7 次中位数为 336.9 / 345.5 ms（差 +8.6 ms），资料保留在 `review/pre-audio-*-summary.json`；最终统计统一采用两边均含 T05 的新一轮 7 次。未扣漂移的废弃统计也保留在 `review/uncorrected-*-summary.json`。
