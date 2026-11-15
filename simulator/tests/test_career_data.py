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


if __name__ == "__main__":
    unittest.main()
