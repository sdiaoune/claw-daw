from __future__ import annotations

from pathlib import Path

from claw_daw.stylepacks.io import load_beatspec_yaml
from claw_daw.stylepacks.compile import compile_to_script, normalize_beatspec
from claw_daw.stylepacks.run import run_stylepack
from claw_daw.util.resources import resource_path


def iter_demo_specs() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    with resource_path("demos") as demo_root:
        if not demo_root.exists():
            return out
        for yaml_path in sorted(demo_root.glob("*/*.yaml")):
            style = yaml_path.parent.name
            out.append((style, yaml_path))
    return out


def compile_demos(*, tools_dir: str = "tools") -> None:
    for style, p in iter_demo_specs():
        spec = normalize_beatspec(load_beatspec_yaml(p))
        out_prefix = f"demo_{style}_{p.stem}"
        script_path = compile_to_script(spec, out_prefix=out_prefix, tools_dir=tools_dir)
        print(f"compiled: {p} -> {script_path}")


def render_demos(*, soundfont: str, tools_dir: str = "tools", out_dir: str = "out") -> None:
    for style, p in iter_demo_specs():
        spec = load_beatspec_yaml(p)
        out_prefix = f"demo_{style}_{p.stem}"
        rep = run_stylepack(spec, out_prefix=out_prefix, soundfont=soundfont, tools_dir=tools_dir, out_dir=out_dir)
        print(f"rendered: {p} -> {rep}")
