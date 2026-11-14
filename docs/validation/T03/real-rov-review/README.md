## 本轮结果与范围
已用 **merge（未 rebase）** 并入 `origin/main` `87b1ff9`，merge commit 为 `f0852ec`，包含 T02/T04/T05/T08/T12。app.js 冲突仅为 import，保留两侧功能。重读最新 AGENTS.md、[真实 ROV 研究报告](https://github.com/jekaihsu/rov/blob/87b1ff9/docs/reference/real-rov-research.md) 与 reference README；`docs/reference/own/` 尚无实测资料。

本轮将镜头动作接到 T02，消除 G 键冲突，并按新的最高目标调整**镜头呈现层**的默认值。不改物理、SDK、协议、后端或 T02 的飞行控制语意。

## 审查意见逐条处理
- **T02 动作整合**：新增输入层 `registerActions` 与 feature-action 分派；相机不再自行监听键盘。V 走既有 camera 动作；B 切换雲台/硬连结；`[`/`]` 调整雲台俯仰；G 保留 T02 飞行档位。修正 merge 后旧 `cycleCam()` 回调已不存在的问题。
- **右杆环绕**：通过 T02 标准化、死区、焦点保护后的动作驱动镜头；环绕时消费对应的手柄右杆通道，避免同时推动 ROV。回到机载后恢复飞行通道。键盘飞行不受此通道消费影响。
- **动作可配置**：五个镜头动作出现在原有输入设置中；支持手柄绑定、清除绑定与切换预设后保留动作入口。没有假定真实专用遥控器的未公开键位。
- **T08 清单**：未增加 addon；`THREE.Spherical` 来自已有核心模块。`vendor_manifest.py --check` 通过，清单仍是 10 个文件，无需新增依赖或修改 vendor 清单。
- **HUD 权威状态**：保留 `updateFlightHUD(S, W, dt, input.hudState())`，HUD 读 `S`，不读延迟或预测后的模型状态。
- **前轮意见仍维持**：定向复制运动字段、共享只读遥测；app.js 只留模组初始化/ingest/update；等时间戳暂停替换、恢复时钟、限时角预测与断包恢复限速均有回归测试，没有重新加入整份 structuredClone。

## 真实 ROV 对齐与明确假设
依据研究报告「镜头、灯光与延迟」及 TRANSoM 段落：第一人称与受限信息是驾驶基准，外部视角是训练辅助；延迟必须保留，但 X1 数据仍需自有实测。

| 镜头呈现选择 | 行为 |
|---|---|
| 默认（真实镜头呈现） | 机载第一人称、硬连结保留横滚/俯仰，共用 **150 ms** 延迟渲染时间；不使用本机前瞻预测 |
| `?presentation=assisted` | 显式选择低延迟辅助；本机前瞻最多半包/25 ms，所有外插仍上限 100 ms；不改变权威状态 |
| `?gimbal=1` / B | 显式开启/切换雲台；默认关闭。关闭后恢复硬连结姿态 |
| `?cam=chase/orbit/top` / V | 显式选择第三人称训练辅助；回到 onboard 可关闭外部视角 |
| `?videoDelayMs=` | 配置暂定影像呈现延迟，供实测校准；默认 150 ms |

**150 ms 是暂定通用模拟假设，不是 X1 的事实。** 研究报告建议 150–250 ms，但引用的 150–200 ms 属其他世代厂商自述，X1 仍待测。现有 70° 机载 FOV、雲台限位、运镜参数也未经过 X1 标定，不借用其他机型数值宣称已验证。此处只实现镜头显示策略；不声称整个模拟器已经完成真实设备验证。

## 本机实际验证（本月 CI 额度已用完）
```text
cd simulator && python -m unittest discover -s tests
Ran 131 tests in 68.698s
OK

node --test simulator/tests/*.mjs
# tests 26, pass 26, fail 0, skipped 0

node simulator/desktop/test_collection_store.cjs
Collection storage passed: serialized writes, reopen, covers, export/import, collisions, validation and failed-write rollback.

python simulator/tools/vendor_manifest.py --check
Three.js manifest: 10 files

for f in simulator/viewer/*.js $(find simulator/viewer -mindepth 2 -name '*.js' -not -path '*/vendor/*') simulator/desktop/*.cjs; do node --check "$f" || exit; done
# exit 0

git diff --check
# exit 0

python simulator/tools/browser_camera_smoke.py
Real onboard default, input actions, orbit, gimbal and physical capture restore passed

python simulator/tools/browser_camera_input_smoke.py
Live V cycle, orbit pad ownership, B/G separation and settings focus guards passed.
# 同时检查五个设置入口、绑定/清除的持久化、切换预设后的动作入口。
# 此专项跳过 GPU 绘制以隔离动作路由，不用它作延迟/画质证据。

cd simulator && python tools/browser_hud_smoke.py
HUD geometry, tap timeout, hold/release, D-pad adapter, hiding and drawer persistence passed.

cd simulator && python tools/browser_input_smoke.py
Input smoke passed: {"standard": true, "known": true, "unknown": false} ; wizard stored 4 axes and 17 buttons; no page errors
# 独立重跑结果；首轮解锁等待曾超时，未删除或忽略该失败，见限制。

cd simulator && python tools/browser_menu_smoke.py
Menu flow passed: /workspace/rov/simulator/output/menu-validation

cd simulator && PYTHONPATH=/tmp/t03-browser:$PWD python tools/observation_smoke.py
17 real-browser observation cases passed.

cd simulator && python tools/browser_smoke.py
Page.wait_for_function: Timeout 30000ms exceeded.
# 等待 window.__viewer.S.operations.arm.grip<.5 时超时。
```
服务：本分支 `python -m qysim.server --http-port 8092 --ws-port 8792`；比较 main 使用 `--http-port 8093 --ws-port 8793 --rpc-port 9761`；原输入脚本使用默认 8080/8765 服务（额外 `--rpc-port 9762` 避免冲突）。临时 `/tmp/t03-browser` 仅为仍指定 Chrome 的旧工具移除 `channel='chrome'`，使用已安装 Chromium，不修改任何断言或超时。

**本次没有依赖旧 CI 成功记录，也没有手动触发 CI。没有删除、跳过或放宽既有测试。** 相机 smoke 保留原雲台与观测照姿态断言，并新增默认真实镜头与动作检查。

## 最新延迟：真实模式与辅助模式分开报告
命令：
```bash
python simulator/tools/camera_latency.py --runs 7 --output /tmp/t03-current-latency-verified
python simulator/tools/camera_latency.py --runs 7 --only after --presentation real --output /tmp/t03-current-real-latency
```
两版同为 1600×900、机载镜头，main=`87b1ff9`。reset、关闭洋流与湍流，等待 3 秒，用 8 个中立帧估计漂移；同一 JS task 解锁并送 ArrowUp，量到扣除漂移后的水平渲染位移超过 20 mm。每个最终系列均独立执行，没有其他浏览器测试并行，未挑选/剔除其中任何一次。不是玻璃到玻璃或实体手柄仪器量测。

| 版本/呈现 | 7 次输出（ms） | 中位数 | 最小 | 最大 |
|---|---|---:|---:|---:|
| main 机载 | 297.3, 391.2, 317.1, 388.4, 309.3, 347.5, 372.6 | **347.5** | 297.3 | 391.2 |
| 本分支显式 assisted | 399.7, 371.6, 376.3, 355.4, 372.9, 337.4, 396.5 | **372.9** | 337.4 | 399.7 |
| 本分支默认真实镜头 | 518.5, 530.0, 555.8, 601.9, 514.8, 539.1, 476.1 | **530.0** | 476.1 | 601.9 |

辅助响应回归：`372.9 <= 347.5 + 30`，差 **+25.4 ms**，达到前轮审查门槛；不声称更快。默认真实镜头刻意保留 150 ms 影像呈现延迟，因此不拿低延迟辅助的门槛去移除真实模式延迟。

在加入半包前瞻前，本轮另跑过完整 7 次，前/后中位数 341.3 / 385.9 ms（+44.6 ms，未达门槛）；这组失败统计保留于 `pre-lookahead-*-summary.json`。随后实现了显式辅助的 25 ms 上限前瞻，再重新执行整组 7 次；没有借改门槛或挑样本通过。

本轮样本、summary、真实模式中立帧资料位于 `docs/validation/T03/real-rov-review/`。前轮不同 main 的数据仅作历史，不能充当本轮成绩。

## 三载具缓冲 CPU 重测
```bash
cd simulator
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_fleet_perf.py --url http://127.0.0.1:8094/ --snapshot ../docs/validation/T03/review/fleet-state.json
PYTHONPATH=/tmp/t03-browser:$PWD python tools/browser_fleet_perf.py --url http://127.0.0.1:8092/ --snapshot ../docs/validation/T03/review/fleet-state.json
```
两次 exit 0，保留原 cable geometry/dirty/dispose/画质断言。使用同一份已捕获的三人房间 19,565-byte 快照，warmup 60 帧，计 600 帧；每帧 local+remote 采样，每 3 帧发包。8094 静态服务为修正全量复制前 `6cf822c`，8092 为本轮实现。

| 缓冲版本 | 平均 ms/帧 | 中位数 ms/帧 | P95 ms/帧 |
|---|---:|---:|---:|
| 全量复制旧版 | 1.4795 | 1.3000 | 2.5000 |
| 当前定向复制 | 0.1132 | 0.1000 | 0.2000 |

这是同快照的浏览器 CPU 微基准，**不是含 GPU、输入与整场物理的实际 FPS**。完整输出为本轮目录 `perf-before.json` / `perf-after.json`。

## 前后画面
![最新 main 默认](https://raw.githubusercontent.com/jekaihsu/rov/task/T03-camera/docs/validation/T03/real-rov-review/before-main.png)
![本分支默认真实镜头](https://raw.githubusercontent.com/jekaihsu/rov/task/T03-camera/docs/validation/T03/real-rov-review/after-real.png)
均为 1600×900。新增截图和小型 JSON 是任务要求的审查证据，每个均小于 2 MB，没有修改 docs/showcase 或增加第三方资产。

## 未完成、未验证与后续
- 原完整 browser smoke 本轮在机械手 grip 等待处超时。前轮审查已确认该完整工具在 main 也失败、不阻挡合并；本轮失败点与上轮 PiP 点不同，原因未确证，不称为通过，也不擅改机械手逻辑。
- 原输入 smoke 首轮出现 rc_lock 等待超时；方向轴已有送达。独立 main 对照和分支独立重跑均通过。保留复锁/状态重同步安全保护，未证明首轮原因，也未为过测删掉保护。新增实际相机输入专项通过。
- 未测实体遥控器、硬件 GPU 30/60/144 fps 体验或完整 render_movie.js 输出。弹簧帧率一致性由 Node 测试验证。
- X1 自有水中 FOV、玻璃到玻璃延迟、雲台/EIS 与控制器映射待实测；不以其他机型资料代替。镜头呈现参数只作暂定值。
- 本次不改飞行辅助/DVL、物理系数、纜线力、训练程序或机械手；这些由对应任务继续对齐真实 ROV。
