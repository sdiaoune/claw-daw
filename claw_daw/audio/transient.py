from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TransientSpec:
    # Attack boost (+) or cut (-), roughly -1..+1
    attack: float = 0.0
    # Sustain boost (+) or cut (-), roughly -1..+1
    sustain: float = 0.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def transient_shaper_wav(in_wav: str, out_wav: str, *, spec: TransientSpec, sample_rate: int = 44100) -> str:
    """Very small, deterministic transient shaper.

    This is not meant to compete with pro DSP; it is a pragmatic offline tool.

    Algorithm (simple):
    - compute a fast envelope (short moving average of abs)
    - compute a slow envelope (long moving average of abs)
    - transient = max(0, fast - slow)
    - apply gain = 1 + attack * (transient / (slow + eps))
    - apply sustain via gain_s = 1 + sustain * (slow / max_slow)

    Works on stereo 16-bit PCM WAV.
    """

    atk = _clamp(spec.attack, -1.0, 1.0)
    sus = _clamp(spec.sustain, -1.0, 1.0)
    if abs(atk) < 1e-6 and abs(sus) < 1e-6:
        Path(out_wav).write_bytes(Path(in_wav).read_bytes())
        return out_wav

    in_path = Path(in_wav)
    out_path = Path(out_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(in_path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        nframes = wf.getnframes()
        if nch != 2 or sw != 2:
            raise ValueError("transient_shaper_wav expects 16-bit stereo WAV")
        if sr != int(sample_rate):
            # not fatal; just proceed
            sample_rate = sr
        raw = wf.readframes(nframes)

    # decode to floats in [-1,1]
    import array

    a = array.array("h")
    a.frombytes(raw)
    # interleaved L R
    n = len(a) // 2
    L = [a[2 * i] / 32768.0 for i in range(n)]
    R = [a[2 * i + 1] / 32768.0 for i in range(n)]

    # envelope windows
    win_fast = max(1, int(sample_rate * 0.002))   # 2ms
    win_slow = max(1, int(sample_rate * 0.030))   # 30ms

    def env(sig: list[float], win: int) -> list[float]:
        out = [0.0] * len(sig)
        s = 0.0
        buf = [0.0] * win
        bi = 0
        for i, x in enumerate(sig):
            ax = abs(x)
            s -= buf[bi]
            buf[bi] = ax
            s += ax
            bi = (bi + 1) % win
            out[i] = s / win
        return out

    efL = env(L, win_fast)
    esL = env(L, win_slow)
    efR = env(R, win_fast)
    esR = env(R, win_slow)

    max_slow = max(max(esL), max(esR), 1e-6)
    eps = 1e-6

    def process(sig: list[float], ef: list[float], es: list[float]) -> list[float]:
        out = [0.0] * len(sig)
        for i, x in enumerate(sig):
            slow = es[i]
            fast = ef[i]
            trans = max(0.0, fast - slow)
            g_atk = 1.0 + atk * (trans / (slow + eps))
            g_sus = 1.0 + sus * (slow / max_slow)
            y = x * g_atk * g_sus
            out[i] = _clamp(y, -1.0, 1.0)
        return out

    L2 = process(L, efL, esL)
    R2 = process(R, efR, esR)

    # encode
    out_arr = array.array("h")
    for i in range(n):
        out_arr.append(int(_clamp(L2[i], -1.0, 1.0) * 32767.0))
        out_arr.append(int(_clamp(R2[i], -1.0, 1.0) * 32767.0))

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(out_arr.tobytes())

    return str(out_path)
