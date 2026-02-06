from __future__ import annotations

from claw_daw.cli.headless import HeadlessRunner
from claw_daw.genre_packs.pipeline import generate_from_genre_pack
from claw_daw.genre_packs.v1 import get_pack_v1, list_packs_v1
from claw_daw.prompt.similarity import project_similarity


def _project_from_script(script: str):
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(script.splitlines(), base_dir=None)
    return r.require_project()


def test_list_packs_v1_contains_three():
    packs = list_packs_v1()
    assert "trap" in packs
    assert "house" in packs
    assert "boom_bap" in packs


def test_pack_generators_are_deterministic(tmp_path):
    pack = get_pack_v1("trap")
    s1 = pack.generator(123, 0, "x")
    s2 = pack.generator(123, 0, "x")
    assert s1 == s2

    # different attempt should typically differ
    s3 = pack.generator(123, 1, "x")
    assert s1 != s3


def test_pack_acceptance_passes_for_each_pack():
    for name in list_packs_v1():
        pack = get_pack_v1(name)
        script = pack.generator(0, 0, None)
        proj = _project_from_script(script)
        pack.accept(proj)  # should not raise


def test_pack_pipeline_enforces_novelty(tmp_path):
    tools_dir = tmp_path / "tools"
    res = generate_from_genre_pack(
        "house",
        out_prefix="house_test",
        tools_dir=str(tools_dir),
        seed=0,
        max_attempts=4,
        max_similarity=0.985,
        write_script=True,
    )
    assert res.script_path.exists()

    # If it did multiple attempts, similarity list should reflect <= threshold at stop.
    if res.similarities:
        assert res.similarities[-1] <= 0.985


def test_pack_pipeline_compares_second_attempt(tmp_path):
    tools_dir = tmp_path / "tools"
    res = generate_from_genre_pack(
        "trap",
        out_prefix="trap_test",
        tools_dir=str(tools_dir),
        seed=0,
        max_attempts=2,
        max_similarity=0.0,
        write_script=True,
    )
    assert res.script_path.exists()
    # With at least 2 attempts configured and novelty enabled, we should compare attempt 2 vs 1.
    assert len(res.similarities) == 1


def test_pack_similarity_changes_across_attempts():
    pack = get_pack_v1("boom_bap")
    p1 = _project_from_script(pack.generator(5, 0, None))
    p2 = _project_from_script(pack.generator(5, 1, None))
    assert project_similarity(p1, p2) < 0.999
