"""MoneyMakingMachine - AI-free footage pre-selection. Desktop app (PySide6)."""
import json
import logging
import logging.handlers
import os
import platform
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QUrl, QPoint, QPointF, QPropertyAnimation, QRectF, QRegularExpression, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QImage, QPainter, QPen, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (QTextBrowser, QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QHeaderView, QCheckBox)

import core
import director
import music
import help_text
import teaser
import ai
import xmlimport
import sync

APP, VER = "MoneyMakingMachine", "v2.7.2"
AUTHOR, AUTHOR_URL = "@sergiugabrielcg", "https://www.instagram.com/sergiugabrielcg/"
REPO = "SergiuGabriel/clipselect"          # GitHub releases are checked for updates (the repo must be public)


def _ver(v):
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def latest_release():
    """(tag, page url) of the newest published version, or None."""
    import ssl
    import urllib.request
    try:                                  # the packed app has no system certificates: bring our own (certifi)
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"User-Agent": "MoneyMakingMachine", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("tag_name", ""), d.get("html_url", "")
C = dict(BG="#1d1d1d", PANEL="#232323", CARD="#2a2a2a", BORDER="#3a3a3a", TEXT="#d6d6d6", MUTED="#8f8f8f",
         BLUE="#1473e6", HOT="#4b9cf5", GOOD="#4cc38a", FAIR="#e6b93a", POOR="#e5534b")   # Premiere Pro look
LV_COL = [C["POOR"], C["FAIR"], C["GOOD"]]
LV_NAME = ["Poor", "Fair", "Good"]
SLIDERS = [("contrast", "Contrast", "Detect low/high contrast frames"),
           ("exposure", "Exposure", "Under/overexposed detection"),
           ("focus", "Blur / Focus", "Out-of-focus frame detection"),
           ("importance", "Visual Importance", "Scene significance scoring"),
           ("stability", "Shakiness / Stability", "Camera shake detection")]
PRESETS = {"Lenient": (15, 50), "Normal": (25, 65), "Strict": (35, 75)}
SEQ_SIZES = ["Match footage", "1920 x 1080", "3840 x 2160", "4096 x 2160", "1080 x 1920"]
SEQ_RATES = ["Match footage", "23.976", "24", "25", "29.97", "30", "50", "59.94", "60"]
SEQ_FIELDS = {"Lower Field First": "lower", "Upper Field First": "upper", "None (Progressive)": "none"}
SEQ_DEFAULT = dict(size="Match footage", rate="Match footage", fields="Lower Field First")
DEFAULT_ON = {k: True for k, _, _ in SLIDERS}
DEFAULTS = dict(mode="auto", thr=60, mincut=3, cutmoves=True, protect=True, contrast=50, exposure=50, focus=60, importance=40,
                stability=50, preset="Normal", p1=25, p2=65)


def norm_settings(s):
    out = dict(DEFAULTS)
    out.update(s)
    out["on"] = {**DEFAULT_ON, **s.get("on", {})}
    return out

STYLE = """
QWidget{background:@BG;color:@TEXT;font-size:12px}
QLabel,QFrame{background:transparent}
QToolTip{background:#2f2f2f;color:#e8e8e8;border:1px solid #4a4a4a;padding:4px}
QFrame#head{border-bottom:1px solid @BORDER;background:@PANEL}
QFrame#leftpanel{border-right:1px solid @BORDER;background:@PANEL}
QFrame#rightpanel{border-left:1px solid @BORDER;background:@PANEL}
QFrame#sidebar{background:#191919;border-right:1px solid @BORDER}
QFrame#card,QFrame#panel{background:@CARD;border:1px solid @BORDER;border-radius:4px}
QFrame#drop{border:1.5px dashed #5c5c5c;border-radius:4px;background:#1a1a1a}
QFrame#drop:hover{border-color:@HOT;background:#202020}
QFrame#info{background:#1f2a38;border:1px solid #2f4b70;border-radius:4px}
QLabel#h1{font-size:17px;font-weight:700;color:#ececec}
QLabel#h2{font-size:14px;font-weight:700;color:#ececec}
QLabel#muted{color:@MUTED;font-size:11px}
QLabel#section{color:#a8a8a8;font-size:11px;font-weight:700}
QLabel#stat{font-size:20px;font-weight:700;color:#ececec}
QLabel#ok{color:@GOOD}
QPushButton{background:transparent;color:#e3e3e3;border:2px solid #8a8a8a;border-radius:14px;padding:4px 16px;font-weight:600;min-height:18px}
QPushButton:hover{background:#3a3a3a;border-color:#b3b3b3}
QPushButton:disabled{color:#5e5e5e;border-color:#454545}
QPushButton#primary{background:@BLUE;border:2px solid @BLUE;color:white}
QPushButton#primary:hover{background:#0d66d0;border-color:#0d66d0}
QPushButton#primary:disabled{background:#2e3f55;border-color:#2e3f55;color:#8a96a6}
QPushButton#nav{text-align:left;border:none;border-radius:4px;background:transparent;padding:7px 10px;color:#a8a8a8;font-weight:500}
QPushButton#nav:hover{background:#2a2a2a}
QPushButton#nav[active="true"]{background:#333333;color:white}
QPushButton#link{border:none;background:transparent;color:@MUTED;padding:4px;font-weight:500}
QPushButton#link:hover{color:white;background:transparent}
QPushButton#seg{border-radius:4px;padding:6px;border:1px solid #4a4a4a;background:#262626;font-weight:500}
QPushButton#seg[active="true"]{border:1px solid @HOT;background:#1d3557;color:white}
QPushButton#del{border:none;background:transparent;color:@MUTED;padding:2px 6px;font-weight:500}
QPushButton#del:hover{color:@POOR;background:transparent}
QLineEdit{background:#161616;border:1px solid #4a4a4a;border-radius:3px;padding:5px 6px;selection-background-color:@BLUE}
QLineEdit:focus{border:1px solid @HOT}
QComboBox{background:#161616;border:1px solid #4a4a4a;border-radius:3px;padding:5px 8px}
QComboBox:hover{border-color:#6a6a6a}
QComboBox QAbstractItemView{background:#2a2a2a;border:1px solid #4a4a4a;selection-background-color:@BLUE}
QSlider::groove:horizontal{height:2px;background:#4a4a4a;border-radius:1px}
QSlider::sub-page:horizontal{background:#c8c8c8;border-radius:1px}
QSlider::handle:horizontal{background:@PANEL;border:2px solid #c8c8c8;width:10px;height:10px;margin:-6px 0;border-radius:7px}
QSlider::handle:horizontal:hover{border-color:white}
QSlider::sub-page:horizontal:disabled{background:#4a4a4a}
QSlider::handle:horizontal:disabled{border-color:#5a5a5a}
QProgressBar{background:#3a3a3a;border:none;border-radius:2px;max-height:4px;min-height:4px}
QProgressBar::chunk{background:@HOT;border-radius:2px}
QProgressBar#big{background:#333333;border-radius:5px;max-height:10px;min-height:10px}
QProgressBar#big::chunk{border-radius:5px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1473e6,stop:1 #4b9cf5)}
QFrame#progress{background:#202a38;border:1px solid #2f4b70;border-radius:6px}
QListWidget{background:transparent;border:none;outline:none}
QListWidget::item{padding:6px 6px;border-bottom:1px solid #2c2c2c}
QListWidget::item:selected{background:#2d4f7c;color:white}
QListWidget::item:hover{background:#2a2a2a}
QTableWidget{background:#1a1a1a;border:1px solid @BORDER;gridline-color:#2c2c2c;selection-background-color:#2d4f7c}
QTableWidget::item{padding:4px}
QHeaderView::section{background:@PANEL;color:#a8a8a8;border:none;border-right:1px solid #2c2c2c;padding:6px}
QTabWidget::pane{border:none}
QTabBar::tab{background:transparent;padding:8px 14px;color:@MUTED;border-bottom:2px solid transparent;font-weight:600}
QTabBar::tab:selected{color:#ececec;border-bottom:2px solid #d6d6d6}
QTabBar::tab:hover{color:#ececec}
QScrollArea{border:none}
QScrollBar:vertical{background:transparent;width:8px}
QScrollBar::handle:vertical{background:#4a4a4a;border-radius:4px;min-height:30px}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
QScrollBar:horizontal{background:transparent;height:8px}
QScrollBar::handle:horizontal{background:#4a4a4a;border-radius:4px;min-width:30px}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0}
QDialog{background:@PANEL}
"""
for _k, _v in C.items():
    STYLE = STYLE.replace("@" + _k, _v)


# ---------------------------------------------------------------- helpers

def lbl(text, obj="", wrap=False):
    l = QLabel(text)
    if obj:
        l.setObjectName(obj)
    l.setWordWrap(wrap)
    return l


def btn(text, obj="", slot=None):
    b = QPushButton(text)
    if obj:
        b.setObjectName(obj)
    if slot:
        b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


def hms(sec):
    sec = int(round(sec))
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def app_icon(size=26):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    for n in ("icon.png", "icon_source.png"):
        if (base / n).exists():
            return QPixmap(str(base / n)).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


def icon_pix(kind, s=56):
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#24324a"))
    p.drawRoundedRect(0, 0, s, s, 12, 12)
    p.setPen(QPen(QColor(C["BLUE"]), 2))
    p.setBrush(Qt.NoBrush)
    if kind == "folder":
        p.drawRoundedRect(QRectF(s * .27, s * .36, s * .46, s * .32), 3, 3)
        p.drawLine(QPointF(s * .27, s * .36), QPointF(s * .36, s * .29))
        p.drawLine(QPointF(s * .36, s * .29), QPointF(s * .45, s * .29))
        p.drawLine(QPointF(s * .5, s * .45), QPointF(s * .5, s * .6))
        p.drawLine(QPointF(s * .43, s * .525), QPointF(s * .57, s * .525))
    else:
        p.drawRoundedRect(QRectF(s * .3, s * .3, s * .4, s * .4), 3, 3)
        for y in (.38, .5, .62):
            p.drawLine(QPointF(s * .3, s * y), QPointF(s * .36, s * y))
            p.drawLine(QPointF(s * .64, s * y), QPointF(s * .7, s * y))
    p.end()
    return pm


SKIP_EXT = {".xml", ".txt", ".json", ".bim", ".xmp", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".csv", ".db", ".plist",
            ".cpf", ".ppn", ".sif", ".smi", ".thm", ".bup", ".ifo", ".srt", ".ini", ".log", ".md", ".html", ".ds_store",
            ".lrf", ".lrv"}   # .LRF = DJI low-res proxy, .LRV = GoPro low-res proxy: same sound as the original -> duplicates


BEATCHECK_RE = re.compile(r" - beats \d+\.wav$", re.I)     # click tracks made by Beat check


def is_proxy(p):
    """Camera proxies / previews and files made by this app that must never be treated as footage."""
    p = Path(p)
    if p.suffix.lower() in (".lrf", ".lrv"):
        return True
    if BEATCHECK_RE.search(p.name) or p.parent.name == "Beat check":
        return True
    return p.parent.name.upper() == "SUB" and p.stem.upper().endswith("S03")   # Sony proxy (M4ROOT/SUB/C0001S03.MP4)


def scan_paths(paths):
    """Returns (video_files, skipped_count). Folders: known video extensions only. Files picked by hand: anything
    except obvious sidecars (Sony M01.XML, thumbnails...)."""
    out, skipped = [], 0
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(str(f) for f in p.rglob("*")
                          if f.is_file() and f.suffix.lower() in core.VIDEO_EXT and not f.name.startswith(".") and not is_proxy(f))
        elif p.is_file():
            if p.suffix.lower() in SKIP_EXT or p.name.startswith(".") or is_proxy(p):
                skipped += 1
            else:
                out.append(str(p))  # picked manually -> accepted whatever the extension
    return out, skipped


def weights_of(s):
    return {k: s[k] / 100 for k, _, _ in SLIDERS}


# ---------------------------------------------------------------- persistence

class Store:
    def __init__(self):
        base = os.environ.get("MMM_DATA") or QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        self.dir = Path(base)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "projects.json"
        try:
            self.projects = json.loads(self.file.read_text("utf-8"))
        except Exception:
            self.projects = []
        cores = os.cpu_count() or 4
        self.app = dict(jobs=max(1, cores // 4), hwaccel=True)
        try:
            self.app.update(json.loads((self.dir / "settings.json").read_text("utf-8")))
        except Exception:
            pass
        core.HWACCEL = self.app["hwaccel"]

    def save_app(self):
        core.HWACCEL = self.app["hwaccel"]
        (self.dir / "settings.json").write_text(json.dumps(self.app), "utf-8")

    def save(self):
        """Debounced: sliders call this many times per second."""
        if not hasattr(self, "_t"):
            self._t = QTimer()
            self._t.setSingleShot(True)
            self._t.setInterval(400)
            self._t.timeout.connect(self.flush)
        self._t.start()

    def flush(self):
        if hasattr(self, "_t"):
            self._t.stop()
        self.file.write_text(json.dumps(self.projects), "utf-8")

    def load_blob(self, pid):
        try:
            return json.loads((self.dir / f"{pid}.analysis.json").read_text("utf-8"))
        except Exception:
            return {}

    def save_blob(self, pid, obj):
        (self.dir / f"{pid}.analysis.json").write_text(json.dumps(obj), "utf-8")

    def new(self, name, kind="footage"):
        p = dict(id=uuid.uuid4().hex, name=name, created=datetime.now().isoformat(timespec="seconds"),
                 videos=[], settings=norm_settings({}), history=[], out_dir="", out_name="", out_sw="Premiere Pro", seq=dict(SEQ_DEFAULT))
        if kind == "multicam":
            p.update(type="multicam", files=[], sync=None, cams=[], infos={}, dir=dict(director.DEFAULTS))
        self.projects.append(p)
        self.save()
        return p

    def delete(self, pid):
        self.projects = [p for p in self.projects if p["id"] != pid]
        self.save()


# ---------------------------------------------------------------- custom widgets

class RangeBar(QWidget):
    """Two-handle slider: [0..p1] Poor, [p1..p2] Fair, [p2..100] Good."""
    changed = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.p1, self.p2, self.drag = 25, 65, None
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)

    def set_values(self, p1, p2):
        self.p1, self.p2 = p1, p2
        self.update()

    def _x(self, v):
        return 10 + (self.width() - 20) * v / 100

    def _v(self, x):
        return (x - 10) / max(1, self.width() - 20) * 100

    def mousePressEvent(self, e):
        x = e.position().x()
        self.drag = 1 if abs(x - self._x(self.p1)) <= abs(x - self._x(self.p2)) else 2
        self.mouseMoveEvent(e)

    def mouseMoveEvent(self, e):
        if not self.drag:
            return
        v = int(round(self._v(e.position().x())))
        if self.drag == 1:
            self.p1 = max(5, min(v, self.p2 - 5))
        else:
            self.p2 = min(95, max(v, self.p1 + 5))
        self.update()
        self.changed.emit(self.p1, self.p2)

    def mouseReleaseEvent(self, _):
        self.drag = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y, h = self.height() / 2 - 3, 6
        for a, b, col in ((0, self.p1, C["POOR"]), (self.p1, self.p2, C["FAIR"]), (self.p2, 100, C["GOOD"])):
            p.fillRect(QRectF(self._x(a), y, self._x(b) - self._x(a), h), QColor(col))
        for v in (self.p1, self.p2):
            p.setPen(QPen(QColor("#d8dde6"), 2))
            p.setBrush(QColor("#161616"))
            p.drawEllipse(QPointF(self._x(v), self.height() / 2), 7, 7)


class DistBar(QWidget):
    def __init__(self, order=(0, 1, 2), height=12):
        super().__init__()
        self.order, self.vals = order, (1, 1, 1)
        self.setFixedHeight(height)

    def set_values(self, poor, fair, good):
        self.vals = (poor, fair, good)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tot = max(1e-9, sum(self.vals))
        x = 0.0
        path_w = self.width()
        for lv in self.order:
            w = path_w * self.vals[lv] / tot
            p.fillRect(QRectF(x, 0, w + 0.5, self.height()), QColor(LV_COL[lv]))
            x += w


class PreviewTimeline(QWidget):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.setFixedHeight(128)

    def set_blocks(self, blocks):
        self.blocks = blocks
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left, W = 46, self.width() - 52
        rows = {2: 8, 1: 38, 0: 68}
        for lv, y in rows.items():
            p.setPen(QColor(C["MUTED"]))
            p.drawText(QRectF(0, y, 42, 22), Qt.AlignVCenter | Qt.AlignLeft, LV_NAME[lv])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2c2c2c"))
            p.drawRoundedRect(QRectF(left, y, W, 22), 3, 3)
        for x0, x1, lv in self.blocks:
            p.setBrush(QColor(LV_COL[lv]))
            p.drawRoundedRect(QRectF(left + x0 * W, rows[lv], max(2.0, (x1 - x0) * W), 22), 2, 2)
        p.setPen(QColor(C["MUTED"]))
        for i, t in enumerate(("0%", "25%", "50%", "75%", "100%")):
            p.drawText(QRectF(min(left + W * i / 4 - 20, self.width() - 40), 98, 40, 16), Qt.AlignCenter, t)


class AutoPreview(QWidget):
    """AUTO mode preview: all the footage on top, the kept shots flowing down into 'Your edit' (packed back to back,
    same time scale), so you see at a glance how much survives and where it comes from."""

    def __init__(self):
        super().__init__()
        self.blocks, self.total = [], 1.0
        self.setFixedHeight(150)

    def set_data(self, blocks, total):
        self.blocks, self.total = blocks, max(1e-6, total)   # blocks: [(x0, x1, keep)] as fractions of the footage
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left, W = 72, self.width() - 78
        y1, y2, h = 8, 104, 24
        for y, t in ((y1, "Footage"), (y2, "Your edit")):
            p.setPen(QColor(C["MUTED"]))
            p.drawText(QRectF(0, y, left - 6, h), Qt.AlignVCenter | Qt.AlignLeft, t)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#262626"))
            p.drawRoundedRect(QRectF(left, y, W, h), 3, 3)
        x = 0.0
        greens = (QColor("#4cc38a"), QColor("#3a9e70"))
        k = 0
        for x0, x1, keep in self.blocks:
            if not keep:
                p.setBrush(QColor("#3a3a3a"))
                p.drawRect(QRectF(left + x0 * W, y1 + 8, max(1.0, (x1 - x0) * W), h - 16))
                continue
            w = (x1 - x0) * W
            fan = QColor("#4cc38a")
            fan.setAlpha(38)
            p.setBrush(fan)
            from PySide6.QtGui import QPolygonF
            p.drawPolygon(QPolygonF([QPointF(left + x0 * W, y1 + h), QPointF(left + x1 * W, y1 + h),
                                     QPointF(left + x + w, y2), QPointF(left + x, y2)]))
            p.setBrush(greens[k % 2])
            p.drawRoundedRect(QRectF(left + x0 * W, y1, max(2.0, w), h), 2, 2)
            p.drawRoundedRect(QRectF(left + x, y2, max(2.0, w), h), 2, 2)
            x += w
            k += 1
        if k:
            secs = sum(b[1] - b[0] for b in self.blocks if b[2]) * self.total
            p.setPen(QColor("#ececec"))
            p.drawText(QRectF(left + x + 8, y2, 200, h), Qt.AlignVCenter | Qt.AlignLeft,
                       f"{int(secs // 60)}:{int(secs % 60):02d}  ·  {secs / self.total:.0%} kept")


class DropZone(QFrame):
    dropped = Signal(list)
    clicked = Signal()

    def __init__(self, compact=False):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignCenter)
        self.t1 = lbl("Drop more videos here" if compact else "Drag & drop a folder or videos here", "h2" if not compact else "")
        self.t1.setAlignment(Qt.AlignCenter)
        self.t2 = lbl("or click to browse" if compact else "or click to browse · MP4, MOV, MXF, AVI, MKV and any other format FFmpeg reads", "muted", True)
        self.t2.setAlignment(Qt.AlignCenter)
        v.addWidget(self.t1)
        v.addWidget(self.t2)
        if compact:
            self.setFixedHeight(64)

    def mousePressEvent(self, _):
        self.clicked.emit()

    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        self.dropped.emit([u.toLocalFile() for u in e.mimeData().urls()])


