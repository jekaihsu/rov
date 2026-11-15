# H2：伺服器 tick 效能

基底 `main`：`5c5dc4c2ff931b8c6a57e2ee568ed47b5f358e45`。固定主機權威 0.01 s 步長。
已讀 AGENTS.md 與 docs/reference/real-rov-research.md；main 未包含 docs/reference/own/。本次不變更物理參數或擬真假設。

## 變更與原因

- 接觸平面快取在子步失效時，舊批次回復 x、v、l0、reel、chafe，整個 tick 重跑 Python 迴圈。
- 新批次保留完成的子步與力／張力／pin peak 累積值，在相同位置重建接觸平面、完成待處理接觸，再進入 Numba。移除五個每 tick 回復用陣列副本。
- 沒有調大接觸容許距離、改變子步數、變更算式次序或啟用 fastmath。NumPy 回退保留。
- 回聲原本即為 5 Hz、磁力計 10 Hz；新增呼叫次數回歸測試，不降低感測器頻率。
- flow_field 原本僅在 Room.state 呼叫 flow_field_state 時建立，並依既有週期快取；新增延遲計算與重用測試。
- benchmark_room 新增 --players 3/6、CPU p95 與 --trace；六載具僅提高基準房間實例容量，不變更正式容量。

## 量測方法

Linux x86_64 / AMD EPYC 9V74；Python 3.12.14、NumPy 2.3.5、Numba 0.68.1。
每組 seed=42、PYTHONHASHSEED=0、120 tick 暖機、600 tick 計時。計時使用 process_time / perf_counter，排除初始化、JIT 暖機、輸出與軌跡雜湊。
實時倍率 = 10 ms / 平均 wall ms；不含渲染、網路與狀態序列化。各組循序執行；共享雲端 CPU 的抖動仍可能影響尾端與小幅差異。
cProfile 另跑，同樣暖機與 tick 數，其時間只用於熱點排序，不混入下表。

```bash
cd simulator
PYTHONHASHSEED=0 python tools/benchmark_room.py --scenario incident_wreck --players 3 --warmup 120 --ticks 600 --output /tmp/room.json --trace /tmp/room.trace
PYTHONHASHSEED=0 python tools/benchmark_room.py --scenario incident_wreck --players 3 --warmup 120 --ticks 600 --profile --output /tmp/profile.json
py-spy record --format raw -o /tmp/tick.spy -- python tools/benchmark_room.py --scenario incident_wreck --ticks 600 --output /tmp/spy.json
```

上述 benchmark 指令分別對四情境 × 3/6 載具執行；基底另建 detached main worktree，複製相同 benchmark 工具執行。

## 前後對照

600 tick 視窗比工具原本 180 tick 更長，會遇到更多接觸刷新；因此 coral_reef 的基底批次率也可能低於 1.00。incident_wreck 三載具重現約 0.923，原因是子步接觸平面過期。
單位 ms/tick；箭頭左 main，右本分支。批次完成率的新值包含刷新後續跑；不代表所有 tick 都免除幾何刷新。

| 情境 | 載具 | CPU 平均 | CPU p95 | 實時倍率 | 批次完成率 |
|---|---:|---:|---:|---:|---:|
| coral_reef | 3 | 4.613 → 4.353 | 9.837 → 9.456 | 2.167 → 2.295 | 0.942 → 1.000 |
| coral_reef | 6 | 8.439 → 8.185 | 18.624 → 16.109 | 1.183 → 1.221 | 0.961 → 1.000 |
| incident_wreck | 3 | 5.151 → 4.961 | 11.253 → 11.137 | 1.941 → 2.014 | 0.923 → 1.000 |
| incident_wreck | 6 | 9.588 → 9.196 | 21.081 → 17.630 | 1.042 → 1.087 | 0.919 → 1.000 |
| jacket_inspection | 3 | 5.299 → 5.131 | 14.188 → 13.947 | 1.886 → 1.948 | 0.849 → 1.000 |
| jacket_inspection | 6 | 9.771 → 10.112 | 21.755 → 24.082 | 1.023 → 0.987 | 0.851 → 1.000 |
| harbor_inspection | 3 | 6.217 → 6.343 | 11.875 → 12.823 | 1.607 → 1.575 | 0.960 → 1.000 |
| harbor_inspection | 6 | 12.013 → 11.532 | 28.491 → 22.064 | 0.831 → 0.866 | 0.951 → 1.000 |

