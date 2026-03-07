from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from claw_daw.__main__ import build_parser, main
from claw_daw.cli.headless import HeadlessRunner
from claw_daw.genre_packs.pipeline import generate_from_genre_pack
from claw_daw.genre_packs.v1 import get_pack_v1
from claw_daw.prompt.parse import parse_prompt
from claw_daw.prompt.pipeline import generate_from_prompt
from claw_daw.prompt.script import brief_to_script
from claw_daw.prompt.similarity import project_similarity


def _project_from_script_path(path: Path):
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(path.read_text(encoding="utf-8").splitlines(), base_dir=path.parent)
    return r.require_project()


def test_generate_from_prompt_auto_resolves_seed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("claw_daw.prompt.pipeline.resolve_generation_seed", lambda seed: 4242 if seed is None else int(seed))

    tools_dir = tmp_path / "tools"
    res = generate_from_prompt(
        "house 124bpm",
        out_prefix="auto_prompt",
        tools_dir=str(tools_dir),
        max_iters=1,
        seed=None,
        render=False,
    )

    expected = brief_to_script(parse_prompt("house 124bpm", title="auto_prompt"), seed=4242, out_prefix="auto_prompt").script
    assert res.seed_used == 4242
    assert res.script_path.read_text(encoding="utf-8") == expected


def test_generate_from_prompt_explicit_seed_is_reproducible(tmp_path: Path) -> None:
    p1 = generate_from_prompt("dark house groove 124 bpm", out_prefix="p1", tools_dir=str(tmp_path / "t1"), max_iters=1, seed=7, render=False)
    p2 = generate_from_prompt("dark house groove 124 bpm", out_prefix="p2", tools_dir=str(tmp_path / "t2"), max_iters=1, seed=7, render=False)
    p3 = generate_from_prompt("dark house groove 124 bpm", out_prefix="p3", tools_dir=str(tmp_path / "t3"), max_iters=1, seed=8, render=False)

    proj1 = _project_from_script_path(p1.script_path)
    proj2 = _project_from_script_path(p2.script_path)
    proj3 = _project_from_script_path(p3.script_path)

    assert project_similarity(proj1, proj2) == 1.0
    assert project_similarity(proj1, proj3) < 1.0


def test_generate_from_genre_pack_auto_resolves_seed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("claw_daw.genre_packs.pipeline.resolve_generation_seed", lambda seed: 5150 if seed is None else int(seed))

    tools_dir = tmp_path / "tools"
    res = generate_from_genre_pack(
        "house",
        out_prefix="auto_pack",
        tools_dir=str(tools_dir),
        seed=None,
        max_attempts=1,
        max_similarity=None,
        write_script=True,
    )

    assert res.seed_used == 5150
    assert res.script_path.read_text(encoding="utf-8") == get_pack_v1("house").generator(5150, 0, "auto_pack")


def test_generate_from_genre_pack_explicit_seed_is_reproducible(tmp_path: Path) -> None:
    g1 = generate_from_genre_pack("house", out_prefix="g1", tools_dir=str(tmp_path / "g1"), seed=7, max_attempts=1, max_similarity=None)
    g2 = generate_from_genre_pack("house", out_prefix="g2", tools_dir=str(tmp_path / "g2"), seed=7, max_attempts=1, max_similarity=None)
    g3 = generate_from_genre_pack("house", out_prefix="g3", tools_dir=str(tmp_path / "g3"), seed=8, max_attempts=1, max_similarity=None)

    proj1 = _project_from_script_path(g1.script_path)
    proj2 = _project_from_script_path(g2.script_path)
    proj3 = _project_from_script_path(g3.script_path)

    assert project_similarity(proj1, proj2) == 1.0
    assert project_similarity(proj1, proj3) < 1.0


def test_prompt_cli_prints_resolved_seed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "claw_daw.prompt.pipeline.generate_from_prompt",
        lambda *args, **kwargs: SimpleNamespace(script_path=Path("/tmp/prompt.txt"), similarities=[], seed_used=12345),
    )

    main(["prompt", "--out", "seed_prompt", "--prompt", "house 124bpm"])

    out = capsys.readouterr().out
    assert "seed: 12345" in out


def test_pack_cli_prints_resolved_seed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "claw_daw.genre_packs.pipeline.generate_from_genre_pack",
        lambda *args, **kwargs: SimpleNamespace(script_path=Path("/tmp/pack.txt"), similarities=[], seed_used=67890),
    )

    main(["pack", "house", "--out", "seed_pack"])

    out = capsys.readouterr().out
    assert "seed: 67890" in out


def test_parser_help_mentions_auto_seed_behavior() -> None:
    parser = build_parser()
    subcommands = next(action for action in parser._actions if getattr(action, "dest", None) == "cmd")
    prompt_help = subcommands.choices["prompt"].format_help()
    pack_help = subcommands.choices["pack"].format_help()
    stylepack_help = subcommands.choices["stylepack"].format_help()

    assert "auto-pick" in prompt_help
    assert "auto-pick" in pack_help
    assert "auto-pick" in stylepack_help
