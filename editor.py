"""The integrated editor of Long Film v2, laid out like Premiere Pro (owner: "exactly like Premiere: several video and
audio tracks, move a shot up, put another in its place, preview video and timeline, same principle").

  top:     the Program monitor (the frame under the playhead; Play plays the topmost visible clip with its sound)
  bottom:  the timeline: time ruler with the part markers, video tracks V1..Vn (V3 and up are free to use), audio
           tracks (one per camera's sound, the recorder, the other sound sources), every clip as long as it is, with
           its picture and its label colour.

Tools: Selection (V) drags clips in time and between video tracks (a clip dropped over others OVERWRITES them, like
Premiere), drags their edges to trim; Razor (C) cuts a clip in two. Delete lifts, Shift+Delete ripple-deletes, Cmd+Z /
Shift+Cmd+Z undo / redo every change, S snapping, Space play / pause, Left / Right one frame, Up / Down previous / next
edit, +/- or Cmd+wheel zoom, \\ fits the whole film. The eye of a video track hides it (its clips are exported switched
off), M on an audio track mutes it.

The timeline is longfilm2.timeline(parts) (seconds); Save keeps it in the project, Export XML writes it with
longfilm2.export_timeline.
"""
import copy
import os
import queue
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QScrollBar, QSizePolicy, QSlider,
                               QStackedLayout, QVBoxLayout, QWidget)

import core
import i18n

FPS = 25.0
FR = 1.0 / FPS
SNAP_PX = 8
HDR = 118                      # width of the track headers
RULER = 26
VH, AH = 46, 26                # video / audio track heights
EDGE = 6                       # px at a clip's edge that trims instead of moving


def _ffmpeg():
    return core.ffmpeg_exe()


# ---------------------------------------------------------------- background picture readers
class FrameReader(QThread):
    """The newest request wins: one frame of (path, second) as a QImage, for the monitor and the clip pictures."""
    got = Signal(str, object)

    def __init__(self, width):
        super().__init__()
        self.q, self.width, self._stop = queue.Queue(), width, False

    def ask(self, tag, path, t, latest=True):
        if latest:
            with self.q.mutex:
                self.q.queue.clear()
        self.q.put((tag, path, t))

    def stop(self):
        self._stop = True
        self.q.put(None)

    def run(self):
        while not self._stop:
            job = self.q.get()
            if job is None or self._stop:
                return
            tag, path, t = job
            try:
                out = subprocess.run([_ffmpeg(), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", path,
                                      "-frames:v", "1", "-vf", f"scale={self.width}:-2", "-f", "image2pipe",
                                      "-vcodec", "mjpeg", "-q:v", "4", "-"],
                                     capture_output=True, timeout=30, **core._NOWIN).stdout
                img = QImage.fromData(out, "JPG") if out else None
            except Exception:
                img = None
            if img is not None and not img.isNull():
                self.got.emit(tag, img)


class ThumbReader(FrameReader):
    """Clip pictures: every request is done (no 'newest wins'), each (path, second) once, cached on disk."""

    def __init__(self, folder):
        super().__init__(176)
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.asked = set()

    def want(self, path, t):
        key = f"{path}|{t:.1f}"
        if key in self.asked:
            return
        self.asked.add(key)
        self.ask(key, path, t, latest=False)

    def run(self):
        import hashlib
        while not self._stop:
            job = self.q.get()
            if job is None or self._stop:
                return
            key, path, t = job
            f = self.folder / (hashlib.md5(key.encode()).hexdigest()[:16] + ".jpg")
            if not f.exists():
                try:
                    subprocess.run([_ffmpeg(), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.2f}", "-i", path,
                                    "-frames:v", "1", "-vf", "scale=176:-2", "-q:v", "5", "-y", str(f)],
                                   capture_output=True, timeout=60, **core._NOWIN)
                except Exception:
                    continue
            if f.exists():
                img = QImage(str(f))
                if not img.isNull():
                    self.got.emit(key, img)


