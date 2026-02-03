# Agent Playbook — claw-daw

This is the “how to be good at this” guide for agents using claw-daw as a **workstation**.

The user is prompting *you* (the agent). Your job is to translate intent → a headless script → exports → iteration.

---

## The 5 agent-first features (quick mental model)

These are the building blocks that make agent workflows fast, repeatable, and revision-friendly:

1) **Drum Kits (role-based drums)** — write `kick/snare/hh` instead of guessing MIDI notes.
   - `list_drum_kits`
   - `set_drum_kit <track> <trap_hard|house_clean|boombap_dusty|gm_basic>`
   - `add_note_pat ... kick ...`

2) **808 presets + glide** — choose a bass *sound* and add portamento intentionally.
   - `set_808 <track> <clean|dist|growl>`
   - `set_glide <track> <ticks|bar:beat>`

3) **Genre Packs (from-scratch generation)** — deterministic scaffolds (no templates) for fast v1s.
   - `claw-daw pack <trap|house|boom_bap> --out <name> --seed <n> --attempts <n> --max-similarity <0..1>`

4) **Novelty control (prompt→script iteration)** — iterate without collapsing into near-duplicates.
   - `claw-daw prompt ... --iters N --max-similarity 0.85–0.95`

5) **Acceptance tests (quality gates)** — genre-specific checks before you export.
   - See “Acceptance tests” below.

---

## 1) Agent contract (inputs → outputs)

### Input (what to ask the user for)
If the user didn’t specify these, ask (quickly):
- **Genre / lane** (1–2 words)
- **BPM** (and whether it should feel half-time)
- **Key** (or “dark minor / ambiguous”)
- **Sections** (bars): Intro / Hook / Verse / Fill / Hook / Outro
- **Palette** (drums + 808 + bed + top)
- **Deliverables**: names + formats

### Output (what you deliver)
Always produce:
- `tools/<name>.txt` (the script)
- `out/<name>.json` (project)
- `out/<name>.mid` (MIDI)
- `out/<name>.mp3` (audio)

**Do not overwrite prior work:**
- Use a unique `<name>` per beat/song (date + genre + bpm + version).
- If files already exist for that prefix, bump the version (`_v2`, `_v3`, …).

Also include a short **change log** if it’s a revision.

---

## 2) Producer brief template (copy/paste)

Use this template when asking a user to describe what they want:

```text
Make an ORIGINAL <genre> instrumental.

BPM: <...> (half-time feel? yes/no)
Key: <...>
Time sig: 4/4

Sections (bars):
- Intro: <n>
- Hook A: <n>
- Verse: <n>
- Fill: <n>
- Hook B: <n>
- Outro: <n>

Drums:
- Snare/clap placement: <...>
- Hats: <density + rolls?>
- Kick feel: <bouncy / sparse / driving>

808/Bass:
- Dominance: <low/med/high>
- Glide moments: <where?>
- Space rules: <where to leave gaps>

Musical bed:
- Chords: <simple/complex>
- Texture: <spacey / gritty / warm>

Top motif:
- Density: <sparse>
- Variation rules: <what changes in Hook B>

Deliverables:
- tools/<name>.txt
- out/<name>.mp3 (preset=clean)
- out/<name>.mid
- out/<name>.json
```

---

## 3) Agent workflow checklist (do this every time)

A reliable agent workflow is boring on purpose:

- [ ] **Pick a unique prefix**: `YYYY-MM-DD_<genre>_<bpm>_v1` (increment for revisions)
- [ ] **Confirm inputs**: BPM, key feel, sections (bar counts), palette, deliverables
- [ ] **Draft patterns** (1–2 bars): drums → 808 → bed → top
- [ ] **Arrange**: place patterns into sections (energy changes every 4–8 bars)
- [ ] **Preview fast**: render 8–16 bars (`export_preview_mp3`) before full render
  - sanity-check **0:00–0:10 drums** specifically (kick/snare/hats should sound like drums; no crackle/noise)
  - sanity-check **bass translation** (audible fundamental or harmonics; not swallowed by chords)
- [ ] **Apply the 5 features when useful**:
  - Drum kit roles (`kick/snare/hh`)
  - 808 preset + glide
  - Pack for scaffolding
  - Prompt with novelty control for exploration
  - Acceptance tests before final export
- [ ] **Export artifacts**: JSON + MIDI + MP3 (and stems if requested)
- [ ] **Repro notes**: claw-daw version + SoundFont path + any seeds
- [ ] **Revision rule**: never overwrite—bump `_v2/_v3` and include a changelog

---

## 4) Originality / “no-template” checklist

Before delivering, confirm:
- You did **not** call `render_demo` / `template_*` (unless explicitly requested as a demo).
- You did **not** reuse a prior script verbatim.
- At least **2 of these** changed vs your last output:
  - kick placement map
  - hat accent/roll pattern
  - bass rhythm + turnaround
  - chord voicing / top note motion
  - arrangement energy (dropouts/fills)

---

## 5) Iteration loop (how to work like a producer)

1) **Draft**: write 1–2 bar patterns per track.
2) **Arrange**: place patterns into sections.
3) **Preview**: render 8–16 bars.
4) **Diagnose**: identify the main failure (groove? sound? arrangement?).
5) **Targeted edits**:
   - drums first (feel)
   - 808 second (authority)
   - bed third (vibe)
   - top last (ear-candy)
6) **Rerender** and repeat 2–4 times.

Helpful tools:
- `select_notes` + `apply_selected` for quick edits
- `export_preview_mp3` for faster checks

