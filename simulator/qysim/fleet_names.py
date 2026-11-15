"""Player-facing names of the YX fleet and named sites (docs/design/game-plan.md §10).

Server-side counterpart of ``viewer/fleet_names.js``: use it for any text a player reads that names a
vehicle or a named site (scenario titles, contract messages, menu catalogue export). Internal model ids,
``VehicleDefinition.name`` (the developer/SDK identity of the simulated vehicle), saves and protocol fields
are unchanged. Keep both files in step.
"""

VEHICLE_NAMES = {
    "x1": "YX Model R",
    "bluerov2_heavy": "YX Model O",
    "falcon": "YX Model V",
}

VEHICLE_ROLES = {
    "x1": "入門觀測型",
    "bluerov2_heavy": "重載觀測型",
    "falcon": "輕作業型",
}

# Fictional name of the korean_castle wreck; the scenario key stays ``korean_castle``.
WRECK_NAME = "碧海號"


def vehicle_name(model_id):
    """Display name for a model id; unknown ids fall back to the id itself."""
    return VEHICLE_NAMES.get(model_id, str(model_id))


def vehicle_role(model_id):
    """Short role line for a model id, or an empty string."""
    return VEHICLE_ROLES.get(model_id, "")
