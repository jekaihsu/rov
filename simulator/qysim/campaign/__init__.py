"""Room-owned data-driven narrative; existing mission engines remain authoritative."""
from copy import deepcopy
import json
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError

DATA = Path(__file__).resolve().parents[2] / 'campaign'
SCHEMA = Draft202012Validator(json.loads((DATA / 'schema.json').read_text()))
# Chapter list order: the story campaign first, then the standalone incident drills.
CATEGORIES = ('story', 'incident')
CHAPTER_FIELDS = ('id', 'title', 'requires', 'placeholder', 'outline', 'category', 'order')
TYPES = {'dialogue', 'wait', 'objective', 'hint', 'branch', 'reward', 'checkpoint', 'environment', 'spawn', 'remove'}


def validate(script):
    try:
        SCHEMA.validate(script)
    except ValidationError as error:
        raise ValueError(error.message) from error
    if not isinstance(script, dict) or not isinstance(script.get('nodes'), list):
        raise ValueError('invalid campaign')
    required = ('id', 'title', 'scenario', 'mode')
    if any(not isinstance(script.get(key), str) for key in required):
        raise ValueError('missing script metadata')
    if script.get('category') not in CATEGORIES:
        raise ValueError('invalid chapter category')
    order = script.get('order')
    if isinstance(order, bool) or not isinstance(order, int):
        raise ValueError('invalid chapter order')
    ids = [node.get('id') for node in script['nodes']]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) for i in ids):
        raise ValueError('duplicate or invalid node id')
    for node in script['nodes']:
        if node.get('type') not in TYPES:
            raise ValueError('unsupported node type')
        if node['type'] in ('wait', 'branch'):
            condition = node.get('condition', {})
            if (condition.get('op') not in ('eq', 'gt', 'lt')
                    or not isinstance(condition.get('path'), str) or 'value' not in condition):
                raise ValueError('invalid condition')
        if node['type'] == 'branch' and node.get('target') not in ids:
            raise ValueError('invalid branch target')
    strings = script.get('strings', {}).get('zh-TW', {})
    for node in script['nodes']:
        for field in ('text', 'speaker', 'hint'):
            if field + '_key' in node:
                key = node[field + '_key']
                if key not in strings:
                    raise ValueError('missing locale key')
                node[field] = strings[key]
    return script


def condition_matches(condition, state):
    value = state
    try:
        for part in condition['path'].split('.'):
            value = value[int(part)] if isinstance(value, list) else value[part]
        expected = condition['value']
        op = condition['op']
        if op == 'eq':
            return value == expected
        if op == 'gt':
            return value > expected
        return value < expected
    except (KeyError, IndexError, TypeError, ValueError):
        return False


