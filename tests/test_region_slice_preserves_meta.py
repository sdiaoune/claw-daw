from __future__ import annotations

from claw_daw.arrange.types import Clip, Pattern
from claw_daw.model.types import InstrumentSpec, Note, Project, SamplePackSpec, Track
from claw_daw.util.region import slice_project_range


def test_slice_project_range_preserves_track_meta() -> None:
    proj = Project(name="SliceMeta", tempo_bpm=120, ppq=480)

    drums = Track(name="Drums", channel=0, sampler="drums")
    drums.sample_pack = SamplePackSpec(id="pack1", path="/tmp/pack", seed=3, gain_db=-1.0)
    drums.sampler_preset = "clean"
    drums.drum_kit = "house_clean"
    drums.bus = "drums"
    drums.humanize_timing = 3
    drums.humanize_velocity = 5
    drums.humanize_seed = 9
    drums.glide_ticks = 2

    pat = Pattern(name="main", length=480)
    pat.notes = [
        Note(
            start=0,
            duration=120,
            pitch=36,
            velocity=100,
            role="kick",
            chance=0.5,
            mute=False,
            accent=1.1,
            glide_ticks=2,
        )
    ]
    drums.patterns["main"] = pat
    drums.clips = [Clip(pattern="main", start=0, repeats=2)]
    proj.tracks.append(drums)

    lead = Track(name="Lead", channel=1)
    lead.instrument = InstrumentSpec(id="synth.basic", preset="sub", params={"tone": 0.5}, seed=7)
    lead.notes = [Note(start=0, duration=240, pitch=60, velocity=100)]
    proj.tracks.append(lead)

    out = slice_project_range(proj, 0, 480)

    out_drums = out.tracks[0]
    assert out_drums.sampler == "drums"
    assert out_drums.sample_pack is not None
    assert out_drums.sample_pack.id == "pack1"
    assert out_drums.sample_pack.path == "/tmp/pack"
    assert out_drums.sample_pack.seed == 3
    assert out_drums.sample_pack.gain_db == -1.0
    assert out_drums.sampler_preset == "clean"
    assert out_drums.drum_kit == "house_clean"
    assert out_drums.bus == "drums"
    assert out_drums.humanize_timing == 3
    assert out_drums.humanize_velocity == 5
    assert out_drums.humanize_seed == 9
    assert out_drums.glide_ticks == 2
    assert out_drums.patterns == {}
    assert out_drums.clips == []
    assert out_drums.notes
    n = out_drums.notes[0]
    assert n.role == "kick"
    assert n.chance == 0.5
    assert n.accent == 1.1
    assert n.glide_ticks == 2

    out_lead = out.tracks[1]
    assert out_lead.instrument is not None
    assert out_lead.instrument.id == "synth.basic"
    assert out_lead.instrument.preset == "sub"
    assert out_lead.instrument.params.get("tone") == 0.5
    assert out_lead.instrument.seed == 7
