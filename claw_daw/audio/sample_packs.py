from __future__ import annotations

import audioop
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from random import Random
from typing import Any

from claw_daw.model.types import Project, SamplePackSpec, Track
from claw_daw.util.drumkit import normalize_role, get_drum_kit
from claw_daw.util.notes import apply_note_chance, flatten_track_notes, note_seed_base
from claw_daw.util.soundfont import app_data_dir


@dataclass
class SampleEntry:
    path: str  # relative to pack root
    gain_db: float = 0.0
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "gain_db": float(self.gain_db), "weight": float(self.weight)}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SampleEntry":
        return SampleEntry(
            path=str(d.get("path", "")).strip(),
            gain_db=float(d.get("gain_db", 0.0) or 0.0),
            weight=float(d.get("weight", 1.0) or 1.0),
        )


@dataclass
class SamplePack:
    id: str
    root: str
    roles: dict[str, list[SampleEntry]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "root": self.root,
            "roles": {k: [e.to_dict() for e in v] for k, v in self.roles.items()},
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SamplePack":
        roles_in = d.get("roles", {}) or {}
        roles: dict[str, list[SampleEntry]] = {}
        for k, v in roles_in.items():
            try:
                roles[str(k)] = [SampleEntry.from_dict(x) for x in (v or [])]
            except Exception:
                continue
        return SamplePack(id=str(d.get("id", "")).strip(), root=str(d.get("root", "")).strip(), roles=roles)


ROLE_TOKENS: list[tuple[str, list[str]]] = [
    ("hat_open", ["open", "oh", "openhat"]),
    ("hat_pedal", ["pedal", "foot", "ph"]),
    ("hat_closed", ["hat", "hihat", "hh", "ch", "closed"]),
    ("kick", ["kick", "bd", "bassdrum", "bassdrm"]),
    ("snare", ["snare", "snr"]),
    ("clap", ["clap"]),
    ("rim", ["rim"]),
    ("crash", ["crash"]),
    ("ride", ["ride"]),
    ("shaker", ["shaker", "shk"]),
    ("perc", ["perc", "percussion", "conga", "bongo", "cowbell", "clave", "tambo", "tamb"]),
]


def _tokenize(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def role_from_filename(name: str) -> str | None:
    tokens = _tokenize(name)
    if not tokens:
        return None

    def has_any(xs: list[str]) -> bool:
        return any(x in tokens for x in xs)

    # special handling for hats
    if "openhat" in tokens:
        return "hat_open"
    if "oh" in tokens:
        return "hat_open"
    if ("open" in tokens) and ("hat" in tokens or "hh" in tokens or "hihat" in tokens):
        return "hat_open"
    if (("pedal" in tokens or "foot" in tokens or "ph" in tokens) and ("hat" in tokens or "hh" in tokens or "hihat" in tokens)):
        return "hat_pedal"
    if "hat" in tokens or "hihat" in tokens or "hh" in tokens or "ch" in tokens:
        return "hat_closed"

    if "tom" in tokens or "toms" in tokens:
        if "low" in tokens or "floor" in tokens or "lowtom" in tokens or "tomlow" in tokens:
            return "tom_low"
        if "high" in tokens or "hightom" in tokens or "tomhigh" in tokens:
            return "tom_high"
        if "mid" in tokens or "tommid" in tokens or "midtom" in tokens:
            return "tom_mid"
        return "tom_mid"

    for role, pats in ROLE_TOKENS:
        if has_any(pats):
            return role
    return None


def sample_packs_dir() -> Path:
    env = os.environ.get("CLAW_DAW_SAMPLE_PACKS_DIR")
    if env:
        p = Path(env).expanduser()
    else:
        p = app_data_dir() / "sample_packs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_sample_packs() -> list[str]:
    d = sample_packs_dir()
    out: list[str] = []
    for p in d.glob("*.json"):
        out.append(p.stem)
    out.sort()
    return out


def _pack_path(pack_id: str) -> Path:
    return sample_packs_dir() / f"{pack_id}.json"


def load_sample_pack(pack_id: str) -> SamplePack:
    p = _pack_path(pack_id)
    if not p.exists():
        raise FileNotFoundError(f"sample pack manifest not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return SamplePack.from_dict(data)


def save_sample_pack(pack: SamplePack) -> Path:
    p = _pack_path(pack.id)
    p.write_text(json.dumps(pack.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def _pack_id_from_path(path: Path) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", path.name.lower()).strip("_") or "sample_pack"
    h = sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{base}_{h}"


def scan_sample_pack(path: str | Path, *, pack_id: str | None = None, include: str = "*.wav") -> SamplePack:
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"sample pack directory not found: {root}")

    pack_id = pack_id or _pack_id_from_path(root)

    roles: dict[str, list[SampleEntry]] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if include and not fnmatch.fnmatch(p.name.lower(), include.lower()):
            continue
        role = role_from_filename(p.name)
        if not role:
            continue
        role = normalize_role(role)
        if not role:
            continue
        rel = str(p.relative_to(root))
        roles.setdefault(role, []).append(SampleEntry(path=rel))

    if not roles:
        raise RuntimeError(f"no drum samples found in pack: {root}")

    pack = SamplePack(id=pack_id, root=str(root), roles=roles)
    save_sample_pack(pack)
    return pack


def resolve_sample_pack(spec: SamplePackSpec) -> SamplePack:
    if spec.id:
        pack = load_sample_pack(spec.id)
        if spec.path:
            # Optional override: if path does not match, re-scan to refresh.
            if Path(spec.path).expanduser().resolve() != Path(pack.root).expanduser().resolve():
                pack = scan_sample_pack(spec.path, pack_id=spec.id)
        return pack
    if spec.path:
        pack_id = _pack_id_from_path(Path(spec.path))
        try:
            pack = load_sample_pack(pack_id)
            if Path(pack.root).expanduser().resolve() != Path(spec.path).expanduser().resolve():
                pack = scan_sample_pack(spec.path, pack_id=pack_id)
            return pack
        except Exception:
            return scan_sample_pack(spec.path, pack_id=pack_id)
    raise ValueError("sample pack spec must include id or path")


def _db_to_gain(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _read_wav(path: Path) -> tuple[list[float], list[float], int]:
    import struct
    import wave
    from array import array
    import sys

    try:
        with wave.open(str(path), "rb") as wf:
            sr = int(wf.getframerate())
            ch = int(wf.getnchannels())
            sw = int(wf.getsampwidth())
            frames = wf.getnframes()
            data = wf.readframes(frames)

        # Convert to 16-bit if needed.
        if sw != 2:
            data = audioop.lin2lin(data, sw, 2)
            sw = 2

        # Interpret little-endian signed 16-bit
        sample_count = len(data) // 2
        samples = [0.0] * sample_count
        for i in range(sample_count):
            v = int.from_bytes(data[2 * i : 2 * i + 2], "little", signed=True)
            samples[i] = v / 32768.0

        if ch == 1:
            left = samples
            right = samples[:]
        else:
            left = samples[0::ch]
            right = samples[1::ch]
        return left, right, sr
    except wave.Error as e:
        # Fall back to a minimal RIFF parser for float WAV (format tag 3).
        if "unknown format: 3" not in str(e):
            raise

    with open(path, "rb") as f:
        header = f.read(12)
        if len(header) < 12 or header[8:12] != b"WAVE":
            raise RuntimeError(f"invalid WAV header: {path}")
        if header[0:4] == b"RIFF":
            little = True
        elif header[0:4] == b"RIFX":
            little = False
        else:
            raise RuntimeError(f"invalid WAV container: {path}")

        fmt_chunk: bytes | None = None
        data_chunk: bytes | None = None
        while True:
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                break
            cid = chunk_hdr[0:4]
            size = struct.unpack("<I" if little else ">I", chunk_hdr[4:8])[0]
            payload = f.read(size)
            if cid == b"fmt ":
                fmt_chunk = payload
            elif cid == b"data":
                data_chunk = payload
            # pad to even
            if size % 2 == 1:
                f.read(1)

        if fmt_chunk is None or data_chunk is None:
            raise RuntimeError(f"missing fmt/data chunk in WAV: {path}")

        if len(fmt_chunk) < 16:
            raise RuntimeError(f"invalid fmt chunk in WAV: {path}")

        fmt_tag, ch, sr, _byte_rate, _block_align, bits = struct.unpack(
            "<HHIIHH" if little else ">HHIIHH", fmt_chunk[:16]
        )

        if fmt_tag == 1:
            # PCM: reuse the same 16-bit conversion path.
            sw = max(1, int(bits // 8))
            data = data_chunk
            if sw != 2:
                data = audioop.lin2lin(data, sw, 2)
            sample_count = len(data) // 2
            samples = [0.0] * sample_count
            for i in range(sample_count):
                v = int.from_bytes(data[2 * i : 2 * i + 2], "little", signed=True)
                samples[i] = v / 32768.0
        elif fmt_tag == 3:
            # IEEE float
            if bits not in {32, 64}:
                raise RuntimeError(f"unsupported float WAV bit depth: {bits}")
            if bits == 32:
                arr = array("f")
            else:
                arr = array("d")
            arr.frombytes(data_chunk)
            if (sys.byteorder == "little") != little:
                arr.byteswap()
            samples = [float(x) for x in arr]
        else:
            raise RuntimeError(f"unsupported WAV format tag: {fmt_tag}")

        if ch == 1:
            left = samples
            right = samples[:]
        else:
            left = samples[0::ch]
            right = samples[1::ch]
        return left, right, int(sr)


def _resample_linear(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
    if src_rate == dst_rate:
        return samples
    if not samples:
        return []
    ratio = dst_rate / float(src_rate)
    out_len = max(1, int(len(samples) * ratio))
    out = [0.0] * out_len
    for i in range(out_len):
        pos = i / ratio
        j = int(pos)
        if j >= len(samples) - 1:
            out[i] = samples[-1]
        else:
            frac = pos - j
            out[i] = samples[j] * (1.0 - frac) + samples[j + 1] * frac
    return out


def _apply_fades(buf: list[float], fade_len: int) -> None:
    n = len(buf)
    if n <= 1 or fade_len <= 1:
        return
    fl = min(fade_len, n // 2)
    for i in range(fl):
        buf[i] *= i / float(fl)
        buf[n - 1 - i] *= i / float(fl)


def _select_weighted(rng: Random, entries: list[SampleEntry]) -> SampleEntry:
    if len(entries) == 1:
        return entries[0]
    total = sum(max(0.0, float(e.weight)) for e in entries)
    if total <= 0:
        return entries[int(rng.random() * len(entries)) % len(entries)]
    r = rng.random() * total
    acc = 0.0
    for e in entries:
        acc += max(0.0, float(e.weight))
        if r <= acc:
            return e
    return entries[-1]


def _role_from_pitch(pitch: int) -> str | None:
    mapping = {
        35: "kick",
        36: "kick",
        38: "snare",
        40: "snare",
        39: "clap",
        42: "hat_closed",
        46: "hat_open",
        44: "hat_pedal",
        45: "tom_low",
        47: "tom_mid",
        50: "tom_high",
        49: "crash",
        51: "ride",
        56: "perc",
        82: "shaker",
    }
    return mapping.get(int(pitch))


def render_sample_pack_track(track: Track, *, project: Project, track_index: int, sample_rate: int) -> tuple[list[float], list[float]]:
    spec = track.sample_pack
    if spec is None:
        return [0.0], [0.0]

    pack = resolve_sample_pack(spec)
    notes = flatten_track_notes(
        project,
        track_index,
        track,
        ppq=project.ppq,
        swing_percent=project.swing_percent,
        expand_roles=False,
    )
    seed_base = note_seed_base(track, track_index, extra_seed=int(spec.seed) * 100003)
    notes = apply_note_chance(notes, seed_base=seed_base)
    if not notes:
        return [0.0] * (sample_rate // 2), [0.0] * (sample_rate // 2)

    sec_per_tick = 60.0 / float(project.tempo_bpm) / float(project.ppq)
    length_ticks = max([0] + [n.end for n in notes])
    total_samps = int(math.ceil(length_ticks * sec_per_tick * sample_rate)) + sample_rate
    left: list[float] = [0.0] * total_samps
    right: list[float] = [0.0] * total_samps

    cache: dict[str, tuple[list[float], list[float], int]] = {}
    fade_len = int(0.004 * sample_rate)
    pack_gain = _db_to_gain(float(spec.gain_db))

    active_ends: list[int] = []
    max_poly = 16

    for n in notes:
        role = normalize_role(getattr(n, "role", None)) or _role_from_pitch(n.pitch) or "perc"
        entries = pack.roles.get(role)
        if not entries:
            continue

        rng = Random((seed_base + int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF)
        entry = _select_weighted(rng, entries)
        sample_path = str(Path(pack.root) / entry.path)

        if sample_path not in cache:
            l, r, sr = _read_wav(Path(sample_path))
            if sr != sample_rate:
                l = _resample_linear(l, sr, sample_rate)
                r = _resample_linear(r, sr, sample_rate)
            _apply_fades(l, fade_len)
            _apply_fades(r, fade_len)
            cache[sample_path] = (l, r, sample_rate)
        else:
            l, r, _sr = cache[sample_path]

        start_s = int(n.start * sec_per_tick * sample_rate)
        dur = len(l)
        end_s = start_s + dur
        active_ends = [e for e in active_ends if e > start_s]
        if len(active_ends) >= max_poly:
            continue
        active_ends.append(end_s)

        vel = (n.effective_velocity() if hasattr(n, "effective_velocity") else n.velocity) / 127.0
        gain = vel * pack_gain * _db_to_gain(entry.gain_db)

        for i in range(dur):
            idx = start_s + i
            if idx >= total_samps:
                break
            left[idx] += l[i] * gain
            right[idx] += r[i] * gain

    # simple limiter
    peak = 0.0
    for i in range(len(left)):
        peak = max(peak, abs(left[i]))
    for i in range(len(right)):
        peak = max(peak, abs(right[i]))
    if peak > 0.98:
        g = 0.98 / peak
        for i in range(len(left)):
            left[i] *= g
            right[i] *= g

    return left, right


def sample_pack_to_sfz(pack: SamplePack, *, out_path: Path) -> Path:
    gm = get_drum_kit("gm_basic")
    role_to_pitch = {k: v[0].pitch for k, v in gm.roles.items() if v}

    lines: list[str] = ["<group> loop_mode=one_shot"]
    for role, entries in pack.roles.items():
        pitch = role_to_pitch.get(role)
        if pitch is None:
            continue
        seq_len = len(entries)
        for i, e in enumerate(entries):
            samp = str(Path(pack.root) / e.path)
            vol = float(e.gain_db)
            lines.append(
                f"<region> sample={samp} key={pitch} seq_length={seq_len} seq_position={i+1} volume={vol}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def convert_sample_pack_to_sf2(pack: SamplePack, *, out_sf2: Path, tool: str | None = None) -> Path:
    tool = tool or os.environ.get("CLAW_DAW_SF2_CONVERTER", "sfz2sf2")
    if not shutil.which(tool):
        raise RuntimeError(
            f"SoundFont converter not found: {tool}. Install sfz2sf2 and retry, or set CLAW_DAW_SF2_CONVERTER to your tool."
        )

    out_sf2 = out_sf2.expanduser().resolve()
    out_sf2.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="claw_daw_sfz_") as td:
        sfz_path = Path(td) / f"{pack.id}.sfz"
        sample_pack_to_sfz(pack, out_path=sfz_path)
        cmd = [tool, str(sfz_path), str(out_sf2)]
        subprocess.run(cmd, check=True)
        return out_sf2