class Switch(QWidget):
    toggled = Signal(bool)

    def __init__(self, on=True):
        super().__init__()
        self.on = on
        self.setFixedSize(34, 18)
        self.setCursor(Qt.PointingHandCursor)

    def set(self, v):
        self.on = v
        self.update()

    def mousePressEvent(self, _):
        self.on = not self.on
        self.update()
        self.toggled.emit(self.on)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["BLUE"] if self.on else "#4a4a4a"))
        p.drawRoundedRect(0, 0, 34, 18, 9, 9)
        p.setBrush(QColor("white"))
        p.drawEllipse(18 if self.on else 2, 2, 14, 14)


class SliderRow(QWidget):
    changed = Signal(int)
    switched = Signal(bool)

    def __init__(self, title, sub, value, lo=0, hi=100, suffix="%", switch=False, on=True):
        super().__init__()
        self.suffix = suffix
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(2)
        top = QHBoxLayout()
        self.t = lbl(title)
        q = lbl("?", "muted")
        q.setToolTip(sub)
        self.pct = lbl(f"{value}{suffix}")
        self.pct.setStyleSheet(f"color:{C['HOT']};font-size:12px")
        top.addWidget(self.t)
        top.addWidget(q)
        top.addStretch()
        top.addWidget(self.pct)
        self.sw = None
        if switch:
            self.sw = Switch(on)
            self.sw.toggled.connect(self._sw)
            top.addSpacing(10)
            top.addWidget(self.sw)
        self.sl = QSlider(Qt.Horizontal)
        self.sl.setRange(lo, hi)
        self.sl.setValue(value)
        self.sl.valueChanged.connect(self._ch)
        v.addLayout(top)
        v.addWidget(self.sl)
        v.addWidget(lbl(sub, "muted", True))
        self._dim(on)

    def _dim(self, on):
        self.sl.setEnabled(on)
        self.t.setStyleSheet("font-weight:600" + ("" if on else ";color:#5e5e5e"))

    def _sw(self, on):
        self._dim(on)
        self.switched.emit(on)

    def _ch(self, x):
        self.pct.setText(f"{x}{self.suffix}")
        self.changed.emit(x)

    def set(self, x, on=True):
        self.sl.blockSignals(True)
        self.sl.setValue(x)
        self.sl.blockSignals(False)
        self.pct.setText(f"{x}{self.suffix}")
        if self.sw:
            self.sw.set(on)
        self._dim(on)