# ---------------------------------------------------------------- the model
class Model:
    """The clips (dicts in seconds), the undo stack and the edit operations, without any drawing."""

    def __init__(self, tl, durs):
        self.items = [dict(x) for x in tl["items"]]
        for i, it in enumerate(self.items):
            it["id"] = i
        self.next_id = len(self.items)
        self.markers = [list(m) for m in tl.get("markers", [])]
        self.durs = durs                                    # file length per path (trim limit)
        self.hidden, self.muted = set(), []
        self.undo_st, self.redo_st = [], []
        lanes = []
        for it in self.items:
            if it.get("ak") and it["ak"] not in lanes:
                lanes.append(it["ak"])
        self.lanes = sorted(lanes, key=lambda k: (k[0] == "rec", k[1]))
        self.nv = max([it["v"] for it in self.items if it.get("v")] or [1])

    # ---- undo
    def snap(self):
        return copy.deepcopy((self.items, self.hidden, self.muted))

    def push(self):
        self.undo_st.append(self.snap())
        self.undo_st = self.undo_st[-300:]
        self.redo_st.clear()

    def undo(self):
        if self.undo_st:
            self.redo_st.append(self.snap())
            self.items, self.hidden, self.muted = self.undo_st.pop()
            return True
        return False

    def redo(self):
        if self.redo_st:
            self.undo_st.append(self.snap())
            self.items, self.hidden, self.muted = self.redo_st.pop()
            return True
        return False

    # ---- queries
    def end(self):
        return max([it["start"] + it["dur"] for it in self.items] or [0.0])

    def tracks_v(self):
        return max(3, self.nv, max([it["v"] for it in self.items if it.get("v")] or [1])) + 1   # one free on top

    def by_id(self, i):
        return next((it for it in self.items if it["id"] == i), None)

    def edits(self):
        pts = {0.0}
        for it in self.items:
            pts.add(round(it["start"], 3))
            pts.add(round(it["start"] + it["dur"], 3))
        return sorted(pts)

    def top_at(self, t):
        """The clip seen in the monitor at time t: the highest visible video track."""
        best = None
        for it in self.items:
            v = it.get("v")
            if v and it.get("on", True) and v not in self.hidden and it["start"] <= t < it["start"] + it["dur"]:
                if best is None or v > best["v"]:
                    best = it
        return best

    # ---- operations
    def _split(self, it, t):
        """Cuts `it` at t -> the right part (new clip) or None."""
        if not (it["start"] + FR / 2 < t < it["start"] + it["dur"] - FR / 2):
            return None
        d = t - it["start"]
        right = dict(it, id=self.next_id, start=t, src=it["src"] + d, dur=it["dur"] - d)
        self.next_id += 1
        it["dur"] = d
        self.items.append(right)
        return right

    def razor(self, it, t):
        self.push()
        return self._split(it, t)

    def _overwrite(self, moved):
        """Clips dropped over others overwrite them (Premiere): trimmed, split or removed; video by track, sound-only
        clips by their audio lane."""
        ids = {m["id"] for m in moved}
        for m in moved:
            a, b = m["start"], m["start"] + m["dur"]
            same = (lambda o, m=m: o.get("v") == m["v"]) if m.get("v") else \
                   (lambda o, m=m: not o.get("v") and o.get("ak") == m.get("ak"))
            for o in list(self.items):
                if o["id"] in ids or not same(o):
                    continue
                oa, ob = o["start"], o["start"] + o["dur"]
                if ob <= a + 1e-6 or oa >= b - 1e-6:
                    continue
                if oa >= a - 1e-6 and ob <= b + 1e-6:
                    self.items.remove(o)
                elif oa < a and ob > b:
                    r = self._split(o, b)
                    o["dur"] = a - oa
                    if r is None:
                        continue
                elif oa < a:
                    o["dur"] = a - oa
                else:
                    cut = b - oa
                    o["start"], o["src"], o["dur"] = b, o["src"] + cut, o["dur"] - cut

    def move(self, ids, dt, dv):
        sel = [it for it in self.items if it["id"] in ids]
        if not sel:
            return
        dt = max(dt, -min(it["start"] for it in sel))
        vids = [it["v"] for it in sel if it.get("v")]
        if vids:
            dv = max(dv, 1 - min(vids))
            dv = min(dv, self.tracks_v() - max(vids))
        else:
            dv = 0
        if abs(dt) < 1e-6 and dv == 0:
            return
        self.push()
        for it in sel:
            it["start"] = round((it["start"] + dt) * FPS) / FPS
            if it.get("v"):
                it["v"] += dv
        self._overwrite(sel)

    def trim(self, it, side, dt):
        self.push()
        mx = self.durs.get(it["path"]) or 1e9
        if side == "L":
            dt = max(dt, -it["src"], -it["start"])
            dt = min(dt, it["dur"] - FR)
            it["start"] += dt
            it["src"] += dt
            it["dur"] -= dt
        else:
            dt = min(dt, mx - it["src"] - it["dur"])
            dt = max(dt, FR - it["dur"])
            it["dur"] += dt
        self._overwrite([it])

    def delete(self, ids, ripple=False):
        sel = [it for it in self.items if it["id"] in ids]
        if not sel:
            return
        self.push()
        for it in sel:
            self.items.remove(it)
        if ripple:
            a = min(it["start"] for it in sel)
            b = max(it["start"] + it["dur"] for it in sel)
            busy = any(o["start"] < b and o["start"] + o["dur"] > a for o in self.items)
            if not busy:                      # nothing else there: everything after it moves left
                for o in self.items:
                    if o["start"] >= b - 1e-6:
                        o["start"] -= b - a
                for m in self.markers:
                    if m[1] >= b - 1e-6:
                        m[1] -= b - a

    def timeline(self):
        return dict(items=[{k: v for k, v in it.items() if k != "id"} for it in self.items], markers=self.markers)