平均未達目標：jacket_inspection / 6：10.112 ms；harbor_inspection / 3：6.343 ms；harbor_inspection / 6：11.532 ms。


## 正確性

跨程序須固定 PYTHONHASHSEED：既有 sensors.py:584 在失鎖原因票數相同時以 set 取 max，會隨 hash seed 在 slope / mud 等原因字串中選擇。此問題不影響數值，本次不改動既有感測器決策；列為後續。
只有一項數值路徑優化（可續跑的纜線批次）。八組各 600 tick 的逐欄位位元雜湊全部相同，共 4,800 tick；最大誤差 0，沒有使用 1e-9 寬限。
雜湊涵蓋每台載具完整 dataclass 狀態、纜線位置／速度／rest lengths／施力、完整 SensorFrame 與感測器對外輸出。
雜湊直接讀取 ndarray dtype、shape、bytes 與標量值，不依賴 Python 物件共用關係。
另以相同程序載入 main 的原版回復批次方法，對八組各比較 720 tick（含暖機），所有欄位位元完全相同。另有 600 tick 單元測試，對照續跑批次與逐子步路徑，並確認實際遇到接觸刷新。

## cProfile：各組前 15 熱點

依累積時間排序；每列為呼叫數、self 秒、累積秒、函式。父子呼叫時間不可相加。

### coral_reef / 3 載具

before

```text
   calls     self cumulative function
     600    0.010    3.567 qysim/room.py:187(step)
    1800    0.054    2.972 qysim/engine.py:239(step)
    1800    0.036    0.876 qysim/tether.py:386(step)
    5640    0.058    0.739 qysim/world.py:701(current_at_many)
   12627    0.439    0.700 qysim/ecology.py:24(sample_many)
    1800    0.023    0.550 qysim/sensors.py:420(step)
    4463    0.145    0.446 qysim/world.py:833(sdf_many)
    5640    0.022    0.420 qysim/world.py:593(sample_many)
     600    0.028    0.412 qysim/operations.py:63(step_objects)
    1800    0.095    0.373 qysim/physics.py:242(step)
     315    0.041    0.349 qysim/sensors.py:150(raycast_many)
    1800    0.039    0.265 qysim/world.py:764(vehicle_contact)
    2880    0.044    0.252 qysim/world.py:734(sdf)
    2040    0.003    0.250 qysim/world.py:729(current_at)
     225    0.018    0.237 qysim/sensors.py:524(_ping_dvl)
```

after

```text
   calls     self cumulative function
     600    0.011    3.823 qysim/room.py:187(step)
    1800    0.059    3.179 qysim/engine.py:239(step)
    1800    0.039    0.908 qysim/tether.py:386(step)
    5640    0.067    0.798 qysim/world.py:701(current_at_many)
   12627    0.472    0.754 qysim/ecology.py:24(sample_many)
    1800    0.025    0.618 qysim/sensors.py:420(step)
    4463    0.168    0.496 qysim/world.py:833(sdf_many)
     600    0.030    0.447 qysim/operations.py:63(step_objects)
    5640    0.024    0.446 qysim/world.py:593(sample_many)
    1800    0.103    0.397 qysim/physics.py:242(step)
     315    0.046    0.395 qysim/sensors.py:150(raycast_many)
    1800    0.040    0.280 qysim/world.py:764(vehicle_contact)
     225    0.020    0.278 qysim/sensors.py:524(_ping_dvl)
    2040    0.004    0.272 qysim/world.py:729(current_at)
    2880    0.047    0.268 qysim/world.py:734(sdf)
```

### coral_reef / 6 載具

before

```text
   calls     self cumulative function
     600    0.014    6.617 qysim/room.py:187(step)
    3600    0.107    5.941 qysim/engine.py:239(step)
    3600    0.068    1.835 qysim/tether.py:386(step)
    9240    0.095    1.241 qysim/world.py:701(current_at_many)
   21492    0.741    1.181 qysim/ecology.py:24(sample_many)
    3600    0.045    1.081 qysim/sensors.py:420(step)
    9353    0.307    0.920 qysim/world.py:833(sdf_many)
    9240    0.037    0.746 qysim/world.py:593(sample_many)
    3600    0.185    0.724 qysim/physics.py:242(step)
     630    0.082    0.689 qysim/sensors.py:150(raycast_many)
    3600    0.074    0.514 qysim/world.py:764(vehicle_contact)
     450    0.036    0.470 qysim/sensors.py:524(_ping_dvl)
     180    0.004    0.418 qysim/sensors.py:465(_sample_echo)
     600    0.028    0.407 qysim/operations.py:63(step_objects)
    3600    0.037    0.392 qysim/engine.py:345(_sample_flow)
```