### One-shot workflow (agent-first)
When the user wants a “one-shot” (fast, good-enough v1), treat it as:
- **Genre Pack (style preset) →** default BPM/swing/density/mastering
- **Drum Kit + 808 preset →** sound palette
- **Acceptance tests →** quality gate

Practical recipe:
1) Pick (or infer) the style: `hiphop | lofi | house | techno | ambient | trap | boom_bap`
2) Commit to a kit and bass early:
   - `set_drum_kit <drum_track> <kit>`
   - `set_808 <bass_track> <preset>` (+ `set_glide` for turnarounds)
3) Render a short preview and run the acceptance tests below.
4) Only then build the full arrangement.

If you use `claw-daw prompt` for scaffolding, use **novelty control**:
- `--iters N --max-similarity 0.85–0.92` to avoid near-duplicates across attempts.

---

## 6) Fast reference snippets (NOT templates)

These are micro-snippets to teach an agent, not finished songs.

### Role-based drums (Drum Kits) (1 bar)
```txt
add_track Drums 0
set_sampler 0 drums
set_drum_kit 0 trap_hard
new_pattern 0 d1 1:0
add_note_pat 0 d1 kick  0:0 0:0:120 112
add_note_pat 0 d1 snare 0:2 0:0:120 108
add_note_pat 0 d1 hh    0:0 0:0:60  70 chance=0.95
```

**Avoid unsupported roles:** stick to `kick|snare|clap|rim|hh|oh|ph|tom_low|tom_mid|tom_high|crash|ride|perc|shaker`. If you need “perc low/high”, use `tom_low` / `tom_high` (or `perc`).

### 808 preset + glide (pickup)
```txt
add_track 808 0
set_sampler 1 808
set_808 1 dist
set_glide 1 0:0:90
new_pattern 1 b1 1:0
add_note_pat 1 b1 33 0:3:360 0:0:240 110 glide_ticks=120
```

### Trap-style hat language (2 bars)
```txt
new_pattern 0 hats 4:0
add_note_pat 0 hats 42 0:0:0 0:0:60 60
add_note_pat 0 hats 42 0:0:240 0:0:60 84 accent=1.1
add_note_pat 0 hats 42 0:3:360 0:0:45 58
add_note_pat 0 hats 42 0:3:480 0:0:45 66
add_note_pat 0 hats 42 0:3:600 0:0:45 80 accent=1.12
add_note_pat 0 hats 46 0:3:480 0:0:120 72
```

### House 4-on-the-floor kick (1 bar)
```txt
new_pattern 0 k 0:4
add_note_pat 0 k 36 0:0 0:0:120 112
add_note_pat 0 k 36 0:1 0:0:120 112
add_note_pat 0 k 36 0:2 0:0:120 112
add_note_pat 0 k 36 0:3 0:0:120 112
```

### Boom bap swing feel (snare on 2 and 4)
```txt
set_swing 25
new_pattern 0 bb 0:4
add_note_pat 0 bb 38 0:1 0:0:180 108
add_note_pat 0 bb 38 0:3 0:0:180 108
```

---

## 7) Debugging playbook (common failures → fixes)

- **“Not the genre”**: enforce genre rules (snare placement, hat density, kick language) and re-arrange sections.
- **“Sounds repetitive”**: introduce variation every 4–8 bars (kick change, hat roll, bass turnaround, motif swap).
- **“808 weak”**: increase 808 volume slightly, choose a more aggressive 808 preset, add harmonics/drive via preset, add pickups.
- **“Too busy”**: reduce hat density, remove motif from verses, shorten bass notes, add dropouts.
- **“Not bouncy”**: remove kicks on strong beats, place syncopated kicks around offbeats; add 808 gaps.

---

## 8) Reproducibility recipe

To reproduce exactly, pin:
- claw-daw version
- SoundFont path
- script + seeds (if using generators)
- mastering preset

Write this into your changelog or post:
- `claw-daw --version`
- `SF2=<path>`

---

## 9) Acceptance tests (per-genre mini-gates)

These aren’t “art”—they’re guardrails. Use them as a final checklist before you export.

### Universal (all styles)
- **No broken renders**: `claw-daw --headless ...` completes cleanly and outputs JSON+MIDI+MP3.
- **Variation**: something changes every 4–8 bars (dropouts, fills, hat language, bass turnaround, motif swap).
- **Low end discipline**: kick and bass don’t fight (intentional gaps or alternating hits).

### Trap / modern hiphop (general)
- half-time backbeat is present (snare/clap on 3)
- hats have controlled rolls + at least one open-hat lift per hook
- 808 glides appear at turnarounds (or clear pitch movement)
- hook has higher energy than verse

### Boom bap / lofi-ish hiphop
- snare on 2 and 4, swing feels intentional (not random)
- hats are quieter than snare; ghost notes don’t clutter
- bass supports the groove without constant sustain

### House / techno
- kick is consistent and anchors the bar
- bass locks to kick (tight call/response, no chaotic syncopation)
- hats/percs add groove without masking the kick

### Ambient
- slow harmonic motion, few drum transients
- dynamics and space (reverb/bed) dominate

### Prompt helper (when using `claw-daw prompt`)
- If you ran multiple iterations, the novelty constraint is met:
  - similarity between attempts is **≤ `--max-similarity`**
  - if similarity stays high, lower `--max-similarity` or change constraints (style/BPM/palette).

---

## 10) Deliverable checklist

Before sending:
- confirm all `out/<name>.*` files exist
- confirm BPM/key/sections match the brief
- include a short “what changed” summary if it’s v2+.
