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
languages in sync when features change). Sidebar header (like the owner's WarpAutomation app): big icon, MoneyMaking<b>Machine</b>, @sergiugabrielcg link, version (v2.7.0), "by @sergiugabrielcg"
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
  energy_cuts (True). Map computed in the Auto Edit job (MCWorker._analyze) and saved in sync.masters[i]["music"].
- Sync Map "Music" row, XML markers (Song · BPM, DROP), Beat check export (click track + recorder, one sequence).

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
