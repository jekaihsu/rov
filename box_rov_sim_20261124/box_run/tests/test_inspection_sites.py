"""Fixed engineering site integration: geometry, camera evidence and rewards.

Only initial cable settling is mocked. Geometry, camera transforms, visibility,
mission dwell and result generation use the real implementations.
"""
import copy
import math
import unittest
from unittest.mock import patch

import numpy as np

from rov01sim.engine import Simulator
from rov01sim.expedition import ensure_expedition
from rov01sim.inspection_sites import SITE_KEYS as _ALL_SITE_KEYS, site_manifest, site_obstacles
SITE_KEYS = _ALL_SITE_KEYS[:3]
from rov01sim.physics import q_from_euler, q_rot
from rov01sim.scenarios import catalogue
from rov01sim.vehicles import get_vehicle_definition
from rov01sim.world import Box, Cylinder


class InspectionSiteTests(unittest.TestCase):
    def make(self, key, seed=0):
        with patch('rov01sim.tether.Tether.settle'):
            sim = Simulator(key, seed, model_id='rov01_pro', vehicle_id='inspector')
        run = ensure_expedition(sim)
        run.command(sim, 'expedition_start', dict(contract='inspect', request_id='initial'))
        return sim, run

    def pose(self, sim, target):
        pos = np.asarray(target['point'], float)
        delta = np.asarray(target['target_point'], float)-pos
        yaw = math.atan2(delta[1], delta[0])
        pitch = -math.atan2(delta[2], math.hypot(delta[0], delta[1]))
        sim.vehicle.s.pos[:] = pos
        sim.vehicle.s.q[:] = q_from_euler(0., pitch, yaw)
        sim.vehicle.s.vel[:] = 0.
        sim.vehicle.s.omega[:] = 0.

    def evidence(self, sim, target, photo_id):
        return dict(photo_id=photo_id, entity_id=target['entity_id'], view='onboard',
                    visible=True, coverage=.04,
                    camera=dict(pos=(sim.vehicle.s.pos+q_rot(sim.vehicle.s.q,
                        np.asarray(sim.vehicle.definition.camera_body))).tolist(),
                        q=sim.vehicle.s.q.tolist(), fov=70, aspect=16/9))

    def dwell(self, sim, run, seconds):
        # Drive only mission time; no heavy vehicle or tether integration.
        for _ in range(round(seconds/.1)):
            sim.t += .1
            run.update(sim, .1)

    def test_three_sites_have_four_unique_geometry_backed_targets(self):
        self.assertEqual(len(SITE_KEYS), 3)
        advertised = {item['key'] for item in catalogue()}
        for key in SITE_KEYS:
            with self.subTest(site=key):
                site = site_manifest(key)
                self.assertIn(key, advertised)
                self.assertEqual(len(site['targets']), 4)
                ids = {target['entity_id'] for target in site['targets']}
                self.assertEqual(len(ids), 4)
                self.assertTrue(ids <= {item.get('entity_id') for item in site['geometry']})
                self.assertTrue(all(target['hold_s']==5. for target in site['targets']))
                obstacles = site_obstacles(key)
                self.assertEqual(len(obstacles), len(site['geometry']))
                for item, obstacle in zip(site['geometry'], obstacles):
                    self.assertEqual(item['name'], obstacle.name)
                    if item['type']=='cylinder':
                        self.assertIsInstance(obstacle, Cylinder)
                        np.testing.assert_allclose(obstacle.p0, item['p0'])
                        np.testing.assert_allclose(obstacle.p1, item['p1'])
                        self.assertEqual(obstacle.radius, item['radius'])
                    else:
                        self.assertIsInstance(obstacle, Box)
                        np.testing.assert_allclose(obstacle.center, item['center'])
                        np.testing.assert_allclose(obstacle.half, np.asarray(item['size'])/2)

    def test_manifest_is_not_shared_mutable_state(self):
        first = site_manifest(SITE_KEYS[0])
        first['targets'][0]['point'][0] = 999.
        self.assertNotEqual(site_manifest(SITE_KEYS[0])['targets'][0]['point'][0], 999.)
        self.assertIsNone(site_manifest('coral_reef'))

    def test_stances_clear_all_vehicle_hulls_and_camera_paths_across_seeds(self):
        for key in SITE_KEYS:
            for seed in (0, 42, 913):
                sim, run = self.make(key, seed)
                for target in sim.world.inspection_site['targets']:
                    with self.subTest(site=key, seed=seed, target=target['id']):
                        self.pose(sim, target)
                        for model in ('rov01', 'rov02_heavy', 'rov01_pro'):
                            definition = get_vehicle_definition(model)
                            for centre, radius in definition.hull_spheres:
                                point = sim.vehicle.s.pos+q_rot(sim.vehicle.s.q, np.asarray(centre))
                                self.assertGreater(sim.world.sdf(point)[0]-radius, 0., model)
                        origin = np.asarray(self.evidence(sim, target, 'check')['camera']['pos'])
                        delta = np.asarray(target['target_point'])-origin
                        distance = np.linalg.norm(delta)
                        ray_distance = sim.world.raycast(origin, delta, max_range=distance)
                        self.assertGreaterEqual(ray_distance, distance-target['target_radius']-.15)
                        observed = run.observe(sim, self.evidence(sim, target, target['id']))
                        self.assertTrue(observed['observation']['accepted'], observed)

    def test_fixed_inspection_uses_no_dummy_work_objects_and_limits_other_jobs(self):
        for key in SITE_KEYS:
            sim, run = self.make(key)
            task = run.active
            self.assertEqual(len(task['steps']), 4)
            self.assertFalse(any(ob.get('task_id')==task['id'] for ob in sim.world.work_objects.values()))
            self.assertTrue(all(step['fixed_site'] for step in task['steps']))
            offered = {item['kind']:item['enabled'] for item in run.available(sim)}
            self.assertEqual(offered, dict(inspect=True, recover=False, deploy=False))

    def test_three_seconds_cannot_complete_five_second_inspection(self):
        for key in SITE_KEYS:
            sim, run = self.make(key)
            target = sim.world.inspection_site['targets'][0]
            self.pose(sim, target)
            self.dwell(sim, run, 3.)
            response = run.observe(sim, self.evidence(sim, target, 'too-soon'))
            self.assertTrue(response['observation']['accepted'])  # Photograph can be saved.
            self.assertFalse(run.active['steps'][0]['completed'])
            self.assertAlmostEqual(run.state(sim)['active']['steps'][0]['own_progress'], .6)
            self.dwell(sim, run, 2.)
            response = run.observe(sim, self.evidence(sim, target, 'five-seconds'))
            self.assertTrue(response['observation']['accepted'])
            self.assertTrue(run.active['steps'][0]['completed'])

    def test_bad_view_spoofed_camera_and_occlusion_cannot_finish_target(self):
        sim, run = self.make(SITE_KEYS[1])
        target = sim.world.inspection_site['targets'][0]
        self.pose(sim, target)
        self.dwell(sim, run, 5.)
        valid = self.evidence(sim, target, 'valid')
        bad_view = copy.deepcopy(valid)
        bad_view.update(photo_id='orbit', view='orbit')
        spoofed = copy.deepcopy(valid)
        spoofed['photo_id'] = 'spoofed'
        spoofed['camera']['pos'][0] += 10.
        for message in (bad_view, spoofed):
            self.assertFalse(run.observe(sim, message)['observation']['accepted'])
            self.assertFalse(run.active['steps'][0]['completed'])
        centre = (np.asarray(valid['camera']['pos'])+np.asarray(target['target_point']))/2
        sim.world.obstacles.append(Box('inspection test screen', tuple(centre), (.7,.1,.7)))
        blocked = copy.deepcopy(valid)
        blocked['photo_id'] = 'blocked'
        self.assertFalse(run.observe(sim, blocked)['observation']['accepted'])
        self.assertFalse(run.active['steps'][0]['completed'])

    def test_cancel_restart_preserves_real_structure_and_resets_dwell(self):
        for key in SITE_KEYS:
            sim, run = self.make(key)
            geometry = list(sim.world.obstacles)
            work_objects = set(sim.world.work_objects)
            first_id = run.active['id']
            target = sim.world.inspection_site['targets'][0]
            self.pose(sim, target)
            self.dwell(sim, run, 5.)
            run.command(sim, 'expedition_cancel', dict(request_id='cancel'))
            self.assertIsNone(run.active)
            self.assertEqual(run.results, [])
            self.assertEqual(sim.world.obstacles, geometry)
            self.assertEqual(set(sim.world.work_objects), work_objects)
            run.command(sim, 'expedition_start', dict(contract='inspect', request_id='restart'))
            self.assertNotEqual(run.active['id'], first_id)
            self.assertEqual(run.state(sim)['active']['steps'][0]['own_progress'], 0.)
            run.observe(sim, self.evidence(sim, target, 'restart-photo'))
            self.assertFalse(run.active['steps'][0]['completed'])

    def test_all_targets_produce_one_reward_compatible_result_and_no_duplicate(self):
        for key in SITE_KEYS:
            sim, run = self.make(key)
            task_id = run.active['id']
            for target in sim.world.inspection_site['targets']:
                self.pose(sim, target)
                self.dwell(sim, run, 5.)
                message = self.evidence(sim, target, target['id'])
                response = run.observe(sim, message)
                self.assertTrue(response['observation']['accepted'], response)
            self.assertIsNone(run.active)
            self.assertEqual(len(run.results), 1)
            result = run.results[0]
            self.assertEqual(result['id'], task_id)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['kind'], 'inspect')
            self.assertEqual(result['scene'], key)
            self.assertEqual(result['participant_ids'], ['inspector'])
            self.assertEqual(result['contributor_player_ids'], ['inspector'])
            self.assertIn('T', result['created_at'])
            self.assertGreaterEqual(result['elapsed'], 20.)
            self.assertTrue(result['label'])
            self.assertTrue(result['grade'])
            self.assertEqual(run.observe(sim, message), response)
            self.assertEqual(len(run.results), 1)
            self.assertEqual(run.discoveries, [])


if __name__=='__main__':
    unittest.main()
