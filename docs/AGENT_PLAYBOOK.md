# Agent Playbook — claw-daw

This is the “how to be good at this” guide for agents using claw-daw as a **workstation**.

The user is prompting *you* (the agent). Your job is to translate intent → a headless script → exports → iteration.

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

## 3) Originality / “no-template” checklist

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

## 4) Iteration loop (how to work like a producer)

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
1) Pick (or infer) the style: `hiphop | lofi | house | techno | ambient`
2) In the script, commit to a kit and bass early:
   - `set_kit <drum_track> <preset>`
   - `set_808 <bass_track> <preset>` (+ `set_glide` for turnarounds)
3) Render a short preview and run the acceptance tests below.
4) Only then build the full arrangement.

If you use `claw-daw prompt` for scaffolding, use **novelty control**:
- `--iters N --max-similarity 0.85–0.92` to avoid near-duplicates across attempts.

---

## 5) Fast reference snippets (NOT templates)

These are micro-snippets to teach an agent, not finished songs.

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

## 6) Debugging playbook (common failures → fixes)

- **“Not the genre”**: enforce genre rules (snare placement, hat density, kick language) and re-arrange sections.
- **“Sounds repetitive”**: introduce variation every 4–8 bars (kick change, hat roll, bass turnaround, motif swap).
- **“808 weak”**: increase 808 volume slightly, choose a more aggressive 808 preset, add harmonics/drive via preset, add pickups.
- **“Too busy”**: reduce hat density, remove motif from verses, shorten bass notes, add dropouts.
- **“Not bouncy”**: remove kicks on strong beats, place syncopated kicks around offbeats; add 808 gaps.

---

## 7) Reproducibility recipe

To reproduce exactly, pin:
- claw-daw version
- SoundFont path
- script + seeds (if using generators)
- mastering preset

Write this into your changelog or post:
- `claw-daw --version`
- `SF2=<path>`

---

## 8) Acceptance tests (per-genre mini-gates)

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

## 9) Deliverable checklist

Before sending:
- confirm all `out/<name>.*` files exist
- confirm BPM/key/sections match the brief
- include a short “what changed” summary if it’s v2+.
