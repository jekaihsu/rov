"""Load authored Chenjiao snag capsules in the same baked frame as its visual and distance field."""

import json
from pathlib import Path

from .world import SnagFeature


def snag_features(wreck):
    path = Path(__file__).with_name("assets") / "wreck_chenjiao_snags.json"
    features = json.loads(path.read_text(encoding="utf-8"))
    return [
        SnagFeature(
            f["name"],
            tuple(wreck.world_point(f["point"])),
            f["radius"],
            f["height"],
            hold_n=tuple(f["hold_n"]),
            item=f["item"],
            embedded=True,
        )
        for f in features
        if f["point"][2] > 1.3
    ]
