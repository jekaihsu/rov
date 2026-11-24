"""Training data schema, source integrity and existing campaign execution contracts."""
import copy
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError

from qysim.campaign import DATA, validate
from qysim.engine import Simulator
from qysim.room import Room
from qysim.scenarios import build, catalogue


COURSES = sorted(DATA.glob('course_*.json'))
PROVISIONAL = '暫定，待資深操作員基準航次校準'


def read_script(path):
    return json.loads(path.read_text(encoding='utf-8'))


class TrainingCourseTests(unittest.TestCase):
    def test_schema_references_and_hours(self):
        schema = Draft202012Validator(read_script(DATA / 'schema.json'))
        scenarios = {item['key'] for item in catalogue()}
        self.assertEqual(len(COURSES), 12)
        hours = {}
        sources = set()
        ids = set()
        for path in COURSES:
            with self.subTest(course=path.stem):
                script = read_script(path)
                schema.validate(script)
                self.assertEqual(script['id'], path.stem)
                self.assertNotIn(script['id'], ids)
                ids.add(script['id'])
                self.assertEqual(script['category'], 'course')
                self.assertIn(script['scenario'], scenarios)
                self.assertEqual(build(script['scenario']).key, script['scenario'])
                self.assertNotIn('requires', script)
                self.assertFalse(script.get('placeholder'))
                self.assertFalse({'dialogue', 'reward'} & {n['type'] for n in script['nodes']})
                metadata = script['training']
                self.assertEqual(metadata['pass_status'], PROVISIONAL)
                self.assertTrue(metadata['goal'])
                self.assertTrue(metadata['criteria'])
                hours[metadata['level']] = hours.get(metadata['level'], 0) + metadata['simulator_minutes']
                for source in script['source_chapters']:
                    source_script = read_script(DATA / (source + '.json'))
                    sources.add(source)
                    self.assertIn(source_script['scenario'], scenarios)
                    if source.startswith('incident_'):
                        self.assertEqual(script['scenario'], source_script['scenario'])
        self.assertEqual(hours, {'初級': 240, '中級': 240, '進階': 240})
        self.assertTrue({'incident_' + name for name in ('jacket', 'wreck', 'silt', 'compass', 'current')} <= sources)

    def test_only_course_category_is_added(self):
        schema_data = read_script(DATA / 'schema.json')
        self.assertEqual(schema_data['properties']['category']['enum'], ['prelude', 'story', 'incident', 'course'])
        schema = Draft202012Validator(schema_data)
        script = read_script(COURSES[0])
        for category in ('prelude', 'story', 'incident', 'course'):
            script['category'] = category
            schema.validate(script)
        script['category'] = 'unknown'
        with self.assertRaises(ValidationError):
            schema.validate(script)

    def test_runtime_loading_and_explicit_entry(self):
        for path in COURSES:
            with self.subTest(course=path.stem):
                validate(read_script(path))
                room = Room(Simulator('open_water', 42))
                host = room.join(now=0)
                result = room.campaign.command(
                    dict(action='campaign_start', chapter=path.stem, course=True), host)
                self.assertTrue(result['ok'])
                self.assertEqual(room.campaign.status, 'active')
                self.assertEqual(room.primary.scenario.key, read_script(path)['scenario'])
                self.assertEqual(room.campaign.state()['next_story'], 'prologue')
                self.assertEqual(room.campaign.history, [])

    def test_scorer_terminal_branches_without_story(self):
        # Controlled state exercises script routing, not autonomous piloting proficiency.
        for path in COURSES:
            if path.stem == 'course_b01':
                continue
            for failure in (False, True):
                with self.subTest(course=path.stem, failure=failure):
                    room = Room(Simulator('open_water', 42))
                    host = room.join(now=0)
                    room.campaign.command(dict(action='campaign_start', chapter=path.stem, course=True), host)
                    sim = room.primary
                    if failure:
                        sim.tether.broken = True
                    else:
                        for objective in sim.scenario.objectives:
                            objective.done = True
                    sim.scorer.update(.01, sim)
                    room.campaign.update(.01)
                    self.assertEqual(room.campaign.status, 'completed')
                    text = room.campaign.objective
                    expected = '場景失敗' if failure else '場景節點完成'
                    self.assertIn(expected, text)
                    self.assertEqual(bool(sim.scorer.failed), failure)
                    self.assertEqual(room.campaign.rewards, [])

    def test_pool_preserves_existing_interactive_conditions(self):
        source = read_script(DATA / 'prologue.json')
        course = read_script(DATA / 'course_b01.json')
        expected = [copy.deepcopy(node) for node in source['nodes'] if node['type'] == 'wait']
        actual = [node for node in course['nodes'] if node['type'] == 'wait']
        self.assertEqual(actual, expected)
        # course_b01 keeps the company training pool; the directed prologue may use harbor_shallows.
        self.assertEqual(course['scenario'], 'tutorial_pool')
        self.assertIn(source['scenario'], ('tutorial_pool', 'harbor_shallows'))
