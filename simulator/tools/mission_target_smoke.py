"""Check station placement against the same generated scene geometry as engine."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qysim import scenarios
from qysim.world import World
from qysim.mission_modes import MissionRun

result = {}
for key in [*scenarios.LIBRARY,'random']:
    scenario = scenarios.build(key,42)
    world = World(scenario.seabed_depth)
    world.obstacles = list(scenario.obstacles)
    world.current = scenario.current
    world.configure_habitat(scenario.biome,42,keep_clear=[scenario.start_pos,scenario.spool_pos]+
        [o.point for o in scenario.objectives if o.point is not None])
    run = MissionRun(SimpleNamespace(t=0,scenario=scenario,world=world),'inspection_coop')
    result[key] = len(run.targets)
    assert len(run.targets) == 3,(key,run.targets)
output = Path(__file__).resolve().parents[1]/'output'/'gameplay-validation'/'scene-targets.json'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