after

```text
   calls     self cumulative function
     600    0.014    6.801 qysim/room.py:187(step)
    3600    0.109    6.098 qysim/engine.py:239(step)
    3600    0.070    1.862 qysim/tether.py:386(step)
    9240    0.100    1.275 qysim/world.py:701(current_at_many)
   21492    0.769    1.230 qysim/ecology.py:24(sample_many)
    3600    0.045    1.126 qysim/sensors.py:420(step)
    9353    0.318    0.958 qysim/world.py:833(sdf_many)
    9240    0.038    0.760 qysim/world.py:593(sample_many)
    3600    0.191    0.746 qysim/physics.py:242(step)
     630    0.085    0.721 qysim/sensors.py:150(raycast_many)
    3600    0.076    0.530 qysim/world.py:764(vehicle_contact)
     450    0.037    0.487 qysim/sensors.py:524(_ping_dvl)
     180    0.005    0.437 qysim/sensors.py:465(_sample_echo)
     600    0.028    0.424 qysim/operations.py:63(step_objects)
    3600    0.038    0.393 qysim/engine.py:345(_sample_flow)
```

### incident_wreck / 3 載具

before

```text
   calls     self cumulative function
     600    0.011    4.235 qysim/room.py:187(step)
    1800    0.055    3.482 qysim/engine.py:239(step)
    5640    0.024    1.309 qysim/world.py:701(current_at_many)
    1800    0.035    1.101 qysim/tether.py:386(step)
    1800    0.024    0.695 qysim/sensors.py:420(step)
     315    0.068    0.484 qysim/sensors.py:150(raycast_many)
    5640    0.044    0.480 qysim/flow.py:385(apply)
    6057    0.220    0.474 qysim/world.py:833(sdf_many)
    5640    0.019    0.468 qysim/world.py:593(sample_many)
    1800    0.018    0.436 qysim/engine.py:345(_sample_flow)
     600    0.029    0.434 qysim/operations.py:63(step_objects)
    5640    0.351    0.428 qysim/flow.py:443(_box)
    2040    0.003    0.398 qysim/world.py:729(current_at)
   11280    0.106    0.391 qysim/world.py:516(mean_many)
    1800    0.098    0.377 qysim/physics.py:242(step)
```

after

```text
   calls     self cumulative function
     600    0.010    4.154 qysim/room.py:187(step)
    1800    0.054    3.427 qysim/engine.py:239(step)
    5640    0.023    1.290 qysim/world.py:701(current_at_many)
    1800    0.034    1.074 qysim/tether.py:386(step)
    1800    0.024    0.687 qysim/sensors.py:420(step)
     315    0.066    0.479 qysim/sensors.py:150(raycast_many)
    5640    0.019    0.470 qysim/world.py:593(sample_many)
    6057    0.217    0.468 qysim/world.py:833(sdf_many)
    5640    0.044    0.463 qysim/flow.py:385(apply)
    1800    0.018    0.430 qysim/engine.py:345(_sample_flow)
     600    0.027    0.416 qysim/operations.py:63(step_objects)
    5640    0.336    0.411 qysim/flow.py:443(_box)
   11280    0.103    0.386 qysim/world.py:516(mean_many)
    2040    0.003    0.383 qysim/world.py:729(current_at)
    1800    0.095    0.373 qysim/physics.py:242(step)
```

### incident_wreck / 6 載具

before

```text
   calls     self cumulative function
     600    0.016    7.798 qysim/room.py:187(step)
    3600    0.111    6.847 qysim/engine.py:239(step)
    9240    0.040    2.273 qysim/world.py:701(current_at_many)
    3600    0.070    2.219 qysim/tether.py:386(step)
    3600    0.047    1.239 qysim/sensors.py:420(step)
    3600    0.036    0.882 qysim/engine.py:345(_sample_flow)
    9240    0.033    0.845 qysim/world.py:593(sample_many)
     630    0.113    0.821 qysim/sensors.py:150(raycast_many)
   10698    0.378    0.814 qysim/world.py:833(sdf_many)
    9240    0.078    0.812 qysim/flow.py:385(apply)
    3600    0.196    0.767 qysim/physics.py:242(step)
    9240    0.592    0.720 qysim/flow.py:443(_box)
   18480    0.180    0.667 qysim/world.py:516(mean_many)
     450    0.036    0.548 qysim/sensors.py:524(_ping_dvl)
    9240    0.052    0.537 qysim/world.py:584(shedding_travel)
```

