from __future__ import annotations

from claw_daw.audio.drum_render_sanity import convert_sampler_drums_to_gm
from claw_daw.model.types import Note, Pattern, Project, Track


def test_render_default_is_gm_mode_docstring_contract() -> None:
    # This is a light guard: default behavior should be to prefer GM for reliability.
    # (We don't render audio in unit tests.)
    import inspect
    from claw_daw.audio.render import render_project_wav

    sig = inspect.signature(render_project_wav)
    assert sig.parameters["drum_mode"].default == "gm"


def test_convert_sampler_drums_to_gm_sets_channel_and_disables_sampler() -> None:
    dr = Track(name="Drums", channel=0, sampler="drums", drum_kit="house_clean")
    dr.patterns["p1"] = Pattern(
        name="p1",
        length=1920,
        notes=[
            Note(start=0, duration=120, pitch=0, velocity=100, role="kick"),
            Note(start=480, duration=120, pitch=0, velocity=90, role="snare"),
            Note(start=240, duration=60, pitch=0, velocity=70, role="hh"),
        ],
    )
    p = Project(name="x", tempo_bpm=120, ppq=480, tracks=[dr])

    p2 = convert_sampler_drums_to_gm(p)
    d2 = p2.tracks[0]
    assert d2.sampler is None
    assert d2.channel == 9
    assert d2.program == 0

    # Notes should be pitch-based, not role-based.
    notes = p2.tracks[0].patterns["p1"].notes
    assert all(n.role is None for n in notes)
    assert all(0 <= int(n.pitch) <= 127 and int(n.pitch) != 0 for n in notes)
