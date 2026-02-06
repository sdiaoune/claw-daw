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
    param_str,
    softclip,
)
from claw_daw.model.types import Note, Project


class SynthBasicInstrument(InstrumentBase):
    id = "synth.basic"

    def presets(self) -> dict[str, dict[str, float | str]]:
        return {
            "default": {"wave": "saw", "attack": 0.01, "decay": 0.18, "sustain": 0.6, "release": 0.12, "tone": 0.6, "drive": 1.2, "width": 0.8, "polyphony": 8},
            "sub": {"wave": "sine", "attack": 0.01, "decay": 0.10, "sustain": 0.7, "release": 0.12, "tone": 0.25, "drive": 1.1, "width": 0.2, "polyphony": 6},
            "dark_pluck": {"wave": "square", "attack": 0.005, "decay": 0.12, "sustain": 0.2, "release": 0.08, "tone": 0.35, "drive": 1.25, "width": 0.6, "polyphony": 6},
            "soft_pad": {"wave": "saw", "attack": 0.4, "decay": 0.6, "sustain": 0.7, "release": 0.8, "tone": 0.5, "drive": 1.05, "width": 1.2, "polyphony": 10},
            "bright_lead": {"wave": "saw", "attack": 0.01, "decay": 0.2, "sustain": 0.7, "release": 0.15, "tone": 0.9, "drive": 1.3, "width": 0.8, "polyphony": 8},
        }

    def render(self, project: Project, track_index: int, notes: list[Note], out_wav: str, sr: int) -> None:
        spec = self._spec(project, track_index)
        params = self._resolve_params(spec.preset, spec.params)

        wave = param_str(params, "wave", "saw").lower()
        attack = max(0.005, param_float(params, "attack", 0.01, 0.0, 5.0))
        decay = max(0.0, param_float(params, "decay", 0.18, 0.0, 5.0))
        sustain = clamp(param_float(params, "sustain", 0.6, 0.0, 1.0), 0.0, 1.0)
        release = max(0.005, param_float(params, "release", 0.12, 0.0, 5.0))
        tone = clamp(param_float(params, "tone", 0.6, 0.0, 1.0), 0.0, 1.0)
        drive = max(0.5, param_float(params, "drive", 1.2, 0.1, 4.0))
        width = clamp(param_float(params, "width", 0.8, 0.0, 2.0), 0.0, 2.0)
        max_poly = param_int(params, "polyphony", 8, 1, 16)

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
            phase_l = rng.random() * 2.0 * math.pi
            phase_r = rng.random() * 2.0 * math.pi

            detune_cents = width * 6.0
            detune = 2.0 ** (detune_cents / 1200.0) if detune_cents > 0 else 1.0

            f0 = midi_to_hz(n.pitch)
            inc_l = 2.0 * math.pi * f0 / sr
            inc_r = 2.0 * math.pi * f0 * detune / sr

            cutoff = params.get("cutoff_hz", params.get("cutoff", None))
            if cutoff is None:
                cutoff = 200.0 + (tone**2) * 12000.0
            try:
                cutoff = float(cutoff)
            except Exception:
                cutoff = 200.0 + (tone**2) * 12000.0
            cutoff = clamp(cutoff, 80.0, (sr * 0.45))
            alpha = min(1.0, 2.0 * math.pi * cutoff / sr)
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

                phase_l += inc_l
                phase_r += inc_r

                if wave == "sine":
                    s_l = math.sin(phase_l)
                    s_r = math.sin(phase_r)
                elif wave == "square":
                    s_l = 1.0 if math.sin(phase_l) >= 0 else -1.0
                    s_r = 1.0 if math.sin(phase_r) >= 0 else -1.0
                else:
                    s_l = 2.0 * (phase_l / (2.0 * math.pi) - math.floor(phase_l / (2.0 * math.pi) + 0.5))
                    s_r = 2.0 * (phase_r / (2.0 * math.pi) - math.floor(phase_r / (2.0 * math.pi) + 0.5))

                lp_l = lp_l + alpha * (s_l - lp_l)
                lp_r = lp_r + alpha * (s_r - lp_r)

                s_l = softclip(lp_l, drive=drive) * env * vel * 0.9
                s_r = softclip(lp_r, drive=drive) * env * vel * 0.9

                idx = start_s + i
                if idx >= total_samps:
                    break
                left[idx] += s_l
                right[idx] += s_r

        apply_limiter(left, right, limit=0.98)
        write_wav_stereo(Path(out_wav), left, right, sample_rate=sr)