after

```text
   calls     self cumulative function
     600    0.015    7.685 qysim/room.py:187(step)
    3600    0.110    6.756 qysim/engine.py:239(step)
    9240    0.041    2.245 qysim/world.py:701(current_at_many)
    3600    0.068    2.120 qysim/tether.py:386(step)
    3600    0.047    1.245 qysim/sensors.py:420(step)
    3600    0.038    0.894 qysim/engine.py:345(_sample_flow)
    9240    0.032    0.845 qysim/world.py:593(sample_many)
     630    0.114    0.823 qysim/sensors.py:150(raycast_many)
   10698    0.375    0.815 qysim/world.py:833(sdf_many)
    9240    0.076    0.791 qysim/flow.py:385(apply)
    3600    0.195    0.760 qysim/physics.py:242(step)
    9240    0.575    0.702 qysim/flow.py:443(_box)
   18480    0.178    0.659 qysim/world.py:516(mean_many)
     450    0.037    0.547 qysim/sensors.py:524(_ping_dvl)
    9240    0.051    0.528 qysim/world.py:584(shedding_travel)
```

### jacket_inspection / 3 載具

before

```text
   calls     self cumulative function
     600    0.010    4.457 qysim/room.py:187(step)
    1800    0.055    3.745 qysim/engine.py:239(step)
    1800    0.035    1.012 qysim/tether.py:386(step)
    5640    0.023    0.981 qysim/world.py:701(current_at_many)
    1800    0.023    0.804 qysim/sensors.py:420(step)
     240    0.051    0.610 qysim/sensors.py:150(raycast_many)
    4549    0.208    0.595 qysim/world.py:833(sdf_many)
    2880    0.059    0.571 qysim/world.py:734(sdf)
    1800    0.012    0.452 qysim/operations.py:247(step)
   32561    0.210    0.451 qysim/world.py:41(sdf)
    5640    0.018    0.434 qysim/world.py:593(sample_many)
   11280    0.102    0.388 qysim/world.py:516(mean_many)
      90    0.002    0.375 qysim/sensors.py:465(_sample_echo)
    1800    0.096    0.375 qysim/physics.py:242(step)
   83333    0.187    0.350 numpy/linalg/_linalg.py:2623(norm)
```

after

```text
   calls     self cumulative function
     600    0.010    4.421 qysim/room.py:187(step)
    1800    0.056    3.711 qysim/engine.py:239(step)
    5640    0.023    0.976 qysim/world.py:701(current_at_many)
    1800    0.035    0.964 qysim/tether.py:386(step)
    1800    0.023    0.817 qysim/sensors.py:420(step)
     240    0.048    0.624 qysim/sensors.py:150(raycast_many)
    4549    0.206    0.612 qysim/world.py:833(sdf_many)
    2880    0.058    0.575 qysim/world.py:734(sdf)
   32561    0.212    0.455 qysim/world.py:41(sdf)
    1800    0.012    0.451 qysim/operations.py:247(step)
    5640    0.018    0.433 qysim/world.py:593(sample_many)
      90    0.002    0.398 qysim/sensors.py:465(_sample_echo)
   11280    0.102    0.387 qysim/world.py:516(mean_many)
    1800    0.097    0.379 qysim/physics.py:242(step)
   83333    0.190    0.354 numpy/linalg/_linalg.py:2623(norm)
```

### jacket_inspection / 6 載具

before

