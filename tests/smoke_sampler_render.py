from __future__ import annotations

from pathlib import Path

from claw_daw.audio.render import render_project_wav
from claw_daw.model.types import Note, Project, Track


def main() -> None:
    sf = Path(__file__).resolve().parent.parent / "soundfonts" / "GeneralUser-GS-v1.471.sf2"
    if not sf.exists():
        raise SystemExit(f"soundfont missing: {sf}")

    p = Project(name="smoke_sampler", tempo_bpm=140)

    drums = Track(name="Drums", channel=0, sampler="drums")
    # 1 bar hats + kick + snare
    ppq = p.ppq
    step = ppq // 4
    for i in range(8):
        drums.notes.append(Note(start=i * step, duration=step // 2, pitch=42, velocity=70))
    drums.notes.append(Note(start=0, duration=step, pitch=36, velocity=120))
    drums.notes.append(Note(start=4 * step, duration=step, pitch=38, velocity=115))

    bass = Track(name="808", channel=1, sampler="808")
    bass.notes.append(Note(start=0, duration=ppq * 2, pitch=36, velocity=120))
    bass.notes.append(Note(start=ppq * 2, duration=ppq * 2, pitch=34, velocity=120))

    keys = Track(name="Keys", channel=2, program=4)
    keys.notes.append(Note(start=0, duration=ppq * 4, pitch=65, velocity=55))
    keys.notes.append(Note(start=0, duration=ppq * 4, pitch=68, velocity=55))
    keys.notes.append(Note(start=0, duration=ppq * 4, pitch=72, velocity=55))

    p.tracks = [drums, bass, keys]

    out = Path("tmp_export") / "smoke_sampler_mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_project_wav(p, soundfont=str(sf), out_wav=str(out), sample_rate=44100)

    if not out.exists() or out.stat().st_size < 10_000:
        raise SystemExit("render failed: output wav missing or too small")

    print(f"OK: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
