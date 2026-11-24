"""Career data (viewer/career/*.json) validates against its JSON schemas and points at real scenes and chapters.

The YX work orders run on existing scenarios; a chapter whose scene is not in this build (chapter 2's
aquaculture_pen while it is being built) must declare that scene so the board can hide it.
"""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from qysim import scenarios

ROOT = Path(__file__).resolve().parents[1]
CAREER = ROOT / "viewer" / "career"
CAMPAIGN = ROOT / "campaign"


def load(name):
    return json.loads((CAREER / name).read_text(encoding="utf-8"))


class CareerDataTest(unittest.TestCase):
    def validate(self, data_file, schema_file):
        schema = load(schema_file)
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(load(data_file)), key=lambda e: list(e.path))
        self.assertEqual([f"{list(e.path)}: {e.message}" for e in errors], [])

    def test_contracts_match_the_schema(self):
        self.validate("contracts.json", "contracts.schema.json")

    def test_equipment_and_licences_match_their_schemas(self):
        self.validate("equipment.json", "equipment.schema.json")
        self.validate("licences.json", "licences.schema.json")

    def test_cosmetic_stickers_are_accepted_by_the_server(self):
        from qysim.operations import STICKERS
        for item in load("equipment.json")["items"]:
            if item["kind"] == "cosmetic":
                self.assertIn(item["sticker"], STICKERS, item["id"])

    def test_schema_rejects_a_broken_contract(self):
        schema = load("contracts.schema.json")
        data = load("contracts.json")
        broken = dict(data["contracts"][1])
        broken["deliverables"] = [{"id": "x", "kind": "photo", "label": "no point"}]
        data["contracts"] = [broken]
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(data)))

    def test_contracts_use_existing_scenes_or_a_guarded_chapter(self):
        data = load("contracts.json")
        guarded = {chapter["id"]: chapter.get("scenario") for chapter in data["chapters"]}
        for contract in data["contracts"]:
            known = contract["scenario"] in scenarios.LIBRARY
            self.assertTrue(known or guarded.get(contract["chapter"]) == contract["scenario"], contract["id"])
            if "launchScenario" in contract:
                self.assertIn(contract["launchScenario"], scenarios.LIBRARY, contract["id"])

    def test_chapter_contracts_run_existing_story_chapters(self):
        for contract in load("contracts.json")["contracts"]:
            if contract["runtime"] != "chapter":
                continue
            script = json.loads((CAMPAIGN / f"{contract['campaignChapter']}.json").read_text(encoding="utf-8"))
            self.assertEqual(script["scenario"], contract["scenario"], contract["id"])

    def test_ids_are_unique(self):
        data = load("contracts.json")
        ids = [contract["id"] for contract in data["contracts"]]
        self.assertEqual(len(ids), len(set(ids)))
        for contract in data["contracts"]:
            deliverables = [entry["id"] for entry in contract["deliverables"]]
            self.assertEqual(len(deliverables), len(set(deliverables)), contract["id"])


class PenVariantTest(unittest.TestCase):
    """Site variants the chapter-2 work orders launch: same pen, start point and current setting only."""

    def test_variants_share_the_pen_and_lower_the_current(self):
        from qysim import chapter2 as c2
        from qysim.aquaculture import CENTER, RADIUS
        base = scenarios.build("aquaculture_pen", 0)
        for key in ("aquaculture_pen_slack", "aquaculture_pen_inside", "aquaculture_pen_escape"):
            variant = scenarios.build(key, 0)
            if key == "aquaculture_pen_inside":
                # C2-2 drops the seabed to the net floor and removes floor panels so silt jets hit fluff.
                self.assertEqual(variant.seabed_depth, c2.INSIDE_SEABED, key)
                self.assertLess(len(variant.obstacles), len(base.obstacles), key)
                self.assertFalse(any(str(o.name).startswith("pen-floor-") for o in variant.obstacles), key)
            else:
                self.assertEqual(len(variant.obstacles), len(base.obstacles), key)
                self.assertEqual(variant.seabed_depth, base.seabed_depth, key)
            if key == "aquaculture_pen_escape":
                self.assertGreater(variant.current.surface_kn, base.current.surface_kn * 0.5, key)
                self.assertIn("escape", variant.summary()["aquaculture"], key)
            else:
                self.assertLess(variant.current.surface_kn, base.current.surface_kn, key)
            self.assertIn("aquaculture", variant.summary(), key)
        inside = scenarios.build("aquaculture_pen_inside", 0)
        offset = ((inside.start_pos[0] - CENTER[0]) ** 2 + (inside.start_pos[1] - CENTER[1]) ** 2) ** .5
        self.assertLess(offset, RADIUS - 2, "the recovery dive starts inside the net")

    def test_dead_fish_exist_in_the_inside_variant(self):
        from qysim.engine import Simulator
        from qysim.operations import ensure_objects
        sim = Simulator("aquaculture_pen_inside", 0)
        kinds = {entry["kind"] for entry in ensure_objects(sim).values()}
        self.assertEqual(kinds, {"dead_fish", "collection_basket"})


if __name__ == "__main__":
    unittest.main()
