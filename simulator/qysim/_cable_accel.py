"""Optional compiled version of the tether's existing force equations.

Numba is optional. The reference NumPy implementation remains in tether.py.
No fast-math transforms are used; tests compare both integration paths.
"""
import math
import numpy as np

try:
    from numba import njit
except ImportError:
    njit = None


def _advance(x, v, water, spool, gland, gland_vel, broken, h, m, l0, k, damping,
             diameter, cd_normal, cd_tangent, wet_weight, breaking_n):
    n = len(x)-1
    x[0] = spool
    v[0] = 0.
    if not broken:
        x[n] = gland
        v[n] = gland_vel
    forces = np.zeros_like(x)
    lengths = np.empty(n)
    segment_force = np.zeros((n,3))
    magnitudes = np.empty(n)
    for i in range(n):
        dx, dy, dz = x[i+1,0]-x[i,0], x[i+1,1]-x[i,1], x[i+1,2]-x[i,2]
        length = math.sqrt(dx*dx+dy*dy+dz*dz)
        lengths[i] = length
        denominator = max(length,1e-9)
        ux, uy, uz = dx/denominator, dy/denominator, dz/denominator
        rate = (v[i+1,0]-v[i,0])*ux+(v[i+1,1]-v[i,1])*uy+(v[i+1,2]-v[i,2])*uz
        magnitude = k*(length-l0)+damping*rate if length>l0 else 0.
        if not math.isfinite(magnitude):
            magnitude = 0.
        magnitude = min(max(magnitude,0.),2.*breaking_n)
        magnitudes[i] = magnitude
        segment_force[i,0],segment_force[i,1],segment_force[i,2] = magnitude*ux,magnitude*uy,magnitude*uz
        for axis in range(3):
            forces[i,axis] += segment_force[i,axis]
            forces[i+1,axis] -= segment_force[i,axis]
    drag_scale = .5*1025.*diameter*l0
    for i in range(n+1):
        left,right = max(0,i-1),min(n,i+1)
        tx,ty,tz = x[right,0]-x[left,0],x[right,1]-x[left,1],x[right,2]-x[left,2]
        norm = max(math.sqrt(tx*tx+ty*ty+tz*tz),1e-9)
        tx,ty,tz = tx/norm,ty/norm,tz/norm
        rx,ry,rz = water[i,0]-v[i,0],water[i,1]-v[i,1],water[i,2]-v[i,2]
        projection = rx*tx+ry*ty+rz*tz
        vx,vy,vz = projection*tx,projection*ty,projection*tz
        nx,ny,nz = rx-vx,ry-vy,rz-vz
        vn = math.sqrt(nx*nx+ny*ny+nz*nz)
        vt = math.sqrt(vx*vx+vy*vy+vz*vz)
        forces[i,0] += drag_scale*(cd_normal*nx*vn+cd_tangent*vx*vt)
        forces[i,1] += drag_scale*(cd_normal*ny*vn+cd_tangent*vy*vt)
        forces[i,2] += drag_scale*(cd_normal*nz*vn+cd_tangent*vz*vt)+wet_weight*l0*9.81
    for i in range(n+1):
        for axis in range(3):
            v[i,axis] += forces[i,axis]/m*h
            x[i,axis] += v[i,axis]*h
    return magnitudes,-segment_force[-1]


advance = njit(cache=True)(_advance) if njit is not None else None


def _batch(x,v,water,spool,gland,gland_vel,broken,h,m,l0,k,damping,diameter,
           cd_normal,cd_tangent,wet_weight,breaking_n,substeps,anchor,distances,normals,
           cache_distance,node_radius,friction):
    magnitudes = np.zeros(len(x)-1)
    force = np.zeros(3)
    for _ in range(substeps):
        magnitudes,force = advance(x,v,water,spool,gland,gland_vel,broken,h,m,l0,k,damping,
                                 diameter,cd_normal,cd_tangent,wet_weight,breaking_n)
        # If the local plane approximation expires, the caller restores this
        # entire tick and uses its geometry-refreshing reference substep loop.
        for i in range(len(x)):
            displacement = 0.
            for axis in range(3):
                displacement += (x[i,axis]-anchor[i,axis])**2
            if displacement > cache_distance**2:
                return False,magnitudes,force
        last = len(x) if broken else len(x)-1
        for i in range(1,last):
            distance = distances[i]
            for axis in range(3):
                distance += (x[i,axis]-anchor[i,axis])*normals[i,axis]
            penetration = min(node_radius-distance,.05)
            if penetration <= 0:
                continue
            normal_speed = 0.
            for axis in range(3):
                x[i,axis] += normals[i,axis]*penetration
                normal_speed += v[i,axis]*normals[i,axis]
            into = min(0.,normal_speed)
            normal_speed = 0.
            for axis in range(3):
                v[i,axis] -= into*normals[i,axis]
                normal_speed += v[i,axis]*normals[i,axis]
            tx = v[i,0]-normal_speed*normals[i,0]
            ty = v[i,1]-normal_speed*normals[i,1]
            tz = v[i,2]-normal_speed*normals[i,2]
            tangent_speed = math.sqrt(tx*tx+ty*ty+tz*tz)
            reduction = min(1.,max(0.,1.-friction*(abs(into)+.05)/max(tangent_speed,1e-6)))
            v[i,0] += tx*(reduction-1.)
            v[i,1] += ty*(reduction-1.)
            v[i,2] += tz*(reduction-1.)
    return True,magnitudes,force


advance_batch = njit(cache=True)(_batch) if njit is not None else None
