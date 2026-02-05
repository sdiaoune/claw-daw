import json

from claw_daw.audio.drum_render_sanity import convert_sampler_drums_to_gm
from claw_daw.model.types import Project
from claw_daw.util.region import slice_project_range


def test_slice_project_range_preserves_drum_roles_from_patterns() -> None:
    # Minimal project: one sampler drum track with a pattern note using a role.
    proj = Project.from_dict(
        {
            "name": "t",
            "tempo_bpm": 90,
            "ppq": 480,
            "swing_percent": 0,
            "tracks": [
                {
                    "name": "Drums",
                    "channel": 0,
                    "program": 0,
                    "volume": 100,
                    "pan": 64,
                    "reverb": 0,
                    "chorus": 0,
                    "sampler": "drums",
                    "drum_kit": "boombap_dusty",
                    "patterns": {
                        "p": {
                            "length": 1920,
                            "notes": [
                                {
                                    "start": 0,
                                    "duration": 120,
                                    "pitch": 36,
                                    "velocity": 100,
                                    "role": "kick",
                                }
                            ],
                        }
                    },
                    "clips": [{"pattern": "p", "start": 0, "repeats": 1}],
                }
            ],
        }
    )

    sliced = slice_project_range(proj, start=0, end=1920)
    assert len(sliced.tracks) == 1
    assert sliced.tracks[0].notes, "slice_project_range should flatten pattern clips into linear notes"
    assert sliced.tracks[0].notes[0].role == "kick", "drum role must survive slicing"

    # Ensure downstream GM conversion still works (this is what the renderer relies on).
    gm = convert_sampler_drums_to_gm(sliced)
    # After conversion, roles are expanded into concrete pitches.
    pats = gm.tracks[0].patterns
    assert pats, "converted track should still have patterns"
    # At least one note pitch should be present.
    pitches = {n.pitch for pat in pats.values() for n in pat.notes}
    assert pitches, "expected expanded drum pitches after conversion"
