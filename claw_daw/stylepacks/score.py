from __future__ import annotations

from dataclasses import dataclass

from claw_daw.audio.spectrogram import band_energy_report


@dataclass(frozen=True)
class SpectralScore:
    score: float
    reasons: list[str]
    report: dict


def spectral_balance_score(in_audio: str) -> SpectralScore:
    """Crude spectral balance heuristic.

    Returns a 0..1 score where higher is "more balanced".

    Heuristics:
    - penalize excessive sub dominance vs rest
    - penalize excessive high-end dominance vs mid
    - penalize too quiet / too hot overall
    """

    rep = band_energy_report(in_audio)

    # Optional extra bands if present.
    full = float(rep.get("full", {}).get("mean_volume", 0.0))
    sub = float(rep.get("sub_lt90", {}).get("mean_volume", 0.0))
    rest = float(rep.get("rest_ge90", {}).get("mean_volume", 0.0))

    mid = float(rep.get("mid_200_4k", {}).get("mean_volume", 0.0))
    high = float(rep.get("high_ge4k", {}).get("mean_volume", 0.0))

    penalties: list[tuple[float, str]] = []

    # Low end balance: if sub is much louder than rest, it's boomy.
    # Note: volumes are negative dBFS; "louder" means closer to 0.
    sub_minus_rest = sub - rest
    if sub_minus_rest > 6.0:
        penalties.append((min(0.35, (sub_minus_rest - 6.0) / 20.0), f"too much low end (sub-rest={sub_minus_rest:.1f}dB)"))
    if sub_minus_rest < -6.0:
        penalties.append((min(0.25, (-6.0 - sub_minus_rest) / 24.0), f"too little low end (sub-rest={sub_minus_rest:.1f}dB)"))

    # High end harshness: if high is too loud relative to mid.
    if mid != 0.0 and high != 0.0:
        high_minus_mid = high - mid
        if high_minus_mid > 4.0:
            penalties.append((min(0.25, (high_minus_mid - 4.0) / 18.0), f"too much high end (high-mid={high_minus_mid:.1f}dB)"))

    # Overall loudness sanity.
    if full < -33.0:
        penalties.append((0.15, f"overall too quiet (mean={full:.1f}dB)"))
    if full > -10.0:
        penalties.append((0.15, f"overall too hot (mean={full:.1f}dB)"))

    penalty = sum(p for p, _ in penalties)
    score = max(0.0, min(1.0, 1.0 - penalty))
    reasons = [r for _, r in penalties]

    return SpectralScore(score=score, reasons=reasons, report=rep)
