"""Incident data integration: schema, independent entry and both terminal paths."""
import json
import unittest

import numpy as np

from qysim.campaign import DATA, validate
from qysim.engine import Simulator
from qysim.room import Room
from qysim.scenarios import build, catalogue


KEYS = ['incident_' + key for key in ('jacket', 'wreck', 'silt', 'compass', 'current')]


class IncidentTests(unittest.TestCase):
    def test_schema_and_catalogue(self):
        catalogue_keys = {entry['key'] for entry in catalogue()}
        for key in KEYS:
            with self.subTest(key=key):
                script = validate(json.loads((DATA / (key + '.json')).read_text()))
                self.assertNotIn('requires', script)
                self.assertIn(key, catalogue_keys)
                self.assertEqual(script['scenario'], build(key).key)
                self.assertIn('debrief', script['strings']['zh-TW'])

    def start(self, key):
        room = Room(Simulator('open_water', 42))
        host = room.join(now=0)
        self.assertTrue(room.campaign.command(dict(action='campaign_start', chapter=key), host)['ok'])
        room.campaign.command(dict(action='campaign_advance'), host)
        return room, host

    def finish_dialogue(self, room, host):
        for _ in range(4):
            room.campaign.command(dict(action='campaign_advance'), host)
        self.assertEqual(room.campaign.status, 'completed')
        self.assertIn('debrief', [node['id'] for node in room.campaign.history])

    def count_state_calls(self, sim):
        calls = []
        original = sim.viewer_state

        def counted():
            calls.append(1)
            return original()

        sim.viewer_state = counted
        return calls

    def test_poll_loop_builds_state_once_per_update(self):
        for key in KEYS:
            with self.subTest(key=key):
                room, host = self.start(key)
                sim = room.primary
                calls = self.count_state_calls(sim)
                for _ in range(5):
                    del calls[:]
                    room.campaign.update(.01)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(room.campaign.node['id'], 'repeat')
                sim.tether.broken = True
                sim.scorer.update(.01, sim)
                del calls[:]
                room.campaign.update(.01)
                self.assertEqual(len(calls), 1)
                self.assertEqual(room.campaign.node['id'], 'failure')
                del calls[:]
                room.campaign.update(.01)
                self.assertEqual(len(calls), 0)

    def test_completion(self):
        # Controlled poses exercise the real objective scorer, not a campaign flag.
        for key in KEYS:
            with self.subTest(key=key):
                room, host = self.start(key)
                sim = room.primary
                for objective in sim.scenario.objectives:
                    sim.vehicle.s.pos = np.asarray(objective.point, dtype=float)
                    if objective.kind == 'untangle':
                        sim.tether.wraps[objective.target] = 0
                    for _ in range(5):
                        sim.scorer.update(1, sim)
                sim.scorer.update(.01, sim)
                self.assertTrue(sim.scorer.finished)
                room.campaign.update(.01)
                self.assertEqual(room.campaign.node['id'], 'success')
                self.finish_dialogue(room, host)

    def test_failures(self):
        for key in KEYS:
            for failure in ('timeout', 'broken'):
                with self.subTest(key=key, failure=failure):
                    room, host = self.start(key)
                    sim = room.primary
                    if failure == 'broken':
                        sim.tether.broken = True
                        sim.scorer.update(.01, sim)
                    else:
                        sim.scorer.update(sim.scenario.time_limit_s + 1, sim)
                    self.assertTrue(sim.scorer.failed)
                    room.campaign.update(.01)
                    self.assertEqual(room.campaign.node['id'], 'failure')
                    self.finish_dialogue(room, host)
