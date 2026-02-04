from __future__ import annotations

from typing import Any

from claw_daw.model.types import Project


def _ensure_mix(proj: Project) -> dict[str, Any]:
    if not getattr(proj, "mix", None):
        proj.mix = {}
    if not isinstance(proj.mix, dict):
        proj.mix = {}
    return proj.mix


def _ensure_tracks_mix(m: dict[str, Any]) -> dict[str, Any]:
    tm = m.get("tracks")
    if not isinstance(tm, dict):
        tm = {}
        m["tracks"] = tm
    return tm


def _track_entry(m: dict[str, Any], track: int) -> dict[str, Any]:
    tm = _ensure_tracks_mix(m)
    k = str(int(track))
    te = tm.get(k)
    if not isinstance(te, dict):
        te = {}
        tm[k] = te
    return te


def apply_track_eq(proj: Project, *, track: int, kind: str, f_hz: float, q: float, g_db: float) -> None:
    """Append a parametric EQ band to the project mix spec."""
    m = _ensure_mix(proj)
    te = _track_entry(m, track)
    kind = kind.strip().lower()

    if kind in {"bell", "peaking"}:
        eq = te.get("eq")
        if not isinstance(eq, list):
            eq = []
            te["eq"] = eq
        eq.append({"f": float(f_hz), "q": float(q), "g": float(g_db)})
        return

    if kind in {"hp", "highpass"}:
        te["highpass_hz"] = float(f_hz)
        return

    if kind in {"lp", "lowpass"}:
        te["lowpass_hz"] = float(f_hz)
        return

    raise ValueError(f"unknown eq type: {kind}")


def apply_master_eq(proj: Project, *, f_hz: float, q: float, g_db: float) -> None:
    m = _ensure_mix(proj)
    master = m.get("master")
    if not isinstance(master, dict):
        master = {}
        m["master"] = master
    eq = master.get("eq")
    if not isinstance(eq, list):
        eq = []
        master["eq"] = eq
    eq.append({"f": float(f_hz), "q": float(q), "g": float(g_db)})


def apply_sidechain(
    proj: Project,
    *,
    src_track: int,
    dst_track: int,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    src_role: str | None = None,
) -> None:
    m = _ensure_mix(proj)
    sc = m.get("sidechain")
    if not isinstance(sc, list):
        sc = []
        m["sidechain"] = sc
    payload = {
        "src": int(src_track),
        "dst": int(dst_track),
        "threshold_db": float(threshold_db),
        "ratio": float(ratio),
        "attack_ms": float(attack_ms),
        "release_ms": float(release_ms),
    }
    if src_role:
        payload["src_role"] = str(src_role).strip().lower()
    sc.append(payload)


def apply_transient(proj: Project, *, track: int | None, attack: float, sustain: float) -> None:
    m = _ensure_mix(proj)
    if track is None:
        master = m.get("master")
        if not isinstance(master, dict):
            master = {}
            m["master"] = master
        master["transient"] = {"attack": float(attack), "sustain": float(sustain)}
        return

    te = _track_entry(m, int(track))
    te["transient"] = {"attack": float(attack), "sustain": float(sustain)}
