from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

from claw_daw.audio.sampler import render_sampler_track
from claw_daw.io.midi import export_midi
from claw_daw.model.types import Project


def _write_wav_stereo(path: Path, left: list[float], right: list[float], *, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(len(left), len(right))
    if len(left) < n:
        left = left + [0.0] * (n - len(left))
    if len(right) < n:
        right = right + [0.0] * (n - len(right))

    # hard clip
    def _i16(x: float) -> int:
        v = max(-1.0, min(1.0, float(x)))
        return int(v * 32767.0)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        frames = bytearray()
        for i in range(n):
            frames += int.to_bytes(_i16(left[i]), 2, "little", signed=True)
            frames += int.to_bytes(_i16(right[i]), 2, "little", signed=True)
        wf.writeframes(bytes(frames))


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

    - Sampler tracks (track.sampler in {drums,808}) are synthesized in-process.
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

        # 1) Render non-sampler tracks with FluidSynth.
        allowed: set[int] = set()
        for i, t in enumerate(project.tracks):
            if getattr(t, "sampler", None) is None:
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
            _write_wav_stereo(fs_wav, [0.0] * (sample_rate // 2), [0.0] * (sample_rate // 2), sample_rate=sample_rate)

        # 2) Render sampler tracks and write individual wavs.
        sampler_wavs: list[Path] = []
        for i, t in enumerate(project.tracks):
            if getattr(t, "sampler", None) is None:
                continue
            res = render_sampler_track(t, project=project, sample_rate=sample_rate)
            w = tdir / f"sampler_{i}.wav"
            _write_wav_stereo(w, res.left, res.right, sample_rate=sample_rate)
            sampler_wavs.append(w)

        # 3) Mix everything with ffmpeg (more robust than our own i16 summing).
        inputs = [fs_wav] + sampler_wavs
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