# ---------------------------------------------------------------- the timeline view
class TimelineView(QWidget):
    changed = Signal()
    playhead_moved = Signal(float)

    def __init__(self, model, colours, names):
        super().__init__()
        self.m, self.colours, self.names = model, colours, names
        self.pps, self.x0 = 8.0, 0.0          # pixels per second, first second shown
        self.ph = 0.0                          # playhead (s)
        self.sel = set()
        self.tool, self.snapping = "select", True
        self.drag = None
        self.thumbs = {}
        self.thumb_reader = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(RULER + 4 * VH + 3 * AH + 20)
        self.hbar = QScrollBar(Qt.Horizontal)
        self.hbar.valueChanged.connect(self._scrolled)
        self._range()

    # ---- geometry
    def rows(self):
        """[(kind, key, y, h)] top to bottom: video tracks from the top one down to V1, then the audio lanes."""
        out, y = [], RULER
        for v in range(self.m.tracks_v(), 0, -1):
            out.append(("v", v, y, VH))
            y += VH
        y += 6
        for k in self.m.lanes:
            out.append(("a", k, y, AH))
            y += AH
        return out

    def x_of(self, t):
        return HDR + (t - self.x0) * self.pps

    def t_of(self, x):
        return self.x0 + (x - HDR) / self.pps

    def row_at(self, y):
        for r in self.rows():
            if r[2] <= y < r[2] + r[3]:
                return r
        return None

    def rect_of(self, it):
        for kind, key, y, h in self.rows():
            if (kind == "v" and it.get("v") == key) or (kind == "a" and not it.get("v") and it.get("ak") == key):
                return QRectF(self.x_of(it["start"]), y + 1, max(2.0, it["dur"] * self.pps), h - 2)
        return None

    def audio_rect(self, it):
        """A picture clip's own sound, drawn on its lane (it moves with the picture: linked)."""
        if not it.get("v") or not it.get("ak"):
            return None
        for kind, key, y, h in self.rows():
            if kind == "a" and key == it["ak"]:
                return QRectF(self.x_of(it["start"]), y + 1, max(2.0, it["dur"] * self.pps), h - 2)
        return None

    def hit(self, p):
        for it in reversed(self.m.items):
            for r in (self.rect_of(it), self.audio_rect(it)):
                if r is not None and r.contains(p):
                    return it, r
        return None, None

    def _range(self):
        total = self.m.end() + 30
        vis = max(1.0, (self.width() - HDR) / self.pps)
        self.hbar.setRange(0, int(max(0.0, total - vis) * 10))
        self.hbar.setPageStep(int(vis * 10))

    def _scrolled(self, v):
        self.x0 = v / 10.0
        self.update()

    def resizeEvent(self, e):
        self._range()
        super().resizeEvent(e)

    def zoom(self, f, at=None):
        at = self.ph if at is None else at
        sx = self.x_of(at)
        self.pps = min(200.0, max(0.02, self.pps * f))
        self.x0 = max(0.0, at - (sx - HDR) / self.pps)
        self._range()
        self.hbar.setValue(int(self.x0 * 10))
        self.update()

    def fit(self):
        self.pps = max(0.02, (self.width() - HDR - 20) / max(1.0, self.m.end()))
        self.x0 = 0.0
        self._range()
        self.hbar.setValue(0)
        self.update()

    def set_playhead(self, t, follow=True):
        self.ph = max(0.0, t)
        if follow:
            vis = (self.width() - HDR) / self.pps
            if self.ph < self.x0 or self.ph > self.x0 + vis * 0.95:
                self.hbar.setValue(int(max(0.0, self.ph - vis * 0.1) * 10))
        self.update()

    # ---- snapping
    def _snap(self, t, skip=()):
        if not self.snapping:
            return t
        pts = [self.ph] + [m[1] for m in self.m.markers]
        for it in self.m.items:
            if it["id"] in skip:
                continue
            pts += [it["start"], it["start"] + it["dur"]]
        best = min(pts, key=lambda p: abs(p - t), default=t)
        return best if abs(best - t) * self.pps <= SNAP_PX else t

    # ---- painting
    def paintEvent(self, _e):
        g = QPainter(self)
        W, H = self.width(), self.height()
        g.fillRect(self.rect(), QColor("#1d1d1d"))
        f = QFont(g.font())
        f.setPointSizeF(8.5)
        g.setFont(f)
        t0, t1 = self.t_of(HDR), self.t_of(W)
        rows = self.rows()
        # track backgrounds
        for kind, key, y, h in rows:
            g.fillRect(QRectF(HDR, y, W - HDR, h - 1), QColor("#262626" if kind == "v" else "#222a26"))
        # clips
        for it in self.m.items:
            a, b = it["start"], it["start"] + it["dur"]
            if b < t0 or a > t1:
                continue
            for r, is_audio in ((self.rect_of(it), not it.get("v")), (self.audio_rect(it), True)):
                if r is None:
                    continue
                self._clip(g, it, r, is_audio)
        # headers
        g.fillRect(QRectF(0, 0, HDR, H), QColor("#232323"))
        for kind, key, y, h in rows:
            g.setPen(QColor("#3a3a3a"))
            g.drawLine(0, int(y + h - 1), HDR, int(y + h - 1))
            name = f"V{key}" if kind == "v" else self.names(key)
            g.setPen(QColor("#ddd"))
            g.drawText(QRectF(8, y, HDR - 40, h), Qt.AlignVCenter | Qt.AlignLeft,
                       g.fontMetrics().elidedText(i18n.T(name), Qt.ElideRight, HDR - 44))
            off = (kind == "v" and key in self.m.hidden) or (kind == "a" and list(key) in self.m.muted)
            btn = QRectF(HDR - 30, y + h / 2 - 9, 22, 18)
            g.fillRect(btn, QColor("#b33" if off else "#3a3a3a"))
            g.setPen(QColor("white"))
            g.drawText(btn, Qt.AlignCenter, ("⦸" if off else "👁") if kind == "v" else "M")
        # ruler
        g.fillRect(QRectF(0, 0, W, RULER), QColor("#2a2a2a"))
        step = next((s for s in (FR * 5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600)
                     if s * self.pps >= 80), 3600)
        tt = (int(t0 / step)) * step
        g.setPen(QColor("#999"))
        while tt <= t1:
            x = self.x_of(tt)
            if x >= HDR:
                g.drawLine(int(x), RULER - 8, int(x), RULER)
                g.drawText(int(x) + 3, 12, tc(tt))
            tt += step
        for name, mt in self.m.markers:
            x = self.x_of(mt)
            if HDR <= x <= W:
                g.setPen(QColor("#e3cf3e"))
                g.drawLine(int(x), 14, int(x), RULER)
                g.drawText(int(x) + 3, RULER - 2, name)
        # drop preview / playhead
        if self.drag and self.drag.get("ghost"):
            g.setPen(QPen(QColor("#2d8ceb"), 2, Qt.DashLine))
            for r in self.drag["ghost"]:
                g.drawRect(r)
        x = self.x_of(self.ph)
        if x >= HDR:
            g.setPen(QPen(QColor("#2d8ceb"), 2))
            g.drawLine(int(x), 0, int(x), H)
            g.setBrush(QColor("#2d8ceb"))
            g.drawPolygon([QPointF(x - 6, 0), QPointF(x + 6, 0), QPointF(x, 8)])
        g.end()

    def _clip(self, g, it, r, audio):
        r = r.intersected(QRectF(HDR, 0, self.width() - HDR, self.height()))
        if r.width() <= 0:
            return
        col = QColor(self.colours.get(it.get("label") or "", "#5b6f8f"))
        off = (not it.get("on", True)) or (it.get("v") in self.m.hidden if not audio else
                                            (it.get("ak") in self.m.muted or not it.get("aon", True)))
        if audio:
            base = QColor("#2f6e4f") if not off else QColor("#333")
            g.fillRect(r, base)
            g.setPen(QColor("#5fae86") if not off else QColor("#555"))
            mid = r.center().y()
            g.drawLine(int(r.left()), int(mid), int(r.right()), int(mid))
        else:
            g.fillRect(r, col.darker(170) if not off else QColor("#303030"))
            if r.width() > 24 and r.height() > 20:
                self._pictures(g, it, r)
            g.fillRect(QRectF(r.x(), r.y(), r.width(), 12), col if not off else QColor("#555"))
            if r.width() > 34:
                g.setPen(QColor("#111"))
                g.drawText(QRectF(r.x() + 3, r.y() - 1, r.width() - 5, 13), Qt.AlignVCenter | Qt.AlignLeft,
                           g.fontMetrics().elidedText(Path(it["path"]).name, Qt.ElideRight, int(r.width() - 6)))
        sel = it["id"] in self.sel
        g.setPen(QPen(QColor("#ffffff") if sel else QColor("#111"), 2 if sel else 1))
        g.setBrush(Qt.NoBrush)
        g.drawRect(r)

    def _pictures(self, g, it, r):
        """Premiere-like: pictures along the clip (as many as fit), read in the background."""
        inner = QRectF(r.x() + 1, r.y() + 12, r.width() - 2, r.height() - 13)
        tw = inner.height() * 16 / 9
        n = max(1, min(12, int(inner.width() // tw)))
        g.save()
        g.setClipRect(inner)
        for k in range(n):
            x = inner.x() + k * tw
            t_film = self.t_of(x + tw / 2)
            if not (it["start"] <= t_film <= it["start"] + it["dur"]):
                t_film = it["start"] + it["dur"] / 2
            st = round(it["src"] + (t_film - it["start"]), 0)
            key = f"{it['path']}|{st:.1f}"
            img = self.thumbs.get(key)
            if img is None and self.thumb_reader is not None:
                self.thumb_reader.want(it["path"], st)
            if img is not None:
                g.drawImage(QRectF(x, inner.y(), tw, inner.height()), img)
        g.restore()

    def got_thumb(self, key, img):
        self.thumbs[key] = img
        self.update()

    # ---- mouse
    def _header_click(self, p):
        r = self.row_at(p.y())
        if not r or p.x() > HDR:
            return False
        kind, key = r[0], r[1]
        if HDR - 32 <= p.x() <= HDR - 6:
            self.m.push()
            if kind == "v":
                self.m.hidden ^= {key}
            else:
                k = list(key)
                self.m.muted = [x for x in self.m.muted if x != k] if k in self.m.muted else self.m.muted + [k]
            self.changed.emit()
            self.update()
        return True

    def mousePressEvent(self, e):
        self.setFocus()
        p = e.position()
        if self._header_click(p):
            return
        if p.y() < RULER:                      # click / drag on the ruler moves the playhead
            self.drag = dict(kind="ph")
            self.set_playhead(self.t_of(p.x()), follow=False)
            self.playhead_moved.emit(self.ph)
            return
        it, r = self.hit(p)
        if self.tool == "razor" and it is not None:
            t = self._snap(self.t_of(p.x()))
            self.m.razor(it, round(t * FPS) / FPS)
            self.changed.emit()
            self.update()
            return
        mods = e.modifiers()
        if it is None:
            if not mods & (Qt.ShiftModifier | Qt.ControlModifier | Qt.MetaModifier):
                self.sel.clear()
            self.drag = dict(kind="ph")
            self.set_playhead(self.t_of(p.x()), follow=False)
            self.playhead_moved.emit(self.ph)
            self.update()
            return
        if mods & (Qt.ShiftModifier | Qt.ControlModifier | Qt.MetaModifier):
            self.sel ^= {it["id"]}
        elif it["id"] not in self.sel:
            self.sel = {it["id"]}
        side = "L" if p.x() - r.left() <= EDGE else ("R" if r.right() - p.x() <= EDGE else None)
        self.drag = dict(kind="trim" if side and len(self.sel) == 1 else "move", side=side, it=it,
                         x=p.x(), y=p.y(), started=False)
        self.update()

    def mouseMoveEvent(self, e):
        p = e.position()
        d = self.drag
        if d is None:
            it, r = self.hit(p)
            if it is not None:
                near = p.x() - r.left() <= EDGE or r.right() - p.x() <= EDGE
                self.setCursor(Qt.SplitHCursor if near and self.tool == "select" else
                               (Qt.CrossCursor if self.tool == "razor" else Qt.ArrowCursor))
                self.setToolTip(f"{Path(it['path']).name}  ·  {tc(it['dur'])}  ·  "
                                f"{i18n.T('source')} {tc(it['src'])}")
            else:
                self.setCursor(Qt.ArrowCursor)
            return
        if d["kind"] == "ph":
            self.set_playhead(self.t_of(p.x()), follow=False)
            self.playhead_moved.emit(self.ph)
            return
        if abs(p.x() - d["x"]) < 3 and abs(p.y() - d["y"]) < 3 and not d["started"]:
            return
        d["started"] = True
        dt = (p.x() - d["x"]) / self.pps
        if d["kind"] == "move":
            it = d["it"]
            # snap the dragged clip's start or end
            ns = self._snap(it["start"] + dt, skip=self.sel)
            if ns == it["start"] + dt:
                ne = self._snap(it["start"] + it["dur"] + dt, skip=self.sel)
                ns = ne - it["dur"]
            dt = ns - it["start"]
            r0 = self.row_at(d["y"])
            r1 = self.row_at(p.y())
            dv = 0
            if r0 and r1 and r0[0] == "v" and r1[0] == "v":
                dv = r1[1] - r0[1]
            d["dt"], d["dv"] = dt, dv
            ghost = []
            for o in self.m.items:
                if o["id"] in self.sel:
                    rr = self.rect_of(dict(o, start=o["start"] + dt, v=(o["v"] + dv) if o.get("v") else None))
                    if rr is not None:
                        ghost.append(rr)
            d["ghost"] = ghost
        else:
            it = d["it"]
            edge = it["start"] if d["side"] == "L" else it["start"] + it["dur"]
            ne = self._snap(edge + dt, skip={it["id"]})
            d["dt"] = ne - edge
            r = self.rect_of(it)
            if d["side"] == "L":
                r.setLeft(self.x_of(ne))
            else:
                r.setRight(self.x_of(ne))
            d["ghost"] = [r]
        self.update()

    def mouseReleaseEvent(self, e):
        d, self.drag = self.drag, None
        if d and d.get("started"):
            if d["kind"] == "move":
                self.m.move(set(self.sel), round(d.get("dt", 0.0) * FPS) / FPS, d.get("dv", 0))
            elif d["kind"] == "trim":
                self.m.trim(d["it"], d["side"], round(d.get("dt", 0.0) * FPS) / FPS)
            self.sel = {i for i in self.sel if self.m.by_id(i)}
            self._range()
            self.changed.emit()
        self.update()

    def wheelEvent(self, e):
        if e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier):
            self.zoom(1.2 if e.angleDelta().y() > 0 else 1 / 1.2, self.t_of(e.position().x()))
        else:
            dx = e.angleDelta().x() or e.angleDelta().y()
            self.hbar.setValue(self.hbar.value() - int(dx / 120 * max(1, self.hbar.pageStep() / 8)))
        e.accept()


def tc(t):
    """hh:mm:ss:ff at 25 fps, like Premiere."""
    t = max(0.0, t)
    fr = int(round(t * FPS))
    s, f = divmod(fr, int(FPS))
    h, s = divmod(s, 3600)
    mi, s = divmod(s, 60)
    return f"{h:02d}:{mi:02d}:{s:02d}:{f:02d}"


# ---------------------------------------------------------------- the window
class Editor(QDialog):
    """Program monitor on top, timeline below, tools in between. exec() -> True when saved; .timeline() then."""

    def __init__(self, parent, tl, infos, colours, lane_name, thumbs_dir, hidden=(), muted=()):
        super().__init__(parent)
        self.setWindowTitle("Edit the long film")
        self.resize(1400, 900)
        durs = {p: (i or {}).get("dur") for p, i in infos.items()}
        self.m = Model(tl, durs)
        self.m.hidden, self.m.muted = set(hidden), [list(x) for x in muted]
        self.view = TimelineView(self.m, colours, lane_name)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        # monitor
        mon = QWidget()
        mon.setStyleSheet("background:#000; border-radius:6px")
        self.stack = QStackedLayout(mon)
        self.screen = QLabel()
        self.screen.setAlignment(Qt.AlignCenter)
        self.screen.setMinimumSize(480, 270)
        self.screen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stack.addWidget(self.screen)
        self.player = self.video = None
        try:                                   # real playback with sound when Qt Multimedia is in the app
            if os.environ.get("MMM_NO_PLAYER"):
                raise RuntimeError("player switched off (tests)")
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
            self.video = QVideoWidget()
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.stack.addWidget(self.video)
            self._pending = None
            self.player.mediaStatusChanged.connect(self._media_status)
        except Exception:
            self.player = None
        v.addWidget(mon, 5)
        # transport
        tr = QHBoxLayout()
        self.tc = QLabel("00:00:00:00")
        self.tc.setStyleSheet("color:#2d8ceb; font: 600 15px 'Menlo'")
        tr.addWidget(self.tc)
        tr.addStretch()
        for text, tip, slot in (("⏮", "Previous edit (Up)", lambda: self._edit(-1)),
                                ("−1", "One frame back (Left)", lambda: self._step(-1)),
                                ("▶", "Play / pause (Space)", self.toggle),
                                ("+1", "One frame forward (Right)", lambda: self._step(1)),
                                ("⏭", "Next edit (Down)", lambda: self._edit(1))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(46)
            b.clicked.connect(slot)
            tr.addWidget(b)
            if text == "▶":
                self.b_play = b
        tr.addStretch()
        self.dur_lbl = QLabel("")
        self.dur_lbl.setStyleSheet("color:#999")
        tr.addWidget(self.dur_lbl)
        v.addLayout(tr)
        # tools
        tb = QHBoxLayout()
        self.b_sel = QPushButton("Selection (V)")
        self.b_raz = QPushButton("Razor (C)")
        for b in (self.b_sel, self.b_raz):
            b.setCheckable(True)
            tb.addWidget(b)
        self.b_sel.setChecked(True)
        self.b_sel.clicked.connect(lambda: self._tool("select"))
        self.b_raz.clicked.connect(lambda: self._tool("razor"))
        self.b_snap = QPushButton("Snap (S)")
        self.b_snap.setCheckable(True)
        self.b_snap.setChecked(True)
        self.b_snap.clicked.connect(lambda on: setattr(self.view, "snapping", on))
        tb.addWidget(self.b_snap)
        for text, slot in (("Undo", self.undo), ("Redo", self.redo), ("Delete", lambda: self._delete(False)),
                           ("Ripple delete", lambda: self._delete(True))):
            b = QPushButton(text)
            b.clicked.connect(slot)
            tb.addWidget(b)
        tb.addStretch()
        tb.addWidget(QLabel("Zoom"))
        self.zs = QSlider(Qt.Horizontal)
        self.zs.setRange(0, 1000)
        self.zs.setFixedWidth(200)
        self.zs.valueChanged.connect(self._zoom_slider)
        tb.addWidget(self.zs)
        fitb = QPushButton("Fit (\\)")
        fitb.clicked.connect(self.view.fit)
        tb.addWidget(fitb)
        v.addLayout(tb)
        v.addWidget(self.view, 6)
        v.addWidget(self.view.hbar)
        # bottom row
        bot = QHBoxLayout()
        self.reset = False
        rb = QPushButton("Back to the automatic film")
        rb.setObjectName("link")
        rb.clicked.connect(self._reset)
        bot.addWidget(rb)
        bot.addStretch()
        cb = QPushButton("Cancel")
        cb.clicked.connect(self.reject)
        sb = QPushButton("Save")
        sb.setObjectName("primary")
        sb.clicked.connect(self.accept)
        bot.addWidget(cb)
        bot.addWidget(sb)
        v.addLayout(bot)
        # readers
        self.frames = FrameReader(960)
        self.frames.got.connect(self._frame)
        self.frames.start()
        self.view.thumb_reader = ThumbReader(thumbs_dir)
        self.view.thumb_reader.got.connect(self.view.got_thumb)
        self.view.thumb_reader.start()
        self.view.playhead_moved.connect(self._seek)
        self.view.changed.connect(self._changed)
        self.playing, self.cur, self.t_start, self.ph_start = False, None, 0.0, 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        for b in self.findChildren(QPushButton):     # Space / arrows belong to the editor, not to a button
            b.setFocusPolicy(Qt.NoFocus)
        self.zs.setFocusPolicy(Qt.NoFocus)
        self._changed()
        QTimer.singleShot(0, self._first)

    def _first(self):
        self.view.fit()
        self._sync_slider()
        self._seek(0.0)

    # ---- monitor
    def _show_frame_at(self, t):
        it = self.m.top_at(t)
        self.tc.setText(tc(t))
        if it is None:
            self.screen.setPixmap(QPixmap())
            return
        self.frames.ask("mon", it["path"], it["src"] + (t - it["start"]))

    def _frame(self, tag, img):
        if tag != "mon" or self.playing and self.player is not None:
            return
        pm = QPixmap.fromImage(img).scaled(self.screen.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.screen.setPixmap(pm)

    def _seek(self, t):
        if self.playing:
            self.pause()
        self.stack.setCurrentWidget(self.screen)
        self.view.set_playhead(t, follow=False)
        self._show_frame_at(t)

    def toggle(self):
        self.pause() if self.playing else self.play()

    def play(self):
        if self.view.ph >= self.m.end():
            self.view.set_playhead(0.0)
        self.playing, self.cur = True, None
        self.t_start, self.ph_start = time.monotonic(), self.view.ph
        self.b_play.setText("❚❚")
        if self.player is not None:
            self.stack.setCurrentWidget(self.video)
        self.timer.start()
        self._tick()

    def pause(self):
        self.playing = False
        self.timer.stop()
        self.b_play.setText("▶")
        if self.player is not None:
            self.player.pause()
        self.stack.setCurrentWidget(self.screen)
        self._show_frame_at(self.view.ph)

    def _tick(self):
        t = self.ph_start + (time.monotonic() - self.t_start)
        if t >= self.m.end():
            self.pause()
            return
        self.view.set_playhead(t)
        self.tc.setText(tc(t))
        it = self.m.top_at(t)
        if self.player is None:                # no Qt Multimedia: still pictures, a few per second
            if int(t * 4) != int((t - 0.04) * 4):
                self.frames.ask("mon", it["path"], it["src"] + t - it["start"]) if it else None
            return
        if it is None:
            if self.cur is not None:
                self.player.pause()
                self.cur = None
            return
        if self.cur is None or self.cur["id"] != it["id"]:
            self.cur = it
            pos = int((it["src"] + t - it["start"]) * 1000)
            if self.player.source() != QUrl.fromLocalFile(it["path"]):
                self._pending = pos                # applied when the file is loaded (_media_status)
                self.player.setSource(QUrl.fromLocalFile(it["path"]))
            else:
                self.player.setPosition(pos)
            muted = (not it.get("ak")) or list(it["ak"]) in self.m.muted or not it.get("aon", True)
            self.audio.setMuted(bool(muted))
            self.player.play()

    def _media_status(self, st):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if self._pending is not None and st in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
                pos, self._pending = self._pending, None
                if self.playing and self.cur is not None:      # the time it took to load is caught up
                    pos = int((self.cur["src"] + self.view.ph - self.cur["start"]) * 1000)
                self.player.setPosition(pos)
        except Exception:
            pass

    def _step(self, n):
        self._seek(max(0.0, round(self.view.ph * FPS + n) / FPS))

    def _edit(self, d):
        pts = self.m.edits()
        t = self.view.ph
        nxt = [p for p in pts if p > t + 1e-3] if d > 0 else [p for p in pts if p < t - 1e-3]
        if nxt:
            self._seek(nxt[0] if d > 0 else nxt[-1])

    # ---- tools
    def _tool(self, name):
        self.view.tool = name
        self.b_sel.setChecked(name == "select")
        self.b_raz.setChecked(name == "razor")

    def _delete(self, ripple):
        self.m.delete(set(self.view.sel), ripple)
        self.view.sel.clear()
        self._changed()

    def undo(self):
        if self.m.undo():
            self.view.sel.clear()
            self._changed()

    def redo(self):
        if self.m.redo():
            self.view.sel.clear()
            self._changed()

    def _zoom_slider(self, x):
        if getattr(self, "_zs_lock", False):
            return
        self.view.pps = 0.02 * (10000 ** (x / 1000))       # 0.02 .. 200 px / s
        self.view.zoom(1.0)

    def _sync_slider(self):
        import math
        self._zs_lock = True
        self.zs.setValue(int(1000 * math.log(max(0.02, self.view.pps) / 0.02) / math.log(10000)))
        self._zs_lock = False

    def _changed(self):
        self.view._range()
        self.view.update()
        n = sum(1 for it in self.m.items if it.get("v"))
        self.dur_lbl.setText(i18n.T("{} clips · {}").format(n, tc(self.m.end())))
        if not self.playing:
            self._show_frame_at(self.view.ph)

    def keyPressEvent(self, e):
        k, mods = e.key(), e.modifiers()
        cmd = mods & (Qt.ControlModifier | Qt.MetaModifier)
        if k == Qt.Key_Space:
            self.toggle()
        elif k == Qt.Key_Left:
            self._step(-1)
        elif k == Qt.Key_Right:
            self._step(1)
        elif k == Qt.Key_Up:
            self._edit(-1)
        elif k == Qt.Key_Down:
            self._edit(1)
        elif k in (Qt.Key_Delete, Qt.Key_Backspace):
            self._delete(bool(mods & Qt.ShiftModifier))
        elif cmd and k == Qt.Key_Z:
            self.redo() if mods & Qt.ShiftModifier else self.undo()
        elif k == Qt.Key_V and not cmd:
            self._tool("select")
        elif k == Qt.Key_C and not cmd:
            self._tool("razor")
        elif k == Qt.Key_S and not cmd:
            self.b_snap.toggle()
            self.view.snapping = self.b_snap.isChecked()
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.view.zoom(1.4)
            self._sync_slider()
        elif k == Qt.Key_Minus:
            self.view.zoom(1 / 1.4)
            self._sync_slider()
        elif k == Qt.Key_Backslash:
            self.view.fit()
            self._sync_slider()
        elif k == Qt.Key_Home:
            self._seek(0.0)
        elif k == Qt.Key_End:
            self._seek(self.m.end())
        elif k == Qt.Key_Escape:
            return                                  # never close by accident
        else:
            super().keyPressEvent(e)

    def _reset(self):
        self.reset = True
        self.accept()

    def timeline(self):
        return self.m.timeline()

    def done(self, r):
        self.timer.stop()
        if self.player is not None:
            self.player.stop()
        for rd in (self.frames, self.view.thumb_reader):
            rd.stop()
            rd.wait(3000)
        super().done(r)
