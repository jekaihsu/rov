"""60 s ROV inspection simulation, SI units, offline EGL/OSMesa rendering."""
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
# A fresh process is required when changing the OpenGL backend.
os.environ.setdefault('MUJOCO_GL', 'egl')
import csv
import json
import subprocess
import numpy as np
import mujoco
import imageio.v2 as imageio
from scipy.spatial.transform import Rotation

DURATION = 60.0
FPS = 20
CURRENT = np.array([0., .75 * 1852 / 3600, 0.])
TARGET_Z = .035 + .025 + 1.0  # CG is 1 m above the cable's upper surface.
LINEAR = np.array([9., 14., 18.])
QUADRATIC = np.array([20., 32., 38.])


def main():
    out = ROOT / 'out'
    out.mkdir(exist_ok=True)
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'rov01.xml'))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    try:
        renderer = mujoco.Renderer(model, height=640, width=960)
    except Exception as exc:
        if os.environ['MUJOCO_GL'] == 'egl':
            print(f'EGL failed ({exc}); retrying in a fresh OSMesa process.', flush=True)
            env = dict(os.environ, MUJOCO_GL='osmesa')
            return subprocess.call([sys.executable, str(Path(__file__).resolve())], env=env)
        raise
    body = model.body('rov').id
    cob = model.site('buoyancy_center').id
    dt = model.opt.timestep
    sample_stride = round(1 / FPS / dt)
    ref_R = np.diag([1., -1., -1.])
    allocation = np.column_stack([
        np.r_[model.actuator_gear[i,:3], np.cross(model.site_pos[model.actuator_trnid[i,0]], model.actuator_gear[i,:3])]
        for i in range(6)])
    assert np.linalg.matrix_rank(allocation) == 6
    inverse = np.linalg.inv(allocation)
    integral = np.zeros(3)
    attitude_i = np.zeros(3)
    actual = np.zeros(6)
    records = []
    tracking = []
    thrusts = []
    saturation = 0
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.distance = 4.4
    camera.azimuth = 125
    camera.elevation = -25
    video = imageio.get_writer(str(out/'rov01_cable.mp4'), fps=FPS, codec='libx264', quality=8,
                              macro_block_size=16, ffmpeg_log_level='error')
    print(f'MuJoCo {mujoco.__version__}; backend={os.environ["MUJOCO_GL"]}; 60 s / {FPS} fps', flush=True)
    shots = {200: '10', 600: '30', 1000: '50'}
    frame = 0
    try:
        for step in range(round(DURATION/dt)):
            t = data.time
            R = data.xmat[body].reshape(3,3)
            velocity = np.zeros(6)
            mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, body, velocity, 0)
            omega_world, v_world = velocity[:3], velocity[3:]
            v_relative = R.T @ (v_world - CURRENT)
            drag_body = -LINEAR*v_relative - QUADRATIC*np.abs(v_relative)*v_relative
            omega_body = R.T @ omega_world
            angular_drag = -np.array([.8,1.,1.2])*omega_body - .4*np.abs(omega_body)*omega_body
            buoyancy = np.array([0.,0.,12*9.81 + 2.0])
            buoyancy_moment = np.cross(data.site_xpos[cob]-data.xipos[body], buoyancy)
            data.xfrc_applied[:] = 0
            # xfrc_applied is a world-frame COM wrench: r x F places buoyancy at the COB.
            data.xfrc_applied[body,:3] = buoyancy + R @ drag_body
            data.xfrc_applied[body,3:] = buoyancy_moment + R @ angular_drag
            speed = .3*min(t/3.,1.)
            x_ref = .05*t*t if t < 3 else .3*(t-1.5)
            desired = np.array([x_ref,0.,TARGET_Z])
            error = desired-data.xpos[body]
            integral = np.clip(integral+error*dt,-1.,1.)
            v_ref = np.array([speed,0.,0.])
            force_world = np.array([20.,42.,65.])*error + np.array([22.,32.,38.])*(v_ref-v_world) + np.array([4.,9.,14.])*integral
            force_world += np.array([1.2 if t < 3 else 0.,0.,-2.]) - R@drag_body
            attitude_error = Rotation.from_matrix(ref_R @ R.T).as_rotvec()
            attitude_i = np.clip(attitude_i+attitude_error*dt,-.3,.3)
            torque_world = np.array([12.,16.,14.])*attitude_error - np.array([4.,5.,5.])*omega_world + 2*attitude_i
            torque_world -= buoyancy_moment + R@angular_drag
            command = inverse @ np.r_[R.T@force_world,R.T@torque_world]
            saturation += int(np.any(np.abs(command)>45))
            command = np.clip(command,-45,45)
            actual += (1-np.exp(-dt/.08))*(command-actual)
            data.ctrl[:] = actual
            tracking.append([error[2],data.xpos[body,1]])
            thrusts.append(actual.copy())
            if step % sample_stride == 0:
                records.append([t,error[2],data.xpos[body,1],*actual])
                camera.lookat[:] = data.xpos[body] + np.array([.25,0.,-.32])
                renderer.update_scene(data,camera=camera)
                # Disable shadow-map acne on the large, grazing-angle seabed.
                renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
                pixels=renderer.render()
                video.append_data(pixels)
                if frame in shots:
                    imageio.imwrite(out/f'shot_{shots[frame]}.png',pixels)
                frame += 1
            mujoco.mj_step(model,data)
            if not np.isfinite(data.qpos).all():
                raise RuntimeError('Non-finite simulation state')
            if (step+1) % 2000 == 0:
                print(f't={data.time:.0f}s, xyz={data.xpos[body].round(3)}, max thrust={np.abs(actual).max():.2f} N',flush=True)
    finally:
        video.close()
        renderer.close()
    with (out/'thrust.csv').open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['t','depth_err','cross_track','T1','T2','T3','T4','T5','T6'])
        writer.writerows(records)
    errors=np.array(tracking); forces=np.array(thrusts)
    warnings={str(i):int(w.number) for i,w in enumerate(data.warning) if w.number}
    summary={
        'duration_s':float(data.time), 'mujoco_version':mujoco.__version__, 'render_backend':os.environ['MUJOCO_GL'],
        'current_y_kn':.75,'current_y_m_s':float(CURRENT[1]),'target_speed_m_s':.3,
        'target_cg_height_above_cable_m':1.,'target_world_z_m':TARGET_Z,
        'depth_error_rms_m':float(np.sqrt(np.mean(errors[:,0]**2))),
        'depth_error_max_m':float(np.abs(errors[:,0]).max()),
        'cross_track_rms_m':float(np.sqrt(np.mean(errors[:,1]**2))),
        'cross_track_max_m':float(np.abs(errors[:,1]).max()),
        'thrust_rms_N':{f'T{i+1}':float(v) for i,v in enumerate(np.sqrt(np.mean(forces**2,axis=0)))},
        'final_position_m':data.qpos[:3].tolist(), 'mean_forward_speed_m_s':float(data.qpos[0]/DURATION),
        'actuator_limit_N':45.,'saturated_step_fraction':saturation/len(tracking),
        'video_frames':frame, 'csv_rows':len(records), 'mujoco_warnings':warnings,
        'notes':'Engineering-estimate hydrodynamics; FRD source geometry preserved. Positive depth_err means too deep. Elastic straight spatial tendon models umbilical tension, not distributed cable drag or sag.'
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    assert not warnings, f'MuJoCo warnings: {warnings}'
    assert summary['depth_error_max_m'] < .2 and summary['cross_track_max_m'] < .3
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
