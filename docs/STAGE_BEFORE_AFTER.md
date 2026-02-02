# Before / After (Stage A→F)

## Before
- Agents could generate headless scripts via templates, prompt helper, or genre packs.
- Novelty control existed (similarity), but iteration was mostly “structural” (project similarity) and not audio-aware.
- No standard way to ship golden demos with specs + reports.

## After
- **Stylepacks** add a reproducible, tweakable layer on top of genre packs:
  - `BeatSpec` (YAML) → compile script → render → score → iterate → report.
- A simple **spectral balance heuristic** lets agents/CI detect obviously unbalanced renders and try a few deterministic fixes.
- Every run writes `out/<name>.report.json`, which records:
  - attempts, acceptance, similarity, spectral bands, score, chosen attempt.
- “Golden demos” live in `demos/<style>/<name>.yaml` and can be compiled/rendered consistently.

## Why this improves agent output
- Agents now have a **tight loop** with explicit stopping conditions and audit trails.
- Stylepacks provide **3–6 knobs** for fast control without rewriting scripts.
- Reports make iteration debuggable (you can see *why* an attempt was rejected or tweaked).
