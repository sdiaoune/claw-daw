from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from claw_daw.audio.sampler import render_sampler_track
from claw_daw.audio.wav import write_wav_stereo
from claw_daw.io.midi import export_midi
from claw_daw.model.types import Project
from claw_daw.util.notes import apply_note_chance, flatten_track_notes, note_seed_base


def render_project_wav(
    project: Project,
    *,
    soundfont: str,
    out_wav: str,
    sample_rate: int = 44100,
    drum_mode: str = "gm",  # gm|auto|sampler
    mix: dict | None = None,
) -> str:
    """Render a project to a stereo WAV.

    If mix is provided (or project.mix is set), we render per-track stems then mix via ffmpeg
    to enable deterministic sound-engineering FX (EQ, dynamics, sidechain, sends, stereo tools).

    - Native instrument tracks (track.instrument) are rendered in-process.
    - Sampler tracks (track.sampler in {drums,808}) are synthesized in-process.
      If a sample pack is set on a drums track, we render WAV samples instead of the built-in synth kit.
    - All other tracks are rendered via FluidSynth.

    drum_mode:
      - "gm" (default): ALWAYS convert sampler drums to plain GM drums (MIDI channel 10) and render via FluidSynth.
        This is the most reliable option across SoundFonts and avoids crackly sampler drum renders.
      - "auto": render a short preview in both modes and pick the more reliable one.
      - "sampler": keep sampler drums as-is (opt-in; may crackle depending on environment).

    The goal is correctness + determinism for an offline MVP, not real-time.
    """

    from claw_daw.audio.drum_render_sanity import choose_drum_render_mode, convert_sampler_drums_to_gm

    # Optional mix engine (slow path).
    eff_mix = mix or getattr(project, "mix", None)
    if eff_mix:
        from claw_daw.audio.mix_engine import MixSpec, mix_project_wav

        return mix_project_wav(project, soundfont=soundfont, out_wav=out_wav, sample_rate=sample_rate, mix=MixSpec.from_dict(eff_mix))

    has_sample_pack = any(getattr(t, "sample_pack", None) is not None for t in project.tracks)
    if has_sample_pack and drum_mode == "gm":
        drum_mode = "sampler"

    outp = Path(out_wav).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)

    # Optional: auto-fallback for crackly sampler drums.
    if drum_mode not in {"auto", "sampler", "gm"}:
        raise ValueError("drum_mode must be: gm|auto|sampler")

    # We choose mode up front so the rest of the render logic stays simple.
    if drum_mode == "gm":
        project = convert_sampler_drums_to_gm(project)
    elif drum_mode == "auto":
        # Render small previews w/o recursion/auto.
        with tempfile.TemporaryDirectory(prefix="claw_daw_drum_preview_") as td2:
            t2 = Path(td2)
            n = 0

            def _render_preview_wav(p: Project) -> str:
                nonlocal n
                out_prev = t2 / f"preview_{n}.wav"
                n += 1
                render_project_wav(p, soundfont=soundfont, out_wav=str(out_prev), sample_rate=sample_rate, drum_mode="sampler")
                return str(out_prev)

            mode, _dbg = choose_drum_render_mode(
                project=project,
                render_preview_wav=_render_preview_wav,
                preview_bars=8,
                threshold_db=6.0,
            )

        if mode == "gm":
            project = convert_sampler_drums_to_gm(project)

    with tempfile.TemporaryDirectory(prefix="claw_daw_render_") as td:
        tdir = Path(td)

        def _active_tracks(p: Project) -> set[int]:
            soloed = {i for i, t in enumerate(p.tracks) if t.solo}
            if soloed:
                return soloed
            return {i for i, t in enumerate(p.tracks) if not t.mute}

        active = _active_tracks(project)

        # 1) Render non-sampler tracks with FluidSynth (respect mute/solo).
        allowed: set[int] = set()
        for i, t in enumerate(project.tracks):
            if i not in active:
                continue
            if getattr(t, "sampler", None) is None and getattr(t, "instrument", None) is None:
                allowed.add(i)

        midi_path = tdir / "proj.mid"
        export_midi(project, midi_path, allowed_tracks=allowed)

        fs_wav = tdir / "fluidsynth.wav"
        if allowed:
            cmd = [
                "fluidsynth",
                "-ni",
                "-F",
                str(fs_wav),
                "-r",
                str(int(sample_rate)),
                str(Path(soundfont).expanduser()),
                str(midi_path),
            ]
            subprocess.run(cmd, check=True)
        else:
            # empty placeholder
            write_wav_stereo(fs_wav, [0.0] * (sample_rate // 2), [0.0] * (sample_rate // 2), sample_rate=sample_rate)

        # 2) Render sampler tracks and write individual wavs.
        sampler_wavs: list[Path] = []
        for i, t in enumerate(project.tracks):
            if i not in active:
                continue
            if getattr(t, "instrument", None) is not None:
                continue
            if getattr(t, "sampler", None) is None:
                continue
            res = render_sampler_track(t, project=project, sample_rate=sample_rate, track_index=i)
            w = tdir / f"sampler_{i}.wav"
            write_wav_stereo(w, res.left, res.right, sample_rate=sample_rate)
            sampler_wavs.append(w)

        # 3) Render native instrument tracks (offline plugins).
        instrument_wavs: list[Path] = []
        for i, t in enumerate(project.tracks):
            if i not in active:
                continue
            spec = getattr(t, "instrument", None)
            if spec is None:
                continue
            from claw_daw.instruments.registry import get_instrument

            inst = get_instrument(getattr(spec, "id", "") or "")
            if inst is None:
                raise ValueError(f"unknown instrument id: {getattr(spec, 'id', '')}")
            notes = flatten_track_notes(project, i, t, ppq=project.ppq, swing_percent=project.swing_percent)
            notes = apply_note_chance(notes, seed_base=note_seed_base(t, i))
            w = tdir / f"instrument_{i}.wav"
            if not notes:
                write_wav_stereo(w, [0.0] * (sample_rate // 2), [0.0] * (sample_rate // 2), sample_rate=sample_rate)
            else:
                inst.render(project, i, notes, str(w), sample_rate)
            instrument_wavs.append(w)

        # 4) Mix everything with ffmpeg (more robust than our own i16 summing).
        inputs = [fs_wav] + sampler_wavs + instrument_wavs
        if len(inputs) == 1:
            Path(fs_wav).replace(outp)
            return str(outp)

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for inp in inputs:
            cmd += ["-i", str(inp)]

        # amix then normalize to avoid clipping.
        cmd += [
            "-filter_complex",
            f"amix=inputs={len(inputs)}:normalize=0,alimiter=limit=0.98",
            "-ar",
            str(int(sample_rate)),
            str(outp),
        ]
        subprocess.run(cmd, check=True)
        return str(outp)
