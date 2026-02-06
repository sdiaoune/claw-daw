from __future__ import annotations

from typing import Dict, List

from claw_daw.instruments.base import InstrumentPlugin
from claw_daw.instruments.noise_pad import NoisePadInstrument
from claw_daw.instruments.pluck_karplus import PluckKarplusInstrument
from claw_daw.instruments.synth_basic import SynthBasicInstrument


_INSTRUMENTS: Dict[str, InstrumentPlugin] = {}


def _register(inst: InstrumentPlugin) -> None:
    _INSTRUMENTS[inst.id] = inst


def _init_registry() -> None:
    if _INSTRUMENTS:
        return
    _register(SynthBasicInstrument())
    _register(PluckKarplusInstrument())
    _register(NoisePadInstrument())


def list_instruments() -> List[InstrumentPlugin]:
    _init_registry()
    return list(_INSTRUMENTS.values())


def get_instrument(inst_id: str) -> InstrumentPlugin | None:
    _init_registry()
    return _INSTRUMENTS.get(str(inst_id).strip())
