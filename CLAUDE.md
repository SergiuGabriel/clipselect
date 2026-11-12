# MoneyMakingMachine — project context

Desktop app (Python + PySide6) for a wedding/party videographer who edits in Premiere Pro.
The owner talks in Romanian; the **app UI must stay in English**. Main machine: Mac (Apple Silicon). Cameras: Sony FX6 (.MXF).

## What it does
1. **Footage Selection** projects: analyses clips (contrast, exposure, focus, visual importance, stability), grades every
   2-second window Poor / Fair / Good and exports an xmeml (FCP7 XML) for Premiere / Resolve with 3 video tracks
   (V1 Poor, V2 Fair, V3 Good), colour labels Rose / Yellow / Forest.
   - **Auto** mode = the original algorithm the owner liked (focus 0.4, stability_v1 0.3, exposure 0.3 + min-blend,
     absolute threshold, kept if score >= thr), now per 1 s inside "holds": camera moves between subjects (robust shift
     > MOVE_PX or whole-frame change) are cut out, so 3 people filmed 2 s each become 3 shots. Exports ONE track with
     the kept shots back to back (owner's explicit wish). Kept shots shorter than "minimum cut" are dropped.
     Its preview (AutoPreview) shows the footage on top and the kept shots flowing into "Your edit" (no red row).
   - Footage export: every cut carries its own sound on A1/A2 (source channels 1-2; files with more than 2 channels, e.g. FX6 MXF, use channel 1 only, mono), LINKED to the picture with
     xmeml <link> elements (trackindex / clipindex must match the real position of each clipitem).
   - Dashboard: compact project cards, 4 per row, badge FOOTAGE / MULTICAM, delete asks for confirmation.
   - **Custom** mode = per-criterion on/off switches + weights, percentile distribution (p1/p2), "Protect good frames".
   - "Minimum cut length" (default 3 s) merges short segments into the neighbour with the closest level.
2. **Multicam** projects: the owner dumps EVERYTHING (cards, recorder files, folders) like in Syncaila.
   `sync.classify` finds the master (audio-only files, else the longest clip with sound), `sync.run_sync` aligns every
   clip (GCC-PHAT, confidence, drift), `sync.auto_cameras` groups clips into cameras (card folder + format fingerprint
   + file-name pattern, overlapping clips split), `director.detect_role` sets Static/Handheld. `director.build` scores
   every camera on a 0.5 s grid (handheld judged against its own footage, moves penalised, static gets an activity
   bonus) and runs a Viterbi over (camera, shot length) with min/max shot, switch penalty (pace) and handheld/static
   bias, then snaps cuts to onsets of the master audio. Max shot (up to 120 s) is applied after the DP by
   interrupting long shots with the best other camera. "Static cameras only as backup" = -40 on static.
   Two separate steps in the UI: **Sync** (fast, audio only) and **Auto Edit** (video analysis + director).
   Sync uses clocks as hints (camera timecode, BWF time_reference of the recorder, creation time, file date): the first
   clip of each camera folder is searched in the whole master, its result gives that camera's clock error, the next
   clips are searched only +-90 s around the prediction (~18x faster), with fallback to a full search.
   Export = ONE sequence (owner's wish): V1..Vn one track per camera holding ONLY that camera's cuts of the auto edit
   (no overlaps, so it plays as the edit; full clips when there is no auto edit yet), A1(/A2) = all recorder files,
   uncut, on one common timeline (`sync.master_starts`), then one audio track per camera, uncut and NOT muted
   (owner's wish: only the track mute was unwanted). Renaming a camera to an existing name merges them.
   The owner's usual Premiere workflow for reference: Premiere audio sync, or timecode sync (TC set by hand on each
   camera, not frame accurate) + camera labels + "Create Multi-Camera Source Sequence", then a manual audio re-sync.
   Video analyses of multicam projects live in `<project id>.analysis.json` next to projects.json (cached by size+mtime).

## Pages (sidebar)
Dashboard · Analysis Queue (shows every running job: footage analyses, multicam Sync / Auto Edit, with progress; it
is refreshed by a timer in Main) · Settings (performance) · Info / How to use (RO/EN, text in help_text.py; keep both
languages in sync when features change). Sidebar header (like the owner's WarpAutomation app): big icon, MoneyMaking<b>Machine</b>, @sergiugabrielcg link, version (v2.12.0), "by @sergiugabrielcg"
linking to https://www.instagram.com/sergiugabrielcg/.

## Files
- `app.py` — whole UI (dashboard, projects, footage pages, analysing page, results, multicam page). Data in
  `projects.json` under the OS app-data folder (`MMM_DATA` env var overrides it, used in tests).
- `core.py` — video analysis via FFmpeg (any format: MXF, MOV, MP4...), grading, xmeml export.
- `sync.py` — media detection, audio sync engine, camera grouping, onsets.
- `director.py` — multicam auto director + XML export.
- `help_text.py` — Info / How to use page (HTML, Romanian + English).
- `xmlimport.py` — import of an already synced FCP7 XML for Auto Edit.
- `music.py` — music map of a recorder (beats with LOCAL tempo, downbeats, regions music/speech/silence, energy,
  drops, build-ups, speech pauses). Used by director.py.
- `style.py` — Learn my editing style: measures an XML the editor cut himself (shots seen on top, music of its
  recorder files if on disk) and proposes Auto Director settings; saved in store.app["style"] (this computer only).
- `i18n.py` — Romanian / English for the whole UI (Settings > Language, applies at the next start).
- `longfilm.py` — Long Film: trains (cameras) by the pause in his selects, parts from whole selections, optional
  vornic (face or Mango) with medium / wide / cut tracks, 25 fps XML.
- `faces.py` — local face recognition (OpenCV Zoo YuNet MIT + SFace Apache 2.0, downloaded once into
  <data>/ai_model/faces; cosine >= 0.363 = same person). Used for the vornic; later the bride and groom.
- `teaser.py` — Teaser Studio engine (labels, music parts, beats, drop, edit, XML export).
- `make_icons.py` — builds icon.icns / icon.ico / icon.png from `icon_source.png` (run in CI before PyInstaller).
- `.github/workflows/build.yml` — builds macOS DMGs (Apple Silicon + Intel) and a Windows folder with PyInstaller on every push.

## UI style
Premiere Pro look (owner's wish): neutral greys (#1d1d1d / #232323 / #2a2a2a), pill buttons (blue #1473e6 for the main
action, outlined for the rest), dark inputs, slider values in blue. Settings > Performance shows CPU / RAM and has
"Parallel jobs" and "Hardware video decoding (Mac)" (VideoToolbox when the bundled FFmpeg has it). RAM is not the
bottleneck, decoding is: explain this if asked again.

## Done in v2.2 (was planned)
- "Export to Premiere" is now "Export XML" everywhere (the XML works in Premiere and DaVinci Resolve). If Resolve later
  needs special handling, add a Premiere / DaVinci choice next to the button (like the Footage results page).
- Import XML (xmlimport.py): an already synced FCP7 XML (Syncaila / Premiere / Resolve) -> every video track = a camera,
  clip positions taken as they are, audio-only files = recorder (master "start" = timeline position, used by
  sync.master_starts); without a recorder the timeline is the reference (no beat snapping).
- Low-confidence ("Check") clips never split a camera into many tracks: they go to one "<group> · check sync" camera and
  are not used by the director (a DJI Osmo project once exploded into 59 tracks).

## Done in v2.3
- Fast sync: a 100 Hz loudness contour scans the whole recorder per window (MasterIndex.coarse), the exact GCC-PHAT runs
  only +-1.5 s around the candidates (MasterIndex.fine); a second pass re-checks every window at the offsets the other
  windows found (repetitive music); the old exhaustive search remains the fallback when the fast one is not sure.
  ~5x faster on a 3 h recorder. run_sync.report = "Sync took … reading … searching …" (disk vs CPU).
- classify(): main recorder = audio-only folder with the most hours; other audio-only folders (LAV I, LAV II) are extra
  sources: synced like clips, cams with role "Audio", exported on their own audio tracks.
- place_by_time(): clips without usable sound (drone, mic off) get conf "approx" from their clock corrected by the
  folder's (else median) clock error; own "<group> · by time" camera, full clips in the export, never in the auto edit.
- Teaser Studio (teaser.py + TeaserPage): the password was REMOVED in v2.5.0 (owner's decision). Built from the owner's 5
  shortmovies: TEASER (~1 min, song with a drop: before the drop bride/groom/church/couple/drone, after it party +
  couple), PREGĂTIRI (calm song, bride/groom alternating, ends with couple), BISERICA (church, last quarter couple),
  PETRECERE (venue + drone first, then the party shots he selected). Categories = his Premiere label colours: Rose bride,
  Blue groom, Purple couple, Brown church, Yellow/Caribbean venue, Iris party, Violet drone; ignore Tan (interviews),
  Forest (nests), Lavender (adjustment layers). Music = one joined file or the XML of his music edit (song changes =
  part boundaries); beat grid per part, drop = biggest loudness jump in the teaser. SIX editable boundaries (v2.4.1,
  teaser.BOUNDS): Drop, Teaser ends, Pregătiri ends, Biserica ends (couple + end of vows start), Party song starts
  (venue presentation + drone), Venue ends (party). Export: V1 shots on beats, music on A1/A2, markers Teaser / DROP /
  Pregătiri / Biserica / Cuplu + jurăminte / Petrecere: sala / Petrecere: party. He adds testimonials and vows himself.
  v2.4.2: all Teaser Studio text in ENGLISH (no Romanian in the UI except the RO page of Info), red "NEW" badge,
  m:ss fields (digits only, invalid ones turn red), Detect again only with music, Story order explained (Chronological =
  recording time / timecode, else the selects order; Mixed = random within each part; the teaser is always mixed),
  footage / music / moments remembered and reloaded, warnings for missing songs, ignored multicam clips and categories
  replaced by others, Settings > "Lock Teaser Studio".
  Not done yet: slow motion (he uses 50% on party/couple), quality-based picking inside a labelled clip, Lock / Swap /
  Never use, quick preview render.

## Progress UI
Every long process shows the same ProgressPanel (step text, %, thick gradient bar, elapsed + estimated time left):
multicam Sync / Auto Edit / Import XML (top of the centre column), footage "Analyze Footage" page, Analysis Queue cards.

## Learned from comparing his finished edit (Madalina si Radu) with the program's (v2.4.3)
- His music XML was ONE joined file cut into pieces with crossfades. xmeml writes start/end = -1 next to a transition:
  those clips must be kept (start = end - length / end = start + length) everywhere we read XML (teaser._times,
  xmlimport). Skipping them lost the whole soundtrack (analysis on the last 4 s, export without the song).
- Part boundaries = cuts between music pieces, also inside one file (song_starts), not only different files.
- The change in the music after the church is the PARTY SONG; church end = ~23 s earlier (couple + end of vows).
  Priors from his 6 films in teaser.PRIOR (teaser ~50 s, getting ready ~70 s, church ~45 s, couple ~23 s, venue ~20 s).
- In getting ready he mixes many couple shots between bride / groom (blocks of 2-4, more couple towards the end).
- A slot is filled only by a piece long enough for it (no holes); reuse before accepting a shorter piece.
- Green toast (Main.toast) after Generate / Export in Teaser Studio; red NEW badge on the Teaser Studio menu item.
- Do not send the owner screenshots of Teaser Studio any more unless he asks.
- v2.4.4 shot rules (teaser.Pool): a MOMENT IS NEVER USED TWICE (every take is cut out of that file's free time, for
  every labelled piece of the same file, teaser included; when footage runs out the previous shot runs longer, never a
  repeat; leftover seconds are reported); never the same clip twice in a row if there is another; chronological =
  spread over ALL the material of that kind in recording order (+-5% randomness), not the first clips; church and
  venue OPEN WITH THE DRONE shot recorded closest in time (no stand-in from another place); the teaser only uses drone
  when there are more than 2 drone clips; 'before'/'after' the church by recording time: morning couple / first look
  -> getting ready, couple after church -> couple part, Iris after church -> party; no rest < 0.35 s at part ends.

## v2.5.0
- Teaser Studio: every selection is analysed once on import (core.analyze_range, 4 samples/s: quality + movement,
  cached in teaser_cache.json); the best part of a selection is used (movement preferred on the drop / party, calmer
  in getting ready / church: teaser.ENERGY); one bit of every selection before a second one; footage interpreted at
  another frame rate in Premiere (50p as 25p: clip <duration> longer than the real file) is converted back to real
  time (else the export points past the end of the file = striped clips); touching shots share the boundary frame.
- No slow motion (owner's decision). Static <-> Handheld slider stays as it is.
- Updates: the build workflow publishes a GitHub Release named after VER (app.py) with the DMGs + Windows zip; the
  app checks releases/latest at start and in Settings (repo must stay public). Bump VER for every release.
- Error log: app.log (rotating) in the data folder; crashes are logged and shown; Settings > Save error report.

## v2.6.0
- ai.py: AI test (CLIP ViT-B/32, Xenova/clip-vit-base-patch32 quantized ONNX from Hugging Face, downloaded once into
  <data>/ai_model; onnxruntime + tokenizers, lazily imported). One frame per selection (up to 25 per colour), prompts
  per category (ai.PROMPTS), result = his colour vs AI guess. Only a TEST: it does not change the teaser. Never run on
  the real model in Claude's sandbox (Hugging Face is not reachable there): plumbing tested with a fake ONNX model.
  The real model's input/output names are handled flexibly (outputs containing "embeds", else first output).
- Teaser projects (store.app["teaser_projects"], "teaser_current"); selection analysis cancellable, saved every 25
  selections (resumes), jobs = half the cores; teaser job shows in Analysis Queue.
- Info page: one page per <h2> of help_text + search bar. Analysis screen: running on top, progress middle, done below.
- Queue "Open" bug fixed (clicked(bool) was passed as the key). Footage project button says "View analysis" while
  its analysis runs. NEW badge in the menu: fixed 30x14.

## v2.7.0: Auto Edit on the music (music.py + director.py)
- music.analyze(x at 4 kHz): spectral flux at 100 fps weighted to the LOW bins (kick / bass / snare body); hats play
  between the beats and made the tracker lock on the off-beat. Flux frame time + 50 ms (T_OFF) = the hit. Local tempo
  every 1 s (8 s windows, autocorrelation + harmonic, Viterbi with jump costs, mild prior around 110 BPM). Songs split
  where the tempo PATH steps (> 3 %), tracks stop / start 2 s around it. Beat tracker: predicted from the local tempo,
  pulled to the hit (weighted window), re-locked after 4 off-phase beats or when the tempo moves > 12 %; phase chosen
  on kick+env over 16 beats; octave check: if every other beat has < 0.5 of the low/mid (<300 Hz) energy -> half tempo
  (a snare on 2 and 4 has body, an off-beat hat has none). Each beat moved to the START of the hit (2 ms energy).
  Regions: tempo confidence > 0.45 = music (speech ~0.25, ballad ~0.2, silence ~0.06). Drops: on a bar line the BASS
  (p80 of < 150 Hz, per bar) rises >= 3 dB, stays (next bar >= 2.5, 4 bars >= 3), is the biggest rise around and in the
  top 40 %; NOT loudness (risers are loudest before the drop). Build-up = up to 8 bars of less bass before it.
  Tests (synthetic, /tmp/mt/*): 94-98 % of beats within 20 ms, median ~1 ms, 0 false beats, downbeats 100 %, drops exact,
  70-140 BPM hip-hop / house / rock correct, 160-174 BPM read at half tempo (beats still real). 1 h of audio in ~2 s.
- director.build: with st["beat"] and a music map, music regions are cut on SLOTS (_music_slots: bars by energy and
  minshot (powers of 2, phrase-aligned), drop slots every drop_beats, build-up held or accelerating) and the camera per
  slot comes from _slot_dp (state = camera now + camera before: staying costs, going back costs = no ping-pong;
  vectorised, checked against brute force). Outside the music the old 0.5 s grid DP, cuts moved to speech pauses
  (+-1.5 s), slivers < 0.6 * minshot glued to a neighbour. Cut on the beat OFF = old behaviour exactly.
- Global settings store.app["music"] = drop_beats (1/2/4/8/16, default 4 = 1 bar), buildup (hold / accelerate),
  energy_cuts (True). v2.7.1: the controls live in the Auto Director panel ("On the music · all projects", greyed when
  Cut on the beat is off), NOT in Settings. Auto Director panel and Settings right column are scroll areas (nothing
  squeezed on small screens). Update check + AI download use certifi (packed apps have no system certificates). Map computed in the Auto Edit job (MCWorker._analyze) and saved in sync.masters[i]["music"].
- Sync Map "Music" row. (Beat check existed until v2.9.1, removed in v2.10.0.)
- v2.7.2 (from his real 9.5 h party XML): NO markers in the multicam export or the beat check (owner's choice; Teaser
  Studio keeps its 7 part markers). Per-beat tempo wobbled on real music (243 "Song" markers, and the downbeat count
  restarted at every wobble): music.py now keeps a song id per beat (the tracked song), one tempo per song, downbeats
  per tracked song. Holes of 2-8 frames: a slot accepted a camera covering 90 %; now slot cost uses the EXACT clip
  coverage (cover_frac) and a final pass fills any hole with the camera before / after / best that filmed it.
  Slivers (4 frames) from a bar cut short at the end of the music: tiny slots (< max(0.4 s, 0.9 beat)) glued to the
  slot before; only drop / build slots are protected from the sliver clean-up. Whole camera clips on a track (cameras
  not in the edit: check sync / by time) overlapping the edit are expected, not a bug.
- Sync Map legend: one row per item (table under the map). Info > Teaser Studio: recommended Premiere label colours
  for colleagues (Rose bride, Blue groom, Purple couple, Brown church, Yellow/Caribbean venue, Iris party, Violet drone,
  Tan/Forest/Lavender ignored). The owner tried 3 alternative layouts and kept the current interface.

## v2.8.0
- "Slower cuts" zones: p["zones"] = [[t0, t1]] in timeline seconds, drawn / dragged / right-click-deleted on the SyncMap,
  exact times typed in the list under the map. In director.build the music slots skip the zones; inside a zone the OLD
  way (0.5 s grid DP + snapping to the nearest onset within 0.3 s) and short shots glued up to max(6 s, 2 x minshot),
  never past maxshot. Meant for folk music (live band, changing tempo).
- Alternative angle: edit["alt"] = second best camera covering the WHOLE shot, never for shots on a Static camera, never
  the same camera; exported as the TOP video track, enabled FALSE, clips named "ALT · camera · file".
- Cut before the beat: store.app["music"]["pre_frames"] 0/1/2, every bar / beat boundary moved earlier by n frames of
  the sequence frame rate (director.seq_fps = the export's first camera rate).
- Learn my editing style (style.py, button in Auto Director): suggestions minshot (p15), maxshot (p95), pace (median),
  energy (handheld share, needs the project's files), drop_beats / energy_cuts / pre_frames (needs the recorder files).
  "Use as my style" -> store.app["style"] -> every NEW multicam project starts with it (Store.new + MulticamPage.load).
- Rejected by the owner (do not propose again): wide/close camera tags, rescue cut, sound peaks, proxies for analysis,
  stabilize label, junk bin, colour mismatch; shake must NOT be penalised differently on parties (keep as is).

## v2.8.1 (simplification, owner's decisions)
- FINAL SEQUENCES ARE 25 fps: the multicam export always makes a 25 fps sequence (director.SEQ_FPS), Footage Selection's
  default sequence rate is "25" (still selectable there), Teaser Studio was already 25.
- Cuts on the music fall 1 frame (40 ms) before the beat, fixed (director.PRE_BEAT); no option.
- Faster cuts on intense music: always on (no switch). Build-up Hold / Cut faster and faster: STAYS an option.
- Removed: "Static cameras only as backup" (old projects with it on get the slider at >= 85), Teaser "Story order"
  (always chronological; Shuffle still varies the shots).
- Learn my editing style stays an OPTION: nothing changes unless the editor applies it; it no longer proposes the
  automatic things (faster cuts, cut before the beat).

## v2.9.0: the whole app in Romanian or English (i18n.py)
- The code stays in English. i18n.install() (in main) hooks the Qt setters (QLabel / button setText, tooltips,
  placeholders, window titles, tab texts, table items, QPainter.drawText, message / file / input dialogs) and sweeps
  every widget when it is first shown; T() translates exact texts (EXACT), messages with values (TEMPLATES, "{}" =
  value, values translated too) and HTML piece by piece. Language = store.app["ui_lang"], set before the UI is built.
- EVERY NEW ENGLISH UI TEXT NEEDS ITS ROMANIAN IN i18n.EXACT or i18n.TEMPLATES (else it shows in English). Check with
  a scan of all visible labels / buttons in Romanian (no English words left).
- Texts used as VALUES are never translated: sequence size / rate / fields, output software, camera roles
  (Static / Handheld / Audio), the Footage presets (Lenient / Normal / Strict / Custom). Drop-down lists are translated
  ONLY when marked setProperty("i18n", True) (they work by index: c_drop, c_build).
- Editing terms stay English in Romanian too: Sync, Auto Edit, Export XML, Import XML, Drop, Build-up, Beat check,
  Teaser Studio, Auto Director, Cut on the beat, Slower cuts, Footage Selection, Multicam.
- Text drawn after eliding must be translated BEFORE elidedText (i18n.T(label)).
- v2.9.1: the owner's first AI test showed "0 of 0" (no frame read: the footage disk was most likely not connected).
  ai.run_test now stops with a clear message when the clips are missing / unreadable; result table translated.
  Messages put inside a bigger translated sentence must be translated FIRST (i18n.T(m)): a "." inside them breaks
  the template match.

## v2.10.0
- Beat check REMOVED (owner's decision): no button, no director.export_beatcheck, no help text. Old click-track files
  stay ignored by Add Folder (BEATCHECK_RE).
- Notifications everywhere: notify(text, error=False) (app.py, Toast on the main window; green = done, red = failed,
  a new message restarts the timer, text translated): sync / auto edit / XML import (+ missing files) / exports /
  export failures / multicam job errors / footage analysis finished / teaser footage + music loaded / teaser errors /
  AI test finished or failed / style applied or failed / error report saved / language changed / manual update check.
  Every new finished action or failure must call notify().
- AI test v2 (ai.py): SigLIP 2 So400m ONNX from onnx-community (repo + most precise vision/text files chosen from the
  Hugging Face API, remembered in <data>/ai_model/siglip2/manifest.json, resumable downloads, old CLIP files deleted),
  Core ML provider tried then CPU, 3 frames per selection (sharpest of each third from the quality analysis), log
  "ungrade" (levels 1-99 % + saturation x1.35), prompts for his weddings, an "unclear" class (shown grey, not counted
  in the score), text embeddings cached. Still ONLY a test. Never run on the real model in the sandbox (no HF access):
  plumbing tested with a fake ONNX of the same shape (pixel_values 384, pooler_output 1152, input_ids 64).

## v2.11.0: Long Film (+ vornic with face recognition)
- New sidebar page "Long Film" (own projects: store.app["long_projects"] / "long_current"), between Teaser Studio and
  Settings. His selects XML holds one TRAIN per camera operator, separated by a pause of a few minutes in the timeline
  (longfilm.GAP = 20 s). Inside a train his order is the day and the FIRST Brown shot splits morning / rest (Iris before
  = first look, after = party). Never rely on camera clocks between cameras (they can differ): camera 1 then camera 2.
- Parts, every selection WHOLE (owner's choice, no music needed; he adds music / interviews): Teaser (the teaser part of
  a chosen Teaser Studio project, with its music) · Getting ready (bride / groom, camera 1 only) · First look (Iris +
  couple before the church, both cameras) · Vornic (optional, off by default) · Church (Brown exactly in his order) ·
  Couple and venue (couple after church, then drone, then venue) · a "Party" marker (party = the Multicam edit).
- Vornic: Iris shots of the morning where his face matches the photo (faces.find_person, 3 frames, SAME 0.363) or Mango
  shots. Medium camera = the train with the bigger face (V1, one after the other), wide = synced by sound to it (V2,
  sync.MasterIndex per medium piece), cut version alternating them in his speech pauses, >= 6 s (V3, on top).
- The face models could NOT be downloaded in Claude's sandbox (GitHub LFS media domain blocked): the pipeline was tested
  with a simulated detector / matcher. opencv-python-headless is in requirements, PyInstaller --collect-all cv2.
  Later checked with the REAL models (fetched from media.githubusercontent.com/media/opencv/opencv_zoo/main/models/...,
  which the sandbox reaches): faces.Faces loads YuNet + SFace with cv2 5.0.0, 0 faces on a blank frame, faces + 128-d
  features on a photo, person() self-similarity 1.0. The "setPreferableTarget" warnings of cv2 5.0 are harmless.
- v2.12.0: AI test "Quick" (25 per colour) or "Every selection" (overnight: caffeinate keeps the Mac awake; the result
  is saved in <data>/ai_model/last_test.json). Teaser Studio card "Bride and groom (optional)": one photo each, "Find
  them in the selections" (faces.find_people, every piece read once for both, saved in <data>/faces_cache.json keyed by
  piece + photos), teaser.Pool prefers the selections where they are seen (teaser.WANT per kind; random modes keep only
  them when any, chronological adds a penalty to the others). Not for the first dance (owner).
- Markers in the exported XMLs (Teaser Studio, Long Film) follow the app language (i18n.T at export).
- Final check before v2.12.0: pyflakes clean (no undefined names) + every test script (music, tempo styles, director
  holes / zones / alt, multicam, import XML, teaser, projects / AI / queue / analysis screen, learn my style, faces + AI on
  every selection, long film + closing with a job running, Romanian scan of every screen: 0 English texts).

## NEXT (agreed with the owner) — bring it up ONLY when the owner asks about it
1. Real-wedding test of everything not yet tested on real footage: Sync, Auto Edit on a party, a Slower
   cuts zone on folk music, alternative angle track, export into Premiere AND DaVinci, a teaser, the AI test.
   The owner sends results / XMLs / error reports; fix from them. No new features before this.
2. Automatic tests in GitHub Actions (beats / drops / holes / export 25 fps / zones / alt track) BEFORE the build, so a
   broken version never reaches the owner.
3. Before selling or giving it to friends: code repo private + a second PUBLIC repo with only the DMGs (Check for
   updates needs public releases), Apple Developer notarization ($99/yr), FFmpeg + PySide6 licence check.
4. Windows build: never tested; try with a colleague.
Later, only if the owner asks: interviews (local Whisper transcription + stories via his own ChatGPT/Claude), AI in
Teaser Studio (only if the AI test scores well).
Premiere automation: prefer UXP / ExtendScript scripts written by Claude Code over screen-clicking computer use.
(The notifications, AI test v2 and the Beat check removal were done in v2.10.0.)
v2.10.1: on the owner's Mac the Core ML provider LOADED SigLIP 2 but FAILED at the first image ("Unable to compute the
prediction"). ai.Siglip now falls back to the CPU at run time too and writes <data>/ai_model/siglip2/coreml_failed so
the next runs start on the CPU.

## Rules learned the hard way
- Every clipitem <name> is EXACTLY the file name (e.g. RS-MAIN6210.MP4). DaVinci Resolve links timeline clips to media by
  name: "V1 · RS CAM · RS-MAIN6210" made every clip "Media Offline". Show the camera by track and colour, never in the name.
- Audio for sync is read channel by channel and the LOUDEST single channel is used (never a downmix): dual-mono with one
  empty or polarity-inverted channel, poly-WAVs and Sony MXF all work. Errors show FFmpeg's real message.
  Files with several audio streams (Sony MXF) are read in ONE pass (one output file per stream), never once per
  stream: 4K MXF files are huge and per-stream reading made Sync ~4x slower on disk.
- Camera proxies are never footage: DJI .LRF, GoPro .LRV, Sony SUB/*S03.MP4 (they doubled every Osmo clip into two
  identical cameras).
- Clips without usable sound (gimbal cameras with the mic off: silence or hiss) used to stick to a loud click in the
  recorder and pile up at one position. A weak clip is accepted only when every window agrees (conf high), otherwise
  "Failed: no usable sound". "Medium" needs 2 agreeing windows (one window out of several is "low").
  Future idea: place silent clips by timecode / file order relative to synced neighbours (like Syncaila).
- "A camera cannot film two things at once": in auto_cameras the surest clips are placed first; a clip that overlaps an
  already placed clip of the same camera becomes 'low' and goes to "· check sync", unless it is itself 'high' (then it
  is really a second camera). This stopped short 'Medium' gimbal clips piling up into RS CAM 2..18.
- Import XML skips files that are not on this computer (with a warning) instead of refusing the whole timeline.
- The Sync Map has a colour legend right under it (High / Medium / Check / Failed, auto-edit row = cameras).
- A clip's duration comes from the real sound length when the container duration disagrees (some MP4s inflate it).
- xmeml must declare `<pixelaspectratio>square</pixelaspectratio>` or Premiere applies 109.4 % width scale.
- Sony sidecar files (M01.XML etc.) must be skipped when adding clips.
- Keep FFmpeg bundled via imageio-ffmpeg (owner does not want to install anything).
- Untested in real Premiere so far: audio tracks in the sync XML, colour labels in DaVinci Resolve.
- In every xmeml clipitem, rate, duration, start, end, in and out are all in SEQUENCE frames; only <file> keeps
  the camera's own rate.
- Multicam cut boundaries are converted to frames once for the whole edit; touching pieces share the same
  boundary frame, and each piece's source in-frame is derived from its timeline frame.
- Camera audio tracks in the multicam export must NOT be muted (no <enabled>FALSE</enabled>).

## Testing
No real footage in CI. Generate synthetic clips with FFmpeg (testsrc2 + blur / dark / shaky crop / pan; synthetic music
master with offsets, reverb, atempo drift) and drive the UI headless with `QT_QPA_PLATFORM=offscreen`, taking
screenshots with `widget.grab()` to check layouts.
