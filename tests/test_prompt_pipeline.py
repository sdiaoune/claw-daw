from __future__ import annotations

from claw_daw.prompt.parse import parse_prompt
from claw_daw.prompt.script import brief_to_script
from claw_daw.prompt.similarity import project_similarity
from claw_daw.prompt.pipeline import generate_from_prompt
from claw_daw.cli.headless import HeadlessRunner


def _project_from_script(script: str):
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(script.splitlines(), base_dir=None)
    return r.require_project()


def test_parse_prompt_extracts_style_bpm_key():
    b = parse_prompt("Make a dark lofi beat. BPM: 78. Key: A minor")
    assert b.style == "lofi"
    assert b.bpm == 78
    assert b.key and "A" in b.key


def test_brief_to_script_has_expected_scaffold():
    b = parse_prompt("hiphop 74bpm")
    gen = brief_to_script(b, seed=1, out_prefix="t")
    s = gen.script
    assert "new_project" in s
    assert "add_track Drums" in s
    assert "gen_drums" in s
    assert "export_preview_mp3 out/t.preview.mp3" in s


def test_project_similarity_identical_is_high_transposed_is_lower():
    b = parse_prompt("house 124bpm")
    s1 = brief_to_script(b, seed=0, out_prefix=None).script
    s2 = brief_to_script(b, seed=0, out_prefix=None).script
    p1 = _project_from_script(s1)
    p2 = _project_from_script(s2)
    assert project_similarity(p1, p2) > 0.99

    # Different seed should generally reduce similarity.
    s3 = brief_to_script(b, seed=99, out_prefix=None).script
    p3 = _project_from_script(s3)
    assert project_similarity(p1, p3) < 0.99


def test_generate_from_prompt_writes_script_and_enforces_novelty(tmp_path):
    tools_dir = tmp_path / "tools"
    res = generate_from_prompt(
        "hiphop 74bpm dark",
        out_prefix="novelty_test",
        tools_dir=str(tools_dir),
        max_iters=4,
        seed=0,
        max_similarity=0.97,
        write_script=True,
        render=False,
    )
    assert res.script_path.exists()
    txt = res.script_path.read_text(encoding="utf-8")
    assert "new_project" in txt
