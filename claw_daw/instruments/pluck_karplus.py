from __future__ import annotations

import math
from pathlib import Path

from claw_daw.audio.wav import write_wav_stereo
from claw_daw.instruments.base import (
    InstrumentBase,
    apply_limiter,
    clamp,
    limit_polyphony,
    midi_to_hz,
    param_float,
    param_int,
    softclip,
)
from claw_daw.model.types import Note, Project


class PluckKarplusInstrument(InstrumentBase):
    id = "pluck.karplus"

    def presets(self) -> dict[str, dict[str, float | str]]:
        return {
            "default": {"tone": 0.6, "decay": 0.35, "drive": 1.1, "width": 0.8, "polyphony": 8},
            "guitarish": {"tone": 0.7, "decay": 0.45, "drive": 1.05, "width": 0.7, "polyphony": 8},
            "koto_dark": {"tone": 0.4, "decay": 0.28, "drive": 1.1, "width": 0.9, "polyphony": 8},
            "short_bell": {"tone": 0.9, "decay": 0.2, "drive": 1.2, "width": 0.6, "polyphony": 6},
            "dark_pluck": {"tone": 0.45, "decay": 0.3, "drive": 1.15, "width": 0.75, "polyphony": 6},
        }

    def render(self, project: Project, track_index: int, notes: list[Note], out_wav: str, sr: int) -> None:
        spec = self._spec(project, track_index)
        params = self._resolve_params(spec.preset, spec.params)

        tone = clamp(param_float(params, "tone", 0.6, 0.0, 1.0), 0.0, 1.0)
        decay = clamp(param_float(params, "decay", 0.35, 0.05, 1.0), 0.05, 1.0)
        drive = max(0.5, param_float(params, "drive", 1.1, 0.1, 4.0))
        width = clamp(param_float(params, "width", 0.8, 0.0, 1.0), 0.0, 1.0)
        max_poly = param_int(params, "polyphony", 8, 1, 16)

        notes = limit_polyphony(notes, max_poly)
        if not notes:
            write_wav_stereo(Path(out_wav), [0.0] * (sr // 2), [0.0] * (sr // 2), sample_rate=sr)
            return

        sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
        length_ticks = max([0] + [n.end for n in notes])
        tail_s = 0.25 + decay * 0.25
        total_samps = int(math.ceil(length_ticks * sec_per_tick * sr)) + int(tail_s * sr) + 1

        left: list[float] = [0.0] * total_samps
        right: list[float] = [0.0] * total_samps

        base_seed = int(spec.seed) + int(track_index) * 9176
        attack_s = max(1, int(0.003 * sr))
        release_s = max(1, int(0.01 * sr))

        for n in notes:
            start_s = int(n.start * sec_per_tick * sr)
            dur_s = max(1, int(n.duration * sec_per_tick * sr))
            rel_s = release_s
            total = dur_s + rel_s

            vel = (n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity) / 127.0

            rng = self._note_rng(base_seed, n)
            f0 = midi_to_hz(n.pitch)
            buf_len = max(2, int(sr / max(1.0, f0)))
            buf = [rng.uniform(-1.0, 1.0) for _ in range(buf_len)]
            idx = 0

            damp = 0.90 + decay * 0.08
            avg = 0.45 + tone * 0.30
            pan = (rng.random() * 2.0 - 1.0) * width

            for i in range(total):
                y = avg * (buf[idx] + buf[(idx + 1) % buf_len])
                buf[idx] = y * damp
                idx = (idx + 1) % buf_len

                if i < attack_s:
                    env = i / attack_s
                elif i < dur_s:
                    env = 1.0
                else:
                    env = max(0.0, 1.0 - (i - dur_s) / max(1, rel_s))

                s = softclip(y, drive=drive) * env * vel * 0.9

                angle = (pan + 1.0) * 0.25 * math.pi
                l = s * math.cos(angle)
                r = s * math.sin(angle)

                idx_s = start_s + i
                if idx_s >= total_samps:
                    break
                left[idx_s] += l
                right[idx_s] += r

        apply_limiter(left, right, limit=0.98)
        write_wav_stereo(Path(out_wav), left, right, sample_rate=sr)
