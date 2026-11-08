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
languages in sync when features change). Sidebar header (like the owner's WarpAutomation app): big icon, MoneyMaking<b>Machine</b>, @sergiugabrielcg link, version (v2.2.0), "by @sergiugabrielcg"
linking to https://www.instagram.com/sergiugabrielcg/.

## Files
- `app.py` — whole UI (dashboard, projects, footage pages, analysing page, results, multicam page). Data in
  `projects.json` under the OS app-data folder (`MMM_DATA` env var overrides it, used in tests).
- `core.py` — video analysis via FFmpeg (any format: MXF, MOV, MP4...), grading, xmeml export.
- `sync.py` — media detection, audio sync engine, camera grouping, onsets.
- `director.py` — multicam auto director + XML export.
- `help_text.py` — Info / How to use page (HTML, Romanian + English).
- `xmlimport.py` — import of an already synced FCP7 XML for Auto Edit.
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

## Rules learned the hard way
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