```text
   calls     self cumulative function
     600    0.016    8.237 qysim/room.py:187(step)
    3600    0.111    7.332 qysim/engine.py:239(step)
    3600    0.073    2.065 qysim/tether.py:386(step)
    9240    0.039    1.750 qysim/world.py:701(current_at_many)
    3600    0.047    1.471 qysim/sensors.py:420(step)
     480    0.087    1.088 qysim/sensors.py:150(raycast_many)
    8708    0.372    1.074 qysim/world.py:833(sdf_many)
    3480    0.082    0.917 qysim/world.py:734(sdf)
    3600    0.024    0.852 qysim/operations.py:247(step)
    9240    0.031    0.785 qysim/world.py:593(sample_many)
   53411    0.349    0.750 qysim/world.py:41(sdf)
    3600    0.190    0.749 qysim/physics.py:242(step)
   18480    0.173    0.657 qysim/world.py:516(mean_many)
     180    0.004    0.639 qysim/sensors.py:465(_sample_echo)
    3600    0.036    0.631 qysim/engine.py:345(_sample_flow)
```

after

```text
   calls     self cumulative function
     600    0.015    8.162 qysim/room.py:187(step)
    3600    0.112    7.257 qysim/engine.py:239(step)
    3600    0.070    1.945 qysim/tether.py:386(step)
    9240    0.040    1.739 qysim/world.py:701(current_at_many)
    3600    0.045    1.505 qysim/sensors.py:420(step)
     480    0.088    1.120 qysim/sensors.py:150(raycast_many)
    8708    0.380    1.102 qysim/world.py:833(sdf_many)
    3480    0.083    0.915 qysim/world.py:734(sdf)
    3600    0.024    0.849 qysim/operations.py:247(step)
    9240    0.031    0.784 qysim/world.py:593(sample_many)
    3600    0.193    0.757 qysim/physics.py:242(step)
   53411    0.347    0.747 qysim/world.py:41(sdf)
   18480    0.171    0.656 qysim/world.py:516(mean_many)
     180    0.005    0.649 qysim/sensors.py:465(_sample_echo)
    3600    0.037    0.637 qysim/engine.py:345(_sample_flow)
```

### harbor_inspection / 3 載具

before

```text
   calls     self cumulative function
     600    0.010    4.939 qysim/room.py:187(step)
    1800    0.054    4.011 qysim/engine.py:239(step)
    5640    0.024    1.911 qysim/world.py:701(current_at_many)
    1800    0.034    1.297 qysim/tether.py:386(step)
    5640    0.131    1.093 qysim/flow.py:385(apply)
    1800    0.023    0.842 qysim/sensors.py:420(step)
   11280    0.626    0.770 qysim/flow.py:443(_box)
    4444    0.220    0.662 qysim/world.py:833(sdf_many)
    1800    0.019    0.631 qysim/engine.py:345(_sample_flow)
     600    0.028    0.606 qysim/operations.py:63(step_objects)
    2040    0.003    0.573 qysim/world.py:729(current_at)
     288    0.041    0.571 qysim/sensors.py:150(raycast_many)
    5640    0.018    0.458 qysim/world.py:593(sample_many)
     198    0.017    0.392 qysim/sensors.py:524(_ping_dvl)
   11280    0.103    0.390 qysim/world.py:516(mean_many)
```

after

```text
   calls     self cumulative function
     600    0.010    4.919 qysim/room.py:187(step)
    1800    0.056    3.992 qysim/engine.py:239(step)
    5640    0.024    1.926 qysim/world.py:701(current_at_many)
    1800    0.032    1.282 qysim/tether.py:386(step)
    5640    0.133    1.105 qysim/flow.py:385(apply)
    1800    0.023    0.829 qysim/sensors.py:420(step)
   11280    0.638    0.782 qysim/flow.py:443(_box)
    4444    0.218    0.650 qysim/world.py:833(sdf_many)
    1800    0.018    0.637 qysim/engine.py:345(_sample_flow)
     600    0.028    0.611 qysim/operations.py:63(step_objects)
    2040    0.003    0.576 qysim/world.py:729(current_at)
     288    0.040    0.562 qysim/sensors.py:150(raycast_many)
    5640    0.018    0.457 qysim/world.py:593(sample_many)
   11280    0.102    0.389 qysim/world.py:516(mean_many)
     198    0.017    0.387 qysim/sensors.py:524(_ping_dvl)
```

### harbor_inspection / 6 載具

before

