"""Export lightweight, reproducible scene descriptions for the offline menu."""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from qysim.engine import Simulator
from qysim.scenarios import catalogue
from qysim.server import _json_default
scenes=[]
for item in catalogue():
    sim=Simulator(item['key'],42)
    scenes.append({**item,'world':sim.world_description()})
(root/'viewer/scene_previews.json').write_text(json.dumps(scenes,default=_json_default,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print('Exported',len(scenes),'menu scene previews')
