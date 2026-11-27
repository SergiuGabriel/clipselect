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
languages in sync when features change). Sidebar header (like the owner's WarpAutomation app): big icon, MoneyMaking<b>Machine</b>, @sergiugabrielcg link, version (v4.6.1), "by @sergiugabrielcg"
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
- `longfilm2.py` — Long Film (was v2): the long film from the labelled Create Project sequence (load, selection,
  priest, first look, vornic, party multicam, 1920x1080 25 fps export) or from the wedding folder (automatic).
- `daymap.py` — the moments of the day without labels (scenes, church, faces of groom / bride, venue / couple, party).
- `scenes.py` — what every clip shows, judged by SigLIP 2 (church, drone, speech...), for the automatic mode.
- `resolve.py` — the DaVinci Resolve version of any exported xmeml (no Basic Motion, no Lumetri, project -> sequence).
- `editor.py` — the Premiere-like editor of Long Film v2 (monitor, V / A tracks, overwrite, razor, trim, undo).
- `colour.py` — his LUT(s) as Lumetri + 10 % crop on every clip (assets/ = his Lumetri template).
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

## v3.0.0 (major: the owner asked for 3.0 instead of more 0.1 steps)
- Teaser Studio and Long Film open on a PROJECT CARDS page like Projects (StudioHub + StudioCard: + New Project, click to
  open, ✕ to delete, "← Projects" back in the studio; no project drop-down any more). Sidebar order: Projects, Teaser
  Studio, Long Film, Analysis Queue, Settings, Info.
- Long Film: the church is the BIGGEST block of Brown shots (up to 3 others inside), not the first Brown shot (his first
  test imported a finished shortmovie whose teaser had church shots at second 2 -> getting ready was empty); stray Brown
  shots join the church in his order. A finished film (median cut < 2.5 s, 40+ pieces) gets a warning: import the
  selects sequence. "Built. The long film is about N min long" (it is the FILM length, not a waiting time).
- Long Film does NOT need bride / groom face recognition (it chooses nothing: all his selections, his order); only the
  vornic is found by face there.

## v3.1.0
- Long Film cameras are recognised by their FILES, not by gaps in the timeline (his real selects: V1 + V2, blocks by
  moment, gaps of 1-10 min -> the old 20 s gap rule made 14-16 fake cameras). longfilm.camera_key = file name pattern
  (digits removed) + picture size + frame rate (C9375.MP4 fx3 1080p50 vs C2002.MP4 a74 4K24); every camera's day =
  its FILE NUMBERS (the order it filmed; clocks never used); main camera = most bride / groom shots (getting ready);
  church = ALL Brown shots in HIS timeline order; drone always with the venue; a camera with no church block counts as
  party (its Iris is not first look). Camera names shown from the clips' folder (fx6, fx3, mavic, a74).
  His 4 July test: fx6 475 / fx3 121 / mavic 35 / a74 8 -> getting ready 168, first look 94, church 149, couple+venue 174.
- "Slower cuts" zones use the owner's HORA settings (director.HORA: min 6 s, max 120 s, pace 50, static<->handheld 45)
  whatever the party settings: the zone cells are chosen again with those values.
- Unknown label "Teal" (7 shots near the church on fx6) is ignored: ask him what Teal means if it matters.

- build.yml ignores pushes that only add MoneyMakingMachine*.zip (the upload commit used to start a 15 min build of the
  OLD code that could republish the old release as Latest; it had to be cancelled by hand).

## v3.2.0
- Exports keep HIS label colours: teaser.load_footage stores p["label"]; Long Film and Teaser Studio write it on every
  clip (Caribbean stays Caribbean). Without labels Premiere gave the drone MP4s another default colour (the "red"
  clips he saw in the Long Film timeline).
- Long Film getting ready = groom / bride interleaved (longfilm.interleave, blocks of ~20 s, each side in filming
  order, the side filmed first starts).
- Long Film first look = every camera's first look SYNCED by the sound (longfilm.firstlook_layout -> stack_layout):
  the camera with the most first-look footage on V1, the others on V2 above the same moment (no cut version; he cuts).
  vornic_layout uses the same stack_layout (with the cut version on V3). Audio of a file is read once (cache).

## v3.3.0 (his Mada & Radu test: "it does not work at all")
- Sound NOT linked in Premiere: Long Film wrote every <link> with clipindex 1. export_xml rewritten like core's export:
  entries first, then ids + clip index = POSITION IN ITS TRACK sorted by start, audio links with <groupindex>1</groupindex>.
  Test: every link checked against the real position (0 wrong).
- Church twice: his selects had each church clip on V1 AND a copy on V2 -> longfilm.dedupe (same file + in / out).
- Getting ready must be PARALLEL (as if simultaneous): longfilm.interleave = each side in filming order, the side whose
  story is behind (share of its footage used) gets the next 1-4 shots (the block version left 80 bride shots at the end).
- First look not synced: his 2nd camera had NO church, so its Iris counted as party. Now firstlook_candidates (other
  cameras' Iris after their church / on cameras without one) are matched BY SOUND to the main camera's first look
  (_clip_audio decodes only the selection); matches go on V2+ (one shot per track at a moment), the rest is party.

## v3.4.0: Long Film rebuilt from HIS films (measured, not guessed)
- He gave two pairs (selects XML + his finished long film of the same wedding): Madalina & Radu, Alexandra & Vlad. His
  layout is the SAME every wedding. Findings: 100 % of his shots come from selections; ~40 % of the selections are used;
  his selects END with the drone block and then COPIES (church / Forest party / venue) for the short film: never used.
  Teal = getting-ready location shots. Tan = interviews he puts between the party's music blocks (not ours).
  At Madalina & Radu the vornic + first look starts at 00:03:34:18 of his film.
- longfilm.build_film (the engine now; plan() only feeds the footage card):
  drop_copies (everything after the drone block + any selection repeating an earlier selected piece of the same file) ->
  Getting ready: groom / bride selections <= 8 s (GR_MAX), without the first 15 % of each side, the middle 55 % (0.8-2 s),
  told in parallel (interleave by SHOT progress, runs <= 6), Teal first ->
  Vornic and first look: morning long selections of the main camera (groom / bride > 60 s = VORNIC, Iris > 15 s) WHOLE
  on V1 with continuous linked sound; other cameras' long Iris (before their church, or all when no church) synced by
  sound and cut in on V2 every other stretch (~3-4 s, speech pauses); then the short morning Iris as a 2 s montage ->
  Church: Brown in his timeline order, short ones whole, long (> 15 s) ones a few 6 s pieces (~12 %) ->
  Couple and venue: drone, FIRST venue block (spread to 18), drone, FIRST couple block (spread to 26), a drone every 7.
- tools/longfilm_score: compares build_film with his films part by part. v3.4.0 score (found / right, length app vs his):
  M&R getting ready 95/78 % 3.2 vs 2.6 min, vornic+FL right 92 % (fx3 only syncs on his Mac), church 91/92 % 9.3 vs 9.8,
  couple+venue 93/57 %; A&V getting ready 94/70 % 2.7 vs 2.5, church 87/72 % 6.8 vs 5.7, couple+venue 47/49 %.
  ANY change to Long Film must keep or raise this score on BOTH weddings before it reaches the owner.
- The vornic card (face photo) is hidden: the vornic is found automatically (long morning selections). faces.py stays
  for the bride / groom in Teaser Studio.

## v3.4.1 (his test of v3.4.0 on Madalina & Radu)
- Getting ready was 1 groom / 1 bride: the score did not measure the blocks. Now longfilm.interleave_blocks: a big first
  block (~27 % of the side filmed first, 4-20), a big block of the other side (~20 %, 4-14), then turns of 1-7 (around 4)
  sized so both end together. His blocks: M&R B14 R11 then 2-7 (median 4); A&V B23 (with Teal) R3 B12 ... (median 3).
  tools/longfilm_score now prints the blocks (first two, usual block, number of blocks) vs his.
- Vornic / first look: false sound matches (C9553, C9543, C9575... matched "medium" on room noise) put random 2nd-camera
  shots. Now only conf "high", overlap >= min(20 s, half the clip), and the longest run whose file numbers grow with the
  main camera's time (out of the day's order = false). The 2nd camera goes WHOLE on V2 (track off) with its sound on
  A3/A4 (he wants both cameras' sound complete), the cut-ins on V3; teaser music moved to A5/A6.

## v3.4.2
- The "Dashboard" page (Footage Selection + Multicam projects) is named "Selection & Multicam" everywhere (sidebar,
  page title, the back link of the Footage Selection / Multicam project pages, Info), the same in Romanian. The studios
  (Teaser Studio, Long Film) keep their own "← Projects" back link to their own cards.

## v3.5.0: Blueprints, Card Offload, Transcribe (after a study of Hailo, hailo.studio)
- Blueprints (blueprint.py, Teaser Studio card 2): one of HIS finished films becomes a template (cuts, music, sound
  effects, pacing); every cut refilled with a shot of the SAME colour from the new wedding via teaser.Pool (best part,
  order of the day, never twice; the film's opening teaser = mixed moments until the first run of 6 groom / bride
  cuts). Tan = interview gap + marker; nests = party; Lavender ignored; audio = his music / SFX tracks exactly, without
  camera files (.mxf/.mp4/...) and recorder names (digits only, ZOOM..., TASCAM...). Styles Modern / Traditional, saved
  in store.app["blueprints"] (this computer, all projects). Auto (beat-cut) stays as before. Tested on his 6 shortmovies:
  100 % refilled from both selects, no moment twice.
- Card Offload (offload.py + OffloadPage, first in the sidebar): every ticked card at once (one thread each), cards only
  read, .part then rename, blake2b checksum read back from the destination, identical = "already there", different =
  " (2)", dates kept, _offload_report.txt next to the footage, optional eject (mac). 5 ticks: verify, keep folders, skip
  proxies, report, eject.
  + (his answers): wedding folder "NUNTA 4 IULIE Alexandra si Vlad 2026" (offload.wedding_name, date + names fields),
  every card identified (Sony modelName in the XML sidecars -> fx6 / fx3 / a74..., RODE *_Wireless_PRO.WAV ->
  lavaliere lav 1, lav 2 in turn, Zoom / Tascam / mostly WAV -> recorder, DJI -> drona or osmo by ffprobe tags), size /
  used / type (diskutil) / read speed shown, folder editable per card; backup twins (two slots of one camera) found by
  names + sizes + CONTENT samples (lavaliers never paired: same names / sizes, different sound) -> the fastest copied,
  the other "check only" (offload.verify_only) after its twin's copy. MMM_VOLUMES env = a test folder instead of /Volumes.
  + his test on the Mac: the Mac's own "Data" volume and the app's DMG were listed -> offload._is_card (diskutil:
  not internal-and-not-removable, not "Disk Image"); the date picker looked cheap -> day / month / year lists; the name
  follows the app language (WEDDING 4 JULY Alexandra and Vlad 2026 in English); the folder list closed under the mouse
  (the rows were rebuilt by the 3 s timer) -> rows rebuilt only when something changed and never while a list is open,
  non-editable list + "Other folder…" with an empty field; "Only what was filmed at this wedding" (window = wedding
  day 05:00 -> next day 05:00, editable; shot_time = st_birthtime on mac; sidecars follow their clip); twins measured on
  the SMALLER card (one card may miss a clip) and verify_only COPIES a clip that is only on the backup.
- UI everywhere: drop-down lists have their own arrow area (chevron drawn at start, _arrow_png) and padding; cards
  (Teaser / Long) margins 16 and spacing 10; more space under the page descriptions; Transcribe panes have a frame.
- Transcribe (transcribe.py + TranscribePage after Long Film): faster-whisper local, large-v3-turbo (fast) / large-v3
  (best), int8, model in <data>/ai_model/whisper (downloaded once from Hugging Face; NOT testable in Claude's sandbox:
  tested with a fake model). Next to every file .txt (times) + .srt; Export XML with a marker per sentence. Requirements
  + PyInstaller: faster-whisper, --collect-all faster_whisper / ctranslate2 / av.
- Hailo ideas NOT done (he chose 1, 3, 4 of the list): choosing the camera by who speaks (vornic / speeches).

- The macOS Apple Silicon build runs on macos-15 (not macos-latest): the owner agreed after the M1-M4 job got no
  machine three times; pinned also keeps the app working on older Macs.

## v3.6.0: Auto | Blueprint in Teaser Studio AND Long Film
- BlueprintBox (app.py): two buttons Auto | Blueprint, one or the other (in Auto the blueprint list / add / delete are
  switched off); project keys "mode" + "blueprint" (an old project with a blueprint and no mode = blueprint).
  store.app["blueprints"] entries have kind "short" (Teaser Studio: his shortmovies; old ones without kind) or "long"
  (Long Film: his finished long films); each page lists only its kind.
- Teaser Studio: Blueprint hides the music card and view (the blueprint brings its music). Long Film: Blueprint switches
  off the Teaser card (his film brings its own opening), Build refills the long film (blueprint.build), Export uses
  blueprint.export_xml; long empty stretches of his film (> 60 s, the party nests) get a "Party (the Multicam edit)"
  marker; Tan = "Interview here". In Blueprint the vornic is refilled cut by cut (not synced): Auto for the synced vornic.
  Tested: Madalina & Radu - The Movie refilled from the 4 July selects: 496 shots, 20 interview places, 9 groom holes.

## v3.7.0: Create Project + Import XML in Footage Selection
- Create Project (projectsetup.py + CreateProjectPage, sidebar after Card Offload, NEW badge): the wedding folder -> ONE
  25 fps xmeml laid out like HIS selects (measured on 4 July and Madalina & Radu): cameras one after the other on V1 in
  his order (projectsetup.ORDER fx6, fx3, a74, osmo...; unknown folders next; drone folders drona / mavic / dji after
  them; "trash" / "gunoi" last), 10 s empty between cameras, every camera's clips WHOLE in filming order (the camera's
  own creation_time when every clip has one, else the file date; natural file name on ties, so C9999 -> C0001 is
  right), sound channel k of every clip on Ak (FX6 MXF 4 mono channels A1-A4, MP4 cameras A1-A2, drone none), linked.
  Sound-only folders (recorder, lavaliere) are listed and left out (his selects have none). Proxies (SUB/*S03,
  PROXY folders, .LRF) and sidecars never go in. Camera order editable by drag, untick to leave out. The XML is saved
  in the wedding folder (" (2)" if it exists), prefilled with the last Card Offload wedding; Show in Finder (open -R).
  The app cannot press buttons in Premiere: he drags the XML into the Project panel (DaVinci: File > Import > Timeline).
  A zero-click import would need a Premiere UXP panel (not done; only if he asks).
- Footage Selection > Import XML (xmlimport.footage): the video files of a timeline in timeline order (earlier first, at
  the same moment the lower track first), each once; missing files skipped with a red notification; the analysis and
  the export keep that order. Buttons "Add Folder" and "Import XML" on their own row (Romanian did not fit).

## v3.8.0: the story of the interviews (with Claude) + Transcribe Import XML + "what your selects need"
- Floor / ceiling junk-frame detection was offered and REJECTED by the owner (do not propose again).
- Transcribe: Import XML (xmlimport.media: the timeline's video files in order, a sound-only timeline gives its sound
  files); every list row has a tick (f["story"], default on) and "Who is speaking" (f["who"]: bride / groom / both /
  other). "THE STORY OF THE INTERVIEWS (WITH CLAUDE)" (story.py), through HIS Claude subscription (his choice; no API
  key, no local LLM): 1. Copy for Claude = story.prompt (transcripts with a code per sentence A1.., B1.., NO length choice (as long as the story needs, never shortened by force,
  owner), rules: whole sentences exactly as said, the two tell ONE story together, answer between STORY_START /
  STORY_END) copied to the clipboard + https://claude.ai/new opened (a new chat every time); cfg["story_paths"] keeps
  which file is A, B... (survives a restart, e.g. after Claude's usage limit). 2. Paste Claude's answer = story.parse
  (ranges A12-A14, markdown stars tolerated, wrong codes skipped and counted; the copied prompt itself is refused) ->
  story.ranges (first sentence start -0.15 s, last end +0.30 s, never into the neighbour sentences) -> story.export_xml
  (25 fps, pieces back to back, picture + every sound channel linked, a marker per piece "Bride: text"). The app cannot
  see Claude's limits: Claude.ai shows them itself.
- Long Film footage card spells out what the selects need (colours, church in his order, drone block LAST: everything
  after the last drone selection counts as a copy). longfilm.lost_after_drone warns in red when >= max(10, 20 %) of the
  selections are lost only because they sit after the drone (his two weddings: 0 and 7, no warning). Teaser Studio and
  Blueprint texts say only the colours matter (any order). Disabled drop-downs / fields are greyed (global style). The red warning says EXACTLY what is wrong (owner's wish):
  the last drone clip (longfilm.last_drone) and where it ends on his sequence, the lost selections per colour, the first
  lost one, and what to move. Long Film's right column ends with SelectsMap (QPainter drawing of his layout: camera 1
  groom, bride, first look, church, venue, party, couple (in the middle of the party), party; camera 2; cameras 3, 4,
  5... the same way; drone; NO location train (owner: never there); copies hatched; train names
  above in as many rows as needed, cameras under; texts through i18n.T, Premiere colours in PR_LABEL). Info has a new page "What your selects need" (RO + EN)
  covering every menu item, and the story workflow under Transcribe.

## v3.8.1 updates (the repo already had a v3.8.0 release from the first v3.8.0 zip)
- Updates (owner: people must NEVER see where the app comes from): updater.py. The repo address is stored encoded
  (updater._S, base64 of the reversed "owner/repo"), never shown; messages say "the update server", never GitHub.
  Check = releases API, fallback = the public releases/latest redirect (tag from the final URL). "Download and install"
  downloads the file for THIS computer (Apple Silicon / Intel by sysctl hw.optional.arm64, Windows zip) into Downloads
  (.part -> rename, progress in Settings) and opens it (the DMG mounts); no browser. The repo must stay public for this.
  A programmer could still decode the address: full protection = private code repo + a releases-only public repo
  (NEXT 3), and then only updater._S changes.

## v3.8.2
- Test release only (no code change): the owner installs v3.8.1, then this one is published to test Check for updates
  and Download and install.

## v3.8.3
- His test of v3.8.1 -> v3.8.2: Check for updates + Download and install WORKED, but the 'open' that mounted the DMG was
  never waited for -> zombie child -> the Settings memory panel (1 s timer, psutil children().memory_info()) raised
  ZombieProcess every second -> an error dialog that came back after OK and blocked Force Quit. Fixed: every helper is
  started with updater.launch (waited in a thread), caffeinate is terminated AND waited, the memory panel ignores
  gone / zombie / denied processes, and the crash dialog (sys.excepthook) shows one dialog at a time and the same
  error at most once a minute (always logged). Rule: never Popen without wait(); never let a timer raise.

## v3.8.4
- Info rewritten (help_text.py, RO + EN, ~45 KB each), owner: "more text, but everything very well explained, like the
  Auto selection answer". One <h2> page per menu item in menu order (Card Offload, Create Project, Footage Selection,
  Multicam: Sync, Multicam: Auto Edit and Auto Director, Multicam on the music, Teaser Studio, Long Film, What your
  selects need, Transcribe, Analysis Queue, Settings, Useful tips). Every option with its range, default and real
  numbers from the code (Auto score 40/30/30 + 60 % average / 40 % weakest, shake 1.5 px -> 100 %, 9.5 px -> 0 %,
  moves > MOVE_PX, Custom weights = relative, percentiles Lenient 15/50, Normal 25/65, Strict 35/75, protect 65 / 85,
  exposure 45 / 210 / 15 % burnt, director pace = switch cost 20 -> 2, static <-> handheld +-25, static +10 activity,
  moves x0.15, HORA, offload twins 90 % of the smaller card, etc.). The Romanian text uses the Romanian UI names (with the
  English name in brackets for the main controls). WHEN A NUMBER OR AN OPTION CHANGES IN THE CODE, CHANGE IT IN BOTH.

## v3.8.5
- His first real transcription (a bride's interview, "I ask, she answers"): the questions were mixed in. story.is_question
  (ends with "?") marks them [ÎNTREBARE] / [QUESTION] in the prompt, story.parse splits any range around them (a question
  is never in the story), the prompt tells Claude to skip his other lines (Perfect!, Bravo!, Mulțumesc!, the jokes at the
  end); one interview -> a flowing story of that person. Step 2 opens a paste window (filled when the clipboard already
  holds the answer); a status line says which step he is at.
- BUG (all pages): a worker's done / ended signal runs while QThread.isRunning() is still True, so the buttons refreshed
  there stayed grey (Transcribe step 1 after transcribing: the model is released after 'ended'). Now every worker's
  finished signal refreshes the buttons (multicam, Long Film, Create Project, Transcribe) and Card Offload reports the
  end from finished too, once per offload (_reported). Rule: refresh UI state on QThread.finished, never only on our signals.

## v3.8.6
- Owner: "I need the interviews interleaved, not a transcript". The prompt now weaves BY THEME (he asks both the same
  questions: how they met, what the other is like, what they love, the future, a message to the other): short cuts from
  one to the other on the same theme, theme order met -> how they see each other -> what binds them -> future -> messages
  (ending). The result XML is the edited story.
- (REMOVED in v3.8.9 by the owner) Optional Claude API key (Settings > Claude, store.app["claude_key"], local only, hidden in the error report as
  "(set, hidden)"): Transcribe's button becomes "Make the story with Claude" -> story.ask_claude (POST
  api.anthropic.com/v1/messages, MODELS claude-sonnet-5-5 then claude-opus-5-5 on 404, max_tokens 8000, clear messages
  for invalid key / no credit / 429 / overloaded / no internet) in _ClaudeWorker -> parse -> XML saved next to the first
  interview (no dialog). Without a key: the copy / paste way (his subscription). Not testable in the sandbox (API
  blocked): tested with a simulated API (ok, 404 -> next model, no credit).
- Transcribe: Remove is a real button + Delete / Backspace on the list (clears story_paths if that file was sent);
  "Export XML with markers" hidden (owner: one interview with markers is useless).

## v3.8.7 (his real interviews: groom = Color Matte + lavalier WAV, bride = FX6 MXF 4 channels)
- Transcribe > Import XML = xmlimport.interviews: segments of HIS sequence (xmlimport.source_groups: clips with the same
  start AND end = one segment), one file per segment, a separate sound file (lavalier) preferred over the camera; files
  remember src_xml. Before, only video files were taken and the groom (a WAV under a Color Matte) was lost.
- The story XML copies HIS clips (story.export_from_source = his make_story_xml.py principle, verified IDENTICAL to his
  script's output on a Premiere-shaped test sequence: generatoritem, pproOriginalAudio, exploded stereo tracks,
  premiereChannelType, pproTicks): only start / end / in / out / ticks, ids, links (clipindex) change; the first <file>
  in document order is complete; old markers dropped, one marker per piece. Owner's rule from his notes: NEVER write the
  multichannel FX6 description by hand (Premiere then hears one channel). Without an imported sequence: story.export_xml.
- Whisper: transcribe.read_audio takes the CLEAREST channel (p90 - p20 frame dB; the lavalier beats the room mic), never
  a mix; initial_prompt with the couple's names from the wedding folder (transcribe.couple_names) and wedding words;
  word_timestamps (a sentence = first word start .. last word end); "best" = large-v3 float32 (slower, more accurate).
- Claude writes the corrected text after "|" (story.parse returns it; markers and the story pane use it). Padding
  -0.12 s / +0.20 s (his notes), never into the neighbour sentence.

## v3.8.8
- BUG: pressing Transcribe opened a SECOND copy of the app: tqdm (inside Whisper / Hugging Face) creates a
  multiprocessing lock -> the resource tracker re-runs the frozen executable. multiprocessing.freeze_support() is now the
  first thing in app.py (before the heavy imports). Never remove it.
- His notes from another Claude chat (PROMPT_pentru_Claude_program.md): transcripts split into SENTENCES from word times
  (transcribe.sentences: . ? ! … or a pause > 0.4 s; after 8 s closed at the next comma; hard stop 15 s) so Claude can
  interleave; Whisper loops removed (_dedupe: a segment equal to one of the last two; hallucination_silence_threshold 2.0;
  condition_on_previous_text False); prompt rules added (his unmarked chatter is his, cut often, echoes, short answers out,
  couple names from the folder); WHO line: Claude says which interview is the groom / bride when "Who is speaking" is not
  set (story.parse_who), remembered in the list.
- Speed: Apple Silicon builds try mlx-whisper on the graphics chip (transcribe.mlx_ok / _transcribe_mlx, models
  mlx-community/whisper-large-v3-turbo / whisper-large-v3-mlx in <data>/ai_model/whisper/mlx); any failure -> faster-whisper
  and <data>/ai_model/whisper/mlx_failed. build.yml installs mlx + mlx-whisper WITHOUT torch (--no-deps, + numba scipy
  tiktoken more-itertools) only on the Apple Silicon runner, continue-on-error, and passes MLX_FLAGS to PyInstaller only
  when that step succeeded. NOT testable in Claude's sandbox (Linux): check the Actions log line "mlx ok".
- Drag and drop from Finder on every page (enable_drops / _Drops event filter on the page and all its widgets, each page
  has _drop(paths)); the Card Offload destination area has its own handler.
- Analysis Queue also shows Long Film, Card Offload, Create Project, Transcribe (+ the Claude story) and opens them.
- Card Offload has no NEW badge any more.

## v3.8.9 (his check of the v3.8.8 story XML: "the XML generation is right, change nothing there")
- Pieces still too long (20.9 s, 15 s, 16 s): his transcripts were made before the sentence split. Transcripts now carry
  "tv" = transcribe.VERSION (3); older ones are marked ↻, redone by Transcribe and kept out of the story (status line says
  why). transcribe._split_long: every piece > 8 s is cut again at its best point (3 x pause + comma bonus, near the
  middle, parts >= 1 s) until <= 8 s.
- NO OVERLAP between pieces of one file (owner: #10 ended at 82.80 s, #12 began at 82.64 s): story.bounds gives every
  sentence in = max(start - 0.12, previous sentence's end) and out = min(end + 0.2, NEXT sentence's in); ranges uses
  them, so pieces share at most a boundary frame, wherever they sit in the story.
- Prompt: swearing may stay (he removes it); jokes whole (setup + punchline) or not at all; no information repeated by
  both voices in a row; no piece starting with an answer that needs the question.
- Owner: NO Claude API key (Settings section removed, TranscribePage._key returns ""; story.ask_claude unused). The story
  is made through his subscription (copy / paste). No NEW badge on Transcribe.
- 4-track FX6 source: the copy keeps all 4 exploded tracks (tested); his last check used an older 2-track source.

## v3.9.0 (MODIFICARE_FINALA_program.md: the owner's general final spec; order 1 -> 4 -> 6 -> 3; section 5 = XML untouched)
- Transcription (1): PAUSE 0.6 s, MIN_PIECE 0.8 s, MAX_PIECE 8 s; _split_long prefers pauses, commas and linking words;
  _join_short glues short / filler-only pieces ("ăă", "deci", "așa") to the closer neighbour if the result stays <= 8 s,
  whole short sentences stay alone. transcribe.VERSION = 4 (older transcripts are ↻ and redone). story.is_question also
  marks the interviewer's short lines (Perfect / Bravo / Mulțumesc / Bun...).
- Parsing (4): story.parse_checked(answer, files) -> (pieces, errors, warnings). Errors: no STORY_START, unknown code,
  range across letters, backwards range, a [QUESTION] endpoint, a code used twice. Warnings: a line without a code, a
  question inside a range (split out). story.cut_times: in = start - 0.12 (>= previous code end + 0.02), out = end + 0.2
  (<= next code start - 0.02); overlaps of one file move to the midpoint.
- Checks (6): story.check_cuts (errors: length 0, past the file end, frame overlap; warnings: transcript pieces > 8 s,
  linking-word start without the previous code, same speaker > 3 in a row) and story.check_xml (links / indices,
  pproTicks, file complete at first use). TranscribePage._make_story writes to "<out>.checking", runs check_xml and only
  then os.replace -> out; any error = nothing written + the _report dialog (ERRORS / WARNINGS, "Copy for Claude" copies a
  fix request). "Only one voice on a theme" cannot be checked automatically (themes unknown): told to the owner.
- tools/story_check.py + tools/reference_make_story_xml.py (his proven script): 2- and 4-track sources, app vs reference
  compared element by element + check_xml. Runs in build.yml BEFORE PyInstaller on Mac and Windows: a broken story XML
  stops the build.
- Prompt (3): the owner's final English prompt (story.prompt). First-name field (e_name) next to "Who is speaking",
  stored in f["name"], used in the prompt and the markers. Sequence name "<source xml name> - STORY".
- i18n: the old template "{} core{}" matched any text containing " core" ("corectează" -> "nuclee"); replaced by
  "{} cores" / "{} core". Lazy templates ending in {} are dangerous: check T(T(x)) == T(x) for new strings.

## v3.9.1 (his reading of the real TXT files: B2 = 20.8 s, questions glued to answers)
- transcribe.VERSION = 5 (older transcripts are ↻ and redone).
- Missing full stops: transcribe._cap_start = a capitalised word mid-line after a word without punctuation starts a new
  sentence, unless it is in PROPER (Instagram, Dumnezeu, cities...), the couple's names (folder), "I" or an acronym.
- _join_short never glues across a finished sentence (left piece ends . ? ! …) nor into / out of a question ("Cum este
  Florin...? Iubitor," was glued). _complete requires a capital first letter ("frumos." alone is not a sentence).
- Segments without word times (MLX and faster-whisper): _again transcribes that slice again with word times; if that fails
  estimate_words gives letter-proportional times (4th tuple element True) and sentences() moves every estimated cut to
  the nearest real pause (transcribe.pauses / snap: < -38 dB or p90-18, >= 0.15 s, +-0.6 s).
- story.cut_times(..., audio={fi: samples}): in / out moved into a real pause when they are not in one (within the
  allowed window). _make_story reads the audio of the used files (wait cursor).
- The list shows "⚠ N pieces over 8 s" (tooltip lists them). TXT times with tenths [00:00:05.2].
- His B2 "5 lines in the TXT but one 20.8 s code": both come from the same f["segs"]; the TXT he read and the transcript
  his prompt was built from were from different runs. Not reproducible here; the over-8-s warning makes it visible.

## v3.9.2 ("it must work on ANY wedding": no fixed lists, measured checks, a test set of weddings)
- transcribe.VERSION = 6. The fixed PROPER list is GONE: transcribe.proper_nouns(words, names) = every word that never
  appears with a small letter in THIS transcript (+ the couple from the folder + the first names typed in the list,
  passed by _TranscribeWorker(names=...)). _cap_start uses that set. Nothing wedding-specific may be written in
  transcribe.py / story.py (names, tracks, camera, language all come from the program / the source XML).
- Pause threshold transcribe._thr: max(min(-38, p90-18), p15 + 0.3 * (p90-p15)) = relative to the recording (a windy
  recording never goes under -38 dB). Used by pauses / snap / in_pause.
- transcribe.quality(segs, x, letter) MEASURES: codes > 8 s, < 0.8 s, '?' inside, % of code borders in a real pause
  (in_pause at the middle of the gap) + the list in speech. Worker emits qual(path, q) -> f["quality"]; write_files
  writes <name>_raport.txt (translated through i18n.T). The page shows a green / red "Quality:" line under the text, a
  "Quality report" button (codes shown as A.. / B.. when ticked) and "⚠ N questions glued" in the list.
- _make_story measures every in / out with in_pause, writes <story>_raport.txt next to the XML, puts it under the story
  text and warns when < 95 %.
- qualitytest.py + "Test on several weddings…" (Transcribe page, runs as the Transcribe job in the queue): a folder with
  one sub-folder per wedding (interviews from the source XML via xmlimport.interviews, else every media file);
  transcribe + quality + a test story (every non-question code alternating the interviews) -> cut_times with audio ->
  % cuts in a pause, overlaps, export_from_source / export_xml -> check_xml. rezultate.json keeps every version;
  compare() lists what got worse than the previous version; table: red = misses the target (fails()), ▼ = worse.
  Tested with synthetic weddings and a mock model that "hears" speech regions of the real audio (/home/claude/t5).

## v3.9.3 (owner: single-occurrence capitals and forced cuts, both general)
- transcribe.VERSION = 7. wordfreq.py = the first 5000 words of RO and EN (FrequencyWords, MIT, OpenSubtitles 2018),
  wordfreq.common(lang) (both for "auto"). transcribe.vocabulary(words, names, lang) -> small / count / names / common.
  _cap_start: a capitalised word mid-line after a word without punctuation starts a sentence when it is also seen with a
  small letter, or it appears ONCE and is a common word; never before a chosen name; never after NO_END ("cu", "pe",
  "la", "și", "the", "with"...: the subtitle list contains names like maria / john, NO_END keeps "cu Maria" whole).
  proper_nouns = never small and (said more than once or not common).
- _split_long(ws, audio, forced): real words -> a border in a real pause (gap >= 0.15 s or in_pause); estimated words ->
  the real pauses of the sound (pauses()) pick the border (comma / link preferred within +-0.6 s) and the times move to
  the pause. NO pause at all -> FORCED cut: the quietest moment (_quietest, 50 ms smoothing) between 5 s and 8 s
  (owner said 5-9 s, capped at 8 because 8 s is the hard maximum), then the nearest word border (estimated times move
  to that moment). Forced borders: Segs.forced -> quality()["forced"] -> "Forced cuts (...)" line in the report, the
  "Forced cuts" column in the multi-wedding test.

## v3.10.0 (who speaks MEASURED from the sound; chunked transcription; tested on his REAL interview audio)
- speakers.py: analyse(chans) -> x (clearest distinct channel), regions [(a, b, label)], method, gap, sure.
  Identical channels dropped (FX6 records lav + cam twice: ch0==ch2, ch1==ch3). Close mics = lavaliers (clarity within
  6 dB, corr < 0.5, max 2, sorted by channel: S1 = lower channel); ref = a camera mic (clarity < best - 3).
  VAD = Silero (faster_whisper.vad, bundled by --collect-all faster_whisper) on the lavalier, + speech the lavalier
  missed found on the other mics; energy fallback when Silero is missing or finds < 25 % of the energy regions.
  Per region: with ref median(lav - cam) on the louder half; one channel p90 level. Two-means; videographer = low group
  only if the groups are >= 6 dB (ref) / 8 dB (one channel) apart; band max(1.5, 0.2*gap) and regions < 0.3 s = '?'.
  Two lavaliers: '1' / '2' by lav1 - lav2 > 6 dB. MEASURED on his wedding (Florin & Miruna): FX6 bride +10..+19 dB,
  videographer +1..+4 dB (gap 10.3, all 11 questions found); groom lav-only: groom -28..-41, videographer -44..-55
  (gap 13.1). label_of(a, b, regions): majority, '?' when two definite speakers each > 25 %.
- transcribe.transcribe: chunks(regions) (never across a definite speaker change, a gap > 2 s, or 24 s) -> each chunk
  transcribed alone (_engine: same for MLX and faster-whisper, vad_filter=False, word times; bad = no_speech > 0.6 and
  logprob < -1) -> sentences(words, x, names, lang, hard). Whole-file fallback when chunks give no words.
  Sentences: hard borders at speaker changes; punctuation / capital rules split ONLY at a real pause (_pause_between,
  audio decides), except after "?" (always). _split_long real_pause uses the audio. Border snapping: within +-0.3 s,
  never past a word's middle, a piece grows at most 0.3 s. _fragments: <0.6 s 1-2 word leftovers join their piece; the
  other speaker's first 1-2 words after a full stop move to the next piece ("…asta. Cum va" + "decurge…?").
  Segs.spk / .sep; transcribe.VERSION = 8. TXT marks [QUESTION] / (?) (only when something was measured).
- story.qflags(f): 'v' -> question; 'c'/'1'/'2' -> NOT a question even with "?" ("Ai scăpat?" by the bride); '?' or no
  measure -> the old text rule. Used by prompt, parse_checked, qualitytest. Prompt adds [S1]/[S2] for two lavaliers.
- quality(): border = pause_between(end, next start) (a real pause anywhere between the pieces), forced cuts excluded and
  listed; + vid / unsure / sep lines. qualitytest columns "[QUESTION] from the sound", "Unsure who speaks".
- tools/speakers_check.py (synthetic lav+cam, one channel, two lavaliers) runs in CI next to story_check.py.
- Real-audio before / after (his TXT/SRT text replayed per chunk, word times estimated inside each SRT line, so the
  remaining 10 % of borders off a pause are 0.1-0.3 s from one): bride borders in a pause 49 -> 90 %, groom 76 -> 88 %,
  glued questions 1 -> 0, 0 codes > 8 s. Multi-wedding test v3.9.3 -> v3.10.0: nothing worse, cuts in a pause 51 -> 73 %.
  NOT tested here: real Whisper on chunks (no model in the sandbox), MLX.

## v3.11.0: the interview engine REWRITTEN from zero (transcribe.py v4, owner: "make it general, for any voice")
- The owner asked for a rewrite instead of more patches (v3.8.8 -> v3.10.0 had grown rule on rule). Rewritten: transcribe.py
  (same public API: app.py / qualitytest / tools unchanged). speakers.py (measured on his real interviews) and story.py
  (prompt, parse, cut_times, export_from_source = his proven XML) are kept as they were.
- Tested on HIS REAL interviews (Florin & Miruna: groom lav WAV, bride FX6 4 ch) with REAL Whisper large-v3 through
  whisper.cpp (the sandbox cannot download faster-whisper / MLX models; bench in /home/claude/bench: cppmodel.py =
  a faster-whisper-shaped stand-in, cached). Before (his v3.10.0 TXT): "Superb!" lost, YouTube inventions ("Nu lăsați
  material rețele…", "Nu uitați"), sentences cut at every thinking pause ("Sunt | sigură… o | să fie"). After: 0 codes
  over 8 s, 0 questions glued, 91-93 % of borders in a real pause (the rest is fluent speech with no pause at all),
  "Superb." kept, "Iubitor." alone, every question whole; the cut audio was re-listened with Whisper.
- Pipeline (transcribe.transcribe): 1. speakers.analyse (regions + who). 2. Whisper on the WHOLE file at once (context
  kept; faster-whisper's generator reports real progress and Cancel works inside it). 3. clean(): no-speech /
  compression > 2.4 / loops / a segment equal to one of the 2 before / HALLUCINATIONS patterns (subtitle phrases per
  language, never wedding words) / words outside speech: removed only when > 1 s from any region, or outside and
  probability < 0.3 (MEASURED: real words came out up to 0.55 s outside the VAD regions; the first version removed
  "muncitor frumos", "Cea", "ani"). _complete_words: a segment with fewer timed words than its text gets the missing
  tail estimated (no word lost). 4. calibrate(): a median shift of word times measured at sentence ends (pause start
  after the word) is corrected when > 0.1 s. 5. recover(): a speech region with < 25 % covered by words is transcribed
  again alone with 1 s around it ("Superb!"). 6. sentences(): _glue_marks (a lone "-" joins the next word);
  _word_labels (region of the word's middle; a run of another speaker < 0.6 s inside one speaker's words = '?');
  _sentences cuts at . ? ! …, after "?", at a definite speaker change not already separated by punctuation within
  2 words, at a silence > 2 s, at a forgotten full stop (_cap_start) only with a real pause; NEVER at a pause alone.
  _split_long only above SPLIT_AT 7.5 s (so moving borders never passes 8 s): score = 4 x real pause (searched +-0.45 s:
  word times are 0.3-0.8 s off on real audio) + comma 1.2 + link word 0.8 + capital 0.6 - 3 after NO_END ("o", "să",
  "într-un", "s-au", "fiecare"... ; "lui" only before a capital) - 3 before NO_START ("decât") - 0.08 x imbalance;
  parts >= 1.5 s; best point without a pause = forced (quietest gap among points scoring within 0.3 of the best).
  _snap_borders: kept when the words already have a pause between them; else the nearest pause within 0.6 s (1 s after
  a finished sentence): each word time is CLAMPED into the pause (a soft "că" measured as pause stays with its piece;
  measured on his bride: "că" at 20.1-20.45 s, Whisper said 19.80), both outside -> middle of the pause; no pause /
  forced -> quietest moment within 0.4 s; a piece never passes 8 s.
- Report: + "Removed (Whisper inventions…)" with the texts and "Speech found in the sound but without any text (target 0)";
  quality_line adds "N stretches of speech without text"; the forced-cut line says "between two words". qualitytest
  metrics + "Speech without text" (lower is better) and "Removed inventions". VERSION = 9 (older transcripts ↻).
- tools/transcribe_check.py (synthetic speech + words, no Whisper) runs in CI next to story_check / speakers_check:
  thinking pause, long sentence (<= 8 s, NO_END / NO_START, parts >= 1.5 s), question alone, speaker change and stray
  words, cleaning (real word 0.5 s off kept, inventions / far words / loops removed, missing tail recovered), soft word
  inside a pause (a naive "pause end" border fails it), recover, report keys.
- NOT tested here: faster-whisper / MLX themselves (same call shape as v3.10.0 + word probability). Whole-file
  transcription on MLX gives no progress until the end (mlx_whisper has no callback).

## v3.11.1
- MLX was NEVER in the Apple Silicon build (since v3.8.8): the CI step installed mlx with --no-deps, which skipped
  mlx-metal (it holds libmlx.dylib), so "import mlx.core" failed ("Library not loaded: @rpath/libmlx.dylib"), the step
  was continue-on-error and the app silently transcribed on the processor (faster-whisper). Now mlx-metal is installed
  too. Check the Actions log line "mlx ok" after every build.

## v3.11.2 (his first real test of v3.11.1, large-v3 "best" on his Mac)
- His transcripts came out without full stops and with capitals mid-sentence ("Instagram Într-un an Nu i-am"), and the
  groom's content was worse ("destructivă", "eu am fost operat"). Cause: with condition_on_previous_text off, Whisper
  (openai / mlx code) keeps the initial prompt ONLY for its first 30 s window. Now transcribe.windows(): windows of at
  most WINDOW 28 s cut in the middle of the longest real gap between speech regions (never inside speech), each with
  the prompt. On the bench this fixed the groom ("a fost operată", "cea mai distractivă") and the punctuation.
  It also gives MLX real progress (per window).
- Long thinking pauses cut sentences ("au fost tot | felul", "nu i-am răspuns | la mesaj", "cel mai | mare"): a silence
  > 2 s now cuts only when the previous word can end a phrase (not NO_END) AND the next word starts like a sentence
  (capital or link word); > 5 s cuts anyway (still not after NO_END). Stray speaker runs: < 1 s (was 0.6) -> '?'.
  _split_long: -1.5 before a preposition / NO_END word without a comma ("felul | de", "bucur | de tot"); NO_END +
  ultima / primul... (owner: keep English words) clean(..., lang): only words in ANOTHER ALPHABET (not Latin) are removed
  for ro / en ("выш"); foreign Latin words stay. CI tests 9-11 (long pause, alphabet, windows).
## v3.11.3 (Create Project = a whole Premiere project: camera bins + "selectie" / "select", named by him)
- projectsetup.export_xml(lay, infos, out, name, project=...): <xmeml><project><name>…</name><children> one <bin> per
  camera ("Camera A - fx6", "Drona - dji") with every clip as a master clip (<clip id="masterclip-N"
  explodedTracks="true"> ismasterclip, video clipitem with the FULL <file>, one audio clipitem per source channel), then
  the sequence; sequence clipitems carry <masterclipid> so Premiere links them to the bin clips. Files defined once.
  default_slots / by_slot: every camera folder -> 'A'..'H' (his ORDER), 'drone', 'out' (trash / gunoi).
- CreateProjectPage: PROJECT NAME field (default = wedding folder name, per folder), the sequence name is automatic
  ("selectie" RO / "select" EN), a QTableWidget Folder | Camera (combo A..H / Drone / Leave out, remembered per folder in
  cfg slots / slots_for), XML = "<project>.xml" in the wedding folder, "Open in Premiere Pro" (_premiere_app: newest
  /Applications/Adobe Premiere Pro*/…app, Windows Program Files\Adobe; mac: open -a app xml).
- Auto / Custom modes (cfg mode). Custom = projectsetup.export_bins(groups, infos, out, project): bins only, one per
  camera folder (folder name, chrono order) + optionally the sound folders (sound_files: recorder / lavaliere, audio-only
  master clips, file rate 25), NO sequence (a friend's workflow: he labels the cameras and makes the sequence himself).
- Card Offload option "project": after a clean offload Main.auto_project(root) loads the copied wedding in Create
  Project and starts it (mode chosen there; shows in the queue as the Create Project job).
- A real .prproj cannot be written (closed format): Premiere File > Open on the XML makes the project (Larry Jordan /
  Adobe docs), he saves it. NOT verified in Premiere here: that bins + masterclipid import without duplicate clips, and
  that "open -a Premiere file.xml" opens it as a project (vs. asking). DaVinci Import Timeline with <project> not verified.

## v3.11.4 (his check of v3.11.3 Create Project + his reference sequence in Premiere)
- Sound laid out like PREMIERE (read from his project NUNTA 25 OCTOMBRIE 2026 Ralu si Berti.prproj, sequence "cum trebuie
  sa arate cadrele ca si sunet si setari(cand ai 4 piste audio)": FX6 = A1 STEREO channels 1+2, A2 STEREO 3+4; and from
  his Premiere xmeml exports (4 iulie selects, Mada & Radu) = how a stereo track is WRITTEN: two exploded tracks
  currentExplodedTrackIndex 0/1, totalExplodedTrackCount 2, premiereTrackType="Mono" (as Premiere writes it),
  clipitems premiereChannelType="stereo", sourcetrack trackindex = the channel; the <file> of a 4-channel MXF =
  pproOriginalAudio channelcount 4 + one <audio> channelcount 2 per pair; a 2-channel MP4 = one <audio> 2 (no
  pproOriginalAudio)). projectsetup.groups(ach): pairs as stereo, an odd last channel mono -> FX3 / A7 / osmo = ONE
  stereo track (owner: "FX3 must be one track"), mono lavalier = one mono track. Stereo slots first (A1, A2), mono after.
  _file_xml / _master / _track_attrs shared by Auto (export_xml) and Custom (export_bins): same rules in both.
- GAP = 20 min between cameras (owner: 10 s glued them together visually).
- EVERY folder of the wedding goes in (owner): projectsetup.all_folders = cameras + sound folders (sound=True, slot
  "sound": lavaliere, recorder) -> bins in both modes, and in Auto at the end of the sequence (sound only, mono / stereo
  tracks). The "Also the sound folders" tick is gone (Leave out in the picker instead).
- Create Project has no NEW badge any more. Logi Options+ popping up in Premiere: Logitech's own plugin, starts with
  Premiere; the app only writes an XML and runs "open -a Premiere file.xml".

## v3.11.5
- Owner: the lavaliere / recorder must NOT be on the timeline: Auto puts only the cameras and the drone in the sequence;
  the sound folders are bins only (export_xml(..., bins_only=[(name, files)])). Custom unchanged (bins of everything).

## v3.11.6 (from his screen recording of a colleague's Premiere workflow)
- The Create Project modes are renamed: Auto -> "Chronological" (RO "Cronologic"; only the POSITION in the timeline:
  cameras one after the other, 20 min apart); Custom -> "Timecode synchronized sequence" (RO "Secvență sincronizată pe
  timecode"). The recording: bins per folder -> select a bin's clips -> Metadata > Dynamic Media > Camera Label -> select
  the bins -> Create Multi-Camera Source Sequence (Synchronize Point = Timecode, one multicam sequence) -> Open in
  Timeline. The app does it: the picker's letter = the camera label; projectsetup.export_synced(cams, infos, ...):
  every camera on ITS OWN video track (A first, then B..., the drone), every clip at sync_time(i) = its timecode (probe
  reads "timecode : hh:mm:ss:ff"; 00:00:00:00 = none) else its recording clock (tod from creation_time); before 05:00
  (SYNC_DAY) = after midnight (+24 h); overlapping clips of one camera -> an extra lane under it; clips with no time at
  the end; every camera its own audio tracks (stereo pairs, groups()). Sequence "sincronizare timecode" / "timecode
  sync". Sound folders = bins only in both modes. Written as a NORMAL sequence (what "Open in Timeline" shows), not a
  Premiere multicam clip (xmeml multiclip import not verifiable here); the Camera Label XMP field itself is not written.
- projectsetup._write(items, ...) = the one sequence writer (items = file, video track, audio key, start, length);
  export_xml (chronological) and export_synced use it. export_bins is no longer used by the app.

## v3.11.7 (his own Premiere multicam vs ours: "the label is right, the sync is not")
- Measured on his Premiere "Create Multi-Camera Source Sequence > Timecode" XML (137 of 137 clips): a clip's position =
  its timecode FRAMES / the real rate (23.976 A7 IV: 12:33:25:19 = 45251 s, not 45205 s), the sequence starts at the
  first timecode, NO midnight wrap (his A7S III timecode was set by hand from 00:06:36). projectsetup.tc_seconds does
  the 1000/1001 rule; sync_time(i, use_tc): when any clip has a timecode only timecodes are used, clips without one
  (drone) go at the end (a clock cannot be compared with a hand-set TC); the old clock + 05:00 wrap only when no clip
  has a timecode. The sequence gets <timecode> = first clip's TC (_seq_tc). Ours vs his: every clip within 0.02 s.
  Chronological mode unchanged.

## v3.12.0: Long Film v2 (BETA) + Selection / Multicam split (owner: "change nothing else, work only on v2")
- Menu: Card Offload, Create Project, Selection, Multicam (two Dashboard(kind) pages, each creates its own project type;
  the project pages go back to their own page), Long Film, Long Film v2 (BETA badge, same box as NEW), Teaser Studio, ...
- Long Film v2 = longfilm2.py + LongFilm2Page / _LF2Worker (projects store.app["long2_projects"] / "long2_current", heavy data
  in the project blob <id>.analysis.json: result + analysis cache). Input: HIS labelled sequence (Create Project,
  chronological or timecode) exported as XML; only labelled cameras count; recorder = sound-only files in the sequence.
  Colours (v2 ONLY, the old Long Film / Teaser Studio keep theirs): Blue groom + Rose bride (one part, chronological),
  Teal first look (longfilm.firstlook_layout, synced only), Forest vornic (switch ON/OFF, exactly 2 cameras,
  longfilm.vornic_cut: V1 main whole, V2 second whole clips OFF, V3 cut-ins), Brown church, Yellow venue, Purple couple,
  Violet drone = Auto selection (core.auto_segments thr 60, min cut 2 s, on core.analyze(path, a=, b=) of the range);
  priest = Brown clip with a still run >= 60 s (moving_mask, blips <= 1 s), speech >= half the time, one same face
  (faces.py, 5 frames; skipped if the model cannot load) -> kept WHOLE; Iris / Cerulean party = sync.run_sync of the
  party files on the recorder (else the longest party clip) + director.build on every labelled party range as its own
  clip (key path#a-b, offset = file offset + a), party settings longfilm2.PARTY (3 / 120 / 50 / 65, 1 bar, accelerate,
  editable per project), SyncMap with Slower cuts zones (HORA). Tan + other colours ignored.
  Camera A = camera of the first clip on the lowest video track (V1 timecode / first camera chronological); part order =
  order of the colours on camera A, then DEFAULT_ORDER. Chronological = timeline (timecode layout) else creation time /
  time of day of the files. Export (longfilm2.export_xml): ONE 25 fps 1920x1080 sequence, other sizes Basic Motion scale
  to fill (4K 50 %, non-16:9 fit), every camera its own audio tracks (projectsetup.groups / _file_xml / _track_attrs),
  recorder last under the party span, links = position in track, a marker per part (app language).
  Tested on a synthetic wedding (/home/claude/lf2: gen.py, mkxml*.py, run.py, ui.py): timecode + chronological +
  no recorder + vornic off; check_xml clean; RO scan clean. NOT tested on real footage.

## v3.13.0 (his 2nd real party: Alex & Andreea, a74 static 4K + fx3 + fx6 handheld; "jumping crowds break it")
- MEASURED on his footage (4 min of the dance analysed on his Mac through the device shell, 48 frames judged by eye):
  director.sample_quality took handheld cameras dancing with the crowd for broken shots: the whole-frame shift (gx/gy)
  follows the jumping people (jitter 13-95 px on GOOD frames -> stability 0) and core.moving_mask's frame-difference
  rule marked 55-60 % of the party as "camera moving" (x0.15) -> handheld ~10 vs static ~110; his edit at Handheld 100
  was 66 % a74 (fx3 14 %, fx6 21 %). New director quality (director only, Footage Selection untouched): Handheld =
  ROBUST shift (sx/sy block median, med3) S = 1 - (sp - 5) / 10, sharpness relative to the camera's own median lap
  (refs[ci] = median lap of that camera in this master; F = min(focus_vec, lapr / 0.6)), darkness (E also <= (mean -
  15) / 25), whip pan / blur = sp > HAND_WHIP 14 or lapr < 0.4 -> x0.15; NO frame-difference move rule. Static =
  STATIC_W 0.8 x the old formula + the +10 activity bonus; only a real pan (sp > MOVE_PX) is x0.15. On his 4 min:
  good handheld 46-100, bad 2-25 (2 dark wides ~50); shares a74 / fx3 / fx6 at slider 50: 57/20/23 %, 60: 35/38/27,
  100: 8/56/36 (old 50/23/27); all 9 bad moments avoided. Old analyses stay valid (same raw fs): Auto Edit again.
- Footage Selection "Keep every good frame" (settings keepall, default ON, switch under Cut out camera moves;
  core.auto_segments(..., keep_all) + _kept_moves): every second of a camera move is kept when its median lap >=
  KEEP_MOVE_SHARP 0.45 x the clip's still parts and mean >= KEEP_MOVE_DARK 25 (kept moves = separate segments, so a
  move between two people is its own clip); a short good piece survives when its run of touching kept pieces reaches
  the minimum cut, or the clip is shorter than 2 x min cut and the piece >= 1 s. His church (500_SERJFX63249, 150 s):
  kept 66 -> 119 s at thr 60, good moments 1/14 -> 12/14, blurred 0/4 -> 2/4 (owner prefers keeping too much).
  Threshold slider now 0-90. Long Film v2 still calls auto_segments without keep_all (owner: v2 later).
- Card Offload Backup: offload.backup(root, backup_dir) = offload() of the whole wedding folder into
  backup_dir/<wedding name> (verify, skip identical, " (2)", dates, _backup_report.txt); BACKUP section (Choose + Back up
  now) and the option "At the end, copy the whole wedding folder to the backup drive too" (cfg backup / backup_dest);
  _BackupWorker; Offload _busy includes it (queue).
- Analysis files of this investigation were written in his Documents/_mmm_analiza (the device shell cannot delete).

## v3.13.1 (the long test on his laptop: Alex & Andreea, 3 cameras)
- Analysed on his Mac (device shell, 3-min chunks): the night party C2053 (a74) + C9738 (fx3) + 500_SERJFX63321 (fx6)
  over their whole overlap (~20 min) and two day stretches (2 x 16 min, C2048/C9729/63283 and C2049/C9730/63299).
  director at Handheld 100, minshot 2: night old a74 44 % -> new 10 % (fx3 47, fx6 43), day a74 30-36 % -> 9-15 %.
  Every chosen shot of the new edits looked at (middle frame): night 188 shots, ~25 "meh" (dark crowds, backs,
  silhouettes, mostly fx6), no whip pan / blur; day 221 frames, ~20 meh (people passing in front, ceiling, backs).
  Short close-ups of people jumping (2-3 s) are in. Face detection (YuNet, 2 fps) was tried as a bonus: it only moved
  the time on judged-bad stretches 12.1 -> 11.5 % -> NOT added (needs a re-analysis for little gain).
- New rule director._resting: a handheld camera put down (2 s median frame diff < 4 and shift < 0.5) -> x0.15. His
  FX6 lying on a table (63299, src 79-97 s) scored 99 and was used for 21 s; in 52 min of footage only that stretch
  matches. Old analyses stay valid.

## v3.14.0 (his first real Long Film v2 test: Alex & Andreea, "the party is not cut like Multicam, the sound is cut")
- His export (money test - Long Film v2.xml) showed: party part 840 min long, only 229 min covered. Cause: his sequence
  had TWO recorders (tascam 260823_019x_3.wav + zoom 230826-*.WAV, the zoom's clock a year off) and v2 used all 8 files
  as masters -> sync.master_starts laid them out hours apart. Now longfilm2.party_inputs works like sync.classify: main
  recorder = the sound-only FOLDER with the most hours (tascam), sorted by name; other sound folders = extras, synced like
  clips (run_sync groups "rec:<folder>") and put WHOLE on their own audio tracks (("rec", j) keys).
- Party audio like the Multicam export: video cuts per camera on its own track WITHOUT sound; every camera's sound =
  each synced labelled party range WHOLE (party_layout audio items (t0, path, in, out, key, label)), clipped to the party
  span; recorder + extras whole. export_xml rec items take an optional key + label.
- Party ALWAYS last (load: his 8 morning Iris clips on camera A put the party before the church and the venue after it).
- SelectsMap(groups) + SelectsMap.GROUPS_V2: the Long Film v2 page draws its sequence (camera A every moment, camera B,
  C/D, drone, recorder "Sound only", no colour hatched); PR_LABEL + Forest / Cerulean / Tan / Sound. The v2 right column
  is a scroll area now.
- Progress (owner: "nothing shows in real time, 2:50 left jumps to 2:10 after 40 s"): EtaClock (app.py) = elapsed ticks
  every 0.5 s (QTimer in ProgressPanel and AnalyzingPage), time left smoothed (0.7 / 0.3) and counting DOWN between the
  job's reports, "almost done" under 5 s. Every progress panel uses it.
- Footage Selection "Party footage" switch (settings party, default OFF, Yes / No popup "Are you sure you are giving me
  party footage to select?" when switched on; No puts it back off). core.party_quality = the director's handheld judgement
  (robust shift, sharpness relative to the clip, darkness, whip pan > PARTY_WHIP 14, blur < 0.4, camera put down x0.15);
  auto_segments(..., party=True): holds split only by whip pans, 1 s windows kept when mean quality >= thr, no kept
  moves. OFF = exactly the old selection. On his night party (49 min / camera): of Multicam's picked frames old kept
  fx3 61 % / fx6 73 %, party 77 % / 84 %; fx3 303 shots instead of 1419 pieces.
- Multicam sequence size stays the first camera's (4K stays 4K): owner does NOT want 1920x1080 there.
- His friend's "longv2.xml" (Diana si Vasi, 24 fps 4K, Song · BPM markers, labels per camera) was an OLD Multicam export,
  not Long Film v2.

## v3.15.0: Long Film v2 "complete version" (owner: from Create Project to the XML with little human work)
- AUTOMATIC mode (daymap.py): an XML without any colour, or the WEDDING FOLDER itself (longfilm2.folder_xml: the Create
  Project chronological sequence made in the worker, every camera + drone, then the sound folders at the end; a recorder
  take written as several files (Tascam _3 / _4 / _MIX) -> one file per take, MIX preferred: _one_per_take). In build():
  longfilm2.auto_moments = 1. every clip with sound synced to the recorder (main = folder with most hours) -> every
  camera's clock error (median, conf high) relative to camera 0; own clock = ctime when every clip of the camera has it,
  else mtime - dur; 2. faces of 5 frames per clip (faces.Faces); 3. daymap.classify -> colours (p["label"], p["kind"],
  p["t"] = common clock; chrono() sorts by p["t"]); part order = order of the day, party last; the sync is reused by
  the party step. daymap rules (MEASURED on Alex & Andreea fx6 vs his labels: 130/146 = 89 %): scenes = gaps >= 15 min;
  church = first cluster of long clips (>= 150 s, >= 900 s together, <= 15 min apart) + short clips 5 min before /
  10 min after; groom = face in most clips of the first scene, bride = most clips of the next scenes (excluding groom);
  morning: groom / bride face, else first scene = groom; both = Teal; long morning clip = Forest; after the church (its
  first scene, then until a 40-min break): no faces = Yellow (venue had 0 faces in 14/14), faces = Purple; then party,
  a party scene with the couple in >= 40 % of >= 4 short (< 40 s median) clips = Purple (sunset session); drone =
  DJI / mavic / drona. Misses: his 8 "fetching the bride" clips (labelled Iris, app says Rose), 3 Tan interviews.
  His clocks: fx6 mtime coherent, fx3 ~2 h behind, a74 a day off, lav mtimes = copy time, tascam BWF vs mtime differ.
  tools/daymap_check.py (synthetic day, >= 95 %) runs in CI.
- Getting ready alternates groom / bride (longfilm2.alternate = longfilm.interleave_blocks without re-sorting: one clock).
- Integrated editor (app.FilmEditor + _ShotList + _ThumbWorker): selection parts (ready, church, couple, venue, drone) as
  rows of thumbnails (<data>/thumbs, ffmpeg frame at the middle of the shot); drag to reorder / move between parts,
  Delete / right-click remove, Move to; Blue / pink frame = groom / bride. Saved as p["edits"] = {part: [shot keys
  "path|a|b"]} -> longfilm2.apply_edits in assemble(edits=); cleared on every Build. info["keys"] = part keys.
- Colour (colour.py + card 3 "Colour" on the v2 page, p["look"] + store.app["look"] default): his LUT as Lumetri
  Creative Look (template = his own Lumetri from the selects XML: assets/lumetri_filter.xml + assets/lumetri_look.xml;
  the Look LUT path replaced in the blob (NOT the empty Input LUT), param 24 = UTF-16 base64 path, __Intensity, the
  embedded LUT hash removed, Highlights -36 of his template reset to 0), optional second LUT = second Lumetri, Crop
  effect 10 % top / bottom; written on EVERY video clip of the v2 export (export_xml(look=)). TESTED IN HIS PREMIERE
  2026 through computer use: an ADJUSTMENT LAYER in xmeml (exactly as Premiere exports it) imports as an opaque
  "Black Video" clip -> never write adjustment layers; per-clip Lumetri + crop import fine. assets/ is bundled
  (PyInstaller --add-data assets; colour._ASSETS uses sys._MEIPASS).
- Analysis material of Alex & Andreea kept in /home/claude/day (probe.json, th/ th640/ thumbnails, faces.json, score.py)
  and on his Mac in Documents/_mmm_analiza/day.

## v3.15.1 (his test of v3.15.0 on Alex & Andreea, labelled XML, Build ~1.5 h: "getting ready good, venue not quite")
- He first ran v3.12.1 from the mounted DMG (never copied to Applications): always check the version first.
- BUG: assemble() reused the name `edits` for the director's party edits, so the editor's changes were NEVER applied
  (user_edits now). The editor is a Premiere-like Timeline (app.Timeline in FilmEditor): one track, clip width =
  duration, repeated thumbnails, label colour, part bands + ruler, drag to a blue insertion line (joins the part under
  it), Delete, Swap (2 selected), right-click Move to, Undo / Redo stack (Cmd+Z / Shift+Cmd+Z), zoom slider + Cmd+wheel.
- Party (his export: 467 min long, 228 min of cuts, empty 121 / 65 / 23 min): party_layout drops stretches where no
  camera filmed longer than PARTY_GAP 30 s -> PARTY_PAUSE 2 s; audio (cameras, recorder, extras) split per stretch.
- Alternative angle in v2: director's e["alt"] (handheld shots only) on the track above the cameras, clips switched off.
- Venue: his short labelled clips (63257-61, 3-5 s) were dropped by the Auto selection -> labelled clips <= SHORT_WHOLE
  6 s are kept whole (labelled mode only; not in automatic mode).
- Not done yet: the drone part at Alex & Andreea is the fireworks (mavic doar artificii, at night) but goes before the
  party; Lumetri effect name is empty in his template (<name></name>) - check that the look shows in Premiere.

## v3.16.0: the editor as a real mini Premiere (owner: "several video / audio tracks, move one up, another in its place,
## preview video + timeline, same principle as Premiere")
- editor.py (new): Editor dialog = Program monitor (FrameReader: ffmpeg frame under the playhead, newest request wins;
  Play = QMediaPlayer + QVideoWidget + QAudioOutput playing the TOPMOST visible clip, source switched at every edit,
  seek applied on LoadedMedia; no Qt Multimedia -> still frames) + transport (Space, Left/Right frame, Up/Down edit,
  Home/End, timecode 25 fps) + tools (Selection V, Razor C, Snap S, Undo/Redo, Delete, Ripple delete, zoom, Fit \) +
  TimelineView (custom painted, own horizontal scrollbar, ruler with part markers, V1..Vn + one free track, audio
  lanes per source (camera sound / recorder / extras), clips with label colour and pictures along them (ThumbReader,
  <data>/thumbs), linked sound drawn on its lane and moved with the picture, eye = hide video track, M = mute lane).
  Model: items in seconds; move (time + video track) with Premiere OVERWRITE (covered clips trimmed / split /
  removed, by video track or by audio lane for sound-only clips), trim edges (within the file), razor, delete /
  ripple delete (only when nothing else is in the gap), undo / redo of every step (300), snapping (8 px) to edges,
  playhead, markers.
- longfilm2: export_xml split into _ents(parts) + _write(ents, ...); timeline(parts) = the whole film as editor items;
  export_timeline(tl, infos, out, name, look, hidden, muted) (hidden video track -> clips off, muted lane -> audio clips
  off). Round trip timeline -> export is IDENTICAL to export_xml (tested). The page keeps p["timeline"] / hidden /
  muted, Export XML uses it, Build / new footage clears it. The old row editor (FilmEditor / p["edits"]) is gone from
  the UI (apply_edits stays in assemble for old projects).
- Build: Qt Multimedia is no longer excluded (PyInstaller --hidden-import PySide6.QtMultimediaWidgets). In the sandbox
  QAudioOutput hangs on PipeWire: tests set MMM_NO_PLAYER=1. Real playback NOT testable here (no screen / audio).

## v3.16.1
- Owner: "you cannot go back into the editor after Save / Cancel, do I have to Build again?" No: the build result is in the
  project blob and the edit in p["timeline"], so "Edit the film" (now "Continue editing" when an edit is saved) reopens it,
  also after a restart. The editor now saves WITHOUT closing (Save (Cmd+S), on_save callback -> _remember), "Save and close",
  "Close" / window X asks Save / Don't save / Cancel when dirty (snapshot compare), "Back to the automatic film" asks first.

## v3.17.0 (owner: "the editor is not as fluid as Premiere"; "one button for the whole process, for overnight")
- Editor speed (measured on a synthetic 3000-cut film + 30 recorder files, /home/claude/perf/bench.py): rows() was rebuilt
  for EVERY clip (tracks_v scans all items) -> hover 853 ms, whole-film paint 1060 ms. Now TimelineView._geo caches the
  row layout keyed on Model.rev (bumped by push / undo / redo), rect_of / audio_rect are dict lookups, hit() looks only at
  clips under the mouse in time, thumbnails are scaled once into QPixmaps (self.scaled, device pixel ratio), clips < 4 px
  are plain bars, undo snapshots copy clip dicts (no deepcopy). After: hover 0.2 ms, whole-film paint 30 ms, drag step
  4.6 ms, undo 4 ms. Monitor: -hwaccel videotoolbox (core.decode_flags, when the setting is on) + the last 240 frames
  kept in memory (FrameReader.cache).
- Multicam "Sync + Auto Edit" (primary, b_all): run_all -> sync, and on_done starts _auto_for(p) for the SAME project
  (_chain = project) without waiting; Sync / Auto Edit stay as separate outlined buttons. class Awake = caffeinate -i -w
  (always terminated and waited) during the chain and during the Long Film v2 Build (overnight). Tested headless:
  sync -> analyze -> edit, buttons Cancel while chained, awake released.

## v3.18.0 (owner: "a separate Sync in the menu"; "everything perfect in DaVinci Resolve too: Export for DaVinci / Premiere")
- Sidebar "Sync" (after Selection): Dashboard("sync") lists multicam projects with p["sync_only"] (Store.new(name, "sync"),
  badge SYNC); Multicam lists the others. The same MulticamPage: _mode_ui() in sync-only hides Auto Edit, Sync + Auto Edit,
  the Auto Director panel, the zones card and the map's Auto edit row (SyncMap.show_edit, no zone drawing), Sync is the
  primary button, back link "← Sync"; "Auto Edit in Multicam →" (to_multicam) clears sync_only (sync kept).
- resolve.py convert(src, out): removes Basic Motion (effectid basic: Resolve fits clips itself with "Scale entire image to
  fit"; Premiere's 50 % on 4K came out a quarter size) and Lumetri; a <project> (Create Project bins) is unwrapped to its
  sequence, every <file> complete at first use, masterclipid dropped. Names / times / tracks / links / markers / labels
  untouched. NOT verified in a real Resolve (none in the sandbox; the owner's Mac was not reachable): checked with
  story.check_xml on every converted export (Long Film v2, Create Project chronological + timecode, multicam).
- ExportPair (Export → Premiere | Export → DaVinci) replaces Export XML on Multicam (header + right panel), Teaser Studio,
  Long Film, Long Film v2; export(target) -> for_target(out, target), default file name "<name> (DaVinci).xml"
  (resolve.name_for). Footage results: the existing Premiere Pro / DaVinci Resolve choice now converts too. Create
  Project and the Transcribe story XML write the "(DaVinci)" copy next to the Premiere one automatically.

## v3.18.1 (owner: "DaVinci only when asked, with its own check and timer; Premiere untouched; info points")
- Premiere exports do nothing extra. Export → DaVinci = DaVinciCheck dialog (_DvJob thread, ProgressPanel, Cancel):
  resolve.make = convert (Basic Motion -> counted as scale, Lumetri + Crop -> colour, project unwrapped, every clipitem
  renamed to its file name incl. ALT clips) + verify (one sequence, frame rate, story.check_xml links / complete files,
  no Premiere-only effect left, names = file names, in < out, end-start = out-in, out inside the file, every file on
  disk -> warning). Report + notify ("Ready for DaVinci Resolve" / problems). tools/resolve_check.py checks both in CI.
- Create Project and the Transcribe story no longer write the DaVinci copy automatically: davinci_tick ("Also for
  DaVinci Resolve", cfg["davinci"], default off) -> for_target(dv, "davinci", src=premiere file).
- only_note(text) = blue "ⓘ" line under options that work in one program: Long Film v2 Colour card (Premiere only),
  Create Project bins / Open in Premiere Pro (Premiere only).

## Versions (owner, v4.0.0): a feature release = next minor (v4.1.0 ...); after x.9 comes the next MAJOR (v4.9.0 -> v5.0.0),
## never x.10+; small fixes only = patch (v4.0.1).

## v4.0.0 (his list after v3.18.1, his test on Alex & Andreea in the automatic mode)
- Sliders: SliderRow's blue value is a ValueBox (QLineEdit): click, type, Enter / click away (clamped lo..hi), Esc cancels.
- Long Film v2 "Clip colours" card (ColourCard, card 4; Party is card 5): switch off = defaults; on = a colour per moment
  (longfilm2.MOMENTS) from PR_COLOURS (Premiere labels) or DV_COLOURS (Resolve clip colours), p["colours"] = {on, show,
  premiere: {}, davinci: {}} (+ store.app["colours"] = last used). kinds_for() = label -> moment used by load() (his
  Premiere colours + DaVinci names + defaults not given away); labels_out(c, target) -> {moment: colour} written by
  _ents / timeline / export_timeline (items keep "kind"; party sound via _relabel). DaVinci reading clip colours from an
  xmeml is NOT verified.
- "Build + Edit" (b_be, primary): build, then _after_build (QThread.finished) opens the editor if the Build ended well.
  "· Long Film v2" label removed from the header so 5 buttons fit at 1280 px in Romanian.
- Two jobs at once (owner: "errors"; not reproduced here, his app.log is not reachable): core.slot() = ONE app-wide pool of
  decoding places (core.set_slots(max(2, jobs)), re-entrant per thread) around core.analyze / analyze_range /
  sync.audio_pcm, and analyze / analyze_range decode again in SOFTWARE when the VideoToolbox decode fails or stops early
  (< 80 % of the frames). Tested: Selection analysis + Multicam Sync + Auto Edit together, all pages visited, 0 errors.
- Honest progress: longfilm2.Stages = every Build step gets a share of 0..1 from its expected work (_weights: probe, auto
  sync, faces, analysis seconds / 15 / jobs, priest, first look, vornic, party sync, music), replan() when the automatic
  mode knows the moments; the bar never goes back (auto_moments used to run to 46 % and the analyses started again at 5 %;
  the folder step 0-5 % then the Build restarted at 0). _LF2Worker maps folder 0-4 %, Build 4-100 %. EtaClock: no reset on
  small drops, f monotonic, time left = 0.6 x speed of the last 120 s + 0.4 x whole job, smoothed 0.75 / 0.25, "estimating
  the time left…" until 2 % and 8 s. Multicam Auto Edit progress weighted by clip LENGTH (+ per-clip progress, music after);
  footage analysis weighted by file size.
- Editor: box selection (drag on empty space; click alone = playhead; Shift / Cmd adds), Cmd+A; shortcuts are actions
  (editor.ACTIONS / DEFAULT_KEYS, Ripple delete = X by default), ShortcutsDialog (QKeySequenceEdit per action, a key moves
  from the action that had it, Reset all), saved in store.app["editor_keys"]; buttons show the current key.
- First look synced: longfilm2.firstlook_sync (v2 only; longfilm.firstlook_layout untouched for the v1 score): sound of the
  WHOLE files via sync.audio_pcm (loudest single channel: longfilm._clip_audio downmixed with -ac 1, the FX6's first channel
  can be empty), else the common clock p["t"] of the automatic mode; in the automatic mode every other camera's clip
  overlapping a first-look clip in time joins the first look. His v3.18.1 export had 2 Teal clips one after the other.
- No gaps: his v3.18.1 export had 442 one-frame gaps on V1 (ends rounded from durations): _ents / export_timeline now round
  start AND end from absolute times. Party holes (49-503 frames) removed: PARTY_GAP 0.04 s, PARTY_PAUSE 0.
- Tripod camera: static_cams() = median clip >= STATIC_CLIP 600 s (a74: 7 clips, median 24 min; fx6 11 s, fx3 91 s);
  in the automatic mode its clips are only Brown or Iris (his a74 got 44 Purple selections).
- Menu "Sync" -> "Synchronize" (RO "Sincronizare"), badge SYNCHRONIZE.
- i18n scan (/home/claude/i18nscan/scan.py ro|en: every page, project pages, editor, shortcuts, DaVinci check): RO and
  EN clean (only loan words / file names left).

## v4.1.0 (his list after v4.0.0: editor like Premiere, a friend's Syncaila XML, couple / first look in the automatic mode)
- Editor (editor.py): Ripple delete (X) = Premiere: Model._cut_range(a, b) takes the selected span out of EVERY track
  (later clips move left, clips crossing it are split / trimmed, recorder lanes cut at the same place, markers moved);
  a click on an empty gap selects it (blue box, TimelineView.gap via _gap_at) and X / Delete closes it (Model.ripple_gap).
  The playhead line can be grabbed in the timeline (4 px); dragging the playhead / a clip / the box near the left / right
  edge scrolls the timeline (edge QTimer 30 ms, 4-34 px per tick). Zoom (buttons, slider, keys) anchors on the playhead,
  centred when it is off screen; Cmd+wheel on the mouse. Playback: the PLAYER is the clock while the top clip plays (no
  more loop of the same 2 s after a click far into the film); waits while a file loads, wall clock after a 4 s load /
  1 s stall / end / invalid media, a player that jumps back > 3 times is dropped (still frames). MMM_NO_AUDIO=1 in tests.
- Synced XML (Syncaila etc., layout "timecode") without a recorder: the party used the longest party clip as master ->
  only clips overlapping it (the friend's XML: one camera, 30 min of 4 h). Now longfilm2.timeline_sync = the timeline is
  the reference (virtual master path None, like Multicam Import XML, no music map); with a recorder, timeline_fill gives
  clips the sound could not place their timeline place. Automatic mode: use_timeline (timecode layout and >= 3 h span,
  or no recorder) -> timeline places are the common clock (no clock shifts). static_cams ignored when EVERY camera has
  long clips. Not tested on the friend's real XML (not received yet).
- daymap: after the church a clip with faces is Purple only when the groom or the bride is seen (other faces = guests ->
  Iris); without a known groom / bride the old rule. tools/daymap_check has guest clips now (71/71).
- First look (automatic mode): join_firstlook replaces the clock overlap: other cameras' groom / bride / Teal clips within
  FL_WINDOW 30 min of the first look (by the clock) are synced by SOUND to the main first-look files (sync.sync_clip on
  MasterIndex of the whole files); joined only with conf high and an overlap >= min(5 s, half the clip). Stage
  "auto_fl". Synthetic test: the right clip 8 min off by the clock joined, a clip 10 s away by the clock with other
  sound rejected.

## v4.1.1 (his friend's R&A export of v4.0.0: DaVinci user, filmed differently)
- Measured on the friend's "R&A - Long Film v2 (DaVinci).xml" (automatic mode, no recorder, cameras RAZ / ROX RS-MAIN /
  RX-MAIN 4K50 + OSMO): 6 h 25 min sequence, church 27 min, "couple" 1608 cuts = 5 h, venue 15 min, "drone" 43 min = the
  OSMO, NO party at all. Causes: no getting ready -> no groom / bride faces -> any face = Purple; he filmed without a 40-min
  break -> the whole evening stayed "after the church"; daymap.is_drone took DJI_ names in the OSMO folder for the drone.
  Fixes: is_drone never for OSMO / Pocket / Action / GoPro / Insta360 / Ronin folders (GIMBAL_RE); couple / venue window
  = until the first 40-min break AND at most CV_MAX 2 h after the church (scenes split there); no getting ready -> the
  couple = top faces of the hour after the church (COUPLE_LOOK), plus the church when < 6 clips with faces there.
  tools/daymap_check scenario 2 (no getting ready, no breaks, OSMO): 82/82; the old daymap fails it.
- No recorder (any layout but a synced timeline): party_inputs uses ALL party clips of the camera with the most party
  sound as masters (sorted by its clock), not only its longest clip; auto_moments syncs to them too (clock shifts without
  a recorder); masters placed by themselves (mpaths). Synthetic test: two clips of camera B, each under a different clip
  of camera A, both synced (before, one was lost).
- The crash: his XML imports WITHOUT a crash in the owner's DaVinci Resolve Studio 20 (media offline, 2035 clips,
  6:25:31); structure checked (links, overlaps, durations, file ends, ids): clean. Not reproduced; asked for the friend's
  Resolve version and whether the disk was connected.

## v4.2.0 (owner: "everything at once": Premiere | DaVinci switch, AI for the moments, the vornic, no friend-specific rules)
- The v4.1.1 diagnosis of R&A was WRONG: the friend HAD filmed getting ready; daymap took the getting ready for the church
  (first cluster of long clips: two long morning takes). Removed: CV_MAX (2 h cap) and "couple from the church". The
  v4.1.0 guest rule (faces without a groom / bride match -> Iris) cost 6 of HIS couple clips (face match misses small /
  profile faces): without AI the cv window is v4.0.0 again (faces -> Purple); with AI only clips the AI sees as party -> Iris.
- scenes.py: SigLIP 2 (the AI test model, ai.ensure_model / ai.Siglip) judges 3 frames per clip (20/50/80 %, ungrade):
  ready / church / couple / venue / party / drone / speech (+ unclear). longfilm2.scene_judgements (cache key
  scenes.cache_key in the project's analysis cache, stage "auto_ai"); {} when the model cannot load -> old rules.
  daymap.classify(clips, faces, ai, speech): church = daymap._church_by_ai (runs of church clips, <= 3 others inside,
  earliest run with >= 50 % of the biggest run's time, trimmed to SURE church clips >= AI_SURE 0.9; no HEAD expansion);
  drone: a DJI_ file outside a drone folder only when AI drone >= 0.35 / top (drone folders always, gimbal folders never);
  cv window also ends when 4 of 6 clips in a row are AI party; sunset-couple rule skips AI party clips.
  Measured on HIS Alex & Andreea with a CLIP ViT-B/32 stand-in (tidy app's quantized ONNX, /home/claude/aitest: proxy.py,
  emb.json of his th640 thumbnails, real.py / real2.py / cmp.py): fx6 v4.0.0 130/146 -> no AI 130 -> AI 132; fx6+fx3
  149 -> 154/188 with AI + sound; church: 0 misses. SigLIP 2 itself NOT runnable here (HF blocked in both sandboxes).
- Vornic (daymap._vornic, only when the sound is measured): a continuous take >= VORNIC_TAKE 120 s with speech share
  >= SPEECH_FRAC 0.8 (music.py regions, speech = not music / silence) that another camera films too (a take of 120 s
  overlapping >= 60 s), or other-camera clips >= 30 s inside it when the AI sees a speech. MEASURED on his footage (device
  shell on albastru, Documents/_mmm_analiza/code/speech_aa.json): speech share alone is useless (every talking clip ~1.0),
  his 4 Forest clips = 2 simultaneous fx6+fx3 pairs of 3-5 min -> 4/4 (+ the 11:30 pair he labelled Iris); the lone
  4-min getting-ready take 63181 is no longer the vornic. longfilm2.speech_shares on the morning clips (stage
  "auto_speech", second classify pass); join_by_sound(kind, label, cand_kinds) = join_firstlook generalised, also for
  the vornic. tools/daymap_check: his day (no AI = v4.0.0), with AI + sound, church in short clips, R&A style.
- DaVinci: TargetSwitch top right ("I work in: Premiere Pro | DaVinci Resolve", store.app["target"], set_target /
  target() / on_target listeners); ExportPair = ONE button "Export XML → Premiere / → DaVinci" calling slot(target());
  Footage results follow the switch (its own buttons disabled); Create Project / Transcribe write the DaVinci copy when
  target() == "davinci" (davinci_tick is now an info line); Open in Premiere Pro hidden on DaVinci.
  resolve.rewrite = the DaVinci file written FROM SCRATCH like Resolve's own FCP7 export (reference exported from his
  Resolve Studio 20, /home/claude/dv/ref.xml): sequence only, clipitem ids "<file> <n>", file <timecode> = the camera's
  real timecode (resolve.file_tc via ffmpeg), plain mono audio tracks (sourcetrack = channel), links re-indexed, labels,
  markers; no exploded tracks / premiere attributes / ppro* / filters / bins / generator items. resolve.make uses it.
  KEY FINDING (his Mac, Resolve 20): his own Premiere XML imported into Resolve went OFFLINE ("no overlap between target
  timecodes 00:00:00:00 and file timecodes 23:08:00:36"); the rewrite with file timecodes came in ONLINE (church selects
  414 clips, and v4.0.0 long 2 = 4645 clips with party + recorder). The friends' Resolve 21.2 crash is not reproduced;
  most likely the Premiere-shaped file / timecode mismatch. tools/resolve_check tests the rewrite.
- longfilm2._write: overlapping pieces on one video track are trimmed / dropped (his v4.0.0 export had 3 overlapping
  C2048 pieces on the a74 track; Resolve logged "Trimming item ... overlaps").

## v4.2.1 (his Premiere friend's Denisa & Cornel v4.2.0 export: "the party is not synced, only a part")
- His export: recorder Tascam X8 written as 260711_0190_3-4 + 260711_0190_MIX + 0191_3-4 + 0191_MIX; v2 laid all 4 one
  after the other (the old take regex only knew _<digit> / _MIX, not _3-4, and party_inputs never de-duplicated in the
  labelled mode) -> the cameras synced to either copy landed in different halves (A7iv8619/8620 after 8622, the entrance
  in the middle of the party, the first dance on one camera). sync.one_per_take(files, dur, start) (TAKE_RE: digits,
  3-4, MIX, LR, L, R, ST, Tr1, TrLR; same length +-2 s; merged only when a name is a track or they started together, so
  Lav_01 / Lav_02 stay two takes; MIX / LR kept) is now used by longfilm2.party_inputs (masters + extras),
  longfilm2.folder_xml and sync.classify (Multicam masters / extras, clocks as start).
- longfilm2.camera_order_check (Syncaila's rule) after the party sync: per camera, clips on the common timeline; the
  longest (then most compact) chain whose times grow with the file numbers without overlapping is kept, the rest ->
  conf "low" (not in the multicam). tools/party_check.py (CI) + an end-to-end synthetic test (/tmp/dup: two takes as
  _3-4 + _MIX copies, 4 A7iv clips -> 2 masters, every clip at its true place, 0 out of order).

## v4.3.0 (his list: SSD eject, how long it took, tracks per camera, 28 August labels, false party syncs)
- Disk eject: the Long Film v2 editor's QMediaPlayer kept the last played file open (dialog parented, never deleted) ->
  "albastru couldn't be ejected because MoneyMakingMachine is using it". done() sets the source to QUrl() and the page
  deleteLater()s the dialog. Rule: never keep a media file open after a dialog closes.
- notify(text, took=key) + job_mark(key) at the start: "· took 1 h 05 min" (dur_text) on Long Film v2 Build / Build+Edit,
  Multicam Sync / Auto Edit / Sync + Auto Edit (one clock for the chain) / Import XML, Long Film, footage analysis, Card
  Offload, Backup, Create Project, Transcribe; toast 15 s; > 60 s on a Mac also osascript "display notification"
  (Notification Center; MMM_NO_SYSNOTE=1 in tests). Every new long process: job_mark at start, took= at the end.
- Video tracks: director.video_order(cams, foot) = static camera(s) on V1, secondaries above (check / by-time cams lowest),
  the MAIN camera (handheld, most footage) on top; c["track"] (1-based) chosen by him wins. Multicam: "Track" column
  (Auto (Vn) / V1..Vn, one camera per track, kept by sync.auto_cameras across re-syncs), used by director.export_xml.
  Long Film v2 party: longfilm2.party_tracks (same rule, p["dir"]["tracks"] = {camera name: track}, drop-downs in the
  Party card; changing them with an editor version asks before dropping it). First look / vornic stacks unchanged.
- 28 August (Ciprian & Bianca, whole day at one villa; measured on his footage: 338 clips, real faces from 5 frames on
  his Mac, AI = CLIP stand-in on one frame): his "selectie" was ALL Iris (Premiere's default) -> load() now treats an
  all-Iris sequence (>= 10 clips) as unlabelled. scenes.py: second judgement WHO (bride / groom / both / none) in
  sc["_who"], cache key "scene2|" (old caches re-judged). daymap: couple_faces = top faces of the WHOLE day, bride = the
  one the AI sees in a dress (old first-scene rule kept when the AI agrees with it: lean(bride) >= 0.1 and lean(groom)
  <= -0.1); morning clip without a face match -> side_of (who >= 0.4 / both >= 0.7), else the Blue / Rose filmed within
  NEAR_SIDE 30 min (same camera first), else Yellow when nobody is there (venue / house filmed apart), else the old
  scene side; after the couple met (2 Teal within 10 min) single bride / groom shots before the church = Teal; after
  the church side_of -> Purple. _church_by_ai: the gap is measured to the end of ANY clip since the run began (a 27-min
  service take the AI saw as "party" split the church). 28 Aug: v4.2.1 rules 181/338 (bride 0/44, groom pink) -> 300/338
  (bride 44/44, groom 20/27, church 24/26); his Alex & Andreea unchanged at 154/188. tools/daymap_check scenario 3.
- Automatic order (longfilm2.auto_order): ready, firstlook, vornic, church, couple / venue by median time AFTER the church,
  party last. (v4.3.1: drone first instead of attach_drone.) Labelled mode unchanged. tools/order_check.py (CI).
- Sync verify (sync.verify_clocks, end of run_sync, Multicam + Long Film v2): per camera group the clock error implied by
  every synced clip; the biggest set agreeing within CLOCK_TOL 300 s (>= 2 clips, >= 40 %) is the truth, the others ->
  conf "low" + error "its clock says it was filmed N min later/earlier than this sound match..." (check sync track, never
  in the edit). His multicam 4.2.1 28 Aug: fx3 C9754 / C9759 (first look clips) sat in the party with clock errors 309 /
  491 min vs 867 min for every other fx3 clip -> caught. tools/party_check "clock check".
- NOT done here: running the full app on all 8 weddings of "11 milioane" in Premiere and DaVinci (each Build ~1.5 h on his
  Mac); the folder structures were checked (osmo 11 sept, gopro, drona, trash, lav (interviu pierdut), cealalta lav).

## v4.3.1 (owner: "in Syncaila the clock does not matter, even if it says 2023"; "put the drones at the start")
- sync.verify_clocks (v4.3.0) REPLACED by sync.order_check (end of run_sync; longfilm2.camera_order_check delegates to it):
  per camera group, clips placed where the SOUND put them; the longest (then most compact) chain whose places grow with
  the file numbers without overlapping (1 s tolerance) is kept, others -> conf "low", error "out of the camera's file
  order..." (check sync track, never in the edit). Clocks are only search hints now, never a verdict. _order_key: natural
  sort of the stem, a wrapped counter (9000+ and < 1000 on one camera) continues (< 5000 + 10000). His 28 Aug fx3 C9754 /
  C9759 in the party are caught by the order alone (tools/party_check).
- Automatic Long Film v2: ALL drone shots at the start of the timeline (auto_order puts "drone" first; attach_drone gone).

## v4.3.2 (owner: "the mix should not be the winner, a track; he uses auto, a friend manual"; first real v4.3.1 Build)
- Recorder takes with several files: sync.pick_track(g) by sync.TAKE_PREF = store.app["rec_take"] (Settings > "Recorder
  with several tracks": Automatic (the cleanest track) / The mix / Track 1 / 2 / 3, in name order, MIX / LR not counted).
  auto = fewest clipped samples (|x| >= 32000 in 5 x 20 s at 16 kHz mono, _clean_score cached), then the stronger
  level; never the mix unless only the mix exists. Used everywhere one_per_take is (Multicam classify, Long Film v2).
- The first REAL run of v4.3.1 on his Mac (28 Aug, automatic mode from the wedding folder, real SigLIP 2 + faces, 1 h 20 min
  Build): drone first, groom / bride shots 185 of 199 right (Blue 91, Rose 108), first look 80/80, church 334/334 Brown,
  venue 31/43, couple 51/75 (the misses are empty rooms during the couple session, Yellow). BUT the church was 53 min: two
  27-min service takes (63496, C9768) cut by the Auto selection + the priest's 12-min shot (63507) kept whole. Now in the
  automatic mode a church clip > LONG_TAKE 120 s is thinned (longfilm2.thin): ~12 % (20-90 s) in pieces <= 6 s spread over
  its selected parts, and the priest rule never keeps such a take whole. Labelled mode unchanged.

## v4.4.0 (owner: "reinvent Align for our program, keep a backup; the editor lags everywhere; editor in Multicam too;
## getting ready interleaved or one after the other")
- BACKUP of v4.3.2: branch backup-v4.3.2 on GitHub (tags cannot be pushed from Claude's sessions: 403). The classic engine
  stays in the app: sync.run_sync_classic, chosen in Settings > "Sync engine" (store.app["sync_engine"] graph | classic,
  sync.ENGINE; default graph).
- sync2.py (Align / PluralEyes idea, our own code; Align is GPLv3, never copy it): 4 kHz audio (sync.audio_pcm) ->
  landmarks = local maxima of the WHITENED log spectrum (every bin minus its median: a camera mic and the mixer feed give
  the same peaks; the first version with one peak per band missed 63568 / the osmo 11 s clip / the first-look pair) over
  +-3 frames x +-4 bins, 5 per frame, 64 ms frames -> hashes (f1, f2, dt <= 40 frames, fan-out 8) -> ALL files matched
  at once (hash groups > 60 dropped; votes per (file pair, dt), neighbours merged, >= 5 votes and >= 2 x the next offset)
  -> refine (GCC-PHAT, up to 3 loudest 10 s windows of the overlap, +-0.4 s, agree within 4 ms, sub-sample) -> graph
  solve per component (weighted least squares, the worst edge out while > 40 ms) -> masters' "start" from the graph
  (masters in one component), else clocks (master_starts) -> results like run_sync (a clip only linked to other clips:
  fail "matched other clips but not the recorder"; a master that is also a clip = offset 0) -> sync.order_check.
  MEASURED on his 28 Aug party (2 recorder takes + 48 clips + 6 intruders, 8 kHz opus copies, /home/claude/st28): every
  long clip at the same place as Align and the classic engine (within 5-50 ms), + 63573 (Align missed), 63568 right
  (classic wrong), the first-look pair 63426/C9754 matched to each other (Align too), church intruders out; 27 s vs 144 s
  classic vs 6 s Align (Rust). tools/sync2_check.py (synthetic: 5 clips < 0.05 ms error, an island pair, an outsider) in CI.
  Align itself: built here (patched 2 newer-std calls, /home/claude/ext/align), CLI JSON compared.
- Editor speed (editor.py): the static timeline is drawn once into a cached layer (key = model rev, scroll, zoom, size,
  dpr, selection, thumbs version, hidden / muted); paintEvent blits the dirty rect + overlays (playhead, box, ghosts,
  gap); set_playhead repaints only the old / new 17 px strips; thumbnails arrive -> ONE repaint per 90 ms; clip pictures
  on a fixed source-time grid (scrolling asks for the same pictures, not new ones each step); ThumbReader newest-first
  (LIFO, 160 max, dropped ones can be asked again); playhead drag = picture already in memory + key-frame decode
  (-skip_frame nokey, tag "scrub"), the exact frame 180 ms after the mouse rests; Model.top_at indexed (bisect by rev).
  Bench (/home/claude/perf/bench.py, 3000 cuts): paint 33 -> 1 ms (fit), playback frame 5.3 -> 1.3, drag 5.8 -> 3.5.
- Multicam editor: "Edit" / "Continue editing" button (MulticamPage.edit_film): _mc_timeline = cuts per camera on
  director.video_order tracks (full clips without an auto edit / for check / by-time cameras), camera sound whole
  (("cam", ci) lanes), recorder (("rec", 0)); probe cache in the blob ("probe"); p["mc_timeline"/"mc_hidden"/"mc_muted"];
  Export XML writes it with longfilm2.export_timeline(size = first video clip's size; SEQ_W / SEQ_H set temporarily);
  a new Auto Edit clears it.
- Long Film v2 getting ready: p["ready_mode"] interleave (default, longfilm2.alternate) | sequential (all of the side
  filmed first, then the other); buttons Interleaved / One after the other in the Vornic card; assemble(ready=).

## v4.5.0: the Premiere bridge (owner: "adjustment layer + crop 10 %, exactly like my WarpAutomation panel")
- His WarpAutomation (CEP panel made with Claude, v1.16.0 in his Downloads) does it inside Premiere: File > New >
  Adjustment Layer clicked through System Events (osascript from Node; Premiere has no scripting call for it), Enter on the
  dialog, then ExtendScript overwriteClip on an empty top track (qe addTracks if needed), end = last clip end, QE
  addVideoEffect("Crop"), Top / Bottom = 10. An xmeml adjustment layer still imports as Black Video: never write one.
- premiere_bridge/ (CEP bundle com.moneymakingmachine.bridge, VERSION in bridge.py = manifest ExtensionBundleVersion): a
  visible panel (Window > Extensions > MoneyMakingMachine) AND an invisible worker (UI Type Custom, AutoVisible false,
  StartOn com.adobe.csxs.events.ApplicationActivate) that STARTS BY ITSELF with Premiere (verified on his Premiere 2026).
  Both poll ~/Library/Application Support/MoneyMakingMachine Bridge/jobs every 1.5 s; a job is claimed by renaming
  .json -> .run; answer in done/<id>.json; "alive" file = ms timestamp. Job = {xml, name, adjust: {crop}}: importFiles
  into the OPEN project (no project -> the job waits), open the new sequence, adjustment layer + Crop.
- bridge.py: install() at app start on a Mac with Premiere (copies to ~/Library/Application Support/Adobe/CEP/extensions/
  MoneyMakingMachine, PlayerDebugMode 1 for CSXS 9-14, xattr -cr; only when the version differs), send(), result(),
  alive(). Settings "Premiere bridge" status + Install again. PyInstaller --add-data premiere_bridge. tools/bridge_check.py
  in CI. MMM_CEP / MMM_BRIDGE env = test folders, MMM_NO_BRIDGE=1 = no install.
- Long Film v2 Colour card: "Crop on an adjustment layer (straight into the open Premiere project)" (look["layer"],
  default on, needs look on + crop + _bridge_ok()): Export XML → Premiere writes the XML WITHOUT the per-clip crop (Lumetri
  stays per clip), then to_premiere() sends the job, `open -a` Premiere, polls (notify when done / failed / not picked up
  after 25 s / 30 min). DaVinci and unticked: crop on every clip as before.
- TESTED LIVE on his Mac (Premiere 2026, test project "MMM bridge test" in the 28 August folder): the worker started with
  Premiere without opening the panel, the job imported ADJ_TEST_C.xml, opened the sequence, Adjustment Layer on V2 over the
  whole sequence, Crop Top 10 % / Bottom 10 %. The device shell cannot write ~/Library (protected): files were copied there
  with Finder (Go to Folder) for the test. A missing-media "Link Media" dialog waits for him (offline media only).

## v4.5.1 (bug sweep before his test)
- BUG (v4.4.0): the new sync engine (sync2) put numpy float32 values in the results -> projects.json could NOT be saved
  after a Sync ("float32 is not JSON serializable"; the project's sync would be lost at the next start). sync2 results are
  plain floats now, and every save (settings.json, projects.json, <id>.analysis.json, caches) goes through _write_json:
  numpy values converted (_jsonable) and written to a .tmp file then renamed (a crash never leaves half a file).
- Multicam: the Edit button says "Continue editing" right after Save in the editor.
- Checked: every tools/*_check.py, pyflakes, RO / EN scan of every screen, Long Film v2 scripts (labelled, chrono, no
  recorder, editor, save / reopen), Multicam Sync + Auto Edit chain + editor + export, editor bench, DaVinci conversion,
  the bridge path with a fake Premiere (XML without per-clip crop, job sent, answer -> notification).

## v4.6.0 (his list after v4.5.1: getting ready, a general moments model, the civil ceremony, menu, UI; "test everything")
- Menu: "Long Film" = the old Long Film v2 (no BETA; projects keep store.app["long2_*"]); "Long Film Blueprint" (BETA, new
  LongFilmBPPage(LongFilm2Page), KEY "longbp" -> store.app["longbp_projects" / "longbp_current"]): the wedding read like
  Long Film (folder or labelled XML, same Build worker), then blueprint.build(self._pool(), bp) refills one of his finished
  long films (BlueprintBox kind "long", Auto / Blueprint buttons hidden); pool = every selected range of r["pieces"]
  (r["sel"], whole ranges for non-SELECT parts) by moment (firstlook -> couple, civil -> church, groom / bride also as
  "location" for Teal slots of his older films; the pool never uses a moment twice); Export = blueprint.export_xml.
  Vornic / party / colour cards hidden there. The old Long Film page is hidden (nav "long" hidden, projects kept).
  LongFilm2Page has KEY / BETA / DESC class attributes, _left / _cards / _card for subclasses.
- Getting ready keeps every good shot (owner: "count, not length"): longfilm2.selection uses core.auto_segments(...,
  keep_all=True) and keeps good pieces >= SEL_KEEP 1 s.
- The day model (daymap.classify_ai, used when scenes.py gives "_p" moment probabilities = SigLIP 2 zero-shot over
  scenes.MOMENTS prompts, max per moment, softmax scale 50, mean of the clear frames; cache key "scene3|"): per camera a
  monotone phase Viterbi civil0 -> ready -> firstlook -> couplem -> civil -> church -> after (PHASES emission weights;
  PH_MOVE -2, 15-min pause = cheap move; a camera's first clip starts in the phase the busier cameras reached in the hour
  before it, START_LOOK; both couple faces in a clip = -1.5 for "ready"). civil / civil0 kept only when a clip of it has
  _civil >= CIVIL_SURE 0.7 (the officer's tricolour sash), else church / ready. Cross-camera civil: clips within +-10 min of a
  sure civil clip, and the rest of the same camera scene (no 15-min pause) when it is not groom / bride (never Brown
  outside the window: w28 church follows the civil). After the couple met (couplem / after) one of them alone = couple and
  a church-like building = venue. Groom / bride sides = 2-state Viterbi + the top-2 face identities (AI votes which is the
  groom); details / rooms take the side of the nearest person clip.
  Civil ceremony = colour Mango (KINDS, MOMENTS, DEFAULT_PR Mango / DV Orange, PART "Civil ceremony"), edited like the
  vornic (longfilm.vornic_cut on st("civil"): officer camera on V1, other camera synced above, cut version on top).
- MEASURED on 4 of his weddings (real SigLIP 2 embeddings + faces computed on his SSD through the device VM, every clip
  labelled by eye from contact sheets; /home/claude/ev, his Documents/_mmm_analiza/ev): 28 Aug 317/338 (94 %), 29 Aug
  180/194 (93 %), 4 Sep 209/218 (96 %: civil in the MORNING before getting ready, no church; fx3 clock 2 h behind),
  12 Sep 181/185 (98 %: traditional day, fetching the bride with guests, church, couple with a car). Old rules on the same
  labels: 28 Aug 241, 29 Aug 79. Without faces 94-96 %. tools/daymodel_fixture.json (all 4, per clip: probabilities, civil,
  faces A / B, my label) + tools/daymodel_check.py (>= 90 % each) run in CI.
- UI: dur_text with seconds ("1 h 5 min 12 s"); StudioHub 3 cards per row, no side scroll; camera track box redone
  (QFrame#trkbox, track_row, "V{} · auto"); SyncOptions widget (engine New (recommended) / Classic + recorder take) on the
  Multicam / Synchronize page (SYNC section) and in the Long Film party card, removed from Settings; DropZone centred with
  stretches (a wrapped hint was clipped); SettingsPage.hideEvent safe at exit.
- Help (RO + EN): Long Film page (getting ready, day model, civil ceremony), Long Film Blueprint page replaces the old
  Long Film page, sync options "SYNC section of the page", seconds, 3 projects per row.
- NOT done: another wedding with a real Build in the app on his Mac (each needs his Mac awake ~1.5 h); 30 Aug, 5 / 11 / 20 Sep
  not measured (the device VM embeds ~4 clips per 45 s call).

## v4.6.1 (owner: "minimised in the Dock it went into a sleep mode, the process is very slow"; "the Osmo can have any time")
- App Nap: appnap.disable() at start (ctypes NSProcessInfo beginActivityWithOptions:reason: with
  NSActivityUserInitiatedAllowingIdleSystemSleep, token retained for the app's life; + `defaults write
  com.moneymakingmachine.app NSAppSleepDisabled -bool YES`); build.yml adds NSAppSleepDisabled + LSAppNapIsDisabled to
  Info.plist. The Mac itself still sleeps when idle unless a job holds Awake (caffeinate). NOT testable here (Linux).
- Cameras the sound could not place (not in the recorder sync's median clock errors) get their clock from what they show:
  daymap.clock_offsets(clips, faces, ai, free) = the shift (+-26 h, 1-min steps) where the clips' moment probabilities
  are most similar (Bhattacharyya, sqrt(P) dot) to the reference cameras' clips filmed at the same time (+-10 min,
  intervals); kept 0 unless better by OFF_BETTER 0.05; only for cameras with fewer clips than the reference (>= 20).
  The camera's own order is kept. On the 4 weddings: a camera moved +5 h / -9 h comes back within 0-20 min; right clocks
  stay; it also found the w29 fx3 2 h behind. Checked in tools/daymodel_check.py (CI).

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
