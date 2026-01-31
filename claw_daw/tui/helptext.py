HELP_TEXT = """
claw-daw — keys

  q / Esc        Quit (prompts if unsaved)
  ?              Help
  :              Command mode
  1              Tracks/Mixer view
  2              Arrange view
  g              Toggle view (tracks ↔ arrange)
  Up/Down        Select track
  m              Mute/unmute selected track
  s              Solo/unsolo selected track
  Space          Play/stop
  c              Toggle metronome
  C              Cycle count-in (0 → 1 → 2 bars)

Command mode (press ':' then type):

  new_project <name> [bpm]
  open_project <path>
  save_project [path]

  add_track <name> [program|gm_name]
  delete_track [index]
  set_program <index> <program>

  insert_note <track_index> <pitch> <start_ticks> <duration_ticks> [velocity]

  set_volume <track_index> <0-127>
  set_pan <track_index> <0-127>
  set_reverb <track_index> <0-127>
  set_chorus <track_index> <0-127>

  set_swing <0-75>
  set_loop <start_ticks> <end_ticks>
  clear_loop
  set_render_region <start_ticks> <end_ticks>
  clear_render_region

  quantize_track <track_index> <grid(4|8|16|1/16|beat)> [strength(0..1)]

Arrangement / Patterns:
  new_pattern <track> <name> <length_ticks>
  add_note_pat <track> <pattern> <pitch> <start> <dur> [vel]
  place_pattern <track> <pattern> <start_tick> [repeats]
  move_clip <track> <clip_index> <new_start>
  delete_clip <track> <clip_index>
  copy_bars <track> <src_bar> <bars> <dst_bar>
  rename_pattern <track> <old> <new>
  duplicate_pattern <track> <src> <dst>
  delete_pattern <track> <name>
  clear_clips <track>

Export:
  export_midi <path>
  export_wav <path>
  export_stems <dir>

Notes:
  - Time units are ticks (default PPQ=480). 480 ticks = 1 beat, 1920 ticks = 1 bar in 4/4.
  - Audio playback/export requires: a GM SoundFont (.sf2) + the `fluidsynth` binary.
  - MP3/M4A encoding and mastering presets require `ffmpeg`.
"""
