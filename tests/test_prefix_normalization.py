from __future__ import annotations

from claw_daw.cli.headless import _normalize_out_prefix as normalize_export_prefix
from claw_daw.quality_workflow import _normalize_out_prefix as normalize_quality_prefix


def test_export_prefix_normalization() -> None:
    assert normalize_export_prefix("song_v1") == "song_v1"
    assert normalize_export_prefix("out/song_v1") == "song_v1"
    assert normalize_export_prefix("./out/song_v1/") == "song_v1"


def test_quality_prefix_normalization() -> None:
    assert normalize_quality_prefix("song_v1") == "song_v1"
    assert normalize_quality_prefix("out/song_v1") == "song_v1"
    assert normalize_quality_prefix("./out/song_v1.json") == "song_v1"
