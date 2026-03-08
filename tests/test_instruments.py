from __future__ import annotations

from pathlib import Path

from claw_daw.audio.spectrogram import band_energy_report
from claw_daw.cli.headless import HeadlessRunner
from claw_daw.instruments.registry import get_instrument
from claw_daw.instruments.registry import list_instruments
from claw_daw.io.project_json import load_project, save_project
from claw_daw.model.types import InstrumentSpec, Note, Project, Track


def test_instrument_registry_lists_expected_ids() -> None:
    ids = {inst.id for inst in list_instruments()}
    assert "synth.basic" in ids
    assert "pluck.karplus" in ids
    assert "noise.pad" in ids


def test_instrument_round_trip_in_project_json(tmp_path: Path) -> None:
    p = Project(name="Test", tempo_bpm=120)
    t = Track(name="Lead", channel=0)
    t.instrument = InstrumentSpec(id="pluck.karplus", preset="dark_pluck", params={"tone": 0.5, "decay": 0.3}, seed=7)
    p.tracks.append(t)

    out = tmp_path / "proj.json"
    save_project(p, out)
    loaded = load_project(out)

    inst = loaded.tracks[0].instrument
    assert inst is not None
    assert inst.id == "pluck.karplus"
    assert inst.preset == "dark_pluck"
    assert inst.params.get("tone") == 0.5
    assert inst.seed == 7


def test_headless_set_instrument_clears_sampler() -> None:
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(
        [
            "new_project test 120",
            "add_track Lead 0",
            "set_sampler 0 808",
            "set_instrument 0 pluck.karplus preset=dark_pluck tone=0.55 decay=0.30 seed=7",
        ],
        base_dir=Path("."),
    )
    proj = r.require_project()
    t = proj.tracks[0]
    assert t.sampler is None
    assert t.instrument is not None
    assert t.instrument.id == "pluck.karplus"


def test_noise_pad_defaults_are_cleaner_than_explicit_hiss(tmp_path: Path) -> None:
    inst = get_instrument("noise.pad")
    assert inst is not None

    p = Project(name="pad", tempo_bpm=120)
    t = Track(name="Pad", channel=0)
    t.instrument = InstrumentSpec(id="noise.pad", preset="air_pad", seed=7)
    t.notes = [Note(start=0, duration=1920, pitch=60, velocity=100)]
    p.tracks.append(t)

    clean_wav = tmp_path / "air.wav"
    inst.render(p, 0, t.notes, str(clean_wav), 44100)
    clean_rep = band_energy_report(str(clean_wav))

    t.instrument = InstrumentSpec(id="noise.pad", preset="vinyl_hiss_pad", seed=7)
    hiss_wav = tmp_path / "hiss.wav"
    inst.render(p, 0, t.notes, str(hiss_wav), 44100)
    hiss_rep = band_energy_report(str(hiss_wav))

    clean_high = float(clean_rep["high_ge4k"]["mean_volume"])
    hiss_high = float(hiss_rep["high_ge4k"]["mean_volume"])
    assert clean_high < hiss_high - 3.0