class Toast(QLabel):
    """Green notification that slides down from the top of the window and goes away by itself."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background:#1f8f4e;color:white;font-weight:700;font-size:13px;border-radius:8px;padding:10px 18px")
        self.hide()
        self.anim = None

    def show_msg(self, text, ms=3000):
        self.setText("✓  " + text)
        self.adjustSize()
        x = (self.parent().width() - self.width()) // 2
        self.move(x, -self.height())
        self.show()
        self.raise_()
        self._slide(QPoint(x, -self.height()), QPoint(x, 14))
        QTimer.singleShot(ms, lambda: self._slide(self.pos(), QPoint(self.x(), -self.height() - 4), hide=True))

    def _slide(self, a, b, hide=False):
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(260)
        self.anim.setStartValue(a)
        self.anim.setEndValue(b)
        if hide:
            self.anim.finished.connect(self.hide)
        self.anim.start()


def _fmt_dur(s):
    s = int(max(0, s))
    return f"{s // 3600}h {s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


class ProgressPanel(QFrame):
    """The same loading bar for every long process: step text, percentage, a thick bar, elapsed and time left."""

    def __init__(self):
        super().__init__()
        self.setObjectName("progress")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(6)
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight:600;color:#ececec")
        self.pct = QLabel("0%")
        self.pct.setStyleSheet(f"font-weight:700;color:{C['HOT']}")
        top.addWidget(self.title, 1)
        top.addWidget(self.pct)
        v.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setObjectName("big")
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        v.addWidget(self.bar)
        dr = QHBoxLayout()
        self.detail = lbl("", "muted")
        dr.addWidget(self.detail, 1)
        self.b_cancel = btn("Cancel")
        self.b_cancel.hide()
        dr.addWidget(self.b_cancel)
        v.addLayout(dr)
        self._cancel_cb = None
        self.b_cancel.clicked.connect(lambda: self._cancel_cb and self._cancel_cb())
        self.t0 = time.time()
        self.hide()

    def allow_cancel(self, cb):
        self._cancel_cb = cb
        self.b_cancel.setVisible(cb is not None)

    def start(self, text="Starting…"):
        self.t0 = time.time()
        self.set(text, 0.0)
        self.show()

    def set(self, text, f):
        f = max(0.0, min(1.0, f))
        self.title.setText(text)
        self.pct.setText(f"{int(f * 100)}%")
        self.bar.setValue(int(f * 1000))
        el = time.time() - self.t0
        left = f"  ·  about {_fmt_dur(el * (1 - f) / f)} left" if f > 0.03 and el > 3 and f < 1 else ""
        self.detail.setText(f"{_fmt_dur(el)} elapsed{left}")


class JobCard(QFrame):
    def __init__(self, path):
        super().__init__()
        self.setObjectName("card")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 10, 10, 10)
        self.th = QLabel()
        self.th.setFixedSize(120, 68)
        self.th.setAlignment(Qt.AlignCenter)
        self.th.setStyleSheet("background:#161616;border-radius:4px")
        v = QVBoxLayout()
        v.setAlignment(Qt.AlignVCenter)
        self.name = lbl(Path(path).name)
        self.name.setStyleSheet("font-weight:600")
        self.name.setToolTip(path)
        self.state = lbl("waiting", "muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        row = QHBoxLayout()
        row.addWidget(self.name, 1)
        row.addWidget(self.state)
        v.addLayout(row)
        v.addWidget(self.bar)
        h.addWidget(self.th)
        h.addLayout(v, 1)

    def set_thumb(self, data):
        img = QImage.fromData(data)
        if not img.isNull():
            self.th.setPixmap(QPixmap.fromImage(img).scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_progress(self, f):
        self.state.setText(f"running · {int(f * 100)}%")
        self.bar.setValue(int(f * 1000))

    def finish(self, ok, msg=""):
        self.bar.setValue(1000 if ok else 0)
        self.state.setText("done" if ok else "failed")
        if not ok:
            self.state.setStyleSheet(f"color:{C['POOR']}")
            self.setToolTip(msg)


# ---------------------------------------------------------------- analysis worker

class Worker(QThread):
    progress = Signal(int, float)
    done = Signal(int, object)
    failed = Signal(int, str)
    thumb = Signal(int, bytes)

    def __init__(self, paths, jobs=2):
        super().__init__()
        self.paths = paths
        self.n = max(1, jobs)
        self._stop = False
        self._run = threading.Event()
        self._run.set()

    def pause(self, on):
        self._run.clear() if on else self._run.set()

    def cancel(self):
        self._stop = True
        self._run.set()

    def _check(self):
        self._run.wait()
        return self._stop

    def _one(self, i):
        path = self.paths[i]
        try:
            if self._stop:
                raise InterruptedError("Cancelled")
            self.thumb.emit(i, core.thumb_jpeg(path))
            a = core.analyze(path, lambda f: self.progress.emit(i, f), self._check)
            self.done.emit(i, a)
        except InterruptedError:
            self.failed.emit(i, "Cancelled")
        except Exception as e:
            self.failed.emit(i, str(e))

    def run(self):
        with ThreadPoolExecutor(self.n) as ex:
            list(ex.map(self._one, range(len(self.paths))))


# ---------------------------------------------------------------- pages

class NewProjectDialog(QDialog):
    DESC = {"footage": "Grade your clips Good / Fair / Poor and export a colour-labelled timeline.",
            "multicam": "Sync several cameras to a master audio recorder, then build the multicam edit."}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setFixedWidth(440)
        self._kind = "footage"
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(10)
        v.addWidget(lbl("New Project", "h2"))
        v.addWidget(lbl("Project type", "muted"))
        row = QHBoxLayout()
        self.b1 = btn("Footage Selection", "seg", lambda: self.pick("footage"))
        self.b2 = btn("Multicam", "seg", lambda: self.pick("multicam"))
        row.addWidget(self.b1)
        row.addWidget(self.b2)
        v.addLayout(row)
        self.desc = lbl("", "muted", True)
        v.addWidget(self.desc)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Project name")
        self.edit.returnPressed.connect(self.accept)
        v.addWidget(self.edit)
        r2 = QHBoxLayout()
        r2.addStretch()
        r2.addWidget(btn("Cancel", slot=self.reject))
        r2.addWidget(btn("Create Project", "primary", self.accept))
        v.addLayout(r2)
        self.pick("footage")

    def pick(self, k):
        self._kind = k
        for b, on in ((self.b1, k == "footage"), (self.b2, k == "multicam")):
            b.setProperty("active", on)
            repolish(b)
        self.desc.setText(self.DESC[k])

    def kind(self):
        return self._kind

    def name(self):
        return self.edit.text().strip()


def nice_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except Exception:
        return "never"


class ProjectCard(QFrame):
    """Compact card: 4 per row on the dashboard."""
    opened = Signal(str)
    deleted = Signal(str)

    def __init__(self, p):
        super().__init__()
        self.pid, self.pname = p["id"], p["name"]
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(104)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 8, 10)
        v.setSpacing(3)
        top = QHBoxLayout()
        multi = p.get("type") == "multicam"
        badge = QLabel("MULTICAM" if multi else "FOOTAGE")
        col = "#7c5cff" if multi else C["BLUE"]
        badge.setStyleSheet(f"background:{col};color:white;font-size:9px;font-weight:700;border-radius:3px;padding:1px 6px")
        top.addWidget(badge)
        top.addStretch()
        d = btn("✕", "del", self.ask_delete)
        d.setToolTip("Delete project")
        d.setFixedSize(22, 22)
        top.addWidget(d)
        v.addLayout(top)
        name = QLabel()
        name.setStyleSheet("font-size:13px;font-weight:700;color:#ececec")
        name.setText(name.fontMetrics().elidedText(p["name"], Qt.ElideRight, 230))
        name.setToolTip(p["name"])
        v.addWidget(name)
        if multi:
            v.addWidget(lbl(f"{len(p.get('files', []))} files · {len(p['cams'])} cameras", "muted"))
            v.addWidget(lbl(f"Synced {nice_date((p.get('sync') or {}).get('when', ''))}", "muted"))
        else:
            nh = len(p["history"])
            v.addWidget(lbl(f"{len(p['videos'])} videos · {nh} {'analysis' if nh == 1 else 'analyses'}", "muted"))
            last = p["history"][-1]["ts"] if p["history"] else ""
            v.addWidget(lbl(f"Analysed {nice_date(last)}", "muted"))
        v.addStretch()

    def ask_delete(self):
        from PySide6.QtWidgets import QMessageBox
        r = QMessageBox.question(self, "Delete project",
                                 f"Delete \"{self.pname}\"?\nYour video files are not touched, only the project is removed.")
        if r == QMessageBox.Yes:
            self.deleted.emit(self.pid)

    def mousePressEvent(self, _):
        self.opened.emit(self.pid)


class Dashboard(QWidget):
    new_project = Signal()
    open_project = Signal(str)
    delete_project = Signal(str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        head = QHBoxLayout()
        head.addWidget(lbl("Projects", "h1"))
        head.addStretch()
        head.addWidget(btn("+  New Project", "primary", self.new_project.emit))
        v.addLayout(head)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        # empty state
        e = QWidget()
        ev = QVBoxLayout(e)
        ev.setAlignment(Qt.AlignCenter)
        ic = QLabel()
        ic.setPixmap(icon_pix("folder", 56))
        ic.setAlignment(Qt.AlignCenter)
        t = lbl("No projects yet", "h2")
        t.setAlignment(Qt.AlignCenter)
        d = lbl("Create your first project to start analyzing videos and generating color-coded timelines.", "muted", True)
        d.setAlignment(Qt.AlignCenter)
        d.setMaximumWidth(380)
        b = btn("+  Create First Project", "primary", self.new_project.emit)
        for w in (ic, t):
            ev.addWidget(w, 0, Qt.AlignHCenter)
        ev.addWidget(d, 0, Qt.AlignHCenter)
        ev.addSpacing(8)
        ev.addWidget(b, 0, Qt.AlignHCenter)
        self.stack.addWidget(e)
        # list state
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.stack.addWidget(self.scroll)

    def refresh(self, projects):
        if not projects:
            self.stack.setCurrentIndex(0)
            return
        w = QWidget()
        g = QGridLayout(w)
        g.setAlignment(Qt.AlignTop)
        g.setSpacing(14)
        for i, p in enumerate(reversed(projects)):
            c = ProjectCard(p)
            c.opened.connect(self.open_project)
            c.deleted.connect(self.delete_project)
            g.addWidget(c, i // 4, i % 4)
        for col in range(4):
            g.setColumnStretch(col, 1)
        self.scroll.setWidget(w)
        self.stack.setCurrentIndex(1)


class ProjectPage(QWidget):
    back = Signal()
    analyze = Signal()
    open_history = Signal(int)

    def __init__(self, store):
        super().__init__()
        self.store, self.p, self.an = store, None, None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName("head")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(20, 10, 20, 10)
        hh.addWidget(btn("←  Projects", "link", self.back.emit))
        self.title = lbl("", "h2")
        hh.addWidget(self.title)
        hh.addStretch()
        self.b_an = btn("Analyze Footage", "primary", self.analyze.emit)
        hh.addWidget(self.b_an)
        v.addWidget(head)
        body = QHBoxLayout()
        body.setSpacing(0)
        v.addLayout(body, 1)

        # left: source videos
        left = QFrame()
        left.setObjectName("leftpanel")
        left.setFixedWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 14, 16, 14)
        lh = QHBoxLayout()
        lh.addWidget(lbl("SOURCE VIDEOS", "section"))
        lh.addStretch()
        lh.addWidget(btn("Add Folder", slot=self.pick_dir))
        lv.addLayout(lh)
        self.big = DropZone()
        self.big.dropped.connect(self.add)
        self.big.clicked.connect(self.pick_files)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.hint = lbl("Select videos and press Delete to remove them.", "muted")
        self.small = DropZone(compact=True)
        self.small.dropped.connect(self.add)
        self.small.clicked.connect(self.pick_files)
        lv.addWidget(self.big, 1)
        lv.addWidget(self.list, 1)
        lv.addWidget(self.hint)
        lv.addWidget(self.small)
        body.addWidget(left)

        # middle: settings
        mid = QScrollArea()
        mid.setWidgetResizable(True)
        mw = QWidget()
        mv = QVBoxLayout(mw)
        mv.setContentsMargins(22, 16, 22, 16)
        mv.addWidget(lbl("SELECTION MODE", "section"))
        mrow = QHBoxLayout()
        self.m_auto = btn("Auto", "seg", lambda: self.set_mode("auto"))
        self.m_custom = btn("Custom", "seg", lambda: self.set_mode("custom"))
        mrow.addWidget(self.m_auto)
        mrow.addWidget(self.m_custom)
        mv.addLayout(mrow)
        self.mode_desc = lbl("", "muted", True)
        mv.addWidget(self.mode_desc)
        mv.addSpacing(8)

        # AUTO box
        self.auto_box = QWidget()
        av = QVBoxLayout(self.auto_box)
        av.setContentsMargins(0, 0, 0, 0)
        self.r_thr = SliderRow("Selection threshold", "Higher = pickier. Shots scoring at least this much are kept.",
                               60, lo=20, hi=90, suffix="")
        self.r_thr.changed.connect(lambda x: self.set_s("thr", x))
        av.addWidget(self.r_thr)
        mvr = QHBoxLayout()
        mvr.addWidget(lbl("Cut out camera moves"))
        mq = lbl("?", "muted")
        mq.setToolTip("When the camera moves from one person to another, the move is cut out and every person becomes its own shot.")
        mvr.addWidget(mq)
        mvr.addStretch()
        self.sw_moves = Switch(True)
        self.sw_moves.toggled.connect(lambda v: self.set_s("cutmoves", v))
        mvr.addWidget(self.sw_moves)
        av.addLayout(mvr)
        mv.addWidget(self.auto_box)

        # CUSTOM box
        self.custom_box = QWidget()
        cv = QVBoxLayout(self.custom_box)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(lbl("ANALYSIS SENSITIVITY", "section"))
        cv.addWidget(lbl("Switch a check on or off and adjust how strict it is", "muted"))
        cv.addSpacing(6)
        self.rows = {}
        for key, title, sub in SLIDERS:
            r = SliderRow(title, sub, DEFAULTS[key], switch=True)
            r.changed.connect(lambda x, k=key: self.set_s(k, x))
            r.switched.connect(lambda on, k=key: self.set_on(k, on))
            self.rows[key] = r
            cv.addWidget(r)
        cv.addSpacing(8)
        cv.addWidget(lbl("STRICTNESS PRESET", "section"))
        cv.addWidget(lbl("Controls how aggressively quality issues are flagged. Lenient keeps more frames; Strict removes more.", "muted", True))
        self.combo = QComboBox()
        self.combo.addItems(["Lenient", "Normal", "Strict", "Custom"])
        self.combo.currentTextChanged.connect(self.preset)
        cv.addWidget(self.combo)
        cv.addSpacing(10)
        cv.addWidget(lbl("QUALITY THRESHOLD", "section"))
        cv.addWidget(lbl("Define the distribution of quality ratings across your footage", "muted"))
        self.dist_lbl = QLabel()
        cv.addWidget(self.dist_lbl)
        self.range = RangeBar()
        self.range.changed.connect(self.set_range)
        cv.addWidget(self.range)
        pr = QHBoxLayout()
        pr.addWidget(lbl("Protect good frames"))
        pq = lbl("?", "muted")
        pq.setToolTip("Frames that score well are never marked Poor, even when they fall inside the lowest percentile.")
        pr.addWidget(pq)
        pr.addStretch()
        self.sw_protect = Switch(True)
        self.sw_protect.toggled.connect(lambda v: self.set_s("protect", v))
        pr.addWidget(self.sw_protect)
        cv.addLayout(pr)
        mv.addWidget(self.custom_box)

        # common: minimum cut
        mv.addSpacing(6)
        self.r_cut = SliderRow("Minimum cut length",
                               "Auto: kept shots shorter than this are dropped. Custom: shorter segments are merged into their neighbour.",
                               3, lo=1, hi=10, suffix=" s")
        self.r_cut.changed.connect(lambda x: self.set_s("mincut", x))
        mv.addWidget(self.r_cut)
        mv.addSpacing(6)
        ph = QHBoxLayout()
        ph.addWidget(lbl("PREVIEW TIMELINE", "section"))
        self.sample = lbl("sample data · run an analysis to see your footage", "muted")
        ph.addStretch()
        ph.addWidget(self.sample)
        mv.addLayout(ph)
        self.pv = PreviewTimeline()
        mv.addWidget(self.pv)
        self.apv = AutoPreview()
        mv.addWidget(self.apv)
        self.bar = DistBar(order=(0, 1, 2), height=8)
        mv.addWidget(self.bar)
        self.actual = lbl("", "muted")
        mv.addWidget(self.actual)
        mv.addStretch()
        mid.setWidget(mw)
        body.addWidget(mid, 1)

        # right: history / queue
        right = QFrame()
        right.setObjectName("rightpanel")
        right.setFixedWidth(290)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        hw = QWidget()
        hv = QVBoxLayout(hw)
        hv.setContentsMargins(14, 10, 14, 10)
        self.hist_title = lbl("ANALYSIS HISTORY", "section")
        self.hist_count = lbl("0 past analyses", "muted")
        self.hist = QListWidget()
        self.hist.itemClicked.connect(lambda it: self.open_history.emit(it.data(Qt.UserRole)))
        self.hist_empty = lbl("No analyses yet\nRun your first analysis to see history here", "muted", True)
        self.hist_empty.setAlignment(Qt.AlignCenter)
        for w in (self.hist_title, self.hist_count):
            hv.addWidget(w)
        hv.addWidget(self.hist, 1)
        hv.addWidget(self.hist_empty, 1)
        qw = QWidget()
        qv = QVBoxLayout(qw)
        qv.setContentsMargins(14, 10, 14, 10)
        self.queue_lbl = lbl("Queue is empty", "muted", True)
        self.queue_lbl.setAlignment(Qt.AlignCenter)
        qv.addWidget(self.queue_lbl)
        qv.addStretch()
        self.tabs.addTab(hw, "History")
        self.tabs.addTab(qw, "Queue")
        rv.addWidget(self.tabs)
        body.addWidget(right)
        self.list.keyPressEvent = self._list_key

    # --- loading
    def load(self, p):
        self.p = p
        p["settings"] = norm_settings(p["settings"])
        self.title.setText(p["name"])
        s = p["settings"]
        for k, r in self.rows.items():
            r.set(s[k], s["on"][k])
        self.combo.blockSignals(True)
        self.combo.setCurrentText(s["preset"])
        self.combo.blockSignals(False)
        self.range.set_values(s["p1"], s["p2"])
        self.r_thr.set(s["thr"])
        self.r_cut.set(s["mincut"])
        self.sw_protect.set(s["protect"])
        self.sw_moves.set(s["cutmoves"])
        self.apply_mode()
        self.refresh_videos()
        self.refresh_history()
        self.refresh_preview()

    def refresh_videos(self):
        self.list.clear()
        for path in self.p["videos"]:
            it = QListWidgetItem(Path(path).name)
            it.setToolTip(path)
            it.setData(Qt.UserRole, path)
            self.list.addItem(it)
        has = bool(self.p["videos"])
        self.big.setVisible(not has)
        self.list.setVisible(has)
        self.hint.setVisible(has)
        self.small.setVisible(has)
        self.b_an.setEnabled(has)

    def refresh_history(self):
        h = self.p["history"]
        self.an = [core.Analysis.from_json(d) for d in h[-1]["clips"]] if h else None
        self.hist.clear()
        for i in reversed(range(len(h))):
            e = h[i]
            it = QListWidgetItem(f"{e['ts'][:16].replace('T', ' ')}\n{e['n']} videos · {hms(e['duration'])} · {e['seconds']:.0f}s")
            it.setData(Qt.UserRole, i)
            self.hist.addItem(it)
        self.hist_count.setText(f"{len(h)} past analyses")
        self.hist.setVisible(bool(h))
        self.hist_empty.setVisible(not h)

    # --- video list
    def add(self, paths):
        have = set(self.p["videos"])
        found, skipped = scan_paths(paths)
        if skipped:
            self.hint.setText(f"Skipped {skipped} non-video file(s) (e.g. XML sidecars).")
            QTimer.singleShot(5000, lambda: self.hint.setText("Select videos and press Delete to remove them."))
        for f in found:
            if f not in have:
                self.p["videos"].append(f)
                have.add(f)
        self.store.save()
        self.refresh_videos()

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Choose videos", "", "All files (*)")
        self.add(fs)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if d:
            self.add([d])

    def _list_key(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            gone = {i.data(Qt.UserRole) for i in self.list.selectedItems()}
            self.p["videos"] = [x for x in self.p["videos"] if x not in gone]
            self.store.save()
            self.refresh_videos()
        else:
            QListWidget.keyPressEvent(self.list, e)

    # --- settings
    def apply_mode(self):
        auto = self.p["settings"]["mode"] == "auto"
        self.auto_box.setVisible(auto)
        self.custom_box.setVisible(not auto)
        for b, on in ((self.m_auto, auto), (self.m_custom, not auto)):
            b.setProperty("active", on)
            repolish(b)
        self.mode_desc.setText(
            "The program decides, like the first version: it keeps the good shots (focus, stability, exposure) and exports them on one track. Moves between people are cut out."
            if auto else
            "You choose which checks run, how strict each one is, and how the footage is split into Poor / Fair / Good.")

    def set_mode(self, m):
        self.p["settings"]["mode"] = m
        self.store.save()
        self.apply_mode()
        self.refresh_preview()

    def set_on(self, k, on):
        self.p["settings"]["on"][k] = on
        self.store.save()
        self.refresh_preview()

    def set_s(self, k, x):
        self.p["settings"][k] = x
        self.store.save()
        self.refresh_preview()

    def preset(self, name):
        if name in PRESETS:
            s = self.p["settings"]
            s["p1"], s["p2"] = PRESETS[name]
            s["preset"] = name
            self.range.set_values(s["p1"], s["p2"])
            self.store.save()
            self.refresh_preview()

    def set_range(self, p1, p2):
        s = self.p["settings"]
        s["p1"], s["p2"], s["preset"] = p1, p2, "Custom"
        self.combo.blockSignals(True)
        self.combo.setCurrentText("Custom")
        self.combo.blockSignals(False)
        self.store.save()
        self.refresh_preview()

    def refresh_preview(self):
        s = self.p["settings"]
        p1, p2 = s["p1"], s["p2"]
        self.dist_lbl.setText(
            f'<span style="color:{C["POOR"]}">●</span> <b>Poor {p1}%</b> &nbsp; '
            f'<span style="color:{C["FAIR"]}">●</span> <b>Fair {p2 - p1}%</b> &nbsp; '
            f'<span style="color:{C["GOOD"]}">●</span> <b>Good {100 - p2}%</b>')
        if self.an:
            total = sum(a.duration for a in self.an) or 1
            blocks, pos = [], 0.0
            for a, segs in zip(self.an, core.grade_segments(self.an, s)):
                for t0, t1, g in segs:
                    blocks.append((pos + t0 / total, pos + t1 / total, g))
                pos += a.duration / total
            self.sample.hide()
        else:
            rng = np.random.default_rng(7)
            sc = np.convolve(rng.random(60), np.ones(4) / 4, "same")
            sc = (sc - sc.min()) / (sc.max() - sc.min()) * 100
            if s["mode"] == "auto":
                lo = hi = s["thr"]
            else:
                lo, hi = np.percentile(sc, [p1, p2])
            blocks = [(i / 60, (i + 1) / 60, 0 if x < lo else 1 if x < hi else 2) for i, x in enumerate(sc)]
            self.sample.show()
        merged = []
        for b in blocks:
            if merged and merged[-1][2] == b[2] and abs(merged[-1][1] - b[0]) < 1e-6:
                merged[-1] = (merged[-1][0], b[1], b[2])
            else:
                merged.append(b)
        dur = [0.0, 0.0, 0.0]
        for x0, x1, g in merged:
            dur[g] += x1 - x0
        tot = sum(dur) or 1
        auto = s["mode"] == "auto"
        self.pv.setVisible(not auto)
        self.bar.setVisible(not auto)
        self.apv.setVisible(auto)
        if auto:
            total = sum(a.duration for a in self.an) if self.an else 600.0
            shots = sum(1 for b in merged if b[2] == 2)
            if self.an:
                shots = sum(1 for segs in core.grade_segments(self.an, s) for x in segs if x[2] == 2)
            self.apv.set_data([(x0, x1, g == 2) for x0, x1, g in merged], total)
            kept = dur[2] / tot * total
            self.actual.setText(f"Keeps {shots} shots: {int(kept // 60)}:{int(kept % 60):02d} of {int(total // 60)}:{int(total % 60):02d} "
                                f"of footage. Everything else is left out of the export." + ("" if self.an else "  (sample data)"))
        else:
            self.bar.set_values(*dur)
            self.actual.setText(f"Result: Poor {dur[0] / tot * 100:.0f}%  ·  Fair {dur[1] / tot * 100:.0f}%  ·  Good {dur[2] / tot * 100:.0f}%")
        self.pv.set_blocks(merged)

class AnalyzingPage(QWidget):
    """Top: the clips being analysed right now. Middle: the overall progress. Bottom: the finished clips."""
    pause = Signal(bool)
    cancel = Signal()
    back = Signal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 18, 32, 14)
        v.setSpacing(8)
        # ---- top: running now
        self.run_t = lbl("RUNNING NOW", "section")
        v.addWidget(self.run_t)
        rs = QScrollArea()
        rs.setWidgetResizable(True)
        rs.setFixedHeight(112)
        rs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rw = QWidget()
        self.run_l = QHBoxLayout(rw)
        self.run_l.setContentsMargins(0, 0, 0, 0)
        self.run_l.setAlignment(Qt.AlignLeft)
        rs.setWidget(rw)
        v.addWidget(rs)
        # ---- middle: overall progress
        mid = QFrame()
        mid.setObjectName("card")
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(20, 14, 20, 14)
        mv.setSpacing(6)
        hdr = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icon_pix("film", 40))
        hdr.addWidget(ic)
        tt = QVBoxLayout()
        tt.addWidget(lbl("Analyzing Your Footage", "h2"))
        tt.addWidget(lbl("Now we play the waiting game...", "muted"))
        hdr.addLayout(tt, 1)
        self.b_pause = btn("Pause Analysis", slot=self._toggle)
        hdr.addWidget(self.b_pause)
        hdr.addWidget(btn("Cancel", slot=self.cancel.emit))
        mv.addLayout(hdr)
        row = QHBoxLayout()
        self.count = lbl("", "muted")
        row.addWidget(self.count, 1)
        self.pct = lbl("0%")
        self.pct.setStyleSheet(f"color:{C['HOT']};font-weight:700")
        row.addWidget(self.pct)
        mv.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setObjectName("big")
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        mv.addWidget(self.bar)
        self.eta = lbl("", "muted")
        mv.addWidget(self.eta)
        foot = QHBoxLayout()
        foot.addWidget(lbl("It keeps running in the background: you can leave this screen and come back from Analysis "
                           "Queue (Open) or from the project (View analysis).", "muted", True), 1)
        foot.addWidget(btn("←  Return to project", "link", self.back.emit))
        mv.addLayout(foot)
        v.addWidget(mid)
        # ---- bottom: finished
        self.ok_t = lbl("COMPLETED", "section")
        v.addWidget(self.ok_t)
        os_ = QScrollArea()
        os_.setWidgetResizable(True)
        ow = QWidget()
        self.ok_g = QGridLayout(ow)
        self.ok_g.setAlignment(Qt.AlignTop)
        self.ok_g.setContentsMargins(0, 0, 8, 0)
        self.ok_g.setColumnStretch(0, 1)
        self.ok_g.setColumnStretch(1, 1)
        os_.setWidget(ow)
        v.addWidget(os_, 1)
        self.cards, self.total, self.fin, self.part, self.state = [], 0, 0, [], []
        self.paused = False

    def _toggle(self):
        self.paused = not self.paused
        self.b_pause.setText("Resume Analysis" if self.paused else "Pause Analysis")
        self.pause.emit(self.paused)

    def start(self, paths):
        for lay in (self.run_l, self.ok_g):
            while lay.count():
                w = lay.takeAt(0).widget()
                if w:
                    w.deleteLater()
        self.cards = [JobCard(p) for p in paths]
        for c in self.cards:
            c.setFixedWidth(360)
            c.hide()
        self.total, self.fin, self.part = len(paths), 0, [0.0] * len(paths)
        self.state = ["waiting"] * len(paths)
        self.t0 = time.time()
        self.paused = False
        self.b_pause.setText("Pause Analysis")
        self._upd()

    def _upd(self):
        f = sum(self.part) / max(1, self.total)
        self.bar.setValue(int(f * 1000))
        self.pct.setText(f"{int(f * 100)}%")
        running = self.state.count("running")
        waiting = self.state.count("waiting")
        self.count.setText(f"{self.fin} of {self.total} clips done  ·  {running} running  ·  {waiting} waiting")
        el = time.time() - getattr(self, "t0", time.time())
        self.eta.setText(f"{_fmt_dur(el)} elapsed" + (f"  ·  about {_fmt_dur(el * (1 - f) / f)} left" if 0.03 < f < 1 and el > 3 else ""))
        self.run_t.setText(f"RUNNING NOW  {running}")
        self.ok_t.setText(f"COMPLETED  {self.fin}")

    def _running(self, i):
        if self.state[i] == "waiting":           # the clip has started: show it on top
            self.state[i] = "running"
            self.run_l.addWidget(self.cards[i])
            self.cards[i].show()
            self._upd()

    def thumb(self, i, data):
        self.cards[i].set_thumb(data)
        self._running(i)

    def progress(self, i, f):
        self._running(i)
        self.part[i] = f
        self.cards[i].set_progress(f)
        self._upd()

    def finished(self, i, ok, msg=""):
        self.part[i] = 1.0
        self.fin += 1
        self.state[i] = "done"
        c = self.cards[i]
        c.finish(ok, msg)
        c.setMinimumWidth(0)
        c.setMaximumWidth(16777215)
        n = self.fin - 1
        self.ok_g.addWidget(c, n // 2, n % 2)
        c.show()
        self._upd()


class ResultsPage(QWidget):
    back = Signal()

    def __init__(self, store):
        super().__init__()
        self.store, self.p, self.items = store, None, []
        self.sw = "Premiere Pro"
        h = QHBoxLayout(self)
        h.setContentsMargins(40, 24, 40, 24)
        h.setSpacing(20)
        left = QVBoxLayout()
        left.setAlignment(Qt.AlignTop)
        top = QHBoxLayout()
        top.addWidget(lbl("RESULTS OVERVIEW", "section"))
        top.addStretch()
        top.addWidget(btn("←  Back to project", "link", self.back.emit))
        left.addLayout(top)
        g = QHBoxLayout()
        self.stats = {}
        for key, title in (("videos", "VIDEOS ANALYZED"), ("dur", "TOTAL DURATION"), ("segs", "SEGMENTS FOUND"), ("time", "ANALYSIS TIME")):
            c = QFrame()
            c.setObjectName("card")
            cv = QVBoxLayout(c)
            cv.addWidget(lbl(title, "muted"))
            s = lbl("0", "stat")
            cv.addWidget(s)
            self.stats[key] = s
            g.addWidget(c)
        left.addLayout(g)
        dc = QFrame()
        dc.setObjectName("card")
        dv = QVBoxLayout(dc)
        dv.addWidget(lbl("Quality Distribution", "muted"))
        self.dbar = DistBar(order=(2, 1, 0), height=12)
        dv.addWidget(self.dbar)
        self.legend = QLabel()
        dv.addWidget(self.legend)
        left.addWidget(dc)
        nx = QFrame()
        nx.setObjectName("info")
        nv = QVBoxLayout(nx)
        nv.addWidget(lbl("What to do next", "h2"))
        self.next = lbl("", "muted", True)
        nv.addWidget(self.next)
        left.addWidget(nx)
        left.addWidget(lbl("CLIP DETAILS (average score 0-100, seconds per level)", "section"))
        self.detail = QTableWidget(0, 9)
        self.detail.setHorizontalHeaderLabels(["Clip", "Contrast", "Exposure", "Focus", "Importance", "Stability", "Poor", "Fair", "Good"])
        self.detail.verticalHeader().hide()
        self.detail.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail.setSelectionMode(QAbstractItemView.NoSelection)
        hh = self.detail.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        left.addWidget(self.detail, 1)
        h.addLayout(left, 3)

        right = QFrame()
        right.setObjectName("card")
        right.setFixedWidth(300)
        right.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 14, 16, 16)
        rv.addWidget(lbl("OUTPUT SETTINGS", "section"))
        rv.addWidget(lbl("Save Results File In", "muted"))
        r = QHBoxLayout()
        self.dir = QLineEdit()
        r.addWidget(self.dir, 1)
        r.addWidget(btn("Browse", slot=self.browse))
        rv.addLayout(r)
        rv.addWidget(lbl("Filename", "muted"))
        self.name = QLineEdit()
        rv.addWidget(self.name)
        rv.addWidget(lbl("Output Software", "muted"))
        sr = QHBoxLayout()
        self.b_pp, self.b_dr = btn("Premiere Pro", "seg", lambda: self.set_sw("Premiere Pro")), btn("DaVinci Resolve", "seg", lambda: self.set_sw("DaVinci Resolve"))
        sr.addWidget(self.b_pp)
        sr.addWidget(self.b_dr)
        rv.addLayout(sr)
        rv.addWidget(lbl("Sequence Settings", "muted"))
        self.c_size, self.c_rate, self.c_fields = QComboBox(), QComboBox(), QComboBox()
        self.c_size.addItems(SEQ_SIZES)
        self.c_rate.addItems(SEQ_RATES)
        self.c_fields.addItems(list(SEQ_FIELDS))
        for w, t in ((self.c_size, "Frame size"), (self.c_rate, "Frame rate"), (self.c_fields, "Fields")):
            row = QHBoxLayout()
            row.addWidget(lbl(t, "muted"))
            row.addWidget(w, 1)
            rv.addLayout(row)
        rv.addSpacing(6)
        rv.addWidget(btn("Generate Result File", "primary", self.generate))
        self.msg = lbl("", "ok", True)
        rv.addWidget(self.msg)
        h.addWidget(right, 0, Qt.AlignTop)

    def set_sw(self, sw):
        self.sw = sw
        for b, n in ((self.b_pp, "Premiere Pro"), (self.b_dr, "DaVinci Resolve")):
            b.setProperty("active", n == sw)
            repolish(b)
        if self.p:
            self.p["out_sw"] = sw
            self.store.save()
        app = "Adobe Premiere Pro" if sw == "Premiere Pro" else "DaVinci Resolve"
        how = "File > Import" if sw == "Premiere Pro" else "File > Import > Timeline"
        self.next.setText(f"Import the generated XML file into {app} ({how}). Every segment on the timeline is "
                          f"graded with colors: red / yellow / green, so you can spot the poor, fair and good shots at a glance.")

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Save results in", self.dir.text())
        if d:
            self.dir.setText(d)

    def show_entry(self, p, entry, seconds=None):
        self.p = p
        self.msg.setText("")
        s = p["settings"]
        an = [core.Analysis.from_json(d) for d in entry["clips"]]
        self.items = list(zip(an, core.grade_segments(an, s)))
        cnt, dur = [0, 0, 0], [0.0, 0.0, 0.0]
        auto = s.get("mode", "auto") == "auto"
        self.detail.setRowCount(len(self.items))
        for r, (a, segs) in enumerate(self.items):
            d = [0.0, 0.0, 0.0]
            for t0, t1, g in segs:
                cnt[g] += 1
                dur[g] += t1 - t0
                d[g] += t1 - t0
            st = a.comp["stability_v1"] if auto and "stability_v1" in a.comp else a.comp["stability"]
            vals = [a.comp[k].mean() * 100 for k in ("contrast", "exposure", "focus", "importance")] + [st.mean() * 100]
            cells = [Path(a.info.path).name] + [f"{v:.0f}" for v in vals] + [f"{x:.0f}s" for x in d]
            for c, t in enumerate(cells):
                it = QTableWidgetItem(t)
                if c >= 6:
                    it.setForeground(QColor(LV_COL[c - 6]))
                self.detail.setItem(r, c, it)
        tot = sum(dur) or 1
        self.stats["videos"].setText(str(len(an)))
        self.stats["dur"].setText(hms(sum(a.duration for a in an)))
        self.stats["segs"].setText(str(sum(cnt)))
        self.stats["time"].setText(f"{entry['seconds']:.0f}s")
        self.dbar.set_values(*dur)
        self.legend.setText("&nbsp;&nbsp;".join(
            f'<span style="color:{LV_COL[l]}">●</span> {LV_NAME[l]} <b>{dur[l] / tot * 100:.0f}%</b> '
            f'<span style="color:{C["MUTED"]}">({cnt[l]} segment{'s' if cnt[l] != 1 else ''})</span>' for l in (2, 1, 0)))
        self.dir.setText(p["out_dir"] or str(Path(an[0].info.path).parent))
        self.name.setText(p["out_name"] or p["name"])
        self.set_sw(p["out_sw"])
        sq = {**SEQ_DEFAULT, **p.get("seq", {})}
        self.c_size.setCurrentText(sq["size"])
        self.c_rate.setCurrentText(sq["rate"])
        self.c_fields.setCurrentText(sq["fields"])

    def generate(self):
        name = self.name.text().strip() or "MoneyMakingMachine"
        out = Path(self.dir.text()) / (name + ".xml")
        try:
            seq = {"fields": SEQ_FIELDS[self.c_fields.currentText()]}
            if self.c_size.currentIndex() > 0:
                seq["width"], seq["height"] = (int(x) for x in self.c_size.currentText().split(" x "))
            if self.c_rate.currentIndex() > 0:
                seq["fps"] = float(self.c_rate.currentText())
            n = core.export_xmeml(self.items, str(out), name, seq, single=self.p["settings"].get("mode", "auto") == "auto")
        except Exception as e:
            self.msg.setStyleSheet(f"color:{C['POOR']}")
            self.msg.setText(f"Error: {e}")
            return
        self.p["out_dir"], self.p["out_name"] = self.dir.text(), name
        self.p["seq"] = dict(size=self.c_size.currentText(), rate=self.c_rate.currentText(), fields=self.c_fields.currentText())
        self.store.save()
        self.msg.setStyleSheet(f"color:{C['GOOD']}")
        self.msg.setText(f"Saved {n} segments to\n{out}")
        if getattr(self, "export_done", None):
            self.export_done(out.name)


class QueuePage(QWidget):
    """Everything that is running right now: footage analyses, multicam Sync and Auto Edit."""
    open_job = Signal(str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(10)
        v.addWidget(lbl("Analysis Queue", "h1"))
        v.addWidget(lbl("Everything that is running right now. Jobs keep running while you work on other pages.", "muted"))
        self.box = QVBoxLayout()
        self.box.setSpacing(10)
        v.addLayout(self.box)
        self.empty = lbl("Nothing is running right now.", "muted")
        v.addWidget(self.empty)
        v.addStretch()
        self.cards = {}

    def set_job(self, text):   # kept for compatibility, the main window refreshes the queue itself
        pass

    def set_jobs(self, jobs):
        """jobs: {key: (title, status, progress 0..1)}"""
        for k in list(self.cards):
            if k not in jobs:
                self.cards.pop(k)[0].deleteLater()
        for k, (title, status, prog) in jobs.items():
            if k not in self.cards:
                c = QFrame()
                c.setObjectName("card")
                cv = QVBoxLayout(c)
                top = QHBoxLayout()
                t = lbl(title, "h2")
                top.addWidget(t, 1)
                top.addWidget(btn("Open", slot=lambda _=False, k=k: self.open_job.emit(k)))
                cv.addLayout(top)
                s = lbl("", "muted", True)
                cv.addWidget(s)
                b = QProgressBar()
                b.setObjectName("big")
                b.setRange(0, 1000)
                b.setTextVisible(False)
                cv.addWidget(b)
                self.box.addWidget(c)
                self.cards[k] = (c, t, s, b)
            c, t, s, b = self.cards[k]
            t.setText(title)
            s.setText(f"{status}  ·  {int(prog * 100)}%")
            b.setValue(int(prog * 1000))
        self.empty.setVisible(not jobs)

# ---------------------------------------------------------------- multicam

CONF_COL = {"high": C["GOOD"], "medium": C["FAIR"], "low": "#f08a3c", "approx": "#9b8cff", "fail": C["POOR"]}
CONF_NAME = {"high": "High", "medium": "Medium", "low": "Check", "approx": "By time", "fail": "Failed"}
MEDIA_EXT = core.VIDEO_EXT | sync.AUDIO_EXT


def fmt_t(sec):
    sign = "-" if sec < 0 else ""
    sec = abs(sec)
    return f"{sign}{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:06.3f}"


def parse_t(txt):
    txt = txt.strip().replace(",", ".")
    neg = txt.startswith("-")
    sec = 0.0
    for x in txt.lstrip("+-").split(":"):
        sec = sec * 60 + float(x)
    return -sec if neg else sec


def scan_media(paths):
    """Everything that can hold video or sound. The first folder level under a dropped folder (card / camera folder)
    is remembered as 'group' and used to tell cameras apart."""
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in MEDIA_EXT and not f.name.startswith(".") and not is_proxy(f):
                    rel = f.relative_to(p).parts
                    out.append(dict(path=str(f), group=rel[0] if len(rel) > 1 else p.name))
        elif p.is_file() and p.suffix.lower() not in SKIP_EXT and not p.name.startswith(".") and not is_proxy(p):
            out.append(dict(path=str(p), group=p.parent.name))
    return out


class SyncMap(QWidget):
    """Audio master row, an 'Auto edit' row coloured by camera, then one row per camera."""

    def __init__(self):
        super().__init__()
        self.mdur, self.rows, self.edit, self.tmin, self.tmax = 0.0, [], [], 0.0, 1.0
        self.setMinimumHeight(140)

    def set_data(self, spans, rows, edit=None, music=None):
        """spans: [(t0, t1)] of the recorder files on the common timeline. music: [(offset, music map)]."""
        self.spans, self.rows, self.edit, self.music = spans or [], rows, edit or [], music or []
        starts = [b[0] for _, _, bl in rows for b in bl] + [s[0] for s in self.spans]
        ends = [b[1] for _, _, bl in rows for b in bl] + [s[1] for s in self.spans]
        self.tmin = min([0.0] + starts)
        self.tmax = max(ends) if ends else 1.0
        self.setMinimumHeight(80 + 26 * (len(rows) + 3))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left = 130
        W, span = self.width() - left - 12, max(1e-6, self.tmax - self.tmin)
        X = lambda t: left + (t - self.tmin) / span * W

        def row(y, label, color=None):
            if color:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                p.drawEllipse(QRectF(0, y + 6, 8, 8))
            p.setPen(QColor(C["TEXT"] if color else C["MUTED"]))
            p.drawText(QRectF(14 if color else 0, y, left - 18, 20), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(label, Qt.ElideRight, left - 20))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2c2c2c"))
            p.drawRoundedRect(QRectF(left, y, W, 20), 3, 3)

        y = 6
        row(y, "Recorder")
        p.setBrush(QColor("#3d6fb6"))
        for s0, s1 in getattr(self, "spans", []):
            p.drawRoundedRect(QRectF(X(s0), y, max(2.0, X(s1) - X(s0) - 1), 20), 3, 3)
        y += 26
        if self.music:
            # music row: energy of every song (darker = calmer), speech in grey, drops in pink, tempo written in
            row(y, "Music")
            for g, mm in self.music:
                ev = mm.get("energy", {}).get("v", [])
                er = mm.get("energy", {}).get("rate", 2)
                for r0, r1, kind, bpm in mm.get("regions", []):
                    x0, x1 = X(g + r0), X(g + r1)
                    if kind == "speech":
                        p.setBrush(QColor("#4a4a4a"))
                        p.drawRect(QRectF(x0, y + 7, max(1.0, x1 - x0), 6))
                    elif kind == "music":
                        step = max(1, int((r1 - r0) * er / max(1.0, x1 - x0)))
                        for k in range(int(r0 * er), int(r1 * er), step):
                            if k >= len(ev):
                                break
                            e = ev[k]
                            col = QColor.fromHsvF(0.6 - 0.55 * e, 0.75, 0.45 + 0.5 * e)
                            p.setBrush(col)
                            p.drawRect(QRectF(X(g + k / er), y + 1 + 18 * (1 - e) * 0.6, max(1.0, X(g + (k + step) / er) - X(g + k / er)),
                                              18 - 18 * (1 - e) * 0.6))

                for d0, d1 in mm.get("drops", []):
                    p.setBrush(QColor("#ff5c8a"))
                    p.drawRect(QRectF(X(g + d0) - 1, y - 2, 2.5, 24))
                ss = director.song_starts(mm)                 # the tempo written at the start of every song
                for k, (t0, bpm) in enumerate(ss):
                    t1 = ss[k + 1][0] if k + 1 < len(ss) else mm.get("duration", t0)
                    if X(g + t1) - X(g + t0) > 52:
                        p.setPen(QColor("#ececec"))
                        p.drawText(QRectF(X(g + t0) + 3, y, X(g + t1) - X(g + t0) - 6, 20), Qt.AlignVCenter | Qt.AlignLeft,
                                   f"{bpm:.0f} BPM")
                        p.setPen(Qt.NoPen)
            y += 26
        row(y, "Auto edit")
        for t0, t1, col in self.edit:
            p.setBrush(QColor(col))
            p.drawRect(QRectF(X(t0), y + 1, max(1.5, X(t1) - X(t0)), 18))
        y += 34
        for label, color, blocks in self.rows:
            row(y, label, color)
            for t0, t1, conf in blocks:
                p.setBrush(QColor(CONF_COL[conf]))
                p.drawRoundedRect(QRectF(X(t0), y + 3, max(2.0, X(t1) - X(t0)), 14), 2, 2)
            y += 26
        y += 4
        p.setPen(QColor(C["MUTED"]))
        step = next((s for s in (10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200) if span / s <= 8), 7200)
        t = (self.tmin // step) * step
        while t <= self.tmax:
            if t >= self.tmin:
                a = abs(t)
                lab = (f"{int(a // 3600)}:{int(a % 3600 // 60):02d}:{int(a % 60):02d}" if step >= 60 else f"{int(a)}s")
                p.drawText(QRectF(X(t) - 34, y, 68, 16), Qt.AlignCenter, ("-" if t < 0 else "") + lab)
            t += step


class MCWorker(QThread):
    """mode 'sync': read files, find the recorder, sync audio (fast).  mode 'analyze': video analysis for the auto edit."""
    progress = Signal(str, float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, mode, files, cache=None, todo=None, jobs=2, masters=None):
        super().__init__()
        self.mode, self.files, self.cache, self.todo, self.jobs, self._stop = mode, files, cache or {}, todo or [], jobs, False
        self.masters = masters or []

    def cancel(self):
        self._stop = True

    def run(self):
        logging.info("multicam job '%s' started (%d files)", self.mode, len(self.files or self.todo or []))
        try:
            if self.mode == "xml":
                self.done.emit(xmlimport.build(self.todo, lambda s, f: self.progress.emit(s, f), lambda: self._stop))
                return
            self.done.emit(self._sync() if self.mode == "sync" else self._analyze())
        except InterruptedError:
            self.failed.emit("Cancelled")
        except Exception as e:
            logging.exception("multicam job failed")
            self.failed.emit(str(e))

    def _sync(self):
        files, n = self.files, max(1, len(self.files))
        infos = {}
        for i, f in enumerate(files):
            if self._stop:
                raise InterruptedError
            self.progress.emit(f"Step 1 · reading files: {i + 1} of {n}", 0.05 * i / n)
            infos[f["path"]] = sync.media_info(f["path"])
        masters, videos, note, extra = sync.classify(files, infos)
        if not masters:
            raise ValueError(note or "No audio master found.")
        withsound = [v for v in videos if infos[v]["audio"]] + extra
        info, res = sync.run_sync(masters, withsound, lambda s, f: self.progress.emit(s, 0.05 + 0.95 * f), lambda: self._stop,
                                  clocks={p: i["clock"] for p, i in infos.items()}, groups={f["path"]: f["group"] for f in files},
                                  jobs=self.jobs)
        for v in videos:
            if v not in res:
                res[v] = dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0,
                              dur=infos[v]["duration"], manual=False, error="No audio stream")
        placed = sync.place_by_time(files, infos, res, info)      # drone / mic-off clips: approximately, by their clock
        return dict(infos=infos, masters=info, results=res, note=note,
                    report=getattr(sync.run_sync, "report", "") + (f" · {placed} clip(s) without sound placed by time" if placed else ""))

    def _analyze(self):
        an, keys = {}, {}
        for v in self.todo:
            st = Path(v).stat()
            keys[v] = f"{st.st_size}-{int(st.st_mtime)}"
            c = self.cache.get(v)
            if c and c.get("key") == keys[v]:
                try:
                    an[v] = core.Analysis.from_json(c["a"])
                except Exception:
                    pass
        left = [v for v in self.todo if v not in an]
        done = [0]
        self.progress.emit(f"Step 2 · analysing video for the auto edit: 0 of {len(left)}", 0.0)

        def one(v):
            if self._stop:
                return
            an[v] = core.analyze(v, cancel=lambda: self._stop)
            done[0] += 1
            self.progress.emit(f"Step 2 · analysing video for the auto edit: {done[0]} of {len(left)} clips done", done[0] / max(1, len(left)))

        with ThreadPoolExecutor(max(1, self.jobs)) as ex:
            list(ex.map(one, left))
        if self._stop:
            raise InterruptedError
        # the music map of every recorder file (once: kept in the project)
        maps = {}
        need = [(i, m) for i, m in enumerate(self.masters) if m.get("path") and not m.get("music") and Path(m["path"]).exists()]
        for n, (i, m) in enumerate(need):
            if self._stop:
                raise InterruptedError
            self.progress.emit(f"Step 2 · reading the music (beats, bars, drops): {n + 1} of {len(need)}", (n + 0.5) / len(need))
            try:
                maps[i] = music.analyze(sync.audio_pcm(m["path"]))
            except Exception:
                logging.exception("music analysis failed for %s", m["path"])
        return dict(analyses=an, keys=keys, music=maps)


class MulticamPage(QWidget):
    back = Signal()

    def __init__(self, store):
        super().__init__()
        self.store, self.p, self.worker, self.an, self.edits, self._paths = store, None, None, {}, [], []
        self._job_p, self.job_status, self.job_progress = None, "", 0.0
        self.timer = QTimer(singleShot=True, interval=200)
        self.timer.timeout.connect(self.recompute)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName("head")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(20, 10, 20, 10)
        hh.addWidget(btn("←  Projects", "link", self.back.emit))
        self.title = lbl("", "h2")
        hh.addWidget(self.title)
        hh.addStretch()
        self.b_exp = btn("Export XML", slot=self.export)
        self.b_xml = btn("Import XML", slot=self.import_xml)
        self.b_xml.setToolTip("Use a timeline that is already synced in Syncaila, Premiere Pro or DaVinci Resolve (FCP7 XML).")
        self.b_auto = btn("Auto Edit", slot=self.run_auto)
        self.b_run = btn("Sync", "primary", self.toggle_run)
        self.b_beat = btn("Beat check", "link", self.export_beatcheck)
        self.b_beat.setToolTip("Exports the recorder with a click on every beat (higher on beat 1 of the bar, a long tone on every "
                               "drop) as one sequence: listen / look at the waveform to check the beat on your music.")
        hh.addWidget(self.b_beat)
        hh.addWidget(self.b_xml)
        hh.addWidget(self.b_exp)
        hh.addWidget(self.b_auto)
        hh.addWidget(self.b_run)
        v.addWidget(head)
        body = QHBoxLayout()
        body.setSpacing(0)
        v.addLayout(body, 1)

        # left: everything dumped here
        left = QFrame()
        left.setObjectName("leftpanel")
        left.setFixedWidth(330)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 14, 16, 14)
        lh = QHBoxLayout()
        lh.addWidget(lbl("FOOTAGE", "section"))
        lh.addStretch()
        lh.addWidget(btn("Add Folder", slot=self.pick_dir))
        lv.addLayout(lh)
        self.big = DropZone()
        self.big.t1.setText("Drop everything here")
        self.big.t2.setText("Camera cards, recorder files, whole folders. The audio master and the cameras are found automatically.")
        self.big.dropped.connect(self.add)
        self.big.clicked.connect(self.pick_files)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.keyPressEvent = self._lkey
        self.count = lbl("", "muted", True)
        self.small = DropZone(compact=True)
        self.small.dropped.connect(self.add)
        self.small.clicked.connect(self.pick_files)
        lv.addWidget(self.big, 1)
        lv.addWidget(self.list, 1)
        lv.addWidget(self.count)
        lv.addWidget(self.small)
        body.addWidget(left)

        # center: tabs
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(18, 10, 18, 10)
        self.tabs = QTabWidget()
        t1 = QWidget()
        t1v = QVBoxLayout(t1)
        t1v.setContentsMargins(0, 10, 0, 0)
        top = QHBoxLayout()
        self.note = lbl("Drop your footage, then press Sync.", "muted", True)
        top.addWidget(self.note, 1)
        self.m_sel = QComboBox()
        self.m_sel.currentIndexChanged.connect(lambda _: self.refresh_map())
        top.addWidget(self.m_sel)
        t1v.addLayout(top)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        self.map = SyncMap()
        holder = QWidget()
        hv_ = QVBoxLayout(holder)
        hv_.setContentsMargins(0, 0, 0, 0)
        hv_.addWidget(self.map)
        sc.setWidget(holder)
        t1v.addWidget(sc, 1)
        dot = lambda c: f'<span style="color:{c}">●</span>'
        # the legend, one line per item (there is room under the map)
        rows_ = [(CONF_COL["high"], "High", "sure"),
                 (CONF_COL["medium"], "Medium", "very likely right"),
                 (CONF_COL["low"], "Check", "position unsure: on the \"check sync\" track, not used in the auto edit"),
                 (CONF_COL["approx"], "By time", "no usable sound, placed approximately by its clock, not used in the auto edit"),
                 (CONF_COL["fail"], "Failed", "not placed (see the Clips tab)"),
                 (None, "Auto edit row", "one colour per camera"),
                 (None, "Music row", "after Auto Edit: every song with its tempo, brighter = more intense, grey = speech"),
                 ("#ff5c8a", "Pink line", "a drop")]
        legend = QLabel("<table cellspacing='0' cellpadding='3'>" + "".join(
            f"<tr><td width='18'>{dot(c) if c else ''}</td><td><b style='color:#d6d6d6'>{t}</b></td><td>{d}</td></tr>"
            for c, t, d in rows_) + "</table>")
        legend.setWordWrap(True)
        legend.setStyleSheet(f"color:{C['MUTED']};font-size:12px")
        hv_.addSpacing(6)
        hv_.addWidget(legend)
        hv_.addStretch()
        self.tabs.addTab(t1, "Sync Map")
        self.cam_t = QTableWidget(0, 5)
        self.cam_t.setHorizontalHeaderLabels(["Camera (double-click to rename)", "Role", "Clips", "Footage", "In the edit"])
        self.cam_t.verticalHeader().hide()
        self.cam_t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cam_t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cam_t.itemChanged.connect(self.cam_renamed)
        self.tabs.addTab(self.cam_t, "Cameras")
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Camera", "Clip", "Master", "Start in master", "Duration", "Drift", "Sync", "FPS"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemChanged.connect(self.on_edit)
        self.tabs.addTab(self.table, "Clips")
        mv.addWidget(self.tabs, 1)
        self.pp = ProgressPanel()
        mv.insertWidget(0, self.pp)
        self.status = lbl("", "muted", True)
        mv.addWidget(self.status)
        body.addWidget(mid, 1)

        # right: auto director
        right = QFrame()
        right.setObjectName("rightpanel")
        right.setFixedWidth(310)
        ro = QVBoxLayout(right)
        ro.setContentsMargins(0, 0, 0, 0)
        rsc = QScrollArea()                      # everything stays readable on a small screen: the panel scrolls
        rsc.setWidgetResizable(True)
        rsc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rsc.setStyleSheet("QScrollArea{background:transparent;border:none}")
        rin = QWidget()
        rin.setStyleSheet("background:transparent")
        rv = QVBoxLayout(rin)
        rv.setContentsMargins(16, 14, 16, 14)
        rsc.setWidget(rin)
        ro.addWidget(rsc, 1)
        rv.addWidget(lbl("AUTO DIRECTOR", "section"))
        rv.addWidget(lbl("Picks the best camera for every moment. Changes apply instantly.", "muted", True))
        rv.addSpacing(6)
        self.d_rows = {}
        for key, title, sub, lo, hi, suf in (
                ("minshot", "Minimum shot", "No shot is shorter than this.", 1, 10, " s"),
                ("maxshot", "Maximum shot", "After this the edit prefers to cut to another camera.", 4, 120, " s"),
                ("pace", "Cut pace", "Calm (few cuts) ↔ fast (many cuts).", 0, 100, ""),
                ("energy", "Static  ↔  Handheld", "Left = prefer the static cameras, right = prefer the handheld ones.", 0, 100, "")):
            r = SliderRow(title, sub, director.DEFAULTS[key], lo=lo, hi=hi, suffix=suf)
            r.changed.connect(lambda x, k=key: self.set_d(k, x))
            self.d_rows[key] = r
            rv.addWidget(r)
        br = QHBoxLayout()
        br.addWidget(lbl("Cut on the beat"))
        bq = lbl("?", "muted")
        bq.setToolTip("On music: shots follow the bars and beats of the recorder (tempo followed song by song), a cut exactly "
                      "on every drop, faster cuts when the music is intense (options below). "
                      "On speech: cuts in the pauses between sentences. Off: the old way, on a 0.5 s grid.")
        br.addWidget(bq)
        br.addStretch()
        self.sw_beat = Switch(True)
        self.sw_beat.toggled.connect(lambda v: (self.set_d("beat", v), self._music_enabled()))
        br.addWidget(self.sw_beat)
        rv.addLayout(br)
        sb = QHBoxLayout()
        sb.addWidget(lbl("Static cameras only as backup"))
        sq = lbl("?", "muted")
        sq.setToolTip("The static cameras are used only when no handheld camera has a usable shot.")
        sb.addWidget(sq)
        sb.addStretch()
        self.sw_backup = Switch(False)
        self.sw_backup.toggled.connect(lambda v: self.set_d("static_backup", v))
        sb.addWidget(self.sw_backup)
        rv.addLayout(sb)
        # ---- on the music (the same for every project)
        rv.addSpacing(12)
        rv.addWidget(lbl("ON THE MUSIC  ·  ALL PROJECTS", "section"))
        rv.addWidget(lbl("Used when Cut on the beat is on.", "muted", True))
        ms = self.store.app.setdefault("music", dict(drop_beats=4, buildup="hold", energy_cuts=True))
        self.music_box = QWidget()
        mb = QVBoxLayout(self.music_box)
        mb.setContentsMargins(0, 4, 0, 0)
        mb.setSpacing(6)
        mb.addWidget(lbl("On a drop, change camera every"))
        self.c_drop = QComboBox()
        self._drop_vals = [1, 2, 4, 8, 16]
        self.c_drop.addItems(["1 beat", "2 beats", "1 bar (4 beats)", "2 bars", "4 bars"])
        self.c_drop.setCurrentIndex(self._drop_vals.index(ms.get("drop_beats", 4)) if ms.get("drop_beats", 4) in self._drop_vals else 2)
        self.c_drop.currentIndexChanged.connect(lambda i: self._set_music("drop_beats", self._drop_vals[i]))
        mb.addWidget(self.c_drop)
        mb.addWidget(lbl("Build-up before a drop"))
        self.c_build = QComboBox()
        self.c_build.addItems(["Hold one shot until the drop", "Cut faster and faster"])
        self.c_build.setCurrentIndex(0 if ms.get("buildup", "hold") == "hold" else 1)
        self.c_build.currentIndexChanged.connect(lambda i: self._set_music("buildup", "hold" if i == 0 else "accelerate"))
        mb.addWidget(self.c_build)
        er = QHBoxLayout()
        er.addWidget(lbl("Faster cuts when the music is more intense", "", True), 1)
        self.sw_energy = Switch(ms.get("energy_cuts", True))
        self.sw_energy.toggled.connect(lambda v: self._set_music("energy_cuts", v))
        er.addWidget(self.sw_energy, 0, Qt.AlignTop)
        mb.addLayout(er)
        rv.addWidget(self.music_box)
        rv.addSpacing(10)
        self.stats = lbl("Press Auto Edit to build the edit.", "muted", True)
        rv.addWidget(self.stats)
        rv.addStretch()
        eb = QHBoxLayout()
        eb.setContentsMargins(16, 6, 16, 12)
        eb.addWidget(btn("Export XML", "primary", self.export))
        ro.addLayout(eb)
        body.addWidget(right)

    def _set_music(self, k, v):
        """Music options are global: every multicam project uses them."""
        self.store.app.setdefault("music", {})[k] = v
        self.store.save_app()
        if self.p and self.p.get("sync"):
            self.timer.start()

    def _music_enabled(self):
        self.music_box.setEnabled(bool(self.sw_beat.on))

    # ---- load / migrate
    def load(self, p):
        self.p = p
        if "files" not in p:   # projects from the manual-cameras version
            fl = [dict(path=m, group=Path(m).parent.name) for m in p.get("masters", [])]
            fl += [dict(path=c, group=Path(c).parent.name) for cam in p.get("cams", []) for c in cam["clips"]]
            p.update(files=fl, sync=None, cams=[], infos={})
        p.setdefault("dir", dict(director.DEFAULTS))
        p["dir"] = {**director.DEFAULTS, **p["dir"]}
        self.title.setText(p["name"])
        QTimer.singleShot(0, self._music_enabled)
        for k, r in self.d_rows.items():
            r.set(p["dir"][k])
        self.sw_beat.set(p["dir"]["beat"])
        self.sw_backup.set(p["dir"]["static_backup"])
        blob = self.store.load_blob(p["id"])
        self.an = {}
        for path, v in blob.items():
            try:
                self.an[path] = core.Analysis.from_json(v["a"])
            except Exception:
                pass
        self.status.setText("")
        self.refresh_files()
        self.recompute()

    # ---- files
    def refresh_files(self):
        self.list.clear()
        for f in self.p["files"]:
            it = QListWidgetItem(f"{Path(f['path']).name}   ·   {f['group']}")
            it.setData(Qt.UserRole, f["path"])
            it.setToolTip(f["path"])
            self.list.addItem(it)
        has = bool(self.p["files"])
        self.big.setVisible(not has)
        self.list.setVisible(has)
        self.small.setVisible(has)
        self.count.setVisible(has)
        self.count.setText(f"{len(self.p['files'])} files. Select and press Delete to remove.")
        self._sync_buttons()

    def add(self, paths):
        have = {f["path"] for f in self.p["files"]}
        self.p["files"] += [f for f in scan_media(paths) if f["path"] not in have]
        self.store.save()
        self.refresh_files()

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Choose footage and audio", "", "All files (*)")
        self.add(fs)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder (cards, recorder, everything)")
        if d:
            self.add([d])

    def _lkey(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            gone = {i.data(Qt.UserRole) for i in self.list.selectedItems()}
            self.p["files"] = [f for f in self.p["files"] if f["path"] not in gone]
            self.store.save()
            self.refresh_files()
        else:
            QListWidget.keyPressEvent(self.list, e)

    # ---- run
    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _sync_buttons(self):
        busy = self._busy()
        mine = busy and self.p is getattr(self, "_job_p", None)
        mode = self.worker.mode if busy else ""
        self.b_run.setText("Cancel" if mine and mode == "sync" else "Sync")
        self.b_auto.setText("Cancel" if mine and mode == "analyze" else "Auto Edit")
        self.b_run.setEnabled((not busy and bool(self.p["files"])) or (mine and mode == "sync"))
        self.b_auto.setEnabled((not busy and bool(self.p.get("sync"))) or (mine and mode == "analyze"))
        self.b_xml.setEnabled(not busy)
        if mine and mode == "xml":
            self.b_run.setText("Cancel")
            self.b_run.setEnabled(False)
        self.pp.setVisible(bool(mine))
        if busy and not mine:
            self.status.setText(f"Another job is running ({self._job_p['name']}). See Analysis Queue.")

    def _start(self, worker, button):
        self._job_p, self.job_status, self.job_progress = self.p, "Starting…", 0.0
        self.pp.start()
        self.worker = worker
        worker.progress.connect(self.on_progress)
        worker.done.connect(self.on_done)
        worker.failed.connect(self.on_failed)
        self._button = button
        worker.start()
        self._sync_buttons()

    def toggle_run(self):
        if self._busy():
            if self.p is self._job_p:
                self.worker.cancel()
            return
        if self.p["files"]:
            self._start(MCWorker("sync", list(self.p["files"]), jobs=self.store.app["jobs"]), self.b_run)

    def import_xml(self):
        if self._busy():
            return
        f, _ = QFileDialog.getOpenFileName(self, "Import a synced timeline (Syncaila / Premiere / DaVinci)", "", "XML (*.xml)")
        if f:
            self._start(MCWorker("xml", None, todo=f), self.b_run)

    def run_auto(self):
        if self._busy():
            if self.p is self._job_p:
                self.worker.cancel()
            return
        s = self.p.get("sync")
        if not s:
            return
        todo = [x for c in self.p["cams"] if c["role"] != "Audio" and not c.get("approx") and not c.get("check") for x in c["clips"]]
        self._start(MCWorker("analyze", None, self.store.load_blob(self.p["id"]), todo, self.store.app["jobs"],
                             masters=s["masters"]), self.b_auto)

    def on_progress(self, text, f):
        self.job_status, self.job_progress = text, f
        if self.p is self._job_p:
            self.status.setText("")            # the panel above already shows it
            self.pp.set(text, f)

    def _finish(self):
        if self.worker:
            self.worker.wait(2000)
        self._sync_buttons()

    def on_failed(self, msg):
        logging.error("multicam job stopped: %s", msg)
        self._finish()
        if self.p is self._job_p:
            self.status.setText("Stopped: " + msg)

    def on_done(self, r):
        p = self._job_p                    # the project the job was started for (you may have opened another one)
        here = p is self.p
        an_all = dict(self.an) if here else {}
        if "cams" in r:      # XML imported
            p["files"], p["infos"] = r["files"], r["infos"]
            p["sync"] = dict(masters=r["masters"], clips=r["results"], when=datetime.now().isoformat(timespec="seconds"),
                             note="Imported from XML: positions taken as they are, no sync was done here.")
            p["cams"], p["source"] = r["cams"], "xml"
            if here:
                self.refresh_files()
                miss = r.get("missing") or []
                warn = (f"  {len(miss)} file(s) from the XML were not found and were skipped, e.g. {miss[0]}"
                        if miss else "")
                self.status.setText(f"XML imported: {len(r['results'])} clips on {len(r['cams'])} cameras. "
                                    "Press Auto Edit to build the edit, or Export XML." + warn)
        elif "results" in r:   # sync finished
            p["infos"] = r["infos"]
            p["sync"] = dict(masters=r["masters"], clips=r["results"], note=r["note"], when=datetime.now().isoformat(timespec="seconds"))
            cams = sync.auto_cameras(p["files"], r["infos"], r["results"], p.get("cams"))
            for c in cams:
                if not c.get("user") and c["role"] != "Audio":
                    have = [an_all.get(x) for x in c["clips"]]
                    c["role"] = director.detect_role(have) if all(h is not None for h in have) else "Handheld"
            p["cams"] = cams
            ok = sum(1 for x in r["results"].values() if x["conf"] != "fail")
            msg = ((r.get("report") or "") + "\n" +f"Sync finished: {ok} of {len(r['results'])} clips synced. You can export now, "
                                f"or press Auto Edit to let the program build the edit (this analyses the video and takes longer).")
            if here:
                self.status.setText(msg)
        else:                 # analysis finished
            for i, mm in (r.get("music") or {}).items():
                if i < len(p["sync"]["masters"]):
                    p["sync"]["masters"][i]["music"] = mm
            an_all.update(r["analyses"])
            if here:
                self.an.update(r["analyses"])
            blob = self.store.load_blob(p["id"])
            blob.update({k: dict(key=r["keys"].get(k, ""), a=a.to_json()) for k, a in r["analyses"].items()})
            self.store.save_blob(p["id"], blob)
            for c in p["cams"]:
                if not c.get("user") and c["role"] != "Audio":
                    c["role"] = director.detect_role([an_all.get(x) for x in c["clips"]])
            if here:
                self.status.setText("Auto edit ready. Tweak it on the right, then Export XML.")
        self.job_status, self.job_progress = "Done", 1.0
        self._finish()
        self.store.save()
        if here:
            self.recompute()

    # ---- director
    def set_d(self, k, v):
        self.p["dir"][k] = v
        self.store.save()
        self.timer.start()

    def recompute(self):
        s = self.p.get("sync") if self.p else None
        has_an = s and any(x in self.an for c in self.p["cams"] for x in c["clips"])
        st = {**self.p["dir"], **self.store.app.get("music", {})}
        self.edits = director.build(self.p["cams"], s["clips"], self.an, s["masters"], st) if has_an else []
        self.refresh_all()

    # ---- views
    def refresh_all(self):
        s = self.p.get("sync")
        self.b_exp.setEnabled(bool(s))
        self.m_sel.blockSignals(True)
        self.m_sel.clear()
        if s:
            self.m_sel.addItems([Path(m["path"]).name for m in s["masters"]])
        self.m_sel.setVisible(bool(s) and len(s["masters"]) > 1)
        self.m_sel.blockSignals(False)
        if s:
            res = s["clips"]
            cnt = {k: sum(1 for r in res.values() if r["conf"] == k) for k in CONF_NAME}
            m = ", ".join(Path(x["path"]).name for x in s["masters"] if x.get("path")) or "none (timeline from XML)"
            rates = sorted({i.get("fps") for i in self.p.get("infos", {}).values() if i.get("video") and i.get("fps")})
            mixed = (f"Mixed frame rates ({', '.join(f'{r:g}' for r in rates)} fps): handled in the export, "
                     f"the sequence uses the first camera's rate.  ") if len(rates) > 1 else ""
            self.note.setText(mixed + (s.get("note") + "  " if s.get("note") else "") +
                              f"Audio master: {m}  ·  {len(self.p['cams'])} cameras  ·  {cnt['high'] + cnt['medium']} clips synced, "
                              f"{cnt['low']} to check, {cnt['approx']} placed by time, {cnt['fail']} failed.")
        self.refresh_map()
        self.refresh_cams()
        self.refresh_clips()

    def refresh_map(self):
        s = self.p.get("sync") if self.p else None
        self.m_sel.hide()
        if not s:
            self.map.set_data([], [])
            return
        starts = sync.master_starts(s["masters"])
        spans = [(starts[i], starts[i] + m["duration"]) for i, m in enumerate(s["masters"])]
        rows = []
        for ci, cam in enumerate(self.p["cams"]):
            bl = [(starts[r["master"]] + r["offset"], starts[r["master"]] + r["offset"] + r["dur"], r["conf"])
                  for x in cam["clips"] if (r := s["clips"].get(x)) and r["conf"] != "fail"]
            rows.append((f"{cam['name']}  ({cam['role'][0]})", director.CAM_COLORS[ci % 8], bl))
        edit, shots, share = [], 0, {}
        for e in self.edits:
            if e:
                g = starts[e["master"]]
                edit += [(g + t0, g + t1, director.CAM_COLORS[ci % 8]) for t0, t1, ci in e["segs"]]
                shots += e["stats"]["shots"]
                for t0, t1, ci in e["segs"]:
                    share[ci] = share.get(ci, 0) + t1 - t0
        mus = [(starts[i], m["music"]) for i, m in enumerate(s["masters"]) if m.get("music")]
        self.map.set_data(spans, rows, edit, mus)
        if edit:
            tot = sum(share.values()) or 1
            avg = sum(share.values()) / max(1, shots)
            self.stats.setText(f"Auto edit: {shots} shots, average {avg:.1f} s\n" +
                               "  ·  ".join(f"{self.p['cams'][ci]['name']} {v / tot:.0%}" for ci, v in sorted(share.items())))
        else:
            self.stats.setText("Press Auto Edit to build the edit.")

    def refresh_cams(self):
        s = self.p.get("sync")
        self.cam_t.blockSignals(True)
        self.cam_t.setRowCount(len(self.p["cams"]))
        share = {}
        for e in self.edits:
            if e:
                for t0, t1, ci in e["segs"]:
                    share[ci] = share.get(ci, 0) + t1 - t0
        tot = sum(share.values()) or 1
        for ci, cam in enumerate(self.p["cams"]):
            it = QTableWidgetItem(cam["name"])
            it.setForeground(QColor(director.CAM_COLORS[ci % 8]))
            self.cam_t.setItem(ci, 0, it)
            cb = QComboBox()
            cb.addItems(["Audio"] if cam["role"] == "Audio" else ["Handheld", "Static"])
            cb.setEnabled(cam["role"] != "Audio")
            cb.setCurrentText(cam["role"])
            cb.setMinimumWidth(120)
            cb.setStyleSheet("QComboBox{padding:2px 8px;border-radius:3px}")
            cb.currentTextChanged.connect(lambda t, c=cam: self.set_role(c, t))
            self.cam_t.setCellWidget(ci, 1, cb)
            foot = sum(s["clips"][x]["dur"] for x in cam["clips"] if x in s["clips"]) if s else 0
            for col, txt in ((2, str(len(cam["clips"]))), (3, fmt_t(foot)[:-4]), (4, f"{share.get(ci, 0) / tot:.0%}")):
                x = QTableWidgetItem(txt)
                x.setFlags(x.flags() & ~Qt.ItemIsEditable)
                self.cam_t.setItem(ci, col, x)
        self.cam_t.resizeColumnToContents(1)
        for r_ in range(self.cam_t.rowCount()):
            self.cam_t.setRowHeight(r_, 34)
        self.cam_t.blockSignals(False)

    def set_role(self, cam, role):
        cam.update(role=role, user=True)
        self.store.save()
        self.recompute()

    def cam_renamed(self, item):
        if item.column() != 0:
            return
        cams = self.p["cams"]
        cam = cams[item.row()]
        new = item.text().strip() or cam["name"]
        other = next((c for c in cams if c is not cam and c["name"].lower() == new.lower()), None)
        if other:   # same name = same camera: merge
            other["clips"] += cam["clips"]
            other["user"] = True
            cams.remove(cam)
        else:
            cam.update(name=new, user=True)
        self.store.save()
        self.recompute()

    def refresh_clips(self):
        s = self.p.get("sync")
        rows = []
        if s:
            owner = {x: cam["name"] for cam in self.p["cams"] for x in cam["clips"]}
            rows = [(owner.get(f["path"], "–"), f["path"]) for f in self.p["files"] if f["path"] in s["clips"]]
        self._paths = [x for _, x in rows]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, (camname, path) in enumerate(rows):
            res = s["clips"][path]
            ok = res["conf"] != "fail"
            mp = s["masters"][res["master"]].get("path")
            cells = [camname, Path(path).name, (Path(mp).name if mp else "XML timeline") if ok else "–",
                     fmt_t(res["offset"]) if ok else "–", f"{int(res['dur'] // 60)}:{res['dur'] % 60:04.1f}",
                     f"{res['drift_ppm']:+.0f} ppm" if res["n"] >= 3 and ok else "–",
                     CONF_NAME[res["conf"]] + (" (manual)" if res.get("manual") else "") + (f" · {res['error']}" if res.get("error") else ""),
                     f"{self.p.get('infos', {}).get(path, {}).get('fps', 0):g}"]
            for c, t in enumerate(cells):
                it = QTableWidgetItem(t)
                if c == 6:
                    it.setForeground(QColor(CONF_COL[res["conf"]]))
                if c != 3 or not ok:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, it)
        self.table.blockSignals(False)

    def on_edit(self, item):
        if item.column() != 3 or not self.p.get("sync"):
            return
        r = self.p["sync"]["clips"][self._paths[item.row()]]
        try:
            r.update(offset=parse_t(item.text()), manual=True, conf="high")
        except ValueError:
            pass
        self.store.save()
        self.recompute()

    def export_beatcheck(self):
        s = self.p.get("sync") if self.p else None
        if not s or not any(m.get("music") for m in s["masters"]):
            self.status.setText("Beat check needs the music map: press Auto Edit first (it reads the beats and bars).")
            return
        first = next((m["path"] for m in s["masters"] if m.get("path")), None)
        folder = Path(first).parent / "Beat check"           # its own folder: never mixed with the footage
        try:
            folder.mkdir(exist_ok=True)
        except Exception:
            folder = Path(first).parent
        out, _ = QFileDialog.getSaveFileName(self, "Save beat check", str(folder / f"{self.p['name']} - beat check.xml"),
                                             "XML (*.xml)")
        if not out:
            return
        try:
            n = director.export_beatcheck(s["masters"], out)
            self.status.setText(f"Beat check saved ({n} recorder file(s) + click track). Import the XML: A1 = recorder, A2 = clicks "
                                "(high = beat 1 of the bar, long tone = drop).")
            logging.info("beat check exported: %s", out)
        except Exception as e:
            logging.exception("beat check failed")
            self.status.setText(f"Beat check failed: {e}")

    def export(self):
        s = self.p.get("sync")
        if not s:
            return
        first = next((m["path"] for m in s["masters"] if m.get("path")), None) or self.p["files"][0]["path"]
        d = str(Path(first).parent / f"{self.p['name']}.xml")
        out, _ = QFileDialog.getSaveFileName(self, "Save XML for Premiere", d, "XML (*.xml)")
        if not out:
            return
        try:
            r = director.export_xml(s["masters"], self.p["cams"], s["clips"], self.an, self.edits, out, self.p["name"])
            self.status.setText(f"Saved one sequence ({r['video_tracks']} video, {r['audio_tracks']} audio tracks"
                                f"{', each camera track holds only its cuts' if r['edit'] else ', full clips (no auto edit yet)'}) to {out}. "
                                f"Premiere: File > Import · DaVinci Resolve: File > Import > Timeline.")
        except Exception as e:
            self.status.setText(f"Export failed: {e}")


# ---------------------------------------------------------------- settings / performance

class SettingsPage(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.cores = os.cpu_count() or 4
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(8)
        v.addWidget(lbl("Settings", "h1"))
        v.addSpacing(6)
        v.addWidget(lbl("PERFORMANCE", "section"))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.cards = {}
        for k, t in (("cpu", "PROCESSOR"), ("total", "MEMORY (RAM)"), ("others", "USED BY OTHER APPS"), ("free", "FREE"), ("me", "THIS APP NOW")):
            c = QFrame()
            c.setObjectName("card")
            cv = QVBoxLayout(c)
            cv.addWidget(lbl(t, "muted"))
            s = lbl("–", "stat")
            cv.addWidget(s)
            self.cards[k] = s
            row.addWidget(c)
        v.addLayout(row)
        body = QHBoxLayout()
        body.setSpacing(24)
        left = QVBoxLayout()
        left.addWidget(lbl("Apps using the most memory", "muted"))
        self.top = QTableWidget(0, 2)
        self.top.setHorizontalHeaderLabels(["App", "Memory"])
        self.top.verticalHeader().hide()
        self.top.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.top.setSelectionMode(QAbstractItemView.NoSelection)
        self.top.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.top.setMinimumWidth(360)
        left.addWidget(self.top, 1)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        right.addWidget(lbl("How to make analysis and sync faster", "h2"))
        right.addWidget(lbl(
            "Memory (RAM) is not what limits the speed: the app only keeps small, downscaled pieces of each video in memory "
            "(usually well under 1-2 GB), so giving it more RAM would not make it faster. The time goes into decoding the video "
            "files, which is work for the processor (and the Mac's video decoder). What helps:", "muted", True))
        right.addWidget(lbl("• More parallel jobs: several clips are decoded at the same time. Each job uses a few processor "
                            "cores, so more jobs than about a quarter to a half of your cores usually brings little, and other apps "
                            "(Premiere) get slower.\n• Hardware decoding on the Mac: lets the built-in video decoder do part of the work "
                            "for the formats it supports (not every camera codec is supported, the app falls back automatically).\n"
                            "• Sync alone is fast. Only Auto Edit needs the full video analysis.", "muted", True))
        right.addSpacing(8)
        self.r_jobs = SliderRow("Parallel jobs", f"How many clips are analysed / read at the same time (your Mac has {self.cores} core{"s" if self.cores != 1 else ""}).",
                                store.app["jobs"], lo=1, hi=max(2, self.cores), suffix="")
        self.r_jobs.changed.connect(self.set_jobs)
        right.addWidget(self.r_jobs)
        hw = QHBoxLayout()
        hw.addWidget(lbl("Hardware video decoding (Mac)"))
        hw.addStretch()
        self.sw_hw = Switch(store.app["hwaccel"])
        self.sw_hw.toggled.connect(self.set_hw)
        hw.addWidget(self.sw_hw)
        right.addLayout(hw)
        right.addSpacing(18)
        right.addWidget(lbl("Updates and problems", "h2"))
        ur = QHBoxLayout()
        ur.addWidget(btn("Check for updates", slot=lambda: self.check_updates(False)))
        self.b_dl = btn("Download", "primary", self.open_release)
        self.b_dl.hide()
        ur.addWidget(self.b_dl)
        ur.addStretch()
        right.addLayout(ur)
        self.upd = lbl(f"You have {VER}.", "muted", True)
        right.addWidget(self.upd)
        right.addSpacing(6)
        right.addWidget(btn("Save error report…", slot=self.save_report), 0, Qt.AlignLeft)
        right.addWidget(lbl("When something does not work: save the report and send it to Claude. It contains the app's log "
                            "(what it did and any errors) and basic info about your computer, no video.", "muted", True))
        right.addStretch()
        rw_ = QWidget()
        rw_.setLayout(right)
        rs_ = QScrollArea()                       # nothing gets squeezed: the column scrolls on a small screen
        rs_.setWidgetResizable(True)
        rs_.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rs_.setStyleSheet("QScrollArea{border:none}")
        rs_.setWidget(rw_)
        body.addWidget(rs_, 1)
        v.addLayout(body, 1)
        self.timer = QTimer(interval=2000)
        self.timer.timeout.connect(self.refresh)

    update_found = Signal(str)
    def check_updates(self, silent=True):
        self.upd.setText("Checking…")
        self._uw = _Runner(lambda: latest_release())
        self._uw.done.connect(lambda r: self._update_result(r, silent))
        self._uw.failed.connect(self._update_failed)
        self._uw.start()

    def _update_failed(self, m):
        logging.warning("update check failed: %s", m)
        if "404" in m:
            why = "no version has been published on GitHub yet (the first one appears after the next build)"
        elif "403" in m or "429" in m:
            why = "GitHub refused the check for now (too many checks), try again later"
        elif "CERTIFICATE" in m.upper() or "SSL" in m.upper():
            why = "the secure connection could not be checked (certificates), send the error report to Claude"
        else:
            why = f"no internet connection or GitHub did not answer ({m[:60]})"
        self.upd.setText(f"You have {VER}. Could not check for updates: {why}.")

    def _update_result(self, r, silent):
        tag, url = r or ("", "")
        self._release_url = url
        if tag and _ver(tag) > _ver(VER):
            self.upd.setText(f"New version available: {tag} (you have {VER}).")
            self.b_dl.show()
            logging.info("update available: %s", tag)
            self.update_found.emit(tag)
        else:
            self.upd.setText(f"You have the latest version ({VER}).")
            self.b_dl.hide()

    def open_release(self):
        if getattr(self, "_release_url", ""):
            QDesktopServices.openUrl(QUrl(self._release_url))

    def save_report(self):
        out, _ = QFileDialog.getSaveFileName(self, "Save error report", str(Path.home() / "MoneyMakingMachine report.txt"),
                                             "Text (*.txt)")
        if not out:
            return
        log = self.store.dir / "app.log"
        try:
            text = log.read_text("utf-8", errors="replace")[-300000:]
        except Exception:
            text = "(no log yet)"
        info = (f"{APP} {VER}\n{platform.platform()}\nPython {platform.python_version()}\n"
                f"CPU cores: {os.cpu_count()}\nSettings: {json.dumps(self.store.app)}\n\n")
        Path(out).write_text(info + text, encoding="utf-8")
        self.upd.setText(f"Report saved: {out}")

    def set_jobs(self, x):
        self.store.app["jobs"] = x
        self.store.save_app()

    def set_hw(self, v):
        self.store.app["hwaccel"] = v
        self.store.save_app()

    def showEvent(self, e):
        self.refresh()
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def refresh(self):
        gb = lambda b: f"{b / 1024 ** 3:.1f} GB"
        self.cards["cpu"].setText(f"{self.cores} core{'s' if self.cores != 1 else ''}")
        try:
            import psutil
        except Exception:
            for k in ("total", "others", "free", "me"):
                self.cards[k].setText("n/a")
            return
        vm = psutil.virtual_memory()
        me = psutil.Process()
        mine = me.memory_info().rss + sum(c.memory_info().rss for c in me.children(recursive=True) if c.is_running())
        self.cards["total"].setText(gb(vm.total))
        self.cards["others"].setText(gb(max(0, vm.total - vm.available - mine)))
        self.cards["free"].setText(gb(vm.available))
        self.cards["me"].setText(gb(mine))
        procs = {}
        for p in psutil.process_iter(["name", "memory_info"]):
            try:
                n = p.info["name"] or "?"
                procs[n] = procs.get(n, 0) + p.info["memory_info"].rss
            except Exception:
                pass
        top = sorted(procs.items(), key=lambda kv: -kv[1])[:10]
        self.top.setRowCount(len(top))
        for r, (n, b) in enumerate(top):
            self.top.setItem(r, 0, QTableWidgetItem(n))
            self.top.setItem(r, 1, QTableWidgetItem(gb(b)))


# ---------------------------------------------------------------- info / how to use

class InfoPage(QWidget):
    """One page per feature (from the <h2> parts of help_text), a list on the left and a search bar."""

    def __init__(self, store):
        super().__init__()
        self.store = store
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        top = QHBoxLayout()
        top.addWidget(lbl("Info / How to use", "h1"))
        top.addStretch()
        self.b_ro = btn("RO", "seg", lambda: self.set_lang("ro"))
        self.b_en = btn("EN", "seg", lambda: self.set_lang("en"))
        for b in (self.b_ro, self.b_en):
            b.setFixedWidth(48)
            top.addWidget(b)
        v.addLayout(top)
        body = QHBoxLayout()
        body.setSpacing(18)
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(250)
        self.list.currentRowChanged.connect(self.show_row)
        left.addWidget(self.list, 1)
        self.hits = lbl("", "muted")
        left.addWidget(self.hits)
        body.addLayout(left)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setStyleSheet(f"QTextBrowser{{background:{C['BG']};border:none;color:#c9c9c9;font-size:13px}}")
        self.view.document().setDefaultStyleSheet(
            "h1{font-size:20px;color:#ececec;margin-bottom:6px} h2{font-size:18px;color:#ececec}"
            "h3{font-size:13px;color:#d6d6d6;margin-top:10px} li{margin-bottom:4px} b{color:#ececec}")
        body.addWidget(self.view, 1)
        v.addLayout(body, 1)
        foot = QLabel(f'<span style="color:{C["MUTED"]}">{APP} {VER} · </span>'
                      f'<a href="{AUTHOR_URL}" style="color:{C["HOT"]};text-decoration:none">by {AUTHOR}</a>')
        foot.setOpenExternalLinks(True)
        v.addWidget(foot, 0, Qt.AlignLeft)
        self.sections, self.shown = [], []
        self.set_lang(store.app.get("lang", "ro"), save=False)

    @staticmethod
    def _split(html, lang):
        import re as _re
        parts = _re.split(r"(?=<h2>)", html)
        out = [("Prezentare generală" if lang == "ro" else "Overview", parts[0])]
        for p in parts[1:]:
            m = _re.search(r"<h2>(.*?)</h2>", p, _re.S)
            out.append((_re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else "…", p))
        return out

    def set_lang(self, lang, save=True):
        for b, on in ((self.b_ro, lang == "ro"), (self.b_en, lang == "en")):
            b.setProperty("active", on)
            repolish(b)
        self.sections = self._split(help_text.HELP[lang], lang)
        self.search.setPlaceholderText("Caută…" if lang == "ro" else "Search…")
        self.refresh_list()
        if save:
            self.store.app["lang"] = lang
            self.store.save_app()

    def refresh_list(self):
        import re as _re
        q = self.search.text().strip().lower()
        plain = lambda h: _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", h)).lower()
        self.shown = [s for s in self.sections if not q or q in plain(s[1]) or q in s[0].lower()]
        self.list.blockSignals(True)
        self.list.clear()
        for t, _ in self.shown:
            self.list.addItem(t)
        self.list.blockSignals(False)
        self.hits.setText("" if not q else (f"{len(self.shown)} page(s) found" if self.shown else "Nothing found"))
        if self.shown:
            self.list.setCurrentRow(0)
            self.show_row(0)
        else:
            self.view.setHtml("")

    def show_row(self, r):
        if not (0 <= r < len(self.shown)):
            return
        self.view.setHtml(self.shown[r][1])
        q = self.search.text().strip()
        if q:
            self.view.moveCursor(self.view.textCursor().MoveOperation.Start)
            self.view.find(q)                       # jump to and select the first match


# ---------------------------------------------------------------- teaser studio

class _Runner(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, float)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args, progress=lambda t, f: self.progress.emit(t, f)))
        except TypeError:
            try:
                self.done.emit(self.fn(*self.args))
            except Exception as e:
                logging.exception("teaser job failed")
                self.failed.emit(str(e))
        except Exception as e:
            logging.exception("teaser job failed")
            self.failed.emit(str(e))


class MusicView(QWidget):
    """The music with its four parts, the drop and the beat grid of the current edit."""

    def __init__(self):
        super().__init__()
        self.env, self.dur, self.parts, self.drop, self.beats = None, 1.0, [], None, []
        self.setFixedHeight(130)

    def set_music(self, x, dur):
        n = 1200
        hop = max(1, len(x) // n)
        self.env = np.sqrt((x[:hop * n].reshape(n, hop).astype(np.float64) ** 2).mean(1))
        self.env /= self.env.max() + 1e-9
        self.dur = dur
        self.update()

    def set_parts(self, parts, drop, beats=None):
        self.parts, self.drop, self.beats = parts, drop, beats or []
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        X = lambda t: t / max(1e-6, self.dur) * W
        p.fillRect(0, 0, W, H, QColor("#1a1a1a"))
        if self.env is None:
            p.setPen(QColor(C["MUTED"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Add the music (one audio file, or the XML of your music edit)")
            return
        bounds = [0.0] + list(self.parts) + [self.dur]
        cols = ["#3d5a80", "#4a6fa5", "#7c5a3a", "#7e3fb0", "#9a7b12", "#b5179e"]
        for i in range(min(6, len(bounds) - 1)):
            c = QColor(cols[i])
            c.setAlpha(90)
            p.fillRect(QRectF(X(bounds[i]), 0, X(bounds[i + 1]) - X(bounds[i]), 22), c)
            p.setPen(QColor("#ececec"))
            r_ = QRectF(X(bounds[i]) + 4, 0, max(0.0, X(bounds[i + 1]) - X(bounds[i]) - 6), 22)
            p.save()
            p.setClipRect(r_)                       # a short part never writes over its neighbour
            p.drawText(r_, Qt.AlignVCenter, p.fontMetrics().elidedText(teaser.PARTS[i], Qt.ElideRight, int(r_.width())))
            p.restore()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["HOT"]))
        n = len(self.env)
        for i in range(n):
            h = self.env[i] * (H - 50)
            p.drawRect(QRectF(i / n * W, 26 + (H - 50 - h) / 2, max(1.0, W / n), h))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        for b in self.beats:
            p.drawLine(QPointF(X(b), H - 20), QPointF(X(b), H - 14))
        if self.drop is not None:
            p.setPen(QPen(QColor("#ff5c8a"), 2))
            p.drawLine(QPointF(X(self.drop), 22), QPointF(X(self.drop), H - 22))
            p.drawText(QRectF(X(self.drop) + 4, 24, 60, 16), Qt.AlignLeft, "DROP")
        p.setPen(QColor(C["MUTED"]))
        step = 30 if self.dur <= 400 else 60
        for t in range(0, int(self.dur) + 1, step):
            p.drawText(QRectF(X(t) - 20, H - 14, 40, 14), Qt.AlignCenter, f"{t // 60}:{t % 60:02d}")


class ShotStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.shots, self.dur = [], 1.0
        self.setFixedHeight(54)

    def set(self, shots, dur):
        self.shots, self.dur = shots, dur
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        W = self.width()
        p.fillRect(0, 0, W, 34, QColor("#1a1a1a"))
        for t0, t1, sh in self.shots:
            p.fillRect(QRectF(t0 / self.dur * W, 2, max(1.0, (t1 - t0) / self.dur * W - 0.6), 30), QColor(teaser.CAT_COLOR[sh["cat"]]))
        x = 0
        p.setPen(QColor(C["MUTED"]))
        for c in ("bride", "groom", "couple", "church", "venue", "party", "drone"):
            p.fillRect(QRectF(x, 40, 10, 10), QColor(teaser.CAT_COLOR[c]))
            p.drawText(QRectF(x + 14, 37, 70, 16), Qt.AlignVCenter, teaser.CAT_NAME[c])
            x += 80


class AITestDialog(QDialog):
    """Shows the AI's guess on HIS frames: every thumbnail with his colour and the AI's category (green = same)."""

    def __init__(self, parent, pieces, base):
        super().__init__(parent)
        self.setWindowTitle("AI test: does the AI see what you labelled?")
        self.resize(1180, 820)
        self.setStyleSheet(f"QDialog{{background:{C['BG']}}}")
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.addWidget(lbl("AI test (local, free)", "h1"))
        v.addWidget(lbl("One frame from the middle of up to 25 selections per colour is shown to an image model (CLIP, runs on "
                        "this Mac, nothing is uploaded). It guesses the kind of shot; green = same as your label, red = "
                        "different. The first time the model is downloaded once (~150 MB).", "muted", True))
        self.pp = ProgressPanel()
        v.addWidget(self.pp)
        self.table = QLabel("")
        self.table.setTextFormat(Qt.RichText)
        v.addWidget(self.table)
        r = QHBoxLayout()
        self.only = QCheckBox("Show only the shots where the AI disagrees")
        self.only.toggled.connect(self._grid)
        r.addWidget(self.only)
        r.addStretch()
        v.addLayout(r)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        w = QWidget()
        self.g = QGridLayout(w)
        self.g.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sc.setWidget(w)
        v.addWidget(sc, 1)
        self.res, self._stop = None, False
        self.pp.start("Starting…")
        self.pp.allow_cancel(self._cancel)
        self.job = _Runner(lambda progress=None: ai.run_test(pieces, base, 25, progress, lambda: self._stop))
        self.job.progress.connect(self.pp.set)
        self.job.done.connect(self._done)
        self.job.failed.connect(self._failed)
        self.job.start()

    def _cancel(self):
        self._stop = True

    def _failed(self, m):
        self.pp.hide()
        logging.error("AI test failed: %s", m)
        hint = (" The first run needs internet to download the model." if "urlopen" in m or "resolve" in m.lower()
                or "HTTP" in m else "")
        self.table.setText(f'<span style="color:{C["POOR"]}">The AI test stopped: {m}.{hint} '
                           f'Settings &gt; Save error report and send it to Claude.</span>')

    def _done(self, res):
        self.pp.hide()
        self.res = res
        acc = res["acc"]
        tr, tt = sum(a for a, _ in acc.values()), sum(b for _, b in acc.values())
        rows = "".join(f'<tr><td><span style="color:{teaser.CAT_COLOR[c]}">●</span> {teaser.CAT_NAME[c]}</td>'
                       f'<td align="right">{r} of {t}</td><td align="right"><b>{(100 * r // t) if t else 0}%</b></td></tr>'
                       for c, (r, t) in acc.items())
        self.table.setText(f'<table cellspacing="10"><tr><td><b>Your colour</b></td><td><b>AI agrees</b></td><td></td></tr>'
                           f'{rows}<tr><td><b>All</b></td><td align="right">{tr} of {tt}</td>'
                           f'<td align="right"><b>{(100 * tr // tt) if tt else 0}%</b></td></tr></table>')
        logging.info("AI test: %s", {k: f"{a}/{b}" for k, (a, b) in acc.items()})
        self._grid()

    def _grid(self):
        while self.g.count():
            w = self.g.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not self.res:
            return
        rows = [r for r in self.res["rows"] if not self.only.isChecked() or r[2] != r[3]]
        for n, (p, img, his, g, conf) in enumerate(rows):
            box = QFrame()
            ok = his == g
            box.setStyleSheet(f"QFrame{{border:2px solid {C['GOOD'] if ok else C['POOR']};border-radius:6px;background:#202020}}")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(4, 4, 4, 4)
            pic = QLabel()
            qi = QImage(img.tobytes(), img.shape[1], img.shape[0], img.shape[1] * 3, QImage.Format_RGB888).copy()
            pic.setPixmap(QPixmap.fromImage(qi).scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            pic.setStyleSheet("border:none")
            bv.addWidget(pic)
            cap = QLabel(f'<span style="color:{teaser.CAT_COLOR[his]}">You: {teaser.CAT_NAME[his]}</span><br>'
                         f'<span style="color:{C["GOOD"] if ok else C["POOR"]}">AI: {teaser.CAT_NAME[g]}</span>'
                         f'<span style="color:{C["MUTED"]}"> · {int(conf * 100)}%</span>')
            cap.setStyleSheet("border:none;font-size:11px")
            bv.addWidget(cap)
            name = QLabel(Path(p["path"]).name)
            name.setStyleSheet(f"border:none;font-size:10px;color:{C['MUTED']}")
            bv.addWidget(name)
            self.g.addWidget(box, n // 6, n % 6)

    def closeEvent(self, e):
        self._stop = True
        super().closeEvent(e)


class TeaserPage(QWidget):
    notify = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.pieces, self.music, self.edit, self.runner = [], None, None, None
        self.seed = 1
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        v.addWidget(self.stack)
        # ---- studio
        st = QWidget()
        sv = QVBoxLayout(st)
        sv.setContentsMargins(24, 18, 24, 18)
        sv.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(lbl("Teaser Studio", "h1"))
        badge = QLabel("NEW")
        badge.setStyleSheet(f"background:{C['POOR']};color:white;font-size:10px;font-weight:800;border-radius:9px;padding:2px 8px")
        top.addWidget(badge)
        top.addStretch()
        self.b_shuffle = btn("Shuffle shots", slot=self.shuffle)
        self.b_gen = btn("Generate", "primary", self.generate)
        self.b_exp = btn("Export XML", slot=self.export)
        for b in (self.b_shuffle, self.b_exp, self.b_gen):
            top.addWidget(b)
        sv.addLayout(top)
        sv.addWidget(lbl("Builds your shortmovie structure (teaser with drop → getting ready → church → party) from your colour "
                         "labels, cut on the beat of your music. Testimonials and vows: add them in Premiere afterwards "
                         "(the export has a marker for every part).", "muted", True))
        pr = QHBoxLayout()
        pr.addWidget(lbl("Project", "section"))
        self.pcombo = QComboBox()
        self.pcombo.setMinimumWidth(260)
        self.pcombo.currentIndexChanged.connect(self.switch_project)
        pr.addWidget(self.pcombo)
        pr.addWidget(btn("+  New teaser", slot=self.new_project))
        pr.addWidget(btn("Rename", "link", self.rename_project))
        pr.addWidget(btn("Delete", "link", self.delete_project))
        pr.addStretch()
        sv.addLayout(pr)
        body = QHBoxLayout()
        body.setSpacing(18)
        sv.addLayout(body, 1)
        lscroll = QScrollArea()                 # the cards keep their natural size, the column scrolls instead
        lscroll.setWidgetResizable(True)
        lscroll.setFixedWidth(410)
        lw = QWidget()
        left = QVBoxLayout(lw)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(10)

        def card(n, title):
            f = QFrame()
            f.setObjectName("card")
            f.setFixedWidth(390)
            l = QVBoxLayout(f)
            l.setContentsMargins(14, 12, 14, 12)
            h = QHBoxLayout()
            num = QLabel(str(n))
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"background:{C['BLUE']};color:white;border-radius:11px;font-weight:700")
            h.addWidget(num)
            h.addWidget(lbl(title, "h2"))
            h.addStretch()
            l.addLayout(h)
            left.addWidget(f)
            return l
        l1 = card(1, "Footage (your colour labels)")
        l1.addWidget(lbl("Export from Premiere an XML of a sequence with your labelled clips (selects). Rose bride, Blue "
                         "groom, Purple couple, Brown church, Yellow venue, Iris party, Violet drone.", "muted", True))
        l1.addWidget(btn("Import labelled XML", slot=self.pick_footage))
        self.foot_lbl = QLabel("")
        self.foot_lbl.setWordWrap(True)
        l1.addWidget(self.foot_lbl)
        l2 = card(2, "Music")
        l2.addWidget(lbl("Your songs already joined: one audio file, or the XML of your music edit.", "muted", True))
        r = QHBoxLayout()
        r.addWidget(btn("Audio file", slot=lambda: self.pick_music(False)))
        r.addWidget(btn("Music XML", slot=lambda: self.pick_music(True)))
        l2.addLayout(r)
        self.mus_lbl = lbl("", "muted", True)
        l2.addWidget(self.mus_lbl)
        l3 = card(3, "Parts")
        self.f = {}
        g = QGridLayout()
        g.setVerticalSpacing(8)
        g.setColumnStretch(0, 1)
        val = QRegularExpressionValidator(QRegularExpression(r"^\d{0,2}(:\d{0,2}(\.\d?)?)?$"))
        for i, (k, t) in enumerate(teaser.BOUNDS):
            g.addWidget(lbl(t, "muted"), i, 0, Qt.AlignVCenter)
            e = QLineEdit()
            e.setFixedSize(110, 30)
            e.setPlaceholderText("m:ss.s")
            e.setValidator(val)                 # digits, ":" and "." only
            e.setAlignment(Qt.AlignCenter)
            e.setEnabled(False)
            e.editingFinished.connect(self.parts_edited)
            g.addWidget(e, i, 1)
            self.f[k] = e
        l3.addLayout(g)
        self.parts_note = lbl("", "muted", True)
        self.parts_note.setStyleSheet(f"color:{C['POOR']}")
        l3.addWidget(self.parts_note)
        self.b_detect = btn("Detect again", "link", self.redetect)
        self.b_detect.setToolTip("Sets the six moments back to what the app found in the music (song changes, drop).")
        self.b_detect.setEnabled(False)
        l3.addWidget(self.b_detect)
        l4 = card(4, "Story order")
        r = QHBoxLayout()
        self.b_chrono = btn("Chronological", "seg", lambda: self.set_order(True))
        self.b_mixed = btn("Mixed", "seg", lambda: self.set_order(False))
        r.addWidget(self.b_chrono)
        r.addWidget(self.b_mixed)
        l4.addLayout(r)
        self.order_lbl = lbl("", "muted", True)
        l4.addWidget(self.order_lbl)
        l5 = card(5, "AI test (experimental)")
        l5.addWidget(lbl("Checks if a free AI model, running on this Mac, recognises your shots like your colour labels. "
                         "It does not change your teaser.", "muted", True))
        self.b_ai = btn("Test the AI on my labelled clips", slot=self.ai_test)
        l5.addWidget(self.b_ai)
        left.addStretch()
        lscroll.setWidget(lw)
        body.addWidget(lscroll)
        right = QVBoxLayout()
        right.addWidget(lbl("MUSIC", "section"))
        self.mv = MusicView()
        right.addWidget(self.mv)
        right.addWidget(lbl("The small ticks under the music show where the cuts fall. The pink line is the drop.", "muted"))
        right.addWidget(lbl("YOUR SHORTMOVIE", "section"))
        self.strip = ShotStrip()
        right.addWidget(self.strip)
        self.summary = lbl("", "muted", True)
        right.addWidget(self.summary)
        self.pp = ProgressPanel()
        right.addWidget(self.pp)
        right.addStretch()
        body.addLayout(right, 1)
        self.stack.addWidget(st)
        self.chrono = True
        self.set_order(store.app.get("teaser_chrono", True))
        self.stack.setCurrentIndex(0)
        self.auto_bounds = None
        self._fill_projects()
        self._buttons()
        QTimer.singleShot(0, self.restore)

    def restore(self):
        """Reload the footage XML, the music and your six moments from last time."""
        t = self._cur()
        foot, mus, b = t.get("footage"), t.get("music"), t.get("bounds")
        if t.get("chrono") is not None:
            self.set_order(t["chrono"])
        then = (lambda: self._load_music_file(mus, b)) if mus and Path(mus).exists() else None
        if foot and Path(foot).exists():
            self._load_footage(foot, then)
        elif then:
            then()


    # ---- inputs
    def _run(self, text, fn, args, done):
        if self.runner and self.runner.isRunning():
            if not self.runner.wait(3000):       # the previous job is just finishing (chained loads)
                return
        self.pp.start(text)
        self.pp.set(text, 0.3)
        self.runner = _Runner(fn, *args)
        self.runner.progress.connect(self.pp.set)
        self.pp.allow_cancel(self._cancel_job)
        self.runner.done.connect(lambda r: (self.pp.hide(), self.pp.allow_cancel(None), done(r)))
        self.runner.failed.connect(lambda m: (self.pp.hide(), self.summary.setText("Error: " + m)))
        self.runner.start()

    # ---- projects (one per wedding)
    def _projects(self):
        app = self.store.app
        if "teaser_projects" not in app:
            old = app.pop("teaser", {})
            app["teaser_projects"] = [dict(id=uuid.uuid4().hex, name="My first teaser", **old)]
            app["teaser_current"] = app["teaser_projects"][0]["id"]
        return app["teaser_projects"]

    def _cur(self):
        ps = self._projects()
        return next((p for p in ps if p["id"] == self.store.app.get("teaser_current")), ps[0])

    def _fill_projects(self):
        self.pcombo.blockSignals(True)
        self.pcombo.clear()
        ps = self._projects()
        for p in ps:
            self.pcombo.addItem(p["name"], p["id"])
        self.pcombo.setCurrentIndex(max(0, [p["id"] for p in ps].index(self._cur()["id"])))
        self.pcombo.blockSignals(False)

    def _busy(self):
        return bool(self.runner and self.runner.isRunning())

    def switch_project(self, idx):
        if self._busy():
            self.summary.setText("Wait for the current job to finish (or Cancel it) before switching projects.")
            self._fill_projects()
            return
        self.store.app["teaser_current"] = self.pcombo.itemData(idx)
        self.store.save_app()
        self._clear()
        self.restore()

    def new_project(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New teaser", "Name (e.g. the couple):")
        if not ok or not name.strip() or self._busy():
            return
        p = dict(id=uuid.uuid4().hex, name=name.strip())
        self._projects().append(p)
        self.store.app["teaser_current"] = p["id"]
        self.store.save_app()
        self._fill_projects()
        self._clear()

    def rename_project(self):
        from PySide6.QtWidgets import QInputDialog
        p = self._cur()
        name, ok = QInputDialog.getText(self, "Rename teaser", "Name:", text=p["name"])
        if ok and name.strip():
            p["name"] = name.strip()
            self.store.save_app()
            self._fill_projects()

    def delete_project(self):
        from PySide6.QtWidgets import QMessageBox
        ps = self._projects()
        if self._busy() or len(ps) < 2:
            self.summary.setText("You need at least one teaser project." if len(ps) < 2 else "Wait for the current job.")
            return
        p = self._cur()
        if QMessageBox.question(self, "Delete teaser", f"Delete \"{p['name']}\"? Your files are not touched.") != QMessageBox.Yes:
            return
        ps.remove(p)
        self.store.app["teaser_current"] = ps[0]["id"]
        self.store.save_app()
        self._fill_projects()
        self._clear()
        self.restore()

    def _clear(self):
        self.pieces, self.music, self.edit, self.auto_bounds = [], None, None, None
        self.foot_lbl.setText("")
        self.mus_lbl.setText("")
        self.mv.env = None
        self.mv.set_parts([], None)
        self.strip.set([], 1.0)
        for e in self.f.values():
            e.clear()
            e.setEnabled(False)
            e.setStyleSheet("")
        self.b_detect.setEnabled(False)
        self.parts_note.setText("")
        self._buttons()

    def _remember(self, **kw):
        self._cur().update(kw)
        self.store.save_app()

    def ai_test(self):
        if not self.pieces:
            self.summary.setText("Import your labelled XML first (card 1), then run the AI test.")
            return
        try:
            import onnxruntime  # noqa: F401
            import tokenizers  # noqa: F401
        except Exception as e:
            self.summary.setText(f"The AI parts are missing from this build ({e}).")
            return
        AITestDialog(self, self.pieces, self.store.dir).exec()

    def _cancel_job(self):
        """Stop looking at the selections: what is analysed so far is kept (and the rest continues next time)."""
        self._stop = True
        self.pp.title.setText("Stopping… (what is done is kept)")

    def pick_footage(self):
        f, _ = QFileDialog.getOpenFileName(self, "Labelled footage XML (from Premiere)", "", "XML (*.xml)")
        if f:
            self._load_footage(f)

    def _load_footage(self, f, then=None):
        self._stop = False                       # reset before the job: a Cancel pressed while reading is kept
        self._foot_path = f
        self._run("Reading your labelled clips and their recording times…", self._read_footage, (f,),
                  lambda r: (self.footage_loaded(r), then and then()))

    def _read_footage(self, f, progress=None):
        pieces, skipped = teaser.load_footage(f)
        cache_file = self.store.dir / "teaser_cache.json"
        try:
            cache = json.loads(cache_file.read_text("utf-8"))
        except Exception:
            cache = {}
        save = lambda c: cache_file.write_text(json.dumps(c), "utf-8")
        jobs = max(2, (os.cpu_count() or 4) // 2)        # light work per clip: use half of the cores
        teaser.analyse_pieces(pieces, cache, progress, jobs, cancel=lambda: self._stop, save=save)
        return pieces, skipped

    def footage_loaded(self, r):
        self.pieces, skipped = r
        s = teaser.footage_summary(self.pieces)
        rows = []
        for c in ("bride", "groom", "couple", "church", "venue", "party", "drone"):
            n, sec = s.get(c, (0, 0.0))
            warn = "" if n else f' <span style="color:{C["POOR"]}">missing</span>'
            rows.append(f'<span style="color:{teaser.CAT_COLOR[c]}">●</span> {teaser.CAT_NAME[c]}: {n} clips, '
                        f'{int(sec // 60)}:{int(sec % 60):02d}{warn}')
        ign = ", ".join(f"{k} {v}" for k, v in skipped.items())
        looked = sum(1 for p in self.pieces if p.get("qa"))
        rows.append(f'<span style="color:{C["MUTED"]}">{looked} of {len(self.pieces)} selections analysed: the best part of each '
                    f'one is used' + (" (stopped: the rest continues next time you open this project)" if looked < len(self.pieces) else "")
                    + '</span>')
        self.foot_lbl.setText(f'<b>{Path(self._foot_path).name}</b><br>' + "<br>".join(rows) +
                              (f'<br><span style="color:{C["MUTED"]}">Ignored: {ign}</span>' if ign else ""))
        self._remember(footage=self._foot_path)
        self._buttons()

    def pick_music(self, as_xml):
        if as_xml:
            f, _ = QFileDialog.getOpenFileName(self, "XML of your music edit", "", "XML (*.xml)")
        else:
            f, _ = QFileDialog.getOpenFileName(self, "Music (one file with all the songs)", "", "Audio (*.wav *.mp3 *.aif *.aiff *.m4a *.flac);;All files (*)")
        if f:
            self._load_music_file(f)

    def _load_music_file(self, f, bounds=None):
        self._mus_path = f
        self._run("Reading the music, finding the beat and the drop…", self._load_music, (f,),
                  lambda r: self.music_loaded(r, bounds))

    @staticmethod
    def _load_music(f):
        m = teaser.load_music(f)
        return m, teaser.guess_parts(m)

    def music_loaded(self, r, bounds=None):
        self.music, b = r
        self.auto_bounds = dict(b)
        self.mv.set_music(self.music["x"], self.music["duration"])
        if bounds and teaser.valid(bounds, self.music["duration"]):
            b = bounds                                   # what you had set last time
        for e in self.f.values():
            e.setEnabled(True)
        self.b_detect.setEnabled(True)
        self._set_parts(b)
        d = self.music["duration"]
        miss = self.music.get("missing") or []
        warn = (f'<br><span style="color:{C["POOR"]}">Not found, left out of the analysis: {", ".join(miss)}</span>'
                if miss else "")
        self.mus_lbl.setText(f"<b>{Path(self._mus_path).name}</b> · {int(d // 60)}:{int(d % 60):02d} of music"
                             + (" · song changes taken from the XML" if self.music["song_starts"] else " · moments guessed, adjust them below")
                             + warn)
        self._remember(music=self._mus_path)
        self._buttons()

    # ---- parts
    def _set_parts(self, b):
        self.bounds = dict(b)
        for k, _ in teaser.BOUNDS:
            t = b[k]
            self.f[k].setText(f"{int(t // 60)}:{t % 60:04.1f}")
            self.f[k].setStyleSheet("")
        self.mv.set_parts([b[k] for k, _ in teaser.BOUNDS[1:]], b["drop"])
        self._remember(bounds=self.bounds)

    def parts_edited(self):
        red = f"border:1.5px solid {C['POOR']}"
        b, bad = {}, []
        for k, _ in teaser.BOUNDS:
            try:
                b[k] = parse_t(self.f[k].text())
            except ValueError:
                bad.append(k)
        if not bad and self.music:
            ks = [k for k, _ in teaser.BOUNDS]
            bad = [k2 for k1, k2 in zip(ks, ks[1:]) if b[k2] <= b[k1]]
            if b[ks[-1]] >= self.music["duration"]:
                bad.append(ks[-1])
        for k, e in self.f.items():
            e.setStyleSheet(red if k in bad else "")
        if not bad and self.music and teaser.valid(b, self.music["duration"]):
            self._set_parts(b)
            self.parts_note.setText("")
        else:
            self.parts_note.setText("The times must go forward: Drop < Teaser ends < Getting ready ends < Church ends < "
                                    "Party song starts < Venue ends.")

    def redetect(self):
        if self.music:
            self._set_parts(self.auto_bounds)
            self.parts_note.setText("")

    def set_order(self, chrono):
        self.chrono = chrono
        for b, on in ((self.b_chrono, chrono), (self.b_mixed, not chrono)):
            b.setProperty("active", on)
            repolish(b)
        self.order_lbl.setText(
            "Chronological: every part follows the day in the order the clips were recorded (timecode / file time); "
            "if some clips have no recording time, the order of your selects sequence is used. "
            "The teaser is always mixed." if chrono else
            "Mixed: every part keeps its kind of shots (bride, church, party…) but picks them in random order. "
            "Press Shuffle shots for another mix.")
        if hasattr(self, "pcombo"):
            self._remember(chrono=chrono)

    # ---- build / export
    def _buttons(self):
        ok = bool(self.pieces) and self.music is not None
        self.b_gen.setEnabled(ok)
        self.b_shuffle.setEnabled(ok and self.edit is not None)
        self.b_exp.setEnabled(self.edit is not None)
        if not ok:
            need = [n for n, have in (("the labelled footage XML", bool(self.pieces)), ("the music", self.music is not None)) if not have]
            self.summary.setText("Add " + " and ".join(need) + " to generate.")
        elif self.edit is None:
            self.summary.setText("Ready: press Generate.")

    def generate(self):
        if not self.pieces or self.music is None:
            return
        self.edit = teaser.build(self.pieces, self.music, self.bounds, seed=self.seed, chronological=self.chrono)
        self.strip.set(self.edit["shots"], self.music["duration"])
        allbeats = [t0 for t0, _, _ in self.edit["shots"]]
        self.mv.set_parts([self.bounds[k] for k, _ in teaser.BOUNDS[1:]], self.bounds["drop"], allbeats)
        bpm = " · ".join(f"{k} {v:.0f} BPM" for k, v in self.edit["bpm"].items() if v)
        inst = self.edit.get("used_instead") or {}
        grouped = {}
        for (w, u), n in inst.items():
            grouped.setdefault(w, []).append((n, u))
        miss = "".join(f'<br><span style="color:{C["FAIR"]}">Not enough {teaser.CAT_NAME[w].lower()} shots, filled with: '
                       + ", ".join(f"{teaser.CAT_NAME[u].lower()} ({n}×)" for n, u in sorted(v, reverse=True)) + "</span>"
                       for w, v in sorted(grouped.items()))
        short = self.edit.get("short", 0.0)
        if short > 0.5:
            miss += (f'<br><span style="color:{C["POOR"]}">{int(short)} s have no unused footage left (a moment is never used '
                     f'twice): label more clips in Premiere.</span>')
        self.summary.setText(f"{len(self.edit['shots'])} shots, every cut on a beat, no moment used twice · "
                             f"order: {self.edit['order']}<br>{bpm}{miss}")
        self.notify.emit(f"Shortmovie generated: {len(self.edit['shots'])} shots")
        logging.info("teaser generated: %d shots, short %.1fs, bounds %s", len(self.edit["shots"]), self.edit.get("short", 0), self.bounds)
        self._buttons()

    def shuffle(self):
        self.seed += 1
        self.generate()

    def export(self):
        if not self.edit:
            return
        start = str(Path(getattr(self, "_foot_path", "") or ".").parent / "Shortmovie (auto).xml")
        out, _ = QFileDialog.getSaveFileName(self, "Save XML", start, "XML (*.xml)")
        if out:
            try:
                n = teaser.export_xml(self.edit, self.music, out, Path(out).stem)
                self.summary.setText(f"Saved {n} shots to {out}. Premiere: File > Import · DaVinci: File > Import > Timeline.")
                self.notify.emit(f"XML saved: {Path(out).name}")
            except Exception as e:
                logging.exception("teaser export failed")
                self.summary.setText(f"Export failed: {e}")


# ---------------------------------------------------------------- main window

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        self.resize(1400, 820)
        self.setMinimumSize(1100, 680)
        self.store = Store()
        self.worker, self.job = None, None

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(12, 16, 12, 12)
        sv.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(10)
        pm = app_icon(46)
        if pm:
            ic = QLabel()
            ic.setPixmap(pm)
            top.addWidget(ic, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel('<span style="font-weight:400">MoneyMaking</span><span style="font-weight:800">Machine</span>')
        name.setStyleSheet("font-size:14px;color:#ececec")
        handle = QLabel(f'<a href="{AUTHOR_URL}" style="color:{C["HOT"]};text-decoration:none">{AUTHOR}</a>')
        handle.setOpenExternalLinks(True)
        handle.setCursor(Qt.PointingHandCursor)
        handle.setToolTip("Instagram")
        handle.setStyleSheet("font-size:12px")
        ver = QLabel(VER)
        ver.setStyleSheet(f"font-size:10px;color:{C['MUTED']}")
        for w_ in (name, handle, ver):
            col.addWidget(w_)
        top.addLayout(col, 1)
        sv.addLayout(top)
        sv.addSpacing(14)
        self.nav = {"dash": btn("Dashboard", "nav", lambda: self.go("dash")),
                    "queue": btn("Analysis Queue", "nav", lambda: self.go("queue")),
                    "teaser": btn("Teaser Studio", "nav", lambda: self.go("teaser")),
                    "settings": btn("Settings", "nav", lambda: self.go("settings")),
                    "info": btn("Info / How to use", "nav", lambda: self.go("info"))}
        for b in self.nav.values():
            sv.addWidget(b)
        nb = QHBoxLayout(self.nav["teaser"])
        nb.setContentsMargins(0, 0, 8, 0)
        nb.addStretch()
        new = QLabel("NEW")
        new.setStyleSheet(f"background:{C['POOR']};color:white;font-size:8px;font-weight:800;border-radius:5px;padding:0px 4px")
        new.setAttribute(Qt.WA_TransparentForMouseEvents)
        new.setFixedSize(30, 14)
        new.setAlignment(Qt.AlignCenter)
        nb.addWidget(new, 0, Qt.AlignVCenter)
        sv.addStretch()
        sv.addWidget(lbl("Local workspace", "muted"))
        h.addWidget(side)
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.dash, self.proj = Dashboard(), ProjectPage(self.store)
        self.anl, self.res, self.queue = AnalyzingPage(), ResultsPage(self.store), QueuePage()
        self.mc = MulticamPage(self.store)
        self.settings = SettingsPage(self.store)
        self.info = InfoPage(self.store)
        self.teaser = TeaserPage(self.store)
        self.toast = Toast(self)
        self.res.export_done = lambda name: (self.toast.show_msg(f"XML saved: {name}"), logging.info("footage export %s", name))
        self.teaser.notify.connect(self.toast.show_msg)
        for w in (self.dash, self.proj, self.anl, self.res, self.queue, self.mc, self.settings, self.info, self.teaser):
            self.stack.addWidget(w)
        self.dash.new_project.connect(self.new_project)
        self.dash.open_project.connect(self.open_project)
        self.dash.delete_project.connect(self.delete_project)
        self.proj.back.connect(lambda: self.go("dash"))
        self.mc.back.connect(lambda: self.go("dash"))
        self.proj.analyze.connect(self.start_analysis)
        self.proj.open_history.connect(self.show_history)
        self.anl.back.connect(lambda: self.show_page(self.proj))
        self.anl.pause.connect(lambda on: self.worker and self.worker.pause(on))
        self.anl.cancel.connect(lambda: self.worker and self.worker.cancel())
        self.res.back.connect(lambda: self.show_page(self.proj))
        self.queue.open_job.connect(lambda k: self.show_page({"footage": self.anl, "teaser": self.teaser}.get(k, self.mc)))
        self.qtimer = QTimer(interval=700)
        self.qtimer.timeout.connect(self.refresh_queue)
        self.qtimer.start()
        self.go("dash")

    def refresh_queue(self):
        jobs = {}
        if self.worker and self.worker.isRunning() and self.job:
            jobs["footage"] = (f"Analyze Footage · {self.job['p']['name']}", self.anl.count.text(), self.anl.bar.value() / 1000)
        mw = self.mc.worker
        if mw and mw.isRunning():
            jp = getattr(self.mc, "_job_p", None) or self.mc.p
            jobs["multicam"] = (f"{'Sync' if mw.mode == 'sync' else 'Auto Edit'} · {jp['name']}", self.mc.job_status,
                                self.mc.job_progress)
        tr = getattr(self.teaser, "runner", None)
        if tr and tr.isRunning():
            jobs["teaser"] = ("Teaser Studio", self.teaser.pp.title.text(), self.teaser.pp.bar.value() / 1000)
        running_here = bool(self.worker and self.worker.isRunning() and self.job and self.proj.p is self.job["p"])
        self.proj.b_an.setText("View analysis" if running_here else "Analyze Footage")
        self.queue.set_jobs(jobs)
        self.nav["queue"].setText(f"Analysis Queue ({len(jobs)})" if jobs else "Analysis Queue")

    def closeEvent(self, e):
        self.store.flush()
        super().closeEvent(e)

    # navigation
    def show_page(self, w):
        self.stack.setCurrentWidget(w)
        for k, b in self.nav.items():
            b.setProperty("active", (k == "dash" and w in (self.dash, self.proj, self.res, self.mc)) or (k == "queue" and w in (self.queue, self.anl))
                          or (k == "settings" and w is self.settings) or (k == "info" and w is self.info) or (k == "teaser" and w is self.teaser))
            repolish(b)

    def go(self, where):
        if where == "dash":
            self.dash.refresh(self.store.projects)
            self.show_page(self.dash)
        elif where == "settings":
            self.show_page(self.settings)
        elif where == "info":
            self.show_page(self.info)
        elif where == "teaser":
            self.show_page(self.teaser)
        else:
            self.show_page(self.queue)

    # projects
    def new_project(self):
        d = NewProjectDialog(self)
        if d.exec() and d.name():
            self.open_project(self.store.new(d.name(), d.kind())["id"])

    def open_project(self, pid):
        p = next(x for x in self.store.projects if x["id"] == pid)
        if p.get("type") == "multicam":
            self.mc.load(p)
            self.show_page(self.mc)
            return
        self.proj.load(p)
        self.show_page(self.proj)

    def delete_project(self, pid):
        self.store.delete(pid)
        self.dash.refresh(self.store.projects)

    # analysis
    def start_analysis(self):
        if self.worker and self.worker.isRunning():
            self.show_page(self.anl)
            return
        p = self.proj.p
        paths = list(p["videos"])
        if not paths:
            return
        self.job = dict(p=p, paths=paths, an={}, t=time.time(), cancelled=False)
        self.anl.start(paths)
        w = Worker(paths, self.store.app["jobs"])
        w.thumb.connect(self.anl.thumb)
        w.progress.connect(self.anl.progress)
        w.done.connect(self.on_done)
        w.failed.connect(self.on_failed)
        w.finished.connect(self.on_finished)
        self.worker = w
        self.queue.set_job(f'Analyzing "{p["name"]}" ({len(paths)} videos)')
        self.proj.queue_lbl.setText(f'Analyzing "{p["name"]}"\n{len(paths)} videos')
        w.start()
        self.show_page(self.anl)

    def on_done(self, i, a):
        self.job["an"][i] = a
        self.anl.finished(i, True)

    def on_failed(self, i, msg):
        if msg == "Cancelled":
            self.job["cancelled"] = True
        self.anl.finished(i, False, msg)

    def on_finished(self):
        job = self.job
        self.queue.set_job("")
        self.proj.queue_lbl.setText("Queue is empty")
        if not job["an"]:
            self.show_page(self.proj)
            return
        entry = dict(ts=datetime.now().isoformat(timespec="seconds"), n=len(job["an"]),
                     duration=sum(a.duration for a in job["an"].values()), seconds=time.time() - job["t"],
                     clips=[job["an"][i].to_json() for i in sorted(job["an"])])
        job["p"]["history"].append(entry)
        self.store.save()
        if self.proj.p is job["p"]:
            self.proj.refresh_history()
            self.proj.refresh_preview()
        if self.stack.currentWidget() is self.anl and not job["cancelled"]:
            self.res.show_entry(job["p"], entry)
            self.show_page(self.res)

    def show_history(self, i):
        self.res.show_entry(self.proj.p, self.proj.p["history"][i])
        self.show_page(self.res)


def setup_logging(folder):
    folder.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(folder / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(h)
    logging.info("---- %s %s started on %s", APP, VER, platform.platform())

    def hook(t, v, tb):
        logging.error("unexpected error", exc_info=(t, v, tb))
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, APP, f"Something went wrong: {v}\n\nSettings > Save error report, then send it to Claude.")
        except Exception:
            pass
    sys.excepthook = hook


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    ic = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "icon.png"
    if ic.exists():
        app.setWindowIcon(QIcon(str(ic)))
    app.setStyleSheet(STYLE)
    w = Main()
    setup_logging(w.store.dir)
    w.show()
    w.settings.update_found.connect(lambda tag: w.toast.show_msg(f"New version {tag} available: Settings > Download", 6000))
    QTimer.singleShot(5000, lambda: w.settings.check_updates(True))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
