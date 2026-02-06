from __future__ import annotations

from claw_daw.audio.stems import _group_tracks_by_bus
from claw_daw.model.types import Project, Track


def _make_project() -> Project:
    p = Project(name="bus_test", tempo_bpm=120)
    p.tracks = [
        Track(name="Kick", channel=9, program=0),
        Track(name="Sub", channel=0, program=38),
        Track(name="Pad", channel=1, program=89),
    ]
    return p


def test_group_tracks_by_bus_respects_explicit_bus_assignments() -> None:
    p = _make_project()
    p.tracks[0].bus = "drums"
    p.tracks[1].bus = "bass"
    p.tracks[2].bus = "music"

    groups = _group_tracks_by_bus(p)
    assert groups == {"drums": [0], "bass": [1], "music": [2]}


def test_group_tracks_by_bus_uses_heuristics_for_default_bus() -> None:
    p = _make_project()
    # Default bus is "music"; grouping should still infer obvious drum/bass names.
    p.tracks[0].name = "Drums Main"
    p.tracks[1].name = "808 Sub"
    p.tracks[2].name = "Lead"

    groups = _group_tracks_by_bus(p)
    assert groups["drums"] == [0]
    assert groups["bass"] == [1]
    assert groups["music"] == [2]
