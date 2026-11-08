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
   uncut, on one common timeline (`sync.master_starts`), then one (disabled) audio track per camera, uncut. Renaming a camera to an existing name merges them.
   The owner's usual Premiere workflow for reference: Premiere audio sync, or timecode sync (TC set by hand on each
   camera, not frame accurate) + camera labels + "Create Multi-Camera Source Sequence", then a manual audio re-sync.
   Video analyses of multicam projects live in `<project id>.analysis.json` next to projects.json (cached by size+mtime).

## Files
- `app.py` — whole UI (dashboard, projects, footage pages, analysing page, results, multicam page). Data in
  `projects.json` under the OS app-data folder (`MMM_DATA` env var overrides it, used in tests).
- `core.py` — video analysis via FFmpeg (any format: MXF, MOV, MP4...), grading, xmeml export.
- `sync.py` — media detection, audio sync engine, camera grouping, onsets.
- `director.py` — multicam auto director + XML export.
- `make_icons.py` — builds icon.icns / icon.ico / icon.png from `icon_source.png` (run in CI before PyInstaller).
- `.github/workflows/build.yml` — builds macOS DMGs (Apple Silicon + Intel) and a Windows folder with PyInstaller on every push.

## UI style
Premiere Pro look (owner's wish): neutral greys (#1d1d1d / #232323 / #2a2a2a), pill buttons (blue #1473e6 for the main
action, outlined for the rest), dark inputs, slider values in blue. Settings > Performance shows CPU / RAM and has
"Parallel jobs" and "Hardware video decoding (Mac)" (VideoToolbox when the bundled FFmpeg has it). RAM is not the
bottleneck, decoding is: explain this if asked again.

## Rules learned the hard way
- xmeml must declare `<pixelaspectratio>square</pixelaspectratio>` or Premiere applies 109.4 % width scale.
- Sony sidecar files (M01.XML etc.) must be skipped when adding clips.
- Keep FFmpeg bundled via imageio-ffmpeg (owner does not want to install anything).
- Untested in real Premiere so far: audio tracks in the sync XML, colour labels in DaVinci Resolve.

## Testing
No real footage in CI. Generate synthetic clips with FFmpeg (testsrc2 + blur / dark / shaky crop / pan; synthetic music
master with offsets, reverb, atempo drift) and drive the UI headless with `QT_QPA_PLATFORM=offscreen`, taking
screenshots with `widget.grab()` to check layouts.
