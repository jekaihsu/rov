在此目錄 /workspace/rov_sim/mujoco_rov01 建立 MuJoCo ROV-01 模擬（只用免費 pip 套件，已裝 mujoco 3.17；不聯網上傳、不 git push）。
1. ROV-01：6 推進器，幾何取自 /workspace/rov_sim/box_run/rov01sim/vehicles.py 的 ROV01_THRUSTERS（位置/方向原樣，T1-T4 水平 45° 向量、T5-T6 垂直），寫成 rov01.xml (MJCF)，每個推進器一個 site + motor actuator（gear 對應推力方向）。外觀為原創開放式框架（管狀框架+浮力塊），顏色只用深海青 #06B6D4 與鈦灰 #1E293B，嚴禁橘色及任何第三方 ROV 品牌/外殼模型。
2. 物理：浮力（略正浮力，用 xfrc_applied 於浮心）、線性+二次拖曳（相對流體速度）、臍帶纜：多段 body 鏈或 tendon，一端固定在上方、一端接 ROV。
3. 場景：海床平面+沿 x 軸的電纜（細長圓柱），ROV 定深（電纜上方 1.0 m）沿纜前進約 0.3 m/s，有 0.75 kn 的 y 向側流。用 PID/控制分配到 6 推進器。
4. sim.py：跑 60 s，用 MUJOCO_GL=egl（失敗改 osmesa）離線渲染 out/rov01_cable.mp4（imageio-ffmpeg）及至少 3 張 out/shot_*.png（看得到 ROV 與電纜），寫 out/thrust.csv（t, depth_err, cross_track, T1..T6），out/summary.json（深度誤差 RMS/max、偏離電纜 RMS/max、各推力 RMS）。
自己執行 python3 sim.py 直到成功，最後印出 summary。