```text
   calls     self cumulative function
     600    0.015    9.329 qysim/room.py:187(step)
    3600    0.109    8.221 qysim/engine.py:239(step)
    9240    0.040    3.329 qysim/world.py:701(current_at_many)
    3600    0.067    2.615 qysim/tether.py:386(step)
    9240    0.252    1.893 qysim/flow.py:385(apply)
    3600    0.047    1.810 qysim/sensors.py:420(step)
    8999    0.465    1.411 qysim/world.py:833(sdf_many)
   18480    1.062    1.307 qysim/flow.py:443(_box)
    3600    0.037    1.282 qysim/engine.py:345(_sample_flow)
     576    0.092    1.270 qysim/sensors.py:150(raycast_many)
    9240    0.031    0.831 qysim/world.py:593(sample_many)
     396    0.035    0.827 qysim/sensors.py:524(_ping_dvl)
     180    0.005    0.764 qysim/sensors.py:465(_sample_echo)
    3600    0.184    0.751 qysim/physics.py:242(step)
   18480    0.172    0.654 qysim/world.py:516(mean_many)
```

after

```text
   calls     self cumulative function
     600    0.016    9.560 qysim/room.py:187(step)
    3600    0.113    8.422 qysim/engine.py:239(step)
    9240    0.042    3.438 qysim/world.py:701(current_at_many)
    3600    0.069    2.657 qysim/tether.py:386(step)
    9240    0.255    1.951 qysim/flow.py:385(apply)
    3600    0.048    1.846 qysim/sensors.py:420(step)
    8999    0.473    1.442 qysim/world.py:833(sdf_many)
   18480    1.091    1.349 qysim/flow.py:443(_box)
    3600    0.038    1.331 qysim/engine.py:345(_sample_flow)
     576    0.095    1.295 qysim/sensors.py:150(raycast_many)
    9240    0.033    0.854 qysim/world.py:593(sample_many)
     396    0.035    0.838 qysim/sensors.py:524(_ping_dvl)
     180    0.004    0.783 qysim/sensors.py:465(_sample_echo)
    3600    0.193    0.776 qysim/physics.py:242(step)
   18480    0.176    0.675 qysim/world.py:516(mean_many)
```

## py-spy

基底 incident_wreck / 3：100 Hz，512 samples，0 errors；取樣包含啟動與暖機，因此僅作獨立熱點交叉確認，非基準計時。
下列為含 qysim frame 的樣本，取最深層 qysim frame 計數（Numba 原生內部無 Python frame）。

```text
  63 CurrentProfile.fluctuation_many (qysim/world.py:578)
  14 <module> (qysim/_flow_accel.py:11)
  14 CurrentProfile.mean_many (qysim/world.py:528)
  12 bed_factor (qysim/flow.py:114)
  11 Vehicle._uneven_flow_wrench (qysim/physics.py:217)
  11 Tether._run_batch (qysim/tether.py:504)
  10 Tether.length (qysim/tether.py:201)
   7 <module> (qysim/campaign/__init__.py:5)
   7 World.near (qysim/world.py:831)
   6 World.sdf_many (qysim/world.py:858)
   6 StructureFlow._box (qysim/flow.py:450)
   6 StructureFlow._box (qysim/flow.py:465)
   6 bed_factor (qysim/flow.py:113)
   5 StructureFlow._box (qysim/flow.py:466)
   5 StructureFlow._box (qysim/flow.py:467)
```

## 驗收測試

```text
cd simulator && python -m unittest discover -s tests
Ran 409 tests in 270.857s
OK
```

包含 test_sensors 的凍結參考、test_tether_validation、test_currents，以及既有 Numba / NumPy 等價測試。未修改、跳過或放寬既有測試。

## 限制與後續

本次消除了接觸快取失效造成的整個 tick 重做，並減少回復副本配置；整體平均改善有限，部分差異與雲端執行抖動相當，不宣稱全面顯著加速。
上表仍有組別平均未達 3 載具 5.5 ms / 6 載具 10 ms 目標；其他組的 p95 也可能超過 10 ms，尚不能保證慢機器或更多玩家不掉幀。
harbor 六載具剖析仍以 current_at_many（3.438 s）、StructureFlow.apply（1.951 s）、sensors.step（1.846 s）為主要成本；其中 _box 為 1.349 s、sdf_many 為 1.442 s（累積時間重疊，不可相加）。
下一步優先處理箱體洋流的編譯實作與感測器 sphere tracing 的距離專用查詢／共享空間索引；每項仍須以本工具逐位元或 1e-9 驗證，不能以降低感測器頻率換取效能。
另立後續修正 DVL 失鎖原因平票時的決定性；此 PR 固定 PYTHONHASHSEED 以保留現行輸出。
