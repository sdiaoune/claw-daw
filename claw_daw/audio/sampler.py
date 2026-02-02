from __future__ import annotations

import math
from dataclasses import dataclass

from claw_daw.model.types import Note, Project, Track


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
                    notes.append(Note(start=base + n.start, duration=n.duration, pitch=n.pitch, velocity=n.velocity))

    for n in notes:
        length_ticks = max(length_ticks, n.end)

    sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
    total_samps = int(math.ceil(length_ticks * sec_per_tick * sample_rate)) + sample_rate  # tail

    L: list[float] = [0.0] * total_samps
    R: list[float] = [0.0] * total_samps

    for n in notes:
        start_s = int(n.start * sec_per_tick * sample_rate)
        vel = n.velocity / 127.0

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


def _render_808(track: Track, *, project: Project, sample_rate: int, glide_ticks: int = 0) -> SamplerRenderResult:
    # Sine-based bass with optional portamento/glide.
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
                    notes.append(Note(start=base + n.start, duration=n.duration, pitch=n.pitch, velocity=n.velocity))

    notes = sorted(notes, key=lambda n: n.start)
    length_ticks = max([0] + [n.end for n in notes])

    sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
    total_samps = int(math.ceil(length_ticks * sec_per_tick * sample_rate)) + int(0.5 * sample_rate)

    L: list[float] = [0.0] * total_samps
    R: list[float] = [0.0] * total_samps

    glide_s = max(0.0, glide_ticks * sec_per_tick)

    # Render monophonic: later note steals pitch; glide ramps.
    for idx, n in enumerate(notes):
        start_s = int(n.start * sec_per_tick * sample_rate)
        end_s = int(n.end * sec_per_tick * sample_rate)
        vel = n.velocity / 127.0

        f0 = _midi_to_hz(n.pitch)
        f_prev = f0
        if idx > 0:
            f_prev = _midi_to_hz(notes[idx - 1].pitch)

        phase = 0.0
        for i in range(max(0, end_s - start_s)):
            t = i / sample_rate
            # pitch glide at the start of the note
            if glide_s > 0 and t < glide_s:
                a = t / glide_s
                f = f_prev * (1 - a) + f0 * a
            else:
                f = f0

            # simple amp envelope (fast attack, medium decay)
            env = min(1.0, t / 0.005) * math.exp(-t * 1.7)

            phase += 2 * math.pi * f / sample_rate
            s = math.sin(phase) * env * vel * 0.9
            _add(L, start_s + i, s)
            _add(R, start_s + i, s)

    return SamplerRenderResult(left=L, right=R, sample_rate=sample_rate)


def render_sampler_track(track: Track, *, project: Project, sample_rate: int) -> SamplerRenderResult:
    if track.sampler == "drums":
        return _render_drums(track, project=project, sample_rate=sample_rate)
    if track.sampler == "808":
        glide = int(getattr(track, "glide_ticks", 0) or 0)
        return _render_808(track, project=project, sample_rate=sample_rate, glide_ticks=glide)
    raise ValueError(f"unknown sampler mode: {track.sampler}")