class Campaign:
    def __init__(self, room):
        self.room = room
        self.scripts = {p.stem: validate(json.loads(p.read_text())) for p in sorted(DATA.glob('*.json'))
                        if p.name != 'schema.json'}
        self.chapter = None
        self.index = 0
        self.completed = []
        self.rewards = []
        self.results = []
        self.history = []
        self.objective = ''
        self.status = 'idle'
        self.pilot = 'v1'
        self.started = 0
        self.checkpoint = None
        self.course = False
        self.resume_checkpoint = None
        self.resumed = False
        self.peak_tension = 0.
        self.environment_changed = False

    def chapter_order(self, script):
        """Explicit sort key: (category, order); the id only breaks accidental ties."""
        return (CATEGORIES.index(script['category']), script['order'], script['id'])

    def ordered_scripts(self):
        return sorted(self.scripts.values(), key=self.chapter_order)

    def next_story_chapter(self, completed=None):
        """First playable, unfinished story chapter; incidents are never auto-started."""
        done = self.completed if completed is None else completed
        for script in self.ordered_scripts():
            if script['category'] != 'story' or script.get('placeholder'):
                continue
            if script['id'] in done:
                continue
            if script.get('requires') and script['requires'] not in done:
                continue
            return script['id']
        return None

    def command(self, msg, player):
        if player is None or player.id != self.room.host_id:
            return dict(ok=False, message='host_only')
        action = msg.get('action')
        if action == 'campaign_start':
            key = msg.get('chapter', 'prologue')
            script = self.scripts.get(key)
            if not script or script.get('placeholder'):
                return dict(ok=False, message='unavailable')
            if script.get('requires') and script['requires'] not in self.completed:
                return dict(ok=False, message='locked')
            modes = {vid: sim.operation_mode for vid, sim in self.room.vehicles.items()}
            self.room.reset(script['scenario'], 42)
            for vid, mode in modes.items():
                self.room.vehicles[vid].operation_mode = mode
            from ..mission_modes import MissionRun
            self.room.primary.world.mission_run = MissionRun(self.room.primary, script['mode'])
            self.chapter = key
            self.index = 0
            checkpoint = self.resume_checkpoint
            self.resumed = bool(msg.get('resume') and checkpoint and checkpoint['chapter'] == key)
            if self.resumed:
                self.index = checkpoint['index']
            self.pilot = player.vehicle_id
            self.started = 0
            self.peak_tension = 0.
            self.history = []
            self.objective = ''
            self.status = 'active'
            self.course = bool(msg.get('course', False))
        elif action == 'campaign_advance' and self.status == 'active':
            if self.node and self.node['type'] == 'dialogue':
                self.index += 1
        elif action == 'campaign_skip':
            # Skipping onboarding is explicit; it never earns a rating or reward.
            if self.chapter == 'prologue' and 'prologue' not in self.completed:
                self.completed.append('prologue')
            self.status = 'skipped'
        elif action == 'campaign_restore':
            saved = msg.get('save', {})
            if self.status == 'active' or not isinstance(saved, dict):
                return dict(ok=False, message='busy_or_invalid')
            self.completed = [k for k in saved.get('completed', []) if k in self.scripts]
            self.rewards = [str(k)[:64] for k in saved.get('rewards', [])][:100]
            self.results = [r for r in saved.get('results', []) if isinstance(r, dict)][:100]
            checkpoint = saved.get('checkpoint')
            if isinstance(checkpoint, dict) and checkpoint.get('chapter') in self.scripts:
                index = checkpoint.get('index')
                if isinstance(index, int) and 0 <= index < len(self.scripts[checkpoint['chapter']]['nodes']):
                    self.resume_checkpoint = deepcopy(checkpoint)
                    self.checkpoint = deepcopy(checkpoint)
        else:
            return dict(ok=False, message='invalid_campaign_action')
        self.room._snapshot = None
        self.update(0)
        return dict(ok=True, action=action)

    @property
    def node(self):
        nodes = self.scripts[self.chapter]['nodes'] if self.chapter else []
        return nodes[self.index] if self.index < len(nodes) else None

    def update(self, dt):
        if self.status != 'active':
            return
        sim = self.room.vehicles.get(self.pilot)
        if sim is None:
            return
        self.started += dt
        self.peak_tension = max(self.peak_tension, float(sim.tether.tension_max))
        for _ in range(32):
            node = self.node
            if node is None:
                self.status = 'completed'
                if self.chapter not in self.completed:
                    self.completed.append(self.chapter)
                trainee = next((p.name for p in self.room.players.values() if p.vehicle_id == self.pilot), '')
                self.results.append(dict(chapter=self.chapter, trainee=trainee, elapsed=round(self.started, 2),
                                         collisions=len(sim.world.events), tether_broken=bool(sim.tether.broken),
                                         peak_tension_n=round(self.peak_tension, 1),
                                         completion=1, resumed=self.resumed))
                return
            kind = node['type']
            if kind == 'dialogue':
                if not self.history or self.history[-1]['id'] != node['id']:
                    self.history.append(deepcopy(node))
                if not self.course:
                    return
            elif kind == 'wait':
                if not condition_matches(node['condition'], sim.viewer_state()):
                    return
            elif kind in ('objective', 'hint'):
                self.objective = node.get('text', '')
            elif kind == 'reward':
                if node['reward'] not in self.rewards:
                    self.rewards.append(node['reward'])
            elif kind == 'checkpoint':
                self.checkpoint = dict(chapter=self.chapter, index=self.index + 1)
            elif kind == 'branch':
                if condition_matches(node['condition'], sim.viewer_state()):
                    self.index = next(i for i, n in enumerate(self.scripts[self.chapter]['nodes'])
                                      if n['id'] == node['target'])
                    continue
            elif kind == 'spawn':
                from ..operations import ensure_objects, finite_vector
                import numpy as np
                objects = ensure_objects(sim)
                key = 'campaign-' + node['object_id']
                if len(objects) < 100 and key not in objects:
                    objects[key] = dict(id=key, label=node['label'], pos=finite_vector(node['point'], 3),
                                        vel=np.zeros(3), mass=2., buoyancy_kg=1., radius=.12, held_by=None)
            elif kind == 'remove':
                from ..operations import ensure_objects
                objects = ensure_objects(sim)
                key = 'campaign-' + node['object_id']
                if key in objects and objects[key]['held_by'] is None:
                    del objects[key]
            elif kind == 'environment':
                for vehicle in self.room.vehicles.values():
                    vehicle.scenario.visibility_m = max(1, min(30, float(node['visibility_m'])))
                self.environment_changed = True
            self.index += 1

    def state(self):
        return deepcopy(dict(chapter=self.chapter, index=self.index, node=self.node, status=self.status,
                             objective=self.objective, dialogue=self.history[-30:], completed=self.completed,
                             rewards=self.rewards, results=self.results, checkpoint=self.checkpoint,
                             unlocks=dict(vehicles=['falcon'] if 'harbor_signoff' in self.completed else [],
                                          stickers=['dive'] if 'prologue' in self.completed else []),
                             next_story=self.next_story_chapter(),
                             chapters=[{k: s.get(k) for k in CHAPTER_FIELDS} for s in self.ordered_scripts()]))
