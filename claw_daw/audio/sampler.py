from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

from claw_daw.model.types import Note, Project, Track
from claw_daw.util.drumkit import expand_role_notes


def _midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


@dataclass(frozen=True)
class SamplerRenderResult:
    # interleaved stereo float32-ish in [-1,1]
    left: list[float]
    right: list[float]
    sample_rate: int


def _ensure_len(buf: list[float], n: int) -> None:
    if len(buf) < n:
        buf.extend([0.0] * (n - len(buf)))


def _add(buf: list[float], idx: int, value: float) -> None:
    if 0 <= idx < len(buf):
        buf[idx] += value


def _softclip(x: float, drive: float = 1.0) -> float:
    # deterministic soft clip
    return math.tanh(x * drive)


def _render_drums(track: Track, *, project: Project, sample_rate: int) -> SamplerRenderResult:
    # Minimal deterministic synthesized kit.
    # GM-ish mapping used in the demo: 36 kick, 38 snare, 42 closed hat.
    length_ticks = 0
    notes = track.notes
    if track.clips and track.patterns:
        # Flatten arrangement to linear notes in ticks.
        notes = []
        for clip in track.clips:
            pat = track.patterns.get(clip.pattern)
            if not pat:
                continue
            for rep in range(clip.repeats):
                base = clip.start + rep * pat.length
                for n in pat.notes:
                    notes.append(
                        Note(
                            start=base + n.start,
                            duration=n.duration,
                            pitch=n.pitch,
                            velocity=n.velocity,
                            chance=getattr(n, "chance", 1.0),
                            mute=getattr(n, "mute", False),
                            accent=getattr(n, "accent", 1.0),
                            glide_ticks=getattr(n, "glide_ticks", 0),
                        )
                    )

    # Expand role-based drum notes via the selected kit.
    notes = expand_role_notes(notes, track=track)

    for n in notes:
        length_ticks = max(length_ticks, n.end)

    sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
    total_samps = int(math.ceil(length_ticks * sec_per_tick * sample_rate)) + sample_rate  # tail

    L: list[float] = [0.0] * total_samps
    R: list[float] = [0.0] * total_samps

    for n in notes:
        if getattr(n, "mute", False):
            continue
        chance = float(getattr(n, "chance", 1.0) or 1.0)
        if chance < 1.0:
            r = (int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF
            if Random(r).random() > chance:
                continue

        start_s = int(n.start * sec_per_tick * sample_rate)
        vel = (n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity) / 127.0

        if n.pitch == 36:  # kick
            dur = int(0.20 * sample_rate)
            for i in range(dur):
                t = i / sample_rate
                # decaying sine from 90->40 Hz
                f = 90.0 * (0.5 ** (t * 6)) + 40.0
                env = math.exp(-t * 16)
                s = math.sin(2 * math.pi * f * t) * env * vel * 0.9
                _add(L, start_s + i, s)
                _add(R, start_s + i, s)

        elif n.pitch == 38:  # snare
            dur = int(0.18 * sample_rate)
            for i in range(dur):
                t = i / sample_rate
                # noise + tone
                env = math.exp(-t * 22)
                noise = (math.sin(2 * math.pi * 1800 * t) + math.sin(2 * math.pi * 3300 * t)) * 0.15
                tone = math.sin(2 * math.pi * 220 * t) * 0.2
                s = (noise + tone) * env * vel
                _add(L, start_s + i, s)
                _add(R, start_s + i, s)

        elif n.pitch in {42, 44, 46}:  # hats
            dur = int(0.07 * sample_rate)
            for i in range(dur):
                t = i / sample_rate
                env = math.exp(-t * (55 if n.pitch == 42 else 25))
                s = math.sin(2 * math.pi * 8000 * t) * 0.15 * env * vel
                _add(L, start_s + i, s)
                _add(R, start_s + i, s)
        else:
            # fallback click
            _add(L, start_s, 0.2 * vel)
            _add(R, start_s, 0.2 * vel)

    return SamplerRenderResult(left=L, right=R, sample_rate=sample_rate)


def _render_808(track: Track, *, project: Project, sample_rate: int, glide_ticks: int = 0, preset: str = "default") -> SamplerRenderResult:
    # Sine-based bass with optional portamento/glide.
    # Presets tweak harmonics/drive (still deterministic).
    notes = track.notes
    if track.clips and track.patterns:
        notes = []
        for clip in track.clips:
            pat = track.patterns.get(clip.pattern)
            if not pat:
                continue
            for rep in range(clip.repeats):
                base = clip.start + rep * pat.length
                for n in pat.notes:
                    notes.append(
                        Note(
                            start=base + n.start,
                            duration=n.duration,
                            pitch=n.pitch,
                            velocity=n.velocity,
                            chance=getattr(n, "chance", 1.0),
                            mute=getattr(n, "mute", False),
                            accent=getattr(n, "accent", 1.0),
                            glide_ticks=getattr(n, "glide_ticks", 0),
                        )
                    )

    notes = sorted(notes, key=lambda n: n.start)
    length_ticks = max([0] + [n.end for n in notes])

    sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
    total_samps = int(math.ceil(length_ticks * sec_per_tick * sample_rate)) + int(0.5 * sample_rate)

    L: list[float] = [0.0] * total_samps
    R: list[float] = [0.0] * total_samps

    glide_s_track = max(0.0, glide_ticks * sec_per_tick)

    # Preset shaping (deterministic).
    preset = (preset or "default").strip().lower()
    if preset in {"default", "clean"}:
        harm2, harm3, drive = 0.10, 0.04, 1.15
    elif preset in {"dist", "dirty"}:
        harm2, harm3, drive = 0.22, 0.10, 1.75
    elif preset in {"growl", "grit"}:
        harm2, harm3, drive = 0.18, 0.18, 1.55
    else:
        harm2, harm3, drive = 0.10, 0.04, 1.15

    # Render monophonic: later note steals pitch; glide ramps.
    # IMPORTANT: keep phase continuous across notes and apply a short release fade-out
    # to avoid audible clicks/crackles at note boundaries.
    phase = 0.0
    rel_s = 0.008  # 8ms release

    for idx, n in enumerate(notes):
        if getattr(n, "mute", False):
            continue
        chance = float(getattr(n, "chance", 1.0) or 1.0)
        if chance < 1.0:
            # stable per-note RNG key
            r = (int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF
            if Random(r).random() > chance:
                continue

        start_s = int(n.start * sec_per_tick * sample_rate)
        end_s = int(n.end * sec_per_tick * sample_rate)
        dur = max(0, end_s - start_s)
        vel = (n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity) / 127.0

        f0 = _midi_to_hz(n.pitch)
        f_prev = f0
        if idx > 0:
            f_prev = _midi_to_hz(notes[idx - 1].pitch)

        glide_s = glide_s_track
        # note-level glide override (sampler-only)
        nt = int(getattr(n, "glide_ticks", 0) or 0)
        if nt > 0:
            glide_s = max(0.0, nt * sec_per_tick)

        rel_n = max(1, int(rel_s * sample_rate))

        for i in range(dur):
            t = i / sample_rate
            # pitch glide at the start of the note
            if glide_s > 0 and t < glide_s:
                a = t / glide_s
                f = f_prev * (1 - a) + f0 * a
            else:
                f = f0

            # amp envelope: fast attack, medium decay, short release at end.
            env = min(1.0, t / 0.005) * math.exp(-t * 1.7)
            if dur - i <= rel_n:
                env *= max(0.0, (dur - i) / rel_n)

            phase += 2 * math.pi * f / sample_rate
            base = math.sin(phase)
            # add harmonics for translation; softclip for drive
            x = base + harm2 * math.sin(2 * phase) + harm3 * math.sin(3 * phase)
            s = _softclip(x, drive=drive) * env * vel * 0.9
            _add(L, start_s + i, s)
            _add(R, start_s + i, s)

    return SamplerRenderResult(left=L, right=R, sample_rate=sample_rate)


def render_sampler_track(track: Track, *, project: Project, sample_rate: int) -> SamplerRenderResult:
    preset = str(getattr(track, "sampler_preset", "default") or "default").strip().lower()

    if track.sampler == "drums":
        return _render_drums(track, project=project, sample_rate=sample_rate)

    if track.sampler == "808":
        glide = int(getattr(track, "glide_ticks", 0) or 0)
        # preset is interpreted inside the synth loop for harmonics/drive.
        return _render_808(track, project=project, sample_rate=sample_rate, glide_ticks=glide, preset=preset)

    raise ValueError(f"unknown sampler mode: {track.sampler}")
