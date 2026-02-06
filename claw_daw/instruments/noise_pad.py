from __future__ import annotations

import math
from pathlib import Path

from claw_daw.audio.wav import write_wav_stereo
from claw_daw.instruments.base import (
    InstrumentBase,
    apply_limiter,
    clamp,
    limit_polyphony,
    param_float,
    param_int,
    softclip,
)
from claw_daw.model.types import Note, Project


class NoisePadInstrument(InstrumentBase):
    id = "noise.pad"

    def presets(self) -> dict[str, dict[str, float | str]]:
        return {
            "default": {"attack": 0.6, "decay": 0.6, "sustain": 0.7, "release": 0.8, "tone": 0.4, "drive": 1.05, "width": 0.9, "polyphony": 6},
            "air_pad": {"attack": 0.7, "decay": 0.6, "sustain": 0.75, "release": 0.9, "tone": 0.55, "drive": 1.0, "width": 1.0, "polyphony": 6},
            "vinyl_hiss_pad": {"attack": 0.2, "decay": 0.5, "sustain": 0.5, "release": 0.7, "tone": 0.25, "drive": 1.1, "width": 0.8, "polyphony": 6},
            "dark_wind": {"attack": 0.9, "decay": 0.7, "sustain": 0.6, "release": 1.1, "tone": 0.2, "drive": 1.05, "width": 1.1, "polyphony": 5},
        }

    def render(self, project: Project, track_index: int, notes: list[Note], out_wav: str, sr: int) -> None:
        spec = self._spec(project, track_index)
        params = self._resolve_params(spec.preset, spec.params)

        attack = max(0.01, param_float(params, "attack", 0.6, 0.0, 5.0))
        decay = max(0.0, param_float(params, "decay", 0.6, 0.0, 5.0))
        sustain = clamp(param_float(params, "sustain", 0.7, 0.0, 1.0), 0.0, 1.0)
        release = max(0.02, param_float(params, "release", 0.8, 0.0, 8.0))
        tone = clamp(param_float(params, "tone", 0.4, 0.0, 1.0), 0.0, 1.0)
        drive = max(0.5, param_float(params, "drive", 1.05, 0.1, 3.0))
        width = clamp(param_float(params, "width", 0.9, 0.0, 1.5), 0.0, 1.5)
        max_poly = param_int(params, "polyphony", 6, 1, 12)

        notes = limit_polyphony(notes, max_poly)
        if not notes:
            write_wav_stereo(Path(out_wav), [0.0] * (sr // 2), [0.0] * (sr // 2), sample_rate=sr)
            return

        sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
        length_ticks = max([0] + [n.end for n in notes])
        total_samps = int(math.ceil(length_ticks * sec_per_tick * sr)) + int(release * sr) + 1

        left: list[float] = [0.0] * total_samps
        right: list[float] = [0.0] * total_samps

        base_seed = int(spec.seed) + int(track_index) * 9176
        cutoff = 200.0 + (tone**2) * 9000.0
        cutoff = clamp(cutoff, 120.0, sr * 0.45)
        alpha = min(1.0, 2.0 * math.pi * cutoff / sr)

        for n in notes:
            start_s = int(n.start * sec_per_tick * sr)
            dur_s = max(1, int(n.duration * sec_per_tick * sr))
            rel_s = max(1, int(release * sr))
            total = dur_s + rel_s

            atk_s = max(1, int(attack * sr))
            dec_s = max(1, int(decay * sr)) if decay > 0 else 0
            if dur_s < atk_s + dec_s:
                scale = dur_s / max(1, (atk_s + dec_s))
                atk_s = max(1, int(atk_s * scale))
                dec_s = max(0, dur_s - atk_s)

            vel = (n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity) / 127.0

            rng = self._note_rng(base_seed, n)
            rng_l = self._note_rng(base_seed + 17, n)
            rng_r = self._note_rng(base_seed + 29, n)
            lp_l = 0.0
            lp_r = 0.0

            for i in range(total):
                if i < atk_s:
                    env = i / atk_s
                elif i < atk_s + dec_s:
                    env = 1.0 - (1.0 - sustain) * ((i - atk_s) / max(1, dec_s))
                elif i < dur_s:
                    env = sustain
                else:
                    env = sustain * max(0.0, 1.0 - (i - dur_s) / max(1, rel_s))

                mono = rng.uniform(-1.0, 1.0)
                nl = rng_l.uniform(-1.0, 1.0)
                nr = rng_r.uniform(-1.0, 1.0)
                w = clamp(width, 0.0, 1.0)
                s_l = mono * (1.0 - w) + nl * w
                s_r = mono * (1.0 - w) + nr * w

                lp_l = lp_l + alpha * (s_l - lp_l)
                lp_r = lp_r + alpha * (s_r - lp_r)

                s_l = softclip(lp_l, drive=drive) * env * vel * 0.5
                s_r = softclip(lp_r, drive=drive) * env * vel * 0.5

                idx = start_s + i
                if idx >= total_samps:
                    break
                left[idx] += s_l
                right[idx] += s_r

        apply_limiter(left, right, limit=0.98)
        write_wav_stereo(Path(out_wav), left, right, sample_rate=sr)
