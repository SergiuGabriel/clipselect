"""MoneyMakingMachine - AI-free footage pre-selection. Desktop app (PySide6)."""
import multiprocessing
if __name__ == "__main__":
    # FIRST thing in the packed app: libraries (tqdm inside Whisper / Hugging Face) start multiprocessing's helper
    # process, which re-runs THIS executable; without freeze_support() that started a second copy of the whole app
    # (v3.8.6: pressing Transcribe opened the app twice). With it, the helper does its job and never shows a window.
    multiprocessing.freeze_support()
import json
import logging
import logging.handlers
import os
import shutil
from html import escape
import platform
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QObject, QSize, QUrl, QPoint, QPointF, QPropertyAnimation, QRectF, QRegularExpression, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QImage, QPainter, QPen, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (QPlainTextEdit, QTextBrowser, QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QHeaderView, QCheckBox, QRadioButton, QMessageBox)

import core
import director
import music
import style
import help_text
import i18n
import teaser
import longfilm
import longfilm2
import blueprint
import offload
import updater
import resolve
import transcribe
import ai
import xmlimport
import projectsetup
import story
import sync
import bridge
import appnap
import colour

APP, VER = "MoneyMakingMachine", "v4.6.2"
AUTHOR, AUTHOR_URL = "@sergiugabrielcg", "https://www.instagram.com/sergiugabrielcg/"
# updates: updater.py (the address is never shown to the user)


def _ver(v):
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


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
SEQ_DEFAULT = dict(size="Match footage", rate="25", fields="Lower Field First")      # final sequences are 25 fps
DEFAULT_ON = {k: True for k, _, _ in SLIDERS}
DEFAULTS = dict(mode="auto", thr=60, mincut=3, cutmoves=True, keepall=True, party=False, protect=True, contrast=50, exposure=50, focus=60, importance=40,
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
QLineEdit{background:#161616;border:1px solid #4a4a4a;border-radius:4px;padding:6px 10px;selection-background-color:@BLUE}
QLineEdit:focus{border:1px solid @HOT}
QComboBox{background:#161616;border:1px solid #4a4a4a;border-radius:4px;padding:6px 34px 6px 10px;min-height:18px}
QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:center right;width:30px;border:none}
QComboBox::down-arrow{image:url(@ARROW);width:10px;height:6px}
QComboBox QAbstractItemView::item{min-height:24px;padding:2px 8px}
QComboBox:hover{border-color:#6a6a6a}
QComboBox QAbstractItemView{background:#2a2a2a;border:1px solid #4a4a4a;selection-background-color:@BLUE}
QComboBox:disabled{color:#5e5e5e;background:#1e1e1e;border-color:#353535}
QLineEdit:disabled{color:#5e5e5e;background:#1e1e1e;border-color:#353535}
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


TARGET = {"v": "premiere"}           # the program he works in (top-right switch, store.app["target"])
_TARGET_LISTENERS = []


def target():
    return TARGET["v"]


def on_target(fn):
    """fn(target) is called whenever the Premiere | DaVinci switch changes (and once now)."""
    _TARGET_LISTENERS.append(fn)
    try:
        fn(TARGET["v"])
    except RuntimeError:
        pass


def set_target(t):
    TARGET["v"] = "davinci" if t == "davinci" else "premiere"
    for fn in list(_TARGET_LISTENERS):
        try:
            fn(TARGET["v"])
        except RuntimeError:                # a widget that is gone
            _TARGET_LISTENERS.remove(fn)


class TargetSwitch(QWidget):
    """Top right of the window: Premiere Pro | DaVinci Resolve. Every export writes the XML for the program chosen here
    (remembered for the next start)."""
    def __init__(self, store):
        super().__init__()
        self.store = store
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(lbl("I work in", "muted"))
        h.addSpacing(8)
        self.b = {"premiere": btn("Premiere Pro", "seg", lambda: self.pick("premiere")),
                  "davinci": btn("DaVinci Resolve", "seg", lambda: self.pick("davinci"))}
        for b in self.b.values():
            h.addWidget(b)
        self.setToolTip("Every Export XML is written for this program. DaVinci Resolve gets its own file, written the "
                        "way Resolve writes it (no Premiere effects, the cameras' timecode), checked from end to end.")
        on_target(self._show)

    def pick(self, t):
        if t == target():
            return
        self.store.app["target"] = t
        self.store.save_app()
        set_target(t)
        notify(i18n.T("Exports are now written for {}").format("DaVinci Resolve" if t == "davinci" else "Premiere Pro"))

    def _show(self, t):
        for k, b in self.b.items():
            b.setProperty("active", k == t)
            repolish(b)


class ExportPair(QWidget):
    """ONE Export XML button: the XML for the program of the top-right switch (Premiere Pro or DaVinci Resolve).
    slot(target). (Two buttons until v4.1.1; the name stayed.)"""
    def __init__(self, slot, primary=False):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.b = btn("Export XML", "primary" if primary else "", lambda: slot(target()))
        h.addWidget(self.b)
        on_target(self._show)

    def _show(self, t):
        self.b.setText(i18n.T("Export XML → DaVinci") if t == "davinci" else i18n.T("Export XML → Premiere"))
        self.b.setToolTip(i18n.T("XML made for DaVinci Resolve (File > Import > Timeline). Change the program top right.")
                          if t == "davinci" else
                          i18n.T("XML for Premiere Pro (File > Import). Change the program top right."))


def only_note(text):
    """A fixed info point under an option that works only in one program ("Premiere Pro only…")."""
    w = QLabel("ⓘ  " + i18n.T(text))
    w.setWordWrap(True)
    w.setStyleSheet(f"color:{C['HOT']};font-size:11px")
    return w


def davinci_tick(store, cfg):
    """(until v4.1.1 a tick 'Also for DaVinci Resolve'.) Now a line that follows the top-right switch."""
    w = QLabel()
    w.setWordWrap(True)
    w.setStyleSheet(f"color:{C['HOT']};font-size:11px")

    def show(t):
        w.setText("ⓘ  " + (i18n.T("You work in DaVinci Resolve (top right): the XML is written for DaVinci Resolve.")
                           if t == "davinci" else
                           i18n.T("You work in Premiere Pro (top right): the XML is written for Premiere Pro.")))
    on_target(show)
    return w


def for_target(out, target, src=None):
    """After an export: for DaVinci Resolve the file is converted AND checked (DaVinciCheck, its own progress bar);
    for Premiere nothing more happens (no extra time). src = the Premiere file when the DaVinci one is a copy."""
    if target == "davinci":
        DaVinciCheck(QApplication.activeWindow(), src or out, out).exec()


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

def _jsonable(o):
    """numpy numbers / arrays (from the analyses and the sync) as plain JSON values."""
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _write_json(path, obj):
    """Written whole or not at all: a temporary file, then renamed over the old one (a crash never leaves half a file)."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, default=_jsonable), "utf-8")
    os.replace(tmp, path)


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
        core.set_slots(max(2, self.app["jobs"]))
        sync.TAKE_PREF = self.app.get("rec_take", "auto")
        sync.ENGINE = self.app.get("sync_engine", "graph")

    def save_app(self):
        core.HWACCEL = self.app["hwaccel"]
        core.set_slots(max(2, self.app["jobs"]))
        sync.TAKE_PREF = self.app.get("rec_take", "auto")
        sync.ENGINE = self.app.get("sync_engine", "graph")
        _write_json(self.dir / "settings.json", self.app)

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
        _write_json(self.file, self.projects)

    def load_blob(self, pid):
        try:
            return json.loads((self.dir / f"{pid}.analysis.json").read_text("utf-8"))
        except Exception:
            return {}

    def save_blob(self, pid, obj):
        _write_json(self.dir / f"{pid}.analysis.json", obj)

    def new(self, name, kind="footage"):
        p = dict(id=uuid.uuid4().hex, name=name, created=datetime.now().isoformat(timespec="seconds"),
                 videos=[], settings=norm_settings({}), history=[], out_dir="", out_name="", out_sw="Premiere Pro", seq=dict(SEQ_DEFAULT))
        if kind in ("multicam", "sync"):
            mine = self.app.get("style", {}).get("settings", {})          # this computer's learned style
            p.update(type="multicam", files=[], sync=None, cams=[], infos={},
                     dir={**director.DEFAULTS, **{k: v for k, v in mine.items() if k in ("minshot", "maxshot", "pace", "energy")}})
            if kind == "sync":                         # the Sync page: a multicam project without the auto edit
                p["sync_only"] = True
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


class _Drops(QObject):
    """Drag and drop from Finder anywhere on a page (owner: no hunting through dialogs). handler(paths) decides."""

    def __init__(self, handler, parent):
        super().__init__(parent)
        self.handler = handler

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            md = ev.mimeData()
            paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []
            if paths:
                ev.acceptProposedAction()
                if t == QEvent.Drop:
                    QTimer.singleShot(0, lambda p=paths: self.handler(p))   # dialogs never open inside the drop
                return True
        return False


def enable_drops(widget, handler):
    """Every widget of the page (and the page) takes file / folder drops and gives them to handler."""
    f = _Drops(handler, widget)
    for w in [widget] + widget.findChildren(QWidget):
        w.setAcceptDrops(True)
        w.installEventFilter(f)
    return f


def _labelled(xml_path):
    """True when the XML's clips carry his colour labels (selects), False for a music edit."""
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_path).getroot()
        n = sum(1 for lab in root.iter("label2") if (lab.text or "").strip() in teaser.CATS)
        return n >= 3
    except Exception:
        return False


def _xml_or_rest(paths):
    xmls = [p for p in paths if p.lower().endswith(".xml") and Path(p).is_file()]
    return xmls, [p for p in paths if p not in xmls]


class DropZone(QFrame):
    dropped = Signal(list)
    clicked = Signal()

    def __init__(self, compact=False):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        self.t1 = lbl("Drop more videos here" if compact else "Drag & drop a folder or videos here", "h2" if not compact else "")
        self.t1.setAlignment(Qt.AlignCenter)
        self.t2 = lbl("or click to browse" if compact else "or click to browse · MP4, MOV, MXF, AVI, MKV and any other format FFmpeg reads", "muted", True)
        self.t2.setAlignment(Qt.AlignCenter)
        v.addStretch()                          # stretches, not AlignCenter: a wrapped label then gets its full height
        v.addWidget(self.t1)
        v.addWidget(self.t2)
        v.addStretch()
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


class ValueBox(QLineEdit):
    """The blue value of a slider: click it and type the number (Enter or click away applies it, Esc cancels)."""
    picked = Signal(int)

    def __init__(self, text, lo, hi, suffix):
        super().__init__(text)
        self.lo, self.hi, self.suffix, self._old = lo, hi, suffix, text
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setFixedWidth(70)
        self.setToolTip("Click to type the value")
        self.setCursor(Qt.IBeamCursor)
        self.setStyleSheet(f"QLineEdit{{color:{C['HOT']};font-size:12px;background:transparent;border:1px solid transparent;"
                           f"border-radius:4px;padding:0 4px}} QLineEdit:hover{{border-color:{C['BORDER']}}}"
                           f" QLineEdit:focus{{background:#161616;border-color:{C['HOT']}}}")
        self.editingFinished.connect(self._apply)

    def focusInEvent(self, e):
        self._old = self.text()
        super().focusInEvent(e)
        QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.setText(self._old)
            self.clearFocus()
            return
        super().keyPressEvent(e)

    def _apply(self):
        m = re.search(r"-?\d+", self.text())
        if not m:
            self.setText(self._old)
            return
        x = max(self.lo, min(self.hi, int(m.group())))
        self.setText(f"{x}{self.suffix}")
        self._old = self.text()
        self.picked.emit(x)


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
        self.pct = ValueBox(f"{value}{suffix}", lo, hi, suffix)
        self.pct.picked.connect(lambda x: self.sl.setValue(x))
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
        self.pct.setEnabled(on)
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


_NOTIFY = None      # set by the main window: notify(text) / notify(text, error=True) from anywhere


_T0 = {}             # job clocks: job_mark(key) when a long process starts, notify(..., took=key) when it ends


def job_mark(key):
    _T0[key] = time.time()


def dur_text(sec):
    """1 h 05 min 12 s / 12 min 30 s / 45 s (translated; owner wants the seconds too)."""
    sec = int(round(max(0, sec)))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    if h:
        return i18n.T("{} h {} min {} s").format(h, f"{m:02d}", f"{s:02d}")
    if m:
        return i18n.T("{} min {} s").format(m, f"{s:02d}")
    return i18n.T("{} s").format(s)


def notify(text, error=False, ms=None, took=None):
    """Pop-up notification at the top of the window: green when something finished, red when it failed.
    took = the key given to job_mark when the process started: the message then says how long the whole process took
    (and on a Mac a system notification stays in the Notification Center when it took more than a minute)."""
    extra = ""
    if took is not None and took in _T0:
        sec = time.time() - _T0.pop(took)
        extra = i18n.T("took {}").format(dur_text(sec))
        logging.info("%s (%s)", text, extra)
        ms = max(ms or 0, 15000)
        if sec > 60 and sys.platform == "darwin" and not os.environ.get("MMM_NO_SYSNOTE"):
            try:
                import updater
                t = (i18n.T(text) + " · " + extra).replace("\\", "").replace('"', "'")
                updater.launch(["osascript", "-e", f'display notification "{t}" with title "{APP}"'])
            except Exception:
                logging.exception("system notification")
    if _NOTIFY:
        _NOTIFY(text, error, ms, extra)


class Toast(QLabel):
    """Notification that slides down from the top of the window and goes away by itself (green ok, red error)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWordWrap(False)
        self.hide()
        self.anim = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self._slide(self.pos(), QPoint(self.x(), -self.height() - 4), hide=True))

    def show_msg(self, text, ms=3000, error=False, extra=""):
        self.setStyleSheet(f"background:{'#c0392b' if error else '#1f8f4e'};color:white;font-weight:700;font-size:13px;"
                           "border-radius:8px;padding:10px 18px")
        text = i18n.T(text)
        if len(text) > 110:
            text = text[:107] + "…"
        if extra:
            text += "  ·  " + extra
        self.setText(("✕  " if error else "✓  ") + text)
        self.adjustSize()
        x = (self.parent().width() - self.width()) // 2
        start = self.pos() if self.isVisible() and self.y() >= 0 else QPoint(x, -self.height())
        self.move(start)
        self.show()
        self.raise_()
        self._slide(start, QPoint(x, 14))
        self.timer.start(ms or (6000 if error else 3000))      # a new message restarts the timer

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


class EtaClock:
    """Elapsed + time left that move every second, even when the job reports rarely (one long clip, one long step).
    Time left = the speed of the last 2 minutes and of the whole job together (a slow step pulls it up at once, a fast
    one does not promise too little), smoothed, counting down between reports. The bar never goes back inside one job."""
    WINDOW = 120.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.t0 = time.time()
        self.f, self.total, self.tf, self.hist = 0.0, None, self.t0, [(self.t0, 0.0)]

    def feed(self, f):
        now = time.time()
        if f < 0.01 and self.f > 0.3:           # a new job reuses the panel
            self.reset()
        f = max(f, self.f)                      # never back inside one job
        el = now - self.t0
        if f > self.f:
            self.hist.append((now, f))
            self.hist = [h for h in self.hist if now - h[0] <= self.WINDOW] or [(now, f)]
        if 0.02 <= f < 1 and el > 8:
            glob = el * (1 - f) / f
            t1, f1 = self.hist[0]
            rec = (1 - f) * (now - t1) / (f - f1) if f - f1 > 1e-4 and now - t1 > 5 else glob
            left = 0.6 * rec + 0.4 * glob
            est = el + left
            self.total = est if self.total is None else 0.75 * self.total + 0.25 * est
        self.f, self.tf = f, now

    def text(self):
        el = time.time() - self.t0
        out = f"{_fmt_dur(el)} elapsed"
        if 0 < self.f < 1:
            if self.total is None:
                out += "  ·  estimating the time left…"
            else:
                left = self.total - el
                out += f"  ·  about {_fmt_dur(left)} left" if left >= 5 else "  ·  almost done"
        return out


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
        self.clock = EtaClock()
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self._refresh)
        self.hide()

    def _refresh(self):
        try:
            if not self.isVisible() or self.clock.f >= 1:
                return
            self.detail.setText(self.clock.text())
        except Exception:                       # a timer must never raise
            pass

    def showEvent(self, e):
        self._tick.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._tick.stop()
        super().hideEvent(e)

    def allow_cancel(self, cb):
        self._cancel_cb = cb
        self.b_cancel.setVisible(cb is not None)

    def start(self, text="Starting…"):
        self.t0 = time.time()
        self.clock.reset()
        self.set(text, 0.0)
        self.show()

    def set(self, text, f):
        f = max(0.0, min(1.0, f))
        self.title.setText(text)
        self.pct.setText(f"{int(f * 100)}%")
        self.bar.setValue(int(f * 1000))
        self.clock.feed(f)
        self.detail.setText(self.clock.text())


class _DvJob(QThread):
    progress = Signal(str, float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, src, out):
        super().__init__()
        self.src, self.out, self._stop = src, out, False

    def run(self):
        try:
            self.done.emit(resolve.make(self.src, self.out, lambda t, f: self.progress.emit(t, f), lambda: self._stop))
        except Exception as e:
            logging.exception("DaVinci export")
            self.failed.emit(str(e))


class DaVinciCheck(QDialog):
    """Export for DaVinci Resolve: the XML is made for Resolve, then checked from end to end (links, every clip named
    like its file, in / out inside the file, Premiere-only effects gone, every file found on this computer)."""

    def __init__(self, parent, src, out):
        super().__init__(parent)
        self.setWindowTitle("Export for DaVinci Resolve")
        self.setModal(True)
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        v.addWidget(lbl("Export for DaVinci Resolve", "h2"))
        v.addWidget(lbl("The XML is made for Resolve and checked from end to end before you import it.", "muted", True))
        self.pp = ProgressPanel()
        v.addWidget(self.pp)
        self.rep = lbl("", "", True)
        self.rep.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.rep)
        row = QHBoxLayout()
        row.addStretch()
        self.b_close = btn("Close", "primary", self.accept)
        self.b_close.setEnabled(False)
        row.addWidget(self.b_close)
        v.addLayout(row)
        self.result, self.out = None, out
        self.job = _DvJob(src, out)
        self.job.progress.connect(lambda t, f: self.pp.set(i18n.T(t), f))
        self.job.done.connect(self._done)
        self.job.failed.connect(self._failed)
        self.job.finished.connect(lambda: self.b_close.setEnabled(True))
        self.pp.start("Making the DaVinci Resolve version…")
        self.pp.allow_cancel(lambda: setattr(self.job, "_stop", True))
        self.job.start()

    def _done(self, r):
        self.result = r
        self.pp.hide()
        name = escape(Path(self.out).name)
        lines = [f"<b>{name}</b>", i18n.T("{} clips, {} files checked.").format(r["clips"], r["files"])]
        if r.get("project_unwrapped"):
            lines.append(i18n.T("Bins are Premiere only: Resolve gets the sequence and puts the clips in its Media Pool."))
        if r.get("scale_removed"):
            lines.append(i18n.T("{} Premiere scale settings left out: Resolve fits every clip to the timeline itself.").format(r["scale_removed"]))
        if r.get("colour_removed"):
            lines.append(i18n.T("{} colour effects (LUT / crop) left out: put your LUT on Resolve's Color page.").format(r["colour_removed"]))
        if r.get("renamed"):
            lines.append(i18n.T("{} clip names set to their file name (Resolve links media by name).").format(r["renamed"]))
        for w_ in r["warnings"]:
            lines.append(f'<span style="color:{C["FAIR"]}">⚠ {escape(i18n.T(w_))}</span>')
        if r["errors"]:
            for e in r["errors"]:
                lines.append(f'<span style="color:{C["POOR"]}">✕ {escape(i18n.T(e))}</span>')
            lines.append(i18n.T("Send this file to Claude (Settings > Save error report) so it can be fixed."))
            notify(i18n.T("DaVinci check found problems: {}").format(Path(self.out).name), error=True)
        else:
            lines.append(f'<span style="color:{C["GOOD"]}">✓ ' + i18n.T("Ready for DaVinci Resolve: File > Import > Timeline.") + "</span>")
            notify(i18n.T("Ready for DaVinci Resolve: {}").format(Path(self.out).name))
        self.rep.setText("<br>".join(lines))

    def _failed(self, msg):
        self.pp.hide()
        self.rep.setText(f'<span style="color:{C["POOR"]}">' + escape(i18n.T("The DaVinci version could not be made: {}").format(i18n.T(msg))) + "</span>")
        notify(i18n.T("The DaVinci version could not be made: {}").format(i18n.T(msg)), error=True)

    def reject(self):
        if self.job.isRunning():
            self.job._stop = True
            self.job.wait(5000)
        super().reject()


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
            "multicam": "Sync several cameras to a master audio recorder, then build the multicam edit.",
            "sync": "Only the sync: every camera and the recorder on one timeline, ready for Premiere or DaVinci Resolve."}

    def __init__(self, parent=None, kind=None):
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
        if kind:                          # the Selection / Multicam pages: the type is the page's own
            for w_ in (self.b1, self.b2):
                w_.hide()
            v.itemAt(1).widget().hide()
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
        self.pick(kind or "footage")

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
        badge = QLabel(("SYNCHRONIZE" if p.get("sync_only") else "MULTICAM") if multi else "FOOTAGE")
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

    def __init__(self, kind="footage"):
        super().__init__()
        self.kind = kind                  # "footage" (Selection), "sync" or "multicam": each has its own page in the menu
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        head = QHBoxLayout()
        head.addWidget(lbl({"multicam": "Multicam", "sync": "Synchronize"}.get(kind, "Selection"), "h1"))
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
        if self.kind == "footage":
            projects = [p for p in projects if p.get("type") != "multicam"]
        else:
            projects = [p for p in projects if p.get("type") == "multicam" and bool(p.get("sync_only")) == (self.kind == "sync")]
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
        hh.addWidget(btn("←  Selection", "link", self.back.emit))
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
        lv.addLayout(lh)
        lb = QHBoxLayout()                      # own row: both buttons fit in Romanian too
        lb.setSpacing(8)
        lb.addWidget(btn("Add Folder", slot=self.pick_dir))
        lb.addWidget(btn("Import XML", slot=lambda: self.import_xml()))
        lb.addStretch()
        lv.addLayout(lb)
        lv.addSpacing(4)
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
                               60, lo=0, hi=90, suffix="")
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
        kr = QHBoxLayout()
        kr.addWidget(lbl("Keep every good frame"))
        kq = lbl("?", "muted")
        kq.setToolTip("Smooth camera moves (gimbal, slow pans) that stay sharp are kept as shots of their own; only "
                      "blurred whip pans and dark moves are cut out. A good piece shorter than the minimum cut is kept "
                      "when it touches another kept piece, and a short clip keeps its good part (at least 1 s).")
        kr.addWidget(kq)
        kr.addStretch()
        self.sw_keep = Switch(True)
        self.sw_keep.toggled.connect(lambda v: self.set_s("keepall", v))
        kr.addWidget(self.sw_keep)
        av.addLayout(kr)
        pr = QHBoxLayout()
        pr.addWidget(lbl("Party footage"))
        pq = lbl("?", "muted")
        pq.setToolTip("Only for party footage (people dancing, jumping, lights). The shots are judged like the handheld "
                      "cameras of Multicam: people moving in front of the camera no longer count as a shaking camera; "
                      "only whip pans, blur, dark shots and a camera put down are cut out. Leave it off for everything "
                      "else: then the selection works exactly as before.")
        pr.addWidget(pq)
        pr.addStretch()
        self.sw_party = Switch(False)
        self.sw_party.toggled.connect(self._party_toggled)
        pr.addWidget(self.sw_party)
        av.addLayout(pr)
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
    def _drop(self, paths):
        """Finder drop: an XML is imported (its clips in its order), clips / folders are added."""
        xmls, rest = _xml_or_rest(paths)
        if xmls:
            self.import_xml(xmls[0])
        if rest:
            self.add(rest)

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
        self.sw_keep.set(s.get("keepall", True))
        self.sw_party.set(s.get("party", False))
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

    def import_xml(self, path=None):
        """The clips of a Premiere / DaVinci timeline (FCP7 XML), in the order they sit on it: the analysis and the
        export keep that order (cameras and filming order as he laid them out)."""
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Import XML", "", "XML (*.xml)")
        if not path:
            return
        try:
            found, missing = xmlimport.footage(path)
        except Exception as ex:
            logging.exception("footage xml import")
            notify(i18n.T("Import XML failed: {}").format(i18n.T(str(ex))), error=True)
            return
        if not found:
            notify(i18n.T("None of the clips in this XML were found on this computer (e.g. {}). Is the footage disk connected?")
                   .format(missing[0] if missing else "?"), error=True)
            return
        have = set(self.p["videos"])
        new = [f for f in found if f not in have]
        if not new:
            notify(i18n.T("Every clip of this XML is already in the project."))
            return
        self.p["videos"] += new
        self.store.save()
        self.refresh_videos()
        if missing:
            notify(i18n.T("{} clips added from the XML, in its order. {} clips are not on this computer and were skipped.")
                   .format(len(new), len(missing)), error=True, ms=9000)
        else:
            notify(i18n.T("{} clips added from the XML, in its order.").format(len(new)))

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

    def _party_toggled(self, on):
        """Party footage: a double check (Yes / No) before the party judgement is switched on."""
        if on:
            from PySide6.QtWidgets import QMessageBox
            m = QMessageBox(self)
            m.setIcon(QMessageBox.Question)
            m.setWindowTitle(i18n.T("Party footage"))
            m.setText(i18n.T("Are you sure you are giving me party footage to select?"))
            m.setInformativeText(i18n.T("The shots will be judged like the handheld cameras of Multicam. For anything "
                                        "else (church, getting ready, couple) leave this off."))
            yes = m.addButton(i18n.T("Yes"), QMessageBox.YesRole)
            m.addButton(i18n.T("No"), QMessageBox.NoRole)
            m.exec()
            if m.clickedButton() is not yes:
                self.sw_party.set(False)
                return
        self.set_s("party", on)

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
        self.clock = EtaClock()
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self._tick_eta)

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
        sizes = []
        for p in paths:                        # every clip weighted by its size (~ its length): an honest bar
            try:
                sizes.append(max(1, os.path.getsize(p)))
            except OSError:
                sizes.append(1)
        tot = float(sum(sizes)) or 1.0
        self.wt = [s / tot for s in sizes]
        self.state = ["waiting"] * len(paths)
        self.t0 = time.time()
        self.clock.reset()
        self._tick.start()
        self.paused = False
        self.b_pause.setText("Pause Analysis")
        self._upd()

    def _tick_eta(self):
        try:
            if self.total and self.fin >= self.total:
                self._tick.stop()
                return
            if not self.paused:
                self.eta.setText(self.clock.text())
        except Exception:
            pass

    def _upd(self):
        wt = getattr(self, "wt", None) or [1.0 / max(1, self.total)] * self.total
        f = sum(x * w for x, w in zip(self.part, wt))
        self.bar.setValue(int(f * 1000))
        self.pct.setText(f"{int(f * 100)}%")
        running = self.state.count("running")
        waiting = self.state.count("waiting")
        self.count.setText(f"{self.fin} of {self.total} clips done  ·  {running} running  ·  {waiting} waiting")
        self.clock.feed(f)
        self.eta.setText(self.clock.text())
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
        for b in (self.b_pp, self.b_dr):        # v4.2.0: the program comes from the top-right switch
            b.setEnabled(False)
            b.setToolTip("Change the program top right (I work in: Premiere Pro | DaVinci Resolve).")
        on_target(lambda t: self.set_sw("DaVinci Resolve" if t == "davinci" else "Premiere Pro")
                  if hasattr(self, "next") else None)
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
        self.set_sw("DaVinci Resolve" if target() == "davinci" else "Premiere Pro")
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
            dv = getattr(self, "sw", "Premiere Pro") == "DaVinci Resolve"
            if dv:
                out = Path(resolve.name_for(str(out), "davinci"))
            n = core.export_xmeml(self.items, str(out), name, seq, single=self.p["settings"].get("mode", "auto") == "auto")
            for_target(str(out), "davinci" if dv else "premiere")
        except Exception as e:
            self.msg.setStyleSheet(f"color:{C['POOR']}")
            self.msg.setText(f"Error: {e}")
            logging.exception("footage export failed")
            notify(f"Export failed: {e}", error=True)
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


def fmt_hms(t):
    a = abs(t)
    return ("-" if t < 0 else "") + f"{int(a // 3600)}:{int(a % 3600 // 60):02d}:{a % 60:04.1f}"


class SyncMap(QWidget):
    """Audio master row, an 'Auto edit' row coloured by camera, then one row per camera.
    "Slower cuts" zones are drawn over it: drag on the map to add one, drag its edges to move them, right-click to
    delete it (the exact times are edited in the list under the map)."""
    zones_changed = Signal(list)
    LEFT = 130

    def __init__(self):
        super().__init__()
        self.mdur, self.rows, self.edit, self.tmin, self.tmax = 0.0, [], [], 0.0, 1.0
        self.zones, self.drag, self.sel = [], None, None
        self.show_edit, self.music = True, None   # show_edit False on the Sync page: no auto edit row, no zones
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)

    # ---- zones
    def set_zones(self, zones):
        self.zones = [list(z) for z in zones]
        self.update()

    def _t(self, x):
        W = self.width() - self.LEFT - 12
        return self.tmin + (x - self.LEFT) / max(1.0, W) * max(1e-6, self.tmax - self.tmin)

    def _x(self, t):
        W = self.width() - self.LEFT - 12
        return self.LEFT + (t - self.tmin) / max(1e-6, self.tmax - self.tmin) * W

    def _hit(self, x):
        for i, (z0, z1) in enumerate(self.zones):
            if abs(self._x(z0) - x) <= 6:
                return i, 0
            if abs(self._x(z1) - x) <= 6:
                return i, 1
        for i, (z0, z1) in enumerate(self.zones):
            if self._x(z0) < x < self._x(z1):
                return i, None
        return None, None

    def mousePressEvent(self, e):
        x = e.position().x()
        if not self.show_edit or x < self.LEFT or self.tmax <= self.tmin:
            return
        i, edge = self._hit(x)
        if e.button() == Qt.RightButton:
            if i is not None:
                from PySide6.QtWidgets import QMenu
                m = QMenu(self)
                act = m.addAction("Delete this Slower cuts zone")
                if m.exec(e.globalPosition().toPoint()) == act:
                    self.zones.pop(i)
                    self.sel = None
                    self.zones_changed.emit(self.zones)
                    self.update()
            return
        if i is not None and edge is not None:
            self.drag = ("edge", i, edge)
        elif i is not None:
            self.sel = i
            self.update()
        else:
            t = self._t(x)
            self.drag = ("new", t, t)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if not self.drag:
            i, edge = self._hit(x)
            self.setCursor(Qt.SizeHorCursor if edge is not None else Qt.ArrowCursor)
            return
        t = min(self.tmax, max(self.tmin, self._t(x)))
        if self.drag[0] == "new":
            self.drag = ("new", self.drag[1], t)
        else:
            _, i, edge = self.drag
            z = self.zones[i]
            z[edge] = min(t, z[1] - 2) if edge == 0 else max(t, z[0] + 2)
        self.update()

    def mouseReleaseEvent(self, e):
        if not self.drag:
            return
        if self.drag[0] == "new":
            a_, b_ = sorted(self.drag[1:])
            if b_ - a_ >= 5:                                # shorter = a click, not a zone
                self.zones.append([a_, b_])
                self.sel = len(self.zones) - 1
        self.drag = None
        # overlapping zones become one
        zs = sorted(self.zones)
        out = []
        for z in zs:
            if out and z[0] <= out[-1][1]:
                out[-1][1] = max(out[-1][1], z[1])
            else:
                out.append(list(z))
        self.zones = out
        self.zones_changed.emit(self.zones)
        self.update()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.sel is not None and self.sel < len(self.zones):
            self.zones.pop(self.sel)
            self.sel = None
            self.zones_changed.emit(self.zones)
            self.update()

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
        left = self.LEFT
        W, span = self.width() - left - 12, max(1e-6, self.tmax - self.tmin)
        X = lambda t: left + (t - self.tmin) / span * W

        def row(y, label, color=None):
            if color:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                p.drawEllipse(QRectF(0, y + 6, 8, 8))
            p.setPen(QColor(C["TEXT"] if color else C["MUTED"]))
            p.drawText(QRectF(14 if color else 0, y, left - 18, 20), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(i18n.T(label), Qt.ElideRight, left - 20))
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
        if self.show_edit:
            row(y, "Auto edit")
            for t0, t1, col in self.edit:
                p.setBrush(QColor(col))
                p.drawRect(QRectF(X(t0), y + 1, max(1.5, X(t1) - X(t0)), 18))
            y += 34
        else:
            y += 8
        for label, color, blocks in self.rows:
            row(y, label, color)
            for t0, t1, conf in blocks:
                p.setBrush(QColor(CONF_COL[conf]))
                p.drawRoundedRect(QRectF(X(t0), y + 3, max(2.0, X(t1) - X(t0)), 14), 2, 2)
            y += 26
        y += 4
        zs = [list(z) for z in self.zones]
        if self.drag and self.drag[0] == "new":
            zs.append(sorted(self.drag[1:]))
        for k, (z0, z1) in enumerate(zs):
            sel = k == self.sel
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(240, 180, 60, 70 if sel else 45))
            p.drawRect(QRectF(X(z0), 0, max(2.0, X(z1) - X(z0)), y - 4))
            p.setPen(QPen(QColor("#f0b43c"), 1.5))
            p.drawLine(QPointF(X(z0), 0), QPointF(X(z0), y - 4))
            p.drawLine(QPointF(X(z1), 0), QPointF(X(z1), y - 4))
            if X(z1) - X(z0) > 90:
                p.setPen(QColor("#f0b43c"))
                p.drawText(QRectF(X(z0) + 4, y - 22, X(z1) - X(z0) - 8, 16), Qt.AlignLeft | Qt.AlignVCenter,
                           p.fontMetrics().elidedText(f"Slower cuts  {fmt_hms(z0)} – {fmt_hms(z1)}", Qt.ElideRight,
                                                      int(X(z1) - X(z0) - 8)))
        p.setPen(QColor(C["MUTED"]))
        step = next((s for s in (10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200) if span / s <= 8), 7200)
        t = (self.tmin // step) * step
        while t <= self.tmax:
            if t >= self.tmin:
                a = abs(t)
                lab = (f"{int(a // 3600)}:{int(a % 3600 // 60):02d}:{int(a % 60):02d}" if step >= 60 else f"{int(a)}s")
                p.drawText(QRectF(X(t) - 34, y, 68, 16), Qt.AlignCenter, ("-" if t < 0 else "") + lab)
            t += step


class Awake:
    """Keeps the Mac awake while a long job runs (overnight). Always reaped: no zombie process."""
    def __init__(self):
        self.p = None

    def on(self):
        if self.p is None and sys.platform == "darwin":
            try:
                self.p = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            except Exception:
                self.p = None

    def off(self):
        if self.p is not None:
            try:
                self.p.terminate()
                self.p.wait(timeout=3)
            except Exception:
                pass
            self.p = None


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
        need = [(i, m) for i, m in enumerate(self.masters) if m.get("path") and not m.get("music") and Path(m["path"]).exists()]
        # one bar for the whole step, every clip weighted by its LENGTH (a 20 min clip is not the same as a 10 s one)
        durs = {}
        for v in left:
            try:
                durs[v] = max(1.0, core.probe(v).duration or 60.0)
            except Exception:
                durs[v] = 60.0
        music_h = sum((m.get("duration") or 0.0) for _i, m in need) / 3600.0
        w_an = sum(durs.values()) / 15.0 / max(1, self.jobs)
        w_mu = music_h * 6 + (1 if need else 0)
        share = w_an / max(1e-6, w_an + w_mu) if left else 0.0
        got, done, lock = {}, [0], threading.Lock()
        tot = sum(durs.values()) or 1.0

        def report():
            f = sum(min(1.0, got.get(v, 0.0)) * durs[v] for v in left) / tot
            self.progress.emit(f"Step 2 · analysing video for the auto edit: {done[0]} of {len(left)} clips done", share * f)
        self.progress.emit(f"Step 2 · analysing video for the auto edit: 0 of {len(left)}", 0.0)

        def one(v):
            if self._stop:
                return

            def pr(x):
                with lock:
                    got[v] = x
                report()
            an[v] = core.analyze(v, pr, cancel=lambda: self._stop)
            with lock:
                got[v] = 1.0
                done[0] += 1
            report()

        with ThreadPoolExecutor(max(1, self.jobs)) as ex:
            list(ex.map(one, left))
        if self._stop:
            raise InterruptedError
        # the music map of every recorder file (once: kept in the project)
        maps = {}
        for n, (i, m) in enumerate(need):
            if self._stop:
                raise InterruptedError
            self.progress.emit(f"Step 2 · reading the music (beats, bars, drops): {n + 1} of {len(need)}",
                               share + (1 - share) * (n + 0.5) / len(need))
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
        self.b_back = btn("←  Multicam", "link", self.back.emit)
        hh.addWidget(self.b_back)
        self.title = lbl("", "h2")
        hh.addWidget(self.title)
        hh.addStretch()
        self.b_exp = ExportPair(self.export)
        self.b_xml = btn("Import XML", slot=lambda: self.import_xml())
        self.b_xml.setToolTip("Use a timeline that is already synced in Syncaila, Premiere Pro or DaVinci Resolve (FCP7 XML).")
        self.b_auto = btn("Auto Edit", slot=self.run_auto)
        self.b_run = btn("Sync", slot=self.toggle_run)
        self.b_all = btn("Sync + Auto Edit", "primary", self.run_all)
        self.b_all.setToolTip("Everything in one go (good overnight): Sync, then Auto Edit right after it. "
                              "The Mac is kept awake until it ends.")
        self._chain, self._awake = None, Awake()
        self.b_tomc = btn("Auto Edit in Multicam  →", slot=self.to_multicam)
        self.b_tomc.setToolTip("Moves this project to Multicam, where Auto Edit builds the edit (the sync is kept).")
        self.b_edit = btn("Edit", slot=self.edit_film)
        self.b_edit.setToolTip("Open the edit in the editor (like Premiere): every camera on its track, the recorder and "
                               "the cameras' sound below. Export XML then writes your version.")
        hh.addWidget(self.b_xml)
        hh.addWidget(self.b_edit)
        hh.addWidget(self.b_exp)
        hh.addWidget(self.b_tomc)
        hh.addWidget(self.b_run)
        hh.addWidget(self.b_auto)
        hh.addWidget(self.b_all)
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
        lv.addSpacing(6)
        lv.addWidget(lbl("SYNC", "section"))
        self.syncopt = SyncOptions(store)
        lv.addWidget(self.syncopt)
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
        self.map.zones_changed.connect(self._zones_from_map)
        holder = QWidget()
        hv_ = QVBoxLayout(holder)
        hv_.setContentsMargins(0, 0, 0, 0)
        hv_.addWidget(self.map)
        zf = QFrame()
        zf.setObjectName("card")
        zl = QVBoxLayout(zf)
        zl.setContentsMargins(12, 10, 12, 10)
        zl.setSpacing(6)
        zh = QHBoxLayout()
        zh.addWidget(lbl("SLOWER CUTS ZONES", "section"))
        zh.addStretch()
        zl.addLayout(zh)
        zl.addWidget(lbl("For folk music (and any part where cutting on the bars does not fit): drag on the map to mark a "
                         "zone; there the auto edit cuts the way it did before the bars (on the nearest accent of the "
                         "sound) and with longer shots. Drag an edge to move it, type the exact times below, right-click "
                         "or Delete to remove it.", "muted", True))
        self.zrows = QVBoxLayout()
        self.zrows.setSpacing(4)
        zl.addLayout(self.zrows)
        hv_.addSpacing(6)
        hv_.addWidget(zf)
        self.zf = zf
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
        self.cam_t = QTableWidget(0, 6)
        self.cam_t.setHorizontalHeaderLabels(["Camera (double-click to rename)", "Role", "Clips", "Footage", "In the edit",
                                              "Track"])
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
        self.b_learn = btn("Learn my editing style…", "link", self.learn_style)
        self.b_learn.setToolTip("Give it the XML of a party YOU edited: it measures how you cut (shot lengths, drops, the "
                                "beat) and sets the Auto Director like you. Saved on this computer only.")
        rv.addWidget(self.b_learn, 0, Qt.AlignLeft)
        self.style_lbl = lbl("", "muted", True)
        rv.addWidget(self.style_lbl)
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
        # ---- on the music (the same for every project)
        rv.addSpacing(12)
        rv.addWidget(lbl("ON THE MUSIC  ·  ALL PROJECTS", "section"))
        rv.addWidget(lbl("Used when Cut on the beat is on.", "muted", True))
        ms = self.store.app.setdefault("music", dict(drop_beats=4, buildup="hold"))
        self.music_box = QWidget()
        mb = QVBoxLayout(self.music_box)
        mb.setContentsMargins(0, 4, 0, 0)
        mb.setSpacing(6)
        mb.addWidget(lbl("On a drop, change camera every"))
        self.c_drop = QComboBox()
        self.c_drop.setProperty("i18n", True)        # works by position: safe to translate
        self._drop_vals = [1, 2, 4, 8, 16]
        self.c_drop.addItems(["1 beat", "2 beats", "1 bar (4 beats)", "2 bars", "4 bars"])
        self.c_drop.setCurrentIndex(self._drop_vals.index(ms.get("drop_beats", 4)) if ms.get("drop_beats", 4) in self._drop_vals else 2)
        self.c_drop.currentIndexChanged.connect(lambda i: self._set_music("drop_beats", self._drop_vals[i]))
        mb.addWidget(self.c_drop)
        mb.addWidget(lbl("Build-up before a drop"))
        self.c_build = QComboBox()
        self.c_build.setProperty("i18n", True)
        self.c_build.addItems(["Hold one shot until the drop", "Cut faster and faster"])
        self.c_build.setCurrentIndex(0 if ms.get("buildup", "hold") == "hold" else 1)
        self.c_build.currentIndexChanged.connect(lambda i: self._set_music("buildup", "hold" if i == 0 else "accelerate"))
        mb.addWidget(self.c_build)
        rv.addWidget(self.music_box)
        rv.addSpacing(10)
        self.stats = lbl("Press Auto Edit to build the edit.", "muted", True)
        rv.addWidget(self.stats)
        rv.addStretch()
        eb = QHBoxLayout()
        eb.setContentsMargins(16, 6, 16, 12)
        eb.addWidget(ExportPair(self.export, True))
        ro.addLayout(eb)
        body.addWidget(right)
        self.right = right

    # ---- learn my editing style
    def _drop(self, paths):
        """Finder drop: an XML = a synced timeline (Import XML), everything else is added like Add Folder."""
        xmls, rest = _xml_or_rest(paths)
        if xmls:
            self.import_xml(xmls[0])
        elif rest:
            self.add(rest)

    def _show_style(self):
        s = self.store.app.get("style")
        self.style_lbl.setText(f"Your style: learned from {s['from']} ({s['date']})" if s else "")
        self.style_lbl.setVisible(bool(s))

    def learn_style(self):
        f, _ = QFileDialog.getOpenFileName(self, "XML of a party you edited (export the sequence from Premiere)", "", "XML (*.xml)")
        if not f:
            return
        self.b_learn.setEnabled(False)
        self.status.setText("Learning your style: reading your edit (and its music, if the recorder files are on this computer)…")
        cams = self.p["cams"] if self.p else None
        self._lw = _Runner(lambda progress=None: style.learn(f, cams, progress))
        self._lw.progress.connect(lambda t, x: self.status.setText(t))
        self._lw.done.connect(lambda r: (self.b_learn.setEnabled(True), self.status.setText(""), self._style_dialog(f, r)))
        self._lw.failed.connect(lambda m: (self.b_learn.setEnabled(True), self.status.setText(f"Could not learn from it: {m}"),
                                           notify(f"Could not learn from it: {m}", error=True)))
        self._lw.start()

    def _style_dialog(self, f, r):
        s = r["suggest"]
        d = QDialog(self)
        d.setWindowTitle("Learn my editing style")
        d.setStyleSheet(f"QDialog{{background:{C['BG']}}}")
        v = QVBoxLayout(d)
        v.setContentsMargins(20, 16, 20, 16)
        v.addWidget(lbl("What your edit looks like", "h2"))
        lines = [f"{r['shots']} shots · usually {r['median']:.1f} s (the shortest ones {r['p15']:.1f} s, the longest {r['p95']:.0f} s)"]
        if r.get("music"):
            parts = []
            if r.get("calm"):
                parts.append(f"calm music {r['calm']:.1f} s")
            if r.get("intense"):
                parts.append(f"intense music {r['intense']:.1f} s")
            if r.get("drop"):
                parts.append(f"drops {r['drop']:.1f} s")
            if parts:
                lines.append("Shots on " + " · ".join(parts))
            off = r.get("offset_frames", 0)
            when = "on the beat" if abs(off) < 0.5 else (f"{abs(off):.0f} frame(s) before the beat" if off < 0 else f"{off:.0f} frame(s) after the beat")
            lines.append(f"{r['on_beat'] * 100:.0f}% of your cuts are on a beat, usually {when}")
        else:
            lines.append("The music could not be read (the recorder files of that timeline are not on this computer): "
                         "only the shot lengths were measured.")
        if r.get("handheld_share") is not None:
            lines.append(f"Handheld cameras {r['handheld_share'] * 100:.0f}% of the time")
        for t in lines:
            v.addWidget(lbl("• " + t, "", True))
        v.addSpacing(8)
        v.addWidget(lbl("Settings that cut like you", "h2"))
        names = dict(minshot=("Minimum shot", lambda x: f"{x:g} s"), maxshot=("Maximum shot", lambda x: f"{x} s"),
                     pace=("Cut pace", str), energy=("Static ↔ Handheld", str),
                     drop_beats=("On a drop, change camera every", lambda x: {1: "1 beat", 2: "2 beats", 4: "1 bar", 8: "2 bars", 16: "4 bars"}[x]),
                     energy_cuts=("Faster cuts when the music is more intense", lambda x: "on" if x else "off"),
                     pre_frames=("Cut", lambda x: ["exactly on the beat", "1 frame before the beat", "2 frames before the beat"][x]))
        g = QGridLayout()
        for i, (k, val) in enumerate(s.items()):
            g.addWidget(lbl(names[k][0], "muted"), i, 0)
            g.addWidget(lbl(names[k][1](val)), i, 1)
        v.addLayout(g)
        v.addWidget(lbl("The music options are the same for every project. Your style is saved on this computer only: "
                        "another editor on another computer learns his own.", "muted", True))
        br = QHBoxLayout()
        br.addStretch()
        br.addWidget(btn("Cancel", slot=d.reject))
        b1 = btn("Use for this project", slot=lambda: (self._apply_style(s, f, False), d.accept()))
        b2 = btn("Use as my style (every new project)", "primary", lambda: (self._apply_style(s, f, True), d.accept()))
        br.addWidget(b1)
        br.addWidget(b2)
        v.addLayout(br)
        d.exec()

    def _apply_style(self, s, f, as_default):
        for k in ("minshot", "maxshot", "pace", "energy"):
            if k in s and self.p:
                self.p["dir"][k] = s[k]
        ms = self.store.app.setdefault("music", {})
        for k in ("drop_beats",):
            if k in s:
                ms[k] = s[k]
        if as_default:
            self.store.app["style"] = dict(settings=s, **{"from": Path(f).name, "date": time.strftime("%d.%m.%Y")})
        self.store.save_app()
        self.store.save()
        logging.info("style learned from %s: %s (default=%s)", f, s, as_default)
        notify("Your editing style is applied" + (" (every new project)" if as_default else ""))
        if self.p:
            self.load(self.p)                            # sliders and switches show the new values
        self._show_style()
        if self.p and self.p.get("sync"):
            self.recompute()

    # ---- "Slower cuts" zones (saved in the project, global timeline seconds)
    def _zones_from_map(self, zones):
        if not self.p:
            return
        self.p["zones"] = [[round(a_, 2), round(b_, 2)] for a_, b_ in zones]
        self.store.save()
        self._fill_zone_rows()
        if self.p.get("sync"):
            self.timer.start()

    def _fill_zone_rows(self):
        while self.zrows.count():
            it = self.zrows.takeAt(0)
            w_ = it.widget()
            if w_:
                w_.deleteLater()
            elif it.layout():
                while it.layout().count():
                    x_ = it.layout().takeAt(0).widget()
                    if x_:
                        x_.deleteLater()
        zones = (self.p or {}).get("zones", [])
        if not zones:
            self.zrows.addWidget(lbl("No zones: the whole party is cut on the music (when Cut on the beat is on).", "muted", True))
            return
        for k, (z0, z1) in enumerate(zones):
            row = QWidget()
            r = QHBoxLayout(row)
            r.setContentsMargins(0, 0, 0, 0)
            r.addWidget(lbl(f"Zone {k + 1}"))
            ea, eb = QLineEdit(fmt_hms(z0)), QLineEdit(fmt_hms(z1))
            for e_ in (ea, eb):
                e_.setFixedSize(110, 28)
                e_.setAlignment(Qt.AlignCenter)
                e_.setValidator(QRegularExpressionValidator(QRegularExpression(r"^-?\d{0,2}(:\d{0,2}){0,2}(\.\d?)?$")))
            ea.editingFinished.connect(lambda k=k, ea=ea, eb=eb: self._zone_typed(k, ea, eb))
            eb.editingFinished.connect(lambda k=k, ea=ea, eb=eb: self._zone_typed(k, ea, eb))
            r.addWidget(ea)
            r.addWidget(lbl("→", "muted"))
            r.addWidget(eb)
            r.addWidget(lbl(f"{(z1 - z0) / 60:.1f} min", "muted"))
            r.addStretch()
            r.addWidget(btn("Delete", "link", lambda _=False, k=k: self._zone_delete(k)))
            self.zrows.addWidget(row)

    def _zone_typed(self, k, ea, eb):
        try:
            a_, b_ = parse_t(ea.text()), parse_t(eb.text())
        except ValueError:
            return
        zones = self.p.get("zones", [])
        if k < len(zones) and b_ - a_ >= 2:
            zones[k] = [a_, b_]
            self.map.set_zones(zones)
            self._zones_from_map(self.map.zones)

    def _zone_delete(self, k):
        zones = self.p.get("zones", [])
        if k < len(zones):
            zones.pop(k)
            self.map.set_zones(zones)
            self._zones_from_map(zones)

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
        if not p.get("dir"):                         # a new project starts with this computer's learned style
            mine = self.store.app.get("style", {}).get("settings", {})
            p["dir"] = {**director.DEFAULTS, **{k: v for k, v in mine.items() if k in ("minshot", "maxshot", "pace", "energy")}}
        p["dir"] = {**director.DEFAULTS, **p["dir"]}
        if p["dir"].get("static_backup"):            # that switch was removed: the slider towards Handheld does it
            p["dir"]["energy"] = max(p["dir"].get("energy", 60), 85)
            p["dir"]["static_backup"] = False
        self.title.setText(p["name"])
        self._mode_ui()
        QTimer.singleShot(0, self._music_enabled)
        self.map.set_zones(p.get("zones", []))
        self._fill_zone_rows()
        self._show_style()
        ms_ = self.store.app.get("music", {})
        for cb, val in ((self.c_drop, self._drop_vals.index(ms_.get("drop_beats", 4)) if ms_.get("drop_beats", 4) in self._drop_vals else 2),
                        (self.c_build, 0 if ms_.get("buildup", "hold") == "hold" else 1)):
            cb.blockSignals(True)
            cb.setCurrentIndex(val)
            cb.blockSignals(False)
        for k, r in self.d_rows.items():
            r.set(p["dir"][k])
        self.sw_beat.set(p["dir"]["beat"])
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

    # ---- Sync page (sync only) or Multicam
    def _mode_ui(self):
        so = bool(self.p.get("sync_only"))
        self.b_back.setText("←  Synchronize" if so else "←  Multicam")
        for w_ in (self.b_auto, self.b_all, self.right):
            w_.setVisible(not so)
        self.b_tomc.setVisible(so)
        self.zf.setVisible(not so)
        self.map.show_edit = not so
        self.map.update()
        self.b_run.setObjectName("primary" if so else "")
        repolish(self.b_run)

    def to_multicam(self):
        if self._busy():
            return
        self.p["sync_only"] = False
        self.store.save()
        self._mode_ui()
        notify(i18n.T("Moved to Multicam: press Auto Edit to build the edit."))

    # ---- run
    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _sync_buttons(self):
        busy = self._busy()
        mine = busy and self.p is getattr(self, "_job_p", None)
        mode = self.worker.mode if busy else ""
        chained = mine and self._chain is self._job_p
        self.b_all.setText("Cancel" if chained else "Sync + Auto Edit")
        self.b_all.setEnabled((not busy and bool(self.p["files"])) or chained)
        self.b_run.setText("Cancel" if mine and mode == "sync" and not chained else "Sync")
        self.b_auto.setText("Cancel" if mine and mode == "analyze" and not chained else "Auto Edit")
        self.b_run.setEnabled((not busy and bool(self.p["files"])) or (mine and mode == "sync" and not chained))
        self.b_auto.setEnabled((not busy and bool(self.p.get("sync"))) or (mine and mode == "analyze" and not chained))
        if not busy and self._chain is None:
            self._awake.off()
        self.b_xml.setEnabled(not busy)
        if mine and mode == "xml":
            self.b_run.setText("Cancel")
            self.b_run.setEnabled(False)
        self.pp.setVisible(bool(mine))
        if busy and not mine:
            self.status.setText(f"Another job is running ({self._job_p['name']}). See Analysis Queue.")

    def _start(self, worker, button, p=None, keep_clock=False):
        self._job_p, self.job_status, self.job_progress = p or self.p, "Starting…", 0.0
        if not keep_clock:
            job_mark(("mc", self._job_p["id"]))
        self.pp.start()
        self.worker = worker
        worker.progress.connect(self.on_progress)
        worker.done.connect(self.on_done)
        worker.failed.connect(self.on_failed)
        self._button = button
        worker.finished.connect(self._sync_buttons)     # refresh once the thread has really stopped
        worker.start()
        self._sync_buttons()

    def toggle_run(self):
        if self._busy():
            if self.p is self._job_p:
                self.worker.cancel()
            return
        if self.p["files"]:
            self._start(MCWorker("sync", list(self.p["files"]), jobs=self.store.app["jobs"]), self.b_run)

    def import_xml(self, f=None):
        if self._busy():
            return
        if not f:
            f, _ = QFileDialog.getOpenFileName(self, "Import a synced timeline (Syncaila / Premiere / DaVinci)", "", "XML (*.xml)")
        if f:
            self._start(MCWorker("xml", None, todo=f), self.b_run)

    def run_all(self):
        """Sync, then Auto Edit as soon as the sync ends: one press, nothing to wait for in between."""
        if self._busy():
            if self.p is self._job_p and self._chain is self._job_p:
                self._chain = None
                self.worker.cancel()
            return
        if not self.p["files"]:
            return
        self._chain = self.p
        self._awake.on()
        self._start(MCWorker("sync", list(self.p["files"]), jobs=self.store.app["jobs"]), self.b_all)

    def run_auto(self):
        if self._busy():
            if self.p is self._job_p:
                self.worker.cancel()
            return
        if self.p.get("sync"):
            self._auto_for(self.p)

    def _auto_for(self, p):
        s = p.get("sync")
        todo = [x for c in p["cams"] if c["role"] != "Audio" and not c.get("approx") and not c.get("check") for x in c["clips"]]
        self._start(MCWorker("analyze", None, self.store.load_blob(p["id"]), todo, self.store.app["jobs"],
                             masters=s["masters"]), self.b_auto, p,
                    keep_clock=self._chain is p)

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
        self._chain = None
        self._finish()
        if self.p is self._job_p:
            self.status.setText("Stopped: " + msg)
        if msg != "Cancelled":
            notify(f"{self._job_p['name']}: " + i18n.T(msg), error=True)

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
            notify(f"XML imported: {len(r['results'])} clips on {len(r['cams'])} cameras", took=("mc", p["id"]))
            if r.get("missing"):
                notify(f"{len(r['missing'])} file(s) from the XML were not found", error=True)
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
            if self._chain is p:              # Sync + Auto Edit: the auto edit starts right away
                self.job_status, self.job_progress = "Done", 1.0
                self.store.save()
                if self.worker:
                    self.worker.wait(5000)
                notify(f"Sync finished: {ok} of {len(r['results'])} clips synced", took=("mc", p["id"]))
                if here:
                    self.refresh_files()
                    self.recompute()
                if any(c["role"] != "Audio" and not c.get("approx") and not c.get("check") for c in p["cams"]):
                    self._auto_for(p)
                    return
                self._chain = None
            msg = ((r.get("report") or "") + "\n" +f"Sync finished: {ok} of {len(r['results'])} clips synced. You can export now, "
                                f"or press Auto Edit to let the program build the edit (this analyses the video and takes longer).")
            if here:
                self.status.setText(msg)
            notify(f"Sync finished: {ok} of {len(r['results'])} clips synced", took=("mc", p["id"]))
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
            if p.get("mc_timeline"):           # a new automatic edit: the editor starts from it
                p.update(mc_timeline=None, mc_hidden=[], mc_muted=[])
            notify(f"Auto edit ready: {p['name']}", took=("mc", p["id"]))
            self._chain = None
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
        st = {**self.p["dir"], **self.store.app.get("music", {}), "zones": self.p.get("zones", [])}
        if has_an:
            key = (self.p["id"], len(s["clips"]))
            if getattr(self, "_fps_key", None) != key:
                self._fps_key, self._fps = key, director.seq_fps(self.p["cams"], s["clips"], self.an)
            st["fps"] = self._fps
        self.edits = director.build(self.p["cams"], s["clips"], self.an, s["masters"], st) if has_an else []
        self.refresh_all()

    # ---- views
    def refresh_all(self):
        s = self.p.get("sync")
        self.b_exp.setEnabled(bool(s))
        self.b_edit.setEnabled(bool(s))
        self.b_edit.setText("Continue editing" if self.p.get("mc_timeline") else "Edit")
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
            mixed = (f"Mixed frame rates ({', '.join(f'{r:g}' for r in rates)} fps): handled in the export "
                     f"(the sequence is 25 fps).  ") if len(rates) > 1 else ""
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
            self.cam_t.setCellWidget(ci, 5, self._track_combo(ci))
        self.cam_t.resizeColumnToContents(1)
        for r_ in range(self.cam_t.rowCount()):
            self.cam_t.setRowHeight(r_, 34)
        self.cam_t.blockSignals(False)

    def set_role(self, cam, role):
        cam.update(role=role, user=True)
        self.store.save()
        self.recompute()

    def _track_combo(self, ci):
        """Video track of this camera in the export: Auto = static on V1, main camera on top (director.video_order)."""
        cams = self.p["cams"]
        cam = cams[ci]
        cb = QComboBox()
        if cam["role"] == "Audio":
            cb.addItem("–")
            cb.setEnabled(False)
            return cb
        s = self.p.get("sync")
        foot = {i: sum(s["clips"][x]["dur"] for x in c["clips"] if x in s["clips"]) for i, c in enumerate(cams)} if s else {}
        order = director.video_order(cams, foot)
        n = len(order)
        cb.addItem(i18n.T("V{} · auto").format(order.index(ci) + 1 if ci in order else 1))
        cb.addItems([f"V{k}" for k in range(1, n + 1)])
        t = cam.get("track")
        cb.setCurrentIndex(t if isinstance(t, int) and 1 <= t <= n else 0)
        cb.setMinimumWidth(96)
        cb.setStyleSheet("QComboBox{padding:2px 8px;border-radius:3px}")
        cb.setToolTip("The video track of this camera in Export XML. Auto: the static camera on V1, the main camera on top.")
        cb.currentIndexChanged.connect(lambda k, c=cam: self.set_track(c, k))
        return cb

    def set_track(self, cam, k):
        if k:
            for c in self.p["cams"]:                    # one camera per track: the one that had it goes back to Auto
                if c is not cam and c.get("track") == k:
                    c.pop("track", None)
            cam["track"] = k
        else:
            cam.pop("track", None)
        self.store.save()
        QTimer.singleShot(0, self.refresh_cams)

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
                     i18n.T(CONF_NAME[res["conf"]]) + (" (manual)" if res.get("manual") else "") + (f" · {i18n.T(res['error'])}" if res.get("error") else ""),
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

    def _mc_timeline(self):
        """The multicam as the editor's timeline: every camera's cuts on its own video track (static V1, main camera on
        top, his own choices), the recorder files and every camera's sound whole underneath."""
        s, cams = self.p["sync"], self.p["cams"]
        starts = sync.master_starts(s["masters"])
        res = s["clips"]
        foot = {i: sum(res[x]["dur"] for x in c["clips"] if x in res) for i, c in enumerate(cams)}
        order = director.video_order(cams, foot)
        track = {ci: k + 1 for k, ci in enumerate(order)}
        placed = [(ci, p, starts[res[p]["master"]] + res[p]["offset"]) for ci, c in enumerate(cams)
                  if c.get("role") != "Audio" for p in c["clips"]
                  if p in res and res[p]["conf"] != "fail" and res[p]["master"] < len(starts)]
        T0 = min([0.0] + [g for _c, _p, g in placed])
        lab = lambda ci: sync.CAM_LABELS[ci % len(sync.CAM_LABELS)]
        items = []
        cut = any(e and e.get("pieces") for e in (self.edits or []))
        if cut:
            for e in self.edits or []:
                if not e:
                    continue
                g0 = starts[e["master"]]
                for ci, p, a, b, s0 in e["pieces"]:
                    if ci in track and b - a > 0.02:
                        items.append(dict(path=p, v=track[ci], ak=None, start=g0 + s0 - T0, src=a, dur=b - a,
                                          label=lab(ci), on=True, aon=True))
        for ci, p, g in placed:
            c = cams[ci]
            whole = not cut or c.get("approx") or c.get("check")
            if whole and ci in track:
                items.append(dict(path=p, v=track[ci], ak=["cam", ci], start=g - T0, src=0.0, dur=res[p]["dur"],
                                  label=lab(ci), on=True, aon=True))
            elif cut:
                items.append(dict(path=p, v=None, ak=["cam", ci], start=g - T0, src=0.0, dur=res[p]["dur"],
                                  label=lab(ci), on=True, aon=True))
        for mi, m in enumerate(s["masters"]):
            if m.get("path"):
                items.append(dict(path=m["path"], v=None, ak=["rec", 0], start=starts[mi] - T0, src=0.0,
                                  dur=m["duration"], label="", on=True, aon=True))
        return dict(items=items, markers=[])

    def _mc_infos(self, tl):
        """projectsetup.probe of every file of the timeline (cached in the project blob by size + date)."""
        blob = self.store.load_blob(self.p["id"])
        cache = blob.setdefault("probe", {})
        out, changed = {}, False
        for f in sorted({it["path"] for it in tl["items"]}):
            k = f"{f}|{longfilm2.stamp(f)}"
            if k not in cache:
                try:
                    cache[k] = projectsetup.probe(f)
                except Exception:
                    cache[k] = dict(video=False, dur=0.0, fps=25.0, w=1920, h=1080, ach=0, arate=48000, ctime=None, tod=None)
                changed = True
            out[f] = cache[k]
        if changed:
            self.store.save_blob(self.p["id"], blob)
        return out

    def edit_film(self):
        if not self.p.get("sync"):
            return
        import editor
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tl = self.p.get("mc_timeline") or self._mc_timeline()
            infos = self._mc_infos(tl)
        finally:
            QApplication.restoreOverrideCursor()
        names = {("rec", 0): i18n.T("Recorder")}
        for ci, c in enumerate(self.p["cams"]):
            names[("cam", ci)] = c["name"]
        lane = lambda ak: names.get(tuple(ak) if ak else None, str(ak))

        def keep(dlg):
            self.p.update(mc_timeline=dlg.timeline(), mc_hidden=sorted(dlg.m.hidden), mc_muted=dlg.m.muted)
            self.store.save()
            self.b_edit.setText("Continue editing")
            notify(i18n.T("Your changes are saved."))
        dlg = editor.Editor(self, tl, infos, PR_LABEL, lane, str(self.store.dir / "thumbs"),
                            self.p.get("mc_hidden", []), self.p.get("mc_muted", []), on_save=keep,
                            keys=self.store.app.get("editor_keys"),
                            on_keys=lambda k: (self.store.app.__setitem__("editor_keys", k), self.store.save_app()))
        dlg.setWindowTitle(i18n.T("Edit the multicam"))
        dlg.exec()
        dlg.deleteLater()
        if dlg.reset:
            self.p.update(mc_timeline=None, mc_hidden=[], mc_muted=[])
            self.store.save()
            notify(i18n.T("The automatic edit is back."))
        self._sync_buttons()

    def export(self, target="premiere"):
        s = self.p.get("sync")
        if not s:
            return
        first = next((m["path"] for m in s["masters"] if m.get("path")), None) or self.p["files"][0]["path"]
        d = resolve.name_for(str(Path(first).parent / f"{self.p['name']}.xml"), target)
        out, _ = QFileDialog.getSaveFileName(self, "Save XML", d, "XML (*.xml)")
        if not out:
            return
        if self.p.get("mc_timeline"):          # his version from the editor
            try:
                tl = self.p["mc_timeline"]
                infos = self._mc_infos(tl)
                vid = [infos[it["path"]] for it in tl["items"] if it.get("v") and infos.get(it["path"], {}).get("w")]
                size = (vid[0]["w"], vid[0]["h"]) if vid else None     # the camera's size, like the multicam export
                longfilm2.export_timeline(tl, infos, out, self.p["name"], hidden=self.p.get("mc_hidden", []),
                                          muted=self.p.get("mc_muted", []), size=size)
                for_target(out, target)
                self.status.setText(i18n.T("Saved your edited version to {}.").format(out))
                notify(f"XML saved: {Path(out).name}")
            except Exception as e:
                logging.exception("multicam editor export failed")
                notify(f"Export failed: {e}", error=True)
            return
        try:
            r = director.export_xml(s["masters"], self.p["cams"], s["clips"], self.an, self.edits, out, self.p["name"])
            for_target(out, target)
            self.status.setText(f"Saved one sequence ({r['video_tracks']} video, {r['audio_tracks']} audio tracks"
                                f"{', each camera track holds only its cuts' if r['edit'] else ', full clips (no auto edit yet)'}) to {out}. "
                                f"Premiere: File > Import · DaVinci Resolve: File > Import > Timeline.")
            notify(f"XML saved: {Path(out).name}")
        except Exception as e:
            logging.exception("multicam export failed")
            self.status.setText(f"Export failed: {e}")
            notify(f"Export failed: {e}", error=True)


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
        right.addSpacing(10)
        right.addWidget(lbl("Premiere bridge"))
        right.addWidget(lbl("A small extension inside Premiere Pro (installed by the app, it starts by itself with Premiere): "
                            "Export XML → Premiere can import the film into the open project and put an adjustment layer "
                            "with the crop on top, like WarpAutomation. Restart Premiere once after it is installed.",
                            "muted", True))
        brr = QHBoxLayout()
        self.l_bridge = lbl("", "muted")
        brr.addWidget(self.l_bridge, 1)
        brr.addWidget(btn("Install again", slot=self.reinstall_bridge))
        right.addLayout(brr)
        self._show_bridge()
        right.addSpacing(18)
        right.addWidget(lbl("Language", "h2"))
        lr = QHBoxLayout()
        cur = store.app.get("ui_lang", "en")
        self.b_en = btn("English", "seg", lambda: self._set_lang("en"))
        self.b_ro = btn("Română", "seg", lambda: self._set_lang("ro"))
        for b_, on in ((self.b_en, cur == "en"), (self.b_ro, cur == "ro")):
            b_.setProperty("active", on)
            lr.addWidget(b_)
        lr.addStretch()
        right.addLayout(lr)
        self.lang_note = lbl("The whole app (and the Info pages) in this language. It applies when the app starts again.",
                             "muted", True)
        right.addWidget(self.lang_note)
        right.addSpacing(18)
        right.addWidget(lbl("Updates and problems", "h2"))
        ur = QHBoxLayout()
        ur.addWidget(btn("Check for updates", slot=lambda: self.check_updates(False)))
        self.b_dl = btn("Download and install", "primary", self.open_release)
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
    def _set_lang(self, lang):
        self.store.app["ui_lang"] = lang
        self.store.app["lang"] = lang                 # the Info pages follow
        self.store.save_app()
        for b_, on in ((self.b_en, lang == "en"), (self.b_ro, lang == "ro")):
            b_.setProperty("active", on)
            repolish(b_)
        self.lang_note.setText("Restart MoneyMakingMachine to see it in English." if lang == "en" else
                               "Repornește MoneyMakingMachine ca s-o vezi în română.")
        notify("Restart MoneyMakingMachine to see it in English." if lang == "en" else
               "Repornește MoneyMakingMachine ca s-o vezi în română.")

    def check_updates(self, silent=True):
        self._silent = silent
        self.upd.setText("Checking…")
        self._uw = _UpdWorker("check")
        self._uw.done.connect(lambda r: self._update_result(r, silent))
        self._uw.failed.connect(self._update_failed)
        self._uw.start()

    def _update_failed(self, m):
        logging.warning("update check failed: %s", m)
        if not getattr(self, "_silent", True):
            notify("Could not check for updates", error=True)
        if "no version" in m:
            why = "no version has been published yet"
        elif "403" in m or "429" in m:
            why = "the update server refused the check for now (too many checks), try again later"
        elif "certificate" in m:
            why = "the secure connection could not be checked (certificates), send the error report to Claude"
        elif "no connection" in m:
            why = "no internet connection"
        else:
            why = f"the update server did not answer ({m[:40]})"
        self.upd.setText(i18n.T("You have {}. Could not check for updates: {}.").format(VER, i18n.T(why)))

    def _update_result(self, r, silent):
        self._release = r
        if r and _ver(r["tag"]) > _ver(VER):
            self.upd.setText(f"New version available: {r['tag']} (you have {VER}).")
            self.b_dl.show()
            self.b_dl.setEnabled(True)
            logging.info("update available: %s", r["tag"])
            self.update_found.emit(r["tag"])
        else:
            self.upd.setText(f"You have the latest version ({VER}).")
            if not silent:
                notify(f"You have the latest version ({VER}).")
            self.b_dl.hide()

    def open_release(self):
        """Downloads the new version for this computer inside the app and opens it (no browser, no address)."""
        r = getattr(self, "_release", None)
        if not r or (getattr(self, "_dw", None) and self._dw.isRunning()):
            return
        self.b_dl.setEnabled(False)
        self.upd.setText(i18n.T("Downloading {}…").format(r["tag"]))
        self._dw = _UpdWorker("download", r)
        self._dw.progress.connect(lambda got, tot: self.upd.setText(
            i18n.T("Downloading {}: {} %").format(r["tag"], int(got * 100 / tot)) if tot else
            i18n.T("Downloading {}: {} MB").format(r["tag"], got >> 20)))
        self._dw.done.connect(self._downloaded)
        self._dw.failed.connect(self._download_failed)
        self._dw.start()

    def _downloaded(self, path):
        self.b_dl.setEnabled(True)
        try:
            updater.open_installer(path)
        except Exception:
            logging.exception("open installer")
        if sys.platform == "darwin":
            msg = i18n.T("Downloaded to Downloads and opened: drag MoneyMakingMachine into Applications (Replace), then "
                         "close this app and open it again.")
        else:
            msg = i18n.T("Downloaded to Downloads: unzip it and replace the old MoneyMakingMachine folder, then open it "
                         "again.")
        self.upd.setText(msg)
        notify(msg, ms=12000)
        logging.info("update downloaded: %s", path)

    def _download_failed(self, m):
        self.b_dl.setEnabled(True)
        logging.warning("update download failed: %s", m)
        self.upd.setText(i18n.T("The download failed ({}). Try again.").format(i18n.T(m[:60])))
        notify(i18n.T("The download failed ({}). Try again.").format(i18n.T(m[:60])), error=True)

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
        safe = {k: ("(set, hidden)" if k == "claude_key" and v else v) for k, v in self.store.app.items()}   # never the key
        info = (f"{APP} {VER}\n{platform.platform()}\nPython {platform.python_version()}\n"
                f"CPU cores: {os.cpu_count()}\nSettings: {json.dumps(safe, default=str)}\n\n")
        Path(out).write_text(info + text, encoding="utf-8")
        self.upd.setText(f"Report saved: {out}")
        notify(f"Report saved: {Path(out).name}")

    def set_jobs(self, x):
        self.store.app["jobs"] = x
        self.store.save_app()

    def set_hw(self, v):
        self.store.app["hwaccel"] = v
        self.store.save_app()

    def _show_bridge(self):
        v = bridge.installed_version()
        if sys.platform != "darwin":
            t = i18n.T("Mac only for now.")
        elif not v:
            t = i18n.T("Not installed.")
        elif bridge.alive(10):
            t = i18n.T("Installed ({}), running in Premiere.").format(v)
        else:
            t = i18n.T("Installed ({}). Premiere is closed or was not restarted yet.").format(v)
        self.l_bridge.setText(t)

    def reinstall_bridge(self):
        try:
            bridge.install(force=True)
            notify(i18n.T("Premiere bridge installed: restart Premiere Pro."))
        except Exception as e:
            logging.exception("bridge install failed")
            notify(i18n.T("Could not install the Premiere bridge: {}").format(str(e)), error=True)
        self._show_bridge()

    def showEvent(self, e):
        self.refresh()
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        try:
            self.timer.stop()
        except RuntimeError:                    # the app is closing: the timer is already gone
            pass
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
        def rss(p):
            try:
                return p.memory_info().rss
            except Exception:                 # gone, zombie or not allowed: counts as 0
                return 0
        try:
            vm = psutil.virtual_memory()
            me = psutil.Process()
            try:
                kids = me.children(recursive=True)
            except Exception:
                kids = []
            mine = rss(me) + sum(rss(c) for c in kids)
        except Exception:
            logging.warning("memory panel: could not read memory", exc_info=True)
            return
        self.cards["total"].setText(gb(vm.total))
        self.cards["others"].setText(gb(max(0, vm.total - vm.available - mine)))
        self.cards["free"].setText(gb(vm.available))
        self.cards["me"].setText(gb(mine))
        procs = {}
        try:
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    n = p.info["name"] or "?"
                    procs[n] = procs.get(n, 0) + p.info["memory_info"].rss
                except Exception:
                    pass
        except Exception:
            logging.warning("memory panel: could not list the apps", exc_info=True)
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
            p.drawText(r_, Qt.AlignVCenter, p.fontMetrics().elidedText(i18n.T(teaser.PARTS[i]), Qt.ElideRight, int(r_.width())))
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
        v.addWidget(lbl("Up to 25 selections per colour, 3 frames from each (the sharpest of every third, the flat log look "
                        "corrected), are shown to SigLIP 2, a free image model by Google that runs on this Mac (nothing is "
                        "uploaded). It guesses the kind of shot; green = same as your label, red = different, grey = the "
                        "frames show nothing clear (floor, blur, motion). The first time the model is downloaded once "
                        "(a few GB) and the test takes some minutes.", "muted", True))
        self.pp = ProgressPanel()
        v.addWidget(self.pp)
        self.table = QLabel("")
        self.table.setTextFormat(Qt.RichText)
        self.table.setWordWrap(True)
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
        self.res, self._stop, self.job, self._awake = None, False, None, None
        self.pieces, self.base = pieces, base
        ch = QHBoxLayout()
        self.b_quick = btn("Quick test (25 selections per colour)", slot=lambda: self._start(25))
        self.b_all = btn(f"Every selection ({len(pieces)}): slow, leave it overnight", "primary", lambda: self._start(None))
        ch.addWidget(self.b_quick)
        ch.addWidget(self.b_all)
        ch.addStretch()
        v.insertLayout(2, ch)
        self.choice = [self.b_quick, self.b_all]

    def _start(self, per_cat):
        for b in self.choice:
            b.setEnabled(False)
        self.pp.start("Starting…")
        self.pp.allow_cancel(self._cancel)
        if per_cat is None and sys.platform == "darwin":
            try:                                             # keep the Mac awake until the test ends
                self._awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            except Exception:
                self._awake = None
        self.job = _Runner(lambda progress=None: ai.run_test(self.pieces, self.base, per_cat, progress, lambda: self._stop))
        self.job.progress.connect(self.pp.set)
        self.job.done.connect(self._done)
        self.job.failed.connect(self._failed)
        self.job.finished.connect(self._sleep_again)
        self.job.start()

    def _sleep_again(self):
        if self._awake is not None:
            try:
                self._awake.terminate()
                self._awake.wait(timeout=3)           # reaped: no zombie process left behind
            except Exception:
                pass
            self._awake = None

    def _cancel(self):
        self._stop = True

    def _failed(self, m):
        self.pp.hide()
        logging.error("AI test failed: %s", m)
        hint = (" The first run needs internet to download the model." if "urlopen" in m or "resolve" in m.lower()
                or "HTTP" in m else "")
        m = i18n.T(m)
        if m != i18n.T("Cancelled"):
            notify(m, error=True)
        self.table.setText(f'<span style="color:{C["POOR"]}">The AI test stopped: {m}.{hint} '
                           f'Settings &gt; Save error report and send it to Claude.</span>')

    def _done(self, res):
        self.pp.hide()
        self.res = res
        acc = res["acc"]
        tr, tt = sum(a for a, _ in acc.values()), sum(b for _, b in acc.values())
        of_ = i18n.T("of")
        unc = res.get("unclear", {})
        rows = "".join(f'<tr><td><span style="color:{teaser.CAT_COLOR[c]}">●</span> {i18n.T(teaser.CAT_NAME[c])}</td>'
                       f'<td align="right">{r} {of_} {t}</td><td align="right"><b>{(100 * r // t) if t else 0}%</b></td>'
                       f'<td align="right" style="color:{C["MUTED"]}">{unc.get(c, 0) or ""}</td></tr>'
                       for c, (r, t) in acc.items())
        self.table.setText(f'<table cellspacing="10"><tr><td><b>{i18n.T("Your colour")}</b></td><td><b>{i18n.T("AI agrees")}</b></td>'
                           f'<td></td><td><b>{i18n.T("Unclear")}</b></td></tr>{rows}<tr><td><b>{i18n.T("All")}</b></td>'
                           f'<td align="right">{tr} {of_} {tt}</td><td align="right"><b>{(100 * tr // tt) if tt else 0}%</b></td>'
                           f'<td align="right" style="color:{C["MUTED"]}">{sum(unc.values()) or ""}</td></tr></table>')
        if res.get("missing"):
            self.table.setText(self.table.text() + f'<br><span style="color:{C["FAIR"]}">' +
                               i18n.T("{} clips were not found on this computer and were left out of the test.").format(res["missing"])
                               + '</span>')
        logging.info("AI test: %s", {k: f"{a}/{b}" for k, (a, b) in acc.items()})
        notify(f"AI test finished: {(100 * tr // tt) if tt else 0}% agrees with your labels")
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
            unclear = g == "unclear"
            edge = C["MUTED"] if unclear else (C["GOOD"] if ok else C["POOR"])
            box.setStyleSheet(f"QFrame{{border:2px solid {edge};border-radius:6px;background:#202020}}")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(4, 4, 4, 4)
            pic = QLabel()
            qi = QImage(img.tobytes(), img.shape[1], img.shape[0], img.shape[1] * 3, QImage.Format_RGB888).copy()
            pic.setPixmap(QPixmap.fromImage(qi).scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            pic.setStyleSheet("border:none")
            bv.addWidget(pic)
            gname = i18n.T("Unclear") if unclear else i18n.T(teaser.CAT_NAME[g])
            cap = QLabel(f'<span style="color:{teaser.CAT_COLOR[his]}">{i18n.T("You")}: {i18n.T(teaser.CAT_NAME[his])}</span><br>'
                         f'<span style="color:{edge}">AI: {gname}</span>'
                         f'<span style="color:{C["MUTED"]}"> · {int(conf * 100)}%</span>')
            cap.setStyleSheet("border:none;font-size:11px")
            bv.addWidget(cap)
            name = QLabel(Path(p["path"]).name)
            name.setStyleSheet(f"border:none;font-size:10px;color:{C['MUTED']}")
            bv.addWidget(name)
            self.g.addWidget(box, n // 6, n % 6)

    def closeEvent(self, e):
        self._stop = True
        if self.job is not None and self.job.isRunning():
            self.job.wait(10000)
        self._sleep_again()
        super().closeEvent(e)


# ---------------------------------------------------------------- Auto | Blueprint (Teaser Studio and Long Film)

class BlueprintBox(QWidget):
    """Auto (the app builds it) or Blueprint (one of his finished films as the template): one or the other. kind is
    "short" (Teaser Studio: his shortmovies) or "long" (Long Film: his long films)."""
    changed = Signal()

    def __init__(self, store, kind, auto_text):
        super().__init__()
        self.store, self.kind, self.p = store, kind, None
        self.setStyleSheet("background:transparent")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(lbl(i18n.T(auto_text) + " " + i18n.T("A blueprint is one of your finished films: its cuts, music, sound "
                                                         "effects and pacing stay, and every cut is refilled with a shot of "
                                                         "the same colour from this wedding. Both need your colours: the "
                                                         "film's clips and this wedding's selects (in any order)."), "muted", True))
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.b_auto = btn("Auto", "seg", lambda: self.set_mode("auto"))
        self.b_bp = btn("Blueprint", "seg", lambda: self.set_mode("blueprint"))
        seg.addWidget(self.b_auto)
        seg.addWidget(self.b_bp)
        seg.addStretch()
        v.addLayout(seg)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._picked)
        v.addWidget(self.combo)
        br = QHBoxLayout()
        self.b_add = btn("+  Add a blueprint", slot=self.add)
        self.b_del = btn("Delete", "link", self.delete)
        br.addWidget(self.b_add)
        br.addWidget(self.b_del)
        br.addStretch()
        v.addLayout(br)
        self.info = lbl("", "muted", True)
        v.addWidget(self.info)

    def _all(self):
        return [b for b in self.store.app.setdefault("blueprints", []) if b.get("kind", "short") == self.kind]

    def load(self, project):
        self.p = project
        self.combo.blockSignals(True)
        self.combo.clear()
        for st in blueprint.STYLES:
            for b in self._all():
                if b["style"] == st:
                    self.combo.addItem(f'{i18n.T(st.capitalize())} · {b["name"]}', b["id"])
        ix = self.combo.findData(project.get("blueprint"))
        self.combo.setCurrentIndex(max(0, ix))
        self.combo.blockSignals(False)
        self._show()

    def mode(self):
        if not self.p:
            return "auto"
        return self.p.get("mode") or ("blueprint" if self.p.get("blueprint") else "auto")

    def current(self):
        """The blueprint in use, or None in Auto mode."""
        if self.mode() != "blueprint":
            return None
        bid = self.combo.currentData()
        return next((b for b in self._all() if b["id"] == bid), None)

    def set_mode(self, m):
        if self.p is None:
            return
        self.p["mode"] = m
        self.store.save_app()
        self._show()
        self.changed.emit()

    def _picked(self, _):
        if self.p is not None:
            self.p["blueprint"] = self.combo.currentData()
            self.store.save_app()
        self._show()
        self.changed.emit()

    def _show(self):
        on = self.mode() == "blueprint"
        for b_, act in ((self.b_auto, not on), (self.b_bp, on)):
            b_.setProperty("active", act)
            repolish(b_)
        self.combo.setEnabled(on and self.combo.count() > 0)          # Auto on: the blueprint part is switched off
        self.b_add.setEnabled(on)
        self.b_del.setEnabled(on and self.combo.count() > 0)
        b = self.current()
        if on and not self._all():
            self.info.setText(i18n.T("No blueprint yet: press + Add a blueprint and pick one of your finished films (XML)."))
        elif b:
            s = blueprint.summary(b)
            need = ", ".join(f"{i18n.T(teaser.CAT_NAME.get(k, k)).lower()} {v / 60:.1f} min" if v >= 90 else
                             f"{i18n.T(teaser.CAT_NAME.get(k, k)).lower()} {v:.0f} s"
                             for k, v in sorted(s["need"].items(), key=lambda kv: -kv[1]) if k != "interview")
            extra = (" · " + i18n.T("{} interview places").format(s["interviews"])) if s["interviews"] else ""
            self.info.setText(i18n.T("{} cuts · {}:{} · needs: {}").format(s["cuts"], int(s["duration"] // 60),
                                                                           f"{int(s['duration'] % 60):02d}", need) + extra +
                              "<br>" + i18n.T("From your film {}, music and sound effects included ({} sounds).").format(b["source"], s["songs"]))
        else:
            self.info.setText("")

    def add(self):
        from PySide6.QtWidgets import QInputDialog
        f, _ = QFileDialog.getOpenFileName(self, "A finished film of yours (XML from Premiere)", "", "XML (*.xml)")
        if not f:
            return
        name, ok = QInputDialog.getText(self, "New blueprint", "Name:", text=Path(f).stem)
        if not ok or not name.strip():
            return
        styles = [i18n.T("Modern"), i18n.T("Traditional")]
        st, ok = QInputDialog.getItem(self, "New blueprint", "Style:", styles, 0, False)
        if not ok:
            return
        try:
            b = blueprint.extract(f, name.strip(), blueprint.STYLES[styles.index(st)], self.kind)
        except Exception as e:
            logging.exception("blueprint failed")
            notify(f"Could not read the film: {e}", error=True)
            return
        self.store.app.setdefault("blueprints", []).append(b)
        if self.p is not None:
            self.p["blueprint"] = b["id"]
        self.store.save_app()
        self.load(self.p or {})
        self.changed.emit()
        notify(f"Blueprint added: {b['name']}")
        logging.info("blueprint (%s) added from %s: %d cuts", self.kind, f, len(b["slots"]))

    def delete(self):
        from PySide6.QtWidgets import QMessageBox
        b = self.current()
        if not b:
            return
        if QMessageBox.question(self, "Delete blueprint", f"Delete the blueprint \"{b['name']}\"? Your film is not touched.") != QMessageBox.Yes:
            return
        self.store.app["blueprints"].remove(b)
        self.store.save_app()
        self.load(self.p or {})
        self.changed.emit()


class TeaserPage(QWidget):
    notify = Signal(str)
    back = Signal()

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
        top.addWidget(btn("←  Projects", "link", lambda: self.back.emit()))
        self.pname = lbl("", "h2")
        top.addWidget(self.pname)
        top.addWidget(lbl("·  Teaser Studio", "muted"))
        badge = QLabel("NEW")
        badge.setStyleSheet(f"background:{C['POOR']};color:white;font-size:10px;font-weight:800;border-radius:9px;padding:2px 8px")
        top.addWidget(badge)
        top.addStretch()
        self.b_shuffle = btn("Shuffle shots", slot=self.shuffle)
        self.b_gen = btn("Generate", "primary", self.generate)
        self.b_exp = ExportPair(self.export)
        for b in (self.b_shuffle, self.b_exp, self.b_gen):
            top.addWidget(b)
        sv.addLayout(top)
        sv.addWidget(lbl("Builds your shortmovie structure (teaser with drop → getting ready → church → party) from your colour "
                         "labels, cut on the beat of your music. Testimonials and vows: add them in Premiere afterwards "
                         "(the export has a marker for every part).", "muted", True))
        sv.addSpacing(8)
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
        self.pr_box = QWidget()                     # the old project row: projects are cards now (hidden)
        self.pr_box.setLayout(pr)
        self.pr_box.hide()
        sv.addWidget(self.pr_box)
        rn = QHBoxLayout()
        rn.addWidget(btn("Rename", "link", self.rename_project))
        rn.addStretch()
        sv.addLayout(rn)
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
            l.setContentsMargins(16, 14, 16, 16)
            l.setSpacing(10)
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
        l1.addWidget(lbl("Export from Premiere an XML of the sequence with your selects. Only the COLOURS matter: Rose bride, "
                         "Blue groom, Purple couple, Brown church, Yellow or Caribbean venue, Iris party, Violet drone "
                         "(Teal getting-ready location, Mango vornic). Clips without a colour are not used. The order and the "
                         "tracks do not matter: the order of the day comes from the recording time.", "muted", True))
        l1.addWidget(btn("Import labelled XML", slot=self.pick_footage))
        self.foot_lbl = QLabel("")
        self.foot_lbl.setWordWrap(True)
        l1.addWidget(self.foot_lbl)
        lb = card(2, "Auto or Blueprint")
        self.bpbox = BlueprintBox(self.store, "short", "Auto cuts on the beat of your music (as before).")
        self.bpbox.changed.connect(self._mode_changed)
        lb.addWidget(self.bpbox)
        l2 = card(3, "Music")
        self.music_card = l2
        l2.addWidget(lbl("Your songs already joined: one audio file, or the XML of your music edit.", "muted", True))
        r = QHBoxLayout()
        r.addWidget(btn("Audio file", slot=lambda: self.pick_music(False)))
        r.addWidget(btn("Music XML", slot=lambda: self.pick_music(True)))
        l2.addLayout(r)
        self.mus_lbl = lbl("", "muted", True)
        l2.addWidget(self.mus_lbl)
        l3 = card(4, "Parts")
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
        l4b = card(5, "Bride and groom (optional)")
        l4b.addWidget(lbl("A good photo of each (from the wedding day, face well visible): the teaser and the couple shots "
                          "prefer the selections where they are seen. Local face recognition, nothing is uploaded.", "muted", True))
        fr = QHBoxLayout()
        fr.addWidget(btn("Bride's photo", slot=lambda: self._pick_face("bride")))
        fr.addWidget(btn("Groom's photo", slot=lambda: self._pick_face("groom")))
        l4b.addLayout(fr)
        self.face_lbl = lbl("", "muted", True)
        l4b.addWidget(self.face_lbl)
        self.b_faces = btn("Find them in the selections", "primary", self.find_faces)
        l4b.addWidget(self.b_faces)
        l5 = card(6, "AI test (experimental)")
        l5.addWidget(lbl("Checks if a free AI model, running on this Mac, recognises your shots like your colour labels. "
                         "It does not change your teaser.", "muted", True))
        self.b_ai = btn("Test the AI on my labelled clips", slot=self.ai_test)
        l5.addWidget(self.b_ai)
        left.addStretch()
        lscroll.setWidget(lw)
        body.addWidget(lscroll)
        right = QVBoxLayout()
        self.music_area = [lbl("MUSIC", "section"), MusicView(),
                           lbl("The small ticks under the music show where the cuts fall. The pink line is the drop.", "muted")]
        self.mv = self.music_area[1]
        for w_ in self.music_area:
            right.addWidget(w_)
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
        self.chrono = True                       # the story always follows the day (Shuffle still gives other shots)
        self.stack.setCurrentIndex(0)
        self.auto_bounds = None
        self._buttons()

    def _drop(self, paths):
        """Finder drop: an XML with your colour labels = the footage (selects); an XML without them = your music edit;
        an audio file = the music."""
        for f in paths:
            ext = Path(f).suffix.lower()
            if ext == ".xml":
                if _labelled(f):
                    self._load_footage(f)
                else:
                    self._load_music_file(f)
                return
            if ext in sync.AUDIO_EXT:
                self._load_music_file(f)
                return
        notify(i18n.T("Drop the XML of your selects or your music here."), error=True)

    def open_project(self):
        """Opened from its card."""
        self._fill_projects()
        self._clear()
        self.pname.setText(self._cur()["name"])
        self.restore()

    def restore(self):
        """Reload the footage XML, the music and your six moments from last time."""
        t = self._cur()
        self._face_ui()
        self.bpbox.load(t)
        self._mode_ui()
        foot, mus, b = t.get("footage"), t.get("music"), t.get("bounds")
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
        self.runner.failed.connect(lambda m: (self.pp.hide(), self.summary.setText("Error: " + m), notify(f"Error: {m}", error=True)))
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
        if not ps:
            ps.append(dict(id=uuid.uuid4().hex, name="My first teaser"))
            self.store.app["teaser_current"] = ps[0]["id"]
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
            self.pname.setText(p["name"])

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
        if hasattr(self, "face_lbl"):
            self.face_lbl.setText("")
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
        self._cur().update(kw, when=datetime.now().isoformat(timespec="seconds"))
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

    # ---- bride and groom by their face
    def _pick_face(self, who):
        f, _ = QFileDialog.getOpenFileName(self, "Photo of the bride" if who == "bride" else "Photo of the groom", "",
                                           "Images (*.jpg *.jpeg *.png *.JPG *.PNG)")
        if f:
            self._remember(**{f"{who}_photo": f})
            self._face_ui()

    def _face_key(self):
        t = self._cur()
        return "|".join(str(t.get(k) or "") for k in ("bride_photo", "groom_photo"))

    def _face_ui(self):
        t = self._cur()
        names = [f"{i18n.T('Bride')}: {Path(t['bride_photo']).name}" if t.get("bride_photo") else "",
                 f"{i18n.T('Groom')}: {Path(t['groom_photo']).name}" if t.get("groom_photo") else ""]
        txt = " · ".join(x for x in names if x) or i18n.T("No photos yet.")
        done = [p for p in self.pieces if p.get("who")]
        if done:
            nb = sum(1 for p in done if p["who"].get("bride", -1) >= teaser.FACE_SAME)
            ng = sum(1 for p in done if p["who"].get("groom", -1) >= teaser.FACE_SAME)
            txt += "<br>" + i18n.T("Found: the bride in {} selections, the groom in {}.").format(nb, ng)
        self.face_lbl.setText(txt)
        self.b_faces.setEnabled(bool(self.pieces) and bool(t.get("bride_photo") or t.get("groom_photo")) and not self._busy())

    def _apply_face_cache(self):
        """Faces looked for before (same photos, same selections): back at once, no new search."""
        try:
            data = json.loads((self.store.dir / "faces_cache.json").read_text("utf-8"))
        except Exception:
            return
        key = self._face_key()
        for p in self.pieces:
            w_ = data.get(f'{p.get("_k") or p["path"]}|{p["a"]:.2f}|{key}')
            if w_:
                p["who"] = w_

    def find_faces(self):
        t = self._cur()
        photos = {k: t.get(f"{k}_photo") for k in ("bride", "groom") if t.get(f"{k}_photo")}
        pieces = [p for p in self.pieces if p["cat"] in ("bride", "groom", "couple", "church", "party")]
        base, key = self.store.dir, self._face_key()

        def job(progress=None):
            import faces
            fm = faces.Faces(faces.ensure_models(base, progress))
            refs = {k: fm.person(v) for k, v in photos.items()}
            res = faces.find_people(pieces, refs, fm, progress=progress, cancel=lambda: self._stop,
                                    label="Looking for the bride and groom")
            return res

        def done(res):
            cf = self.store.dir / "faces_cache.json"
            try:
                data = json.loads(cf.read_text("utf-8"))
            except Exception:
                data = {}
            for p in pieces:
                r_ = res.get(id(p))
                if r_:
                    p["who"] = {k: round(v[0], 3) for k, v in r_.items()}
                    data[f'{p.get("_k") or p["path"]}|{p["a"]:.2f}|{key}'] = p["who"]
            cf.write_text(json.dumps(data, default=_jsonable), "utf-8")
            self._face_ui()
            notify("The bride and groom were looked for in every selection")
        self._stop = False
        self._run("Looking for the bride and groom…", job, (), done)

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
        save = lambda c: cache_file.write_text(json.dumps(c, default=_jsonable), "utf-8")
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
        self._apply_face_cache()
        self._face_ui()
        self._buttons()
        notify(f"Footage loaded: {len(self.pieces)} selections")

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
        notify(f"Music loaded: {Path(self._mus_path).name}")

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

    # ---- build / export
    def _buttons(self):
        ok = bool(self.pieces) and (self.music is not None or self._bp() is not None)
        self.b_gen.setEnabled(ok)
        self.b_shuffle.setEnabled(ok and self.edit is not None)
        self.b_exp.setEnabled(self.edit is not None)
        if not ok:
            need = [n for n, have in (("the labelled footage XML", bool(self.pieces)), ("the music", self.music is not None)) if not have]
            self.summary.setText("Add " + " and ".join(need) + " to generate.")
        elif self.edit is None:
            self.summary.setText("Ready: press Generate.")

    # ---- blueprints (one of his finished films as a template)
    def _bp(self):
        """The blueprint in use (None in Auto mode)."""
        return self.bpbox.current() if hasattr(self, "bpbox") else None

    def _mode_ui(self):
        b = self._bp()
        for w_ in self.music_area + [self.music_card.parentWidget()]:          # a blueprint brings its own music
            w_.setVisible(b is None)

    def _mode_changed(self):
        self.edit = None
        self._mode_ui()
        self._buttons()

    def _generate_blueprint(self, b):
        e = blueprint.build(self.pieces, b, seed=self.seed)
        self.edit = dict(shots=e["shots"], gaps=e["gaps"], blueprint=b["id"])
        self.strip.set(self.edit["shots"], b["duration"])
        holes = [k for *_, k in e["gaps"] if k != "interview"]
        inter = sum(1 for *_, k in e["gaps"] if k == "interview")
        txt = i18n.T("{} shots from the blueprint {}, no moment used twice.").format(len(e["shots"]), b["name"])
        if inter:
            txt += "<br>" + i18n.T("{} places for your interviews (marker Interview here).").format(inter)
        if holes:
            txt += (f'<br><span style="color:{C["FAIR"]}">' + i18n.T("{} cuts have no footage left of their colour (marker): label more clips.").format(len(holes)) + "</span>")
        self.summary.setText(txt)
        self.notify.emit(f"Shortmovie generated: {len(e['shots'])} shots")
        logging.info("blueprint %s generated: %d shots, %d holes", b["name"], len(e["shots"]), len(holes))
        self._buttons()

    def generate(self):
        b = self._bp()
        if b and self.pieces:
            return self._generate_blueprint(b)
        if not self.pieces or self.music is None:
            return
        self.edit = teaser.build(self.pieces, self.music, self.bounds, seed=self.seed, chronological=True)
        self.strip.set(self.edit["shots"], self.music["duration"])
        allbeats = [t0 for t0, _, _ in self.edit["shots"]]
        self.mv.set_parts([self.bounds[k] for k, _ in teaser.BOUNDS[1:]], self.bounds["drop"], allbeats)
        bpm = " · ".join(f"{i18n.T(k)} {v:.0f} BPM" for k, v in self.edit["bpm"].items() if v)
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

    def export(self, target="premiere"):
        if not self.edit:
            return
        start = resolve.name_for(str(Path(getattr(self, "_foot_path", "") or ".").parent / "Shortmovie (auto).xml"), target)
        out, _ = QFileDialog.getSaveFileName(self, "Save XML", start, "XML (*.xml)")
        if out:
            try:
                b = next((x for x in self.store.app.get("blueprints", []) if x["id"] == self.edit.get("blueprint")), None)
                n = (blueprint.export_xml(self.edit, b, out, Path(out).stem) if b else
                     teaser.export_xml(self.edit, self.music, out, Path(out).stem))
                for_target(out, target)
                if b:
                    gone = sorted({x["name"] for x in b["audio"] if not Path(x["path"]).exists()})
                    if gone:
                        notify(f"{len(gone)} sounds of the blueprint were not found on this computer, e.g. {gone[0]}", error=True)
                self.summary.setText(f"Saved {n} shots to {out}. Premiere: File > Import · DaVinci: File > Import > Timeline.")
                self.notify.emit(f"XML saved: {Path(out).name}")
            except Exception as e:
                logging.exception("teaser export failed")
                self.summary.setText(f"Export failed: {e}")
                notify(f"Export failed: {e}", error=True)


# ---------------------------------------------------------------- Long Film

# Premiere label colours (approximately as Premiere shows them)
PR_LABEL = {"Blue": "#3f63e0", "Rose": "#f08ccb", "Teal": "#1f9e96", "Iris": "#6d78d6", "Brown": "#9a6233",
            "Yellow": "#e3cf3e", "Purple": "#9b4fc2", "Violet": "#b29de6", "Caribbean": "#22b8a5", "Mango": "#f39c2c",
            "Forest": "#3d8b37", "Cerulean": "#2d9ad8", "Tan": "#c8a97e", "Sound": "#4a5a52",
            "Lavender": "#a99ad6", "Magenta": "#d6338a", "Green": "#4caf50"}
DV_LABEL = {"Orange": "#e8772e", "Apricot": "#f0a35e", "Yellow": "#e2c337", "Lime": "#9fcf3a", "Olive": "#6f8a2e",
            "Green": "#3c9b4a", "Teal": "#22928c", "Navy": "#2c3f87", "Blue": "#3b74d6", "Purple": "#8c4fc0",
            "Violet": "#b26ad6", "Pink": "#e27aa8", "Tan": "#c8a97e", "Beige": "#d9c9a6", "Brown": "#8c5a32",
            "Chocolate": "#5b3a22"}


def _swatch(hexc):
    pm = QPixmap(14, 14)
    pm.fill(QColor(hexc))
    return QIcon(pm)


class ColourCard(QWidget):
    """Clip colours of Long Film v2: the switch off = the default colours; on = his own colour for every moment, from
    the Premiere labels or the DaVinci Resolve clip colours. Used to read his labelled sequence and written on the
    exported clips (each program its own list)."""
    changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.c = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(lbl("Choose my own colours", "", True), 1)
        self.sw = Switch(False)
        self.sw.toggled.connect(self._on)
        top.addWidget(self.sw, 0, Qt.AlignTop)
        v.addLayout(top)
        v.addWidget(lbl("Off: the default colours (Blue groom, Rose bride, Teal first look, Forest vornic, Brown church, "
                        "Yellow venue, Purple couple, Violet drone, Iris party). On: pick a colour for every moment.",
                        "muted", True))
        prow = QHBoxLayout()
        self.b_pr = btn("Premiere Pro", slot=lambda: self._show("premiere"))
        self.b_dv = btn("DaVinci Resolve", slot=lambda: self._show("davinci"))
        for b in (self.b_pr, self.b_dv):
            b.setCheckable(True)
            prow.addWidget(b)
        prow.addStretch()
        v.addLayout(prow)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        self.combos = {}
        for r, m in enumerate(longfilm2.MOMENTS):
            g.addWidget(lbl(longfilm2.MOMENT_NAMES[m]), r, 0)
            cb = QComboBox()
            cb.currentIndexChanged.connect(lambda _i, m=m: self._pick(m))
            g.addWidget(cb, r, 1)
            self.combos[m] = cb
        v.addLayout(g)
        v.addWidget(only_note("The Premiere colours read your labelled sequence and go on the clips of Export → Premiere; "
                              "the DaVinci colours go on the clips of Export → DaVinci. Reading your labels changes at "
                              "the next Build; the exported colours change at once."))
        self.app = "premiere"

    def load(self, c):
        self.c = dict(c or {})
        self.sw.blockSignals(True)
        self.sw.set(bool(self.c.get("on")))
        self.sw.blockSignals(False)
        self._show(self.c.get("show", "premiere"), emit=False)

    def _on(self, on):
        self.c["on"] = on
        self._fill()
        self.changed.emit(dict(self.c))

    def _show(self, app, emit=True):
        self.app = app
        self.c["show"] = app
        for b, on in ((self.b_pr, app == "premiere"), (self.b_dv, app == "davinci")):
            b.setChecked(on)
            b.setObjectName("primary" if on else "")
            repolish(b)
        self._fill()
        if emit:
            self.changed.emit(dict(self.c))

    def _fill(self):
        pr, dv = longfilm2.colour_maps(dict(self.c, on=True) if self.c.get("on") else {})
        cur = pr if self.app == "premiere" else dv
        names = longfilm2.PR_COLOURS if self.app == "premiere" else longfilm2.DV_COLOURS
        hexes = PR_LABEL if self.app == "premiere" else DV_LABEL
        for m, cb in self.combos.items():
            cb.blockSignals(True)
            cb.clear()
            for n in names:
                cb.addItem(_swatch(hexes.get(n, "#777")), n)
            cb.setCurrentIndex(names.index(cur[m]) if cur[m] in names else 0)
            cb.setEnabled(bool(self.c.get("on")))
            cb.blockSignals(False)

    def _pick(self, m):
        cb = self.combos[m]
        self.c.setdefault(self.app, {})[m] = cb.currentText()
        self.changed.emit(dict(self.c))


class SelectsMap(QWidget):
    """How his selects sequence should look (Long Film): trains of colours, the name of each train above it, the
    cameras under it. Measured on his own selects (4 July, Madalina & Radu)."""
    GROUPS = [
        ("Camera 1 (main, e.g. fx6)", [(7, "Blue", "Groom"), (5, "Rose", "Bride"), (3, "Iris", "First look"),
                                       (7, "Brown", "Church"), (3, "Yellow", "Venue"), (4, "Iris", "Party"),
                                       (3, "Purple", "Couple"), (4, "Iris", "Party")]),
        ("Camera 2 (e.g. fx3)", [(4, "Iris", "First look / party"), (3, "Brown", "Church"), (3, "Iris", "Party")]),
        ("Cameras 3, 4, 5…", [(5, "Iris", "Party")]),
        ("Drone", [(4, "Violet", "Drone")]),
        ("Copies", [(4, None, "Left out")]),
    ]
    # Long Film v2: the Create Project sequence (chronological: the cameras one after the other), labelled by moment
    GROUPS_V2 = [
        ("Camera A (e.g. fx6)", [(6, "Blue", "Groom"), (5, "Rose", "Bride"), (3, "Teal", "First look"),
                                 (3, "Forest", "Vornic"), (6, "Brown", "Church"), (3, "Yellow", "Venue"),
                                 (3, "Purple", "Couple"), (6, "Iris", "Party")]),
        ("Camera B (e.g. fx3)", [(3, "Teal", "First look"), (3, "Forest", "Vornic"), (4, "Brown", "Church"),
                                 (5, "Iris", "Party")]),
        ("Cameras C, D…", [(5, "Iris", "Party")]),
        ("Drone", [(3, "Violet", "Drone")]),
        ("Recorder", [(5, "Sound", "Sound only")]),
        ("No colour", [(3, None, "Left out")]),
    ]
    ROW, BAR, GAP = 15, 26, 12

    def __init__(self, groups=None):
        super().__init__()
        if groups:
            self.GROUPS = groups
        self.setMinimumWidth(300)
        self._h = 0
        self.setFixedHeight(120)

    @staticmethod
    def _place(items, W, maxrows=6):
        """items = [(centre x, width)] -> [(left x, row)]: each label in the lowest row where it does not touch another."""
        rows, out = [[] for _ in range(maxrows)], []
        for cx, tw in items:
            lx = min(max(1, cx - tw / 2), W - tw - 1)
            r = next((k for k in range(maxrows) if all(lx > b + 6 or lx + tw < a - 6 for a, b in rows[k])), maxrows - 1)
            rows[r].append((lx, lx + tw))
            out.append((lx, r))
        return out

    def _layout(self, fm):
        W = self.width() - 2
        total = sum(w for _, segs in self.GROUPS for w, _, _ in segs)
        px = (W - self.GAP * (len(self.GROUPS) - 1)) / total
        segs_xy, groups_xy, x = [], [], 1.0
        for gname, segs in self.GROUPS:
            g0 = x
            for w, col, name in segs:
                segs_xy.append((x, w * px, col, i18n.T(name)))
                x += w * px
            groups_xy.append((g0, x, i18n.T(gname)))
            x += self.GAP
        top = self._place([(sx + sw / 2, fm.horizontalAdvance(n)) for sx, sw, _, n in segs_xy], W)
        bot = self._place([((g0 + g1) / 2, fm.horizontalAdvance(n)) for g0, g1, n in groups_xy], W)
        ntop = 1 + max(r for _, r in top)
        nbot = 1 + max(r for _, r in bot)
        h = 2 + ntop * self.ROW + 6 + self.BAR + 8 + nbot * self.ROW + 4
        return segs_xy, groups_xy, top, bot, ntop, nbot, h

    def resizeEvent(self, e):
        f = self.font()
        f.setPixelSize(11)
        from PySide6.QtGui import QFontMetrics
        h = self._layout(QFontMetrics(f))[-1]
        if h != self.height():
            self.setFixedHeight(h)
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = p.font()
        f.setPixelSize(11)
        p.setFont(f)
        fm = p.fontMetrics()
        segs_xy, groups_xy, top, bot, ntop, nbot, _ = self._layout(fm)
        bar_y = 2 + ntop * self.ROW + 6
        for (sx, sw, col, name), (lx, row) in zip(segs_xy, top):
            y = 2 + (ntop - 1 - row) * self.ROW                # row 0 sits right on the bar
            p.setPen(QColor("#d6d6d6") if col else QColor(C["MUTED"]))
            p.drawText(QRectF(lx, y, fm.horizontalAdvance(name) + 2, self.ROW), Qt.AlignLeft | Qt.AlignVCenter, name)
            if row > 0:
                p.setPen(QPen(QColor("#5a5a5a"), 1))
                p.drawLine(QPointF(sx + sw / 2, y + self.ROW - 1), QPointF(sx + sw / 2, bar_y - 1))
        import random
        rnd = random.Random(7)
        for sx, sw, col, name in segs_xy:
            r = QRectF(sx + 0.5, bar_y, max(1.0, sw - 1), self.BAR)
            if col:
                p.fillRect(r, QColor(PR_LABEL[col]))
                p.setPen(QPen(QColor(0, 0, 0, 90), 1))
                t = sx + rnd.uniform(4, 9)
                while t < sx + sw - 3:                       # clip boundaries, like a real timeline
                    p.drawLine(QPointF(t, bar_y + 1), QPointF(t, bar_y + self.BAR - 1))
                    t += rnd.uniform(4, 11)
            else:
                p.fillRect(r, QColor("#3a3a3a"))
                p.save()
                p.setClipRect(r)
                p.setPen(QPen(QColor("#5c5c5c"), 1))
                k = sx - self.BAR
                while k < sx + sw:                           # hatched = left out
                    p.drawLine(QPointF(k, bar_y + self.BAR), QPointF(k + self.BAR, bar_y))
                    k += 6
                p.restore()
        y2 = bar_y + self.BAR + 6
        for (g0, g1, gname), (lx, row) in zip(groups_xy, bot):
            p.setPen(QPen(QColor("#6a6a6a"), 1))
            p.drawLine(QPointF(g0 + 1, y2), QPointF(g1 - 1, y2))
            p.drawLine(QPointF(g0 + 1, y2 - 3), QPointF(g0 + 1, y2))
            p.drawLine(QPointF(g1 - 1, y2 - 3), QPointF(g1 - 1, y2))
            ty = y2 + 2 + row * self.ROW
            if row > 0:
                p.drawLine(QPointF((g0 + g1) / 2, y2), QPointF((g0 + g1) / 2, ty + 2))
            p.setPen(QColor(C["MUTED"]))
            p.drawText(QRectF(lx, ty, fm.horizontalAdvance(gname) + 2, self.ROW), Qt.AlignLeft | Qt.AlignVCenter, gname)
        p.end()


class LongFilmPage(QWidget):
    """The long film pre-cut from his labelled selections (see longfilm.py). Own projects, like Teaser Studio."""
    back = Signal()

    def __init__(self, store, teaser_page):
        super().__init__()
        self.store, self.tp = store, teaser_page
        self.pieces, self.runner, self._stop = [], None, False
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(btn("←  Projects", "link", lambda: self.back.emit()))
        self.pname = lbl("", "h2")
        top.addWidget(self.pname)
        top.addWidget(lbl("·  Long Film", "muted"))
        badge = QLabel("NEW")
        badge.setStyleSheet(f"background:{C['POOR']};color:white;font-size:10px;font-weight:800;border-radius:9px;padding:2px 8px")
        top.addWidget(badge)
        top.addStretch()
        self.b_build = btn("Build", "primary", self.build)
        self.b_exp = ExportPair(self.export)
        top.addWidget(self.b_exp)
        top.addWidget(self.b_build)
        v.addLayout(top)
        v.addWidget(lbl("The long film pre-cut from your labelled selections, every selection whole and in your order: teaser, "
                        "getting ready, first look, (vornic), church, couple and venue. The party is the Multicam edit. You add "
                        "the music, the interviews and the final touches in Premiere.", "muted", True))
        v.addSpacing(8)
        pr = QHBoxLayout()
        pr.addWidget(lbl("Project", "section"))
        self.pcombo = QComboBox()
        self.pcombo.setMinimumWidth(260)
        self.pcombo.currentIndexChanged.connect(self.switch_project)
        pr.addWidget(self.pcombo)
        pr.addWidget(btn("+  New long film", slot=self.new_project))
        pr.addWidget(btn("Rename", "link", self.rename_project))
        pr.addWidget(btn("Delete", "link", self.delete_project))
        pr.addStretch()
        self.pr_box = QWidget()
        self.pr_box.setLayout(pr)
        self.pr_box.hide()
        v.addWidget(self.pr_box)
        rn = QHBoxLayout()
        rn.addWidget(btn("Rename", "link", self.rename_project))
        rn.addStretch()
        v.addLayout(rn)
        body = QHBoxLayout()
        body.setSpacing(18)
        v.addLayout(body, 1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFixedWidth(430)
        lw = QWidget()
        left = QVBoxLayout(lw)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(10)

        def card(n, title):
            f = QFrame()
            f.setObjectName("card")
            l = QVBoxLayout(f)
            l.setContentsMargins(16, 14, 16, 16)
            l.setSpacing(10)
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
        l1.addWidget(lbl("The XML of your selects sequence. What it needs:<br>"
                         "• a COLOUR on every selection: Rose bride, Blue groom, Purple couple, Brown church, Iris first look "
                         "and party, Teal getting-ready location, Yellow or Caribbean venue, Violet drone (Tan interviews and "
                         "clips without a colour are not used);<br>"
                         "• the church (Brown) in the order you want it in the film;<br>"
                         "• the drone block AFTER everything else: only copies for the short film may come after it (they "
                         "are left out).<br>"
                         "Everything else can be in any order, on any tracks: the cameras are recognised by their files and "
                         "every camera's day is read from its file numbers.", "muted", True))
        l1.addWidget(btn("Import labelled XML", slot=self.pick_footage))
        self.foot_lbl = QLabel("")
        self.foot_lbl.setWordWrap(True)
        l1.addWidget(self.foot_lbl)
        lb = card(2, "Auto or Blueprint")
        self.bpbox = BlueprintBox(self.store, "long", "Auto builds it from your selections, the way you cut your long films "
                                                      "(getting ready, vornic and first look synced, church, couple and venue).")
        self.bpbox.changed.connect(self._mode_changed)
        lb.addWidget(self.bpbox)
        l2 = card(3, "Teaser")
        self.teaser_card = l2
        l2.addWidget(lbl("The teaser of a Teaser Studio project (the same wedding), with its music, at the start of the film.",
                         "muted", True))
        self.tcombo = QComboBox()
        self.tcombo.currentIndexChanged.connect(lambda i: self._remember(teaser=self.tcombo.itemData(i)))
        l2.addWidget(self.tcombo)
        l3 = card(4, "Vornic (optional)")
        QTimer.singleShot(0, lambda: l3.parentWidget().hide())      # the vornic is found automatically now (long selections)
        vr = QHBoxLayout()
        vr.addWidget(lbl("This wedding has a vornic", "", True), 1)
        self.sw_v = Switch(False)
        self.sw_v.toggled.connect(lambda x: (self._remember(vornic=x), self._vornic_ui()))
        vr.addWidget(self.sw_v, 0, Qt.AlignTop)
        l3.addLayout(vr)
        self.vbox = QWidget()
        self.vbox.setStyleSheet("background:transparent")
        vb = QVBoxLayout(self.vbox)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.addWidget(lbl("A good photo of the vornic (face well visible): his Iris shots of the morning are found by his face, "
                         "on both cameras. Or mark the vornic shots Mango in Premiere.", "muted", True))
        vb.addWidget(btn("Choose the vornic's photo", slot=self.pick_photo))
        self.photo_lbl = lbl("", "muted", True)
        vb.addWidget(self.photo_lbl)
        l3.addWidget(self.vbox)
        left.addStretch()
        sc.setWidget(lw)
        body.addWidget(sc)
        right = QVBoxLayout()
        right.addWidget(lbl("YOUR LONG FILM", "section"))
        self.parts_lbl = QLabel("")
        self.parts_lbl.setWordWrap(True)
        self.parts_lbl.setTextFormat(Qt.RichText)
        right.addWidget(self.parts_lbl)
        self.pp = ProgressPanel()
        right.addWidget(self.pp)
        right.addStretch()
        right.addWidget(lbl("HOW YOUR SELECTS SEQUENCE SHOULD LOOK", "section"))
        right.addWidget(lbl("Every camera one after the other (with 3, 4 or 5 cameras the same way), each in the order of the "
                            "day; couple shots can sit in the middle of the party. The drone block comes last; after it only "
                            "copies for the short film. Clips without a colour are not used.", "muted", True))
        self.smap = SelectsMap()
        right.addWidget(self.smap)
        body.addLayout(right, 1)
        self.layout_ = None

    def _drop(self, paths):
        """Finder drop: the XML of your selects sequence."""
        xmls, _ = _xml_or_rest(paths)
        if not xmls:
            notify(i18n.T("Drop the XML of your selects sequence here."), error=True)
            return
        self._remember(footage=xmls[0])
        self._load(xmls[0])

    def open_project(self):
        self._fill_projects()
        self.pname.setText(self._cur()["name"])
        self.restore()

    # ---- projects (one per wedding)
    def _projects(self):
        return self.store.app.setdefault("long_projects", [])

    def _cur(self):
        ps = self._projects()
        if not ps:
            ps.append(dict(id=uuid.uuid4().hex, name="My first long film"))
            self.store.app["long_current"] = ps[0]["id"]
        return next((p for p in ps if p["id"] == self.store.app.get("long_current")), ps[0])

    def _remember(self, **kw):
        self._cur().update(kw, when=datetime.now().isoformat(timespec="seconds"))
        self.store.save_app()

    def _fill_projects(self):
        self.pcombo.blockSignals(True)
        self.pcombo.clear()
        for p in self._projects():
            self.pcombo.addItem(p["name"], p["id"])
        self.pcombo.setCurrentIndex([p["id"] for p in self._projects()].index(self._cur()["id"]))
        self.pcombo.blockSignals(False)

    def _busy(self):
        return bool(self.runner and self.runner.isRunning())

    def switch_project(self, i):
        if self._busy():
            self._fill_projects()
            return
        self.store.app["long_current"] = self.pcombo.itemData(i)
        self.store.save_app()
        self.restore()

    def new_project(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New long film", "Name (e.g. the couple):")
        if ok and name.strip() and not self._busy():
            p = dict(id=uuid.uuid4().hex, name=name.strip())
            self._projects().append(p)
            self.store.app["long_current"] = p["id"]
            self.store.save_app()
            self._fill_projects()
            self.restore()

    def rename_project(self):
        from PySide6.QtWidgets import QInputDialog
        p = self._cur()
        name, ok = QInputDialog.getText(self, "Rename long film", "Name:", text=p["name"])
        if ok and name.strip():
            p["name"] = name.strip()
            self.store.save_app()
            self._fill_projects()
            self.pname.setText(p["name"])

    def delete_project(self):
        from PySide6.QtWidgets import QMessageBox
        ps = self._projects()
        if self._busy() or len(ps) < 2:
            return
        p = self._cur()
        if QMessageBox.question(self, "Delete long film", f"Delete \"{p['name']}\"? Your files are not touched.") != QMessageBox.Yes:
            return
        ps.remove(p)
        self.store.app["long_current"] = ps[0]["id"]
        self.store.save_app()
        self._fill_projects()
        self.restore()

    def restore(self):
        if self._busy():
            return
        t = self._cur()
        self.pieces, self.layout_, self.bp_edit = [], None, None
        self.bpbox.load(t)
        self.teaser_card.parentWidget().setEnabled(self.bpbox.current() is None)
        self.foot_lbl.setText("")
        self.parts_lbl.setText(i18n.T("Import your labelled XML to start."))
        self.tcombo.blockSignals(True)
        self.tcombo.clear()
        self.tcombo.addItem(i18n.T("No teaser"), None)
        for tp_ in self.store.app.get("teaser_projects", []):
            self.tcombo.addItem(tp_["name"], tp_["id"])
        ix = self.tcombo.findData(t.get("teaser"))
        self.tcombo.setCurrentIndex(max(0, ix))
        self.tcombo.blockSignals(False)
        self.sw_v.set(bool(t.get("vornic")))
        self.photo_lbl.setText(Path(t["photo"]).name if t.get("photo") else i18n.T("No photo yet."))
        self._vornic_ui()
        self._buttons()
        if t.get("footage") and Path(t["footage"]).exists():
            self._load(t["footage"])

    def _vornic_ui(self):
        self.vbox.setVisible(self.sw_v.on)

    def _buttons(self):
        self.b_build.setEnabled(bool(self.pieces) and not self._busy())
        self.b_exp.setEnabled(self.layout_ is not None and not self._busy())

    # ---- jobs
    def _run(self, text, fn, done):
        if self._busy():                                     # never two jobs: the running one would be destroyed
            notify("Wait for the current job to finish (or Cancel it).", error=True)
            return
        self._stop = False
        self.pp.start(text)
        self.pp.allow_cancel(lambda: setattr(self, "_stop", True))
        self.runner = _Runner(fn)
        self.runner.progress.connect(self.pp.set)
        t0 = time.time()

        def _done(r):
            self.pp.set(text, 1.0)
            self.pp.allow_cancel(None)
            done(r)
            # a very quick job still shows its bar for a moment (you see that something happened)
            QTimer.singleShot(int(max(0, 0.9 - (time.time() - t0)) * 1000), self.pp.hide)
        self.runner.done.connect(_done)
        self.runner.finished.connect(self._buttons)          # only when the job has really ended
        self.runner.failed.connect(lambda m: (self.pp.hide(), self.pp.allow_cancel(None), self._buttons(),
                                              self.parts_lbl.setText(f'<span style="color:{C["POOR"]}">{i18n.T("Error: {}").format(i18n.T(m))}</span>'),
                                              notify(f"Error: {m}", error=True) if m != "Cancelled" else None))
        self.runner.finished.connect(self._buttons)     # done/failed run while the thread is still running
        job_mark("lf")
        self.runner.start()
        self._buttons()

    def pick_footage(self):
        f, _ = QFileDialog.getOpenFileName(self, "Labelled footage XML (from Premiere)", "", "XML (*.xml)")
        if f:
            self._remember(footage=f)
            self._load(f)

    def _load(self, f):
        self._run("Reading your labelled clips…", lambda progress=None: teaser.load_footage(f), self._loaded)

    def _loaded(self, r):
        self.pieces, skipped = r
        kept = longfilm.drop_copies(self.pieces)
        trs, parts = longfilm.plan(kept)
        rows = [f"<b>{Path(self._cur()['footage']).name}</b>"]
        for k, tr in enumerate(trs):
            b, c, _ = longfilm.split_day(tr)
            rows.append(f"<b>{longfilm.camera_name(tr)}</b>: " + i18n.T("{} selections").format(len(tr)) +
                        (f' · {i18n.T("main camera (getting ready)")}' if k == 0 else "") +
                        ("" if c or not any(p["cat"] == "party" for p in tr) else
                         f' <span style="color:{C["MUTED"]}">{i18n.T("(no church on this camera: its first look is found by the sound)")}</span>'))
        if longfilm.looks_like_an_edit(self.pieces):
            rows.append(f'<span style="color:{C["FAIR"]}">' + i18n.T("This looks like a finished film (cuts of 1-2 s), not your selects sequence: "
                        "the long film would reuse those short cuts. Import the sequence with your selections.") + "</span>")
        missing = sum(1 for p in self.pieces if not Path(p["path"]).exists())
        if missing:
            rows.append(f'<span style="color:{C["POOR"]}">' + i18n.T("{} clips not found on this computer: connect the disk with the footage.").format(missing) + "</span>")
        if len(kept) < len(self.pieces):
            rows.append(f'<span style="color:{C["MUTED"]}">' + i18n.T("{} copies at the end of your selects left out (they are for the short film).").format(len(self.pieces) - len(kept)) + "</span>")
        lost = longfilm.lost_after_drone(self.pieces)
        if len(lost) >= max(10, len(self.pieces) // 5):
            rows.append(f'<span style="color:{C["POOR"]}">' + self._drone_problem(lost) + "</span>")
        self.foot_lbl.setText("<br>".join(rows))
        self.parts_lbl.setText(i18n.T("Press Build."))
        notify(f"Footage loaded: {len(self.pieces)} selections")

    def _drone_problem(self, lost):
        """Exactly what is wrong: which drone clip ends last and where, what is lost after it (by colour), the first
        lost selection, and what to move."""
        names = {"Blue": "groom", "Rose": "bride", "Purple": "couple", "Brown": "church", "Iris": "first look / party",
                 "Teal": "getting-ready location", "Yellow": "venue", "Caribbean": "venue", "Mango": "vornic"}
        tc = lambda t: f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}"
        d = longfilm.last_drone(self.pieces)
        dend = d["order"] + d["b"] - d["a"]
        cnt = {}
        for p in lost:
            cnt[p.get("label", "")] = cnt.get(p.get("label", ""), 0) + 1
        what = ", ".join(f"{n} {lab} ({i18n.T(names.get(lab, 'other'))})" for lab, n in sorted(cnt.items(), key=lambda x: -x[1]))
        first = min(lost, key=lambda p: p["order"])
        return ("<b>" + i18n.T("{} selections will be left out.").format(len(lost)) + "</b> " +
                i18n.T("The last drone shot on your sequence is {} (it ends at {}): everything after it counts as copies for "
                       "the short film. After it there are: {}. The first one is {} at {}.").format(
                    escape(Path(d["path"]).name), tc(dend), what, escape(Path(first["path"]).name), tc(first["order"])) +
                " " + i18n.T("Fix: move {} (and the other drone shots) after all the selections you want in the film, or delete it "
                             "if it is a copy.").format(escape(Path(d["path"]).name)) +
                " " + i18n.T("(Times from the start of your sequence.)"))

    def pick_photo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Photo of the vornic", "", "Images (*.jpg *.jpeg *.png *.JPG *.PNG)")
        if f:
            self._remember(photo=f)
            self.photo_lbl.setText(Path(f).name)

    def _show(self, parts, layout):
        rows = []
        lens = {n: L for n, L, _ in (layout or [])}
        counts = {n: len(its) for n, _, its in (layout or [])}                      # shots (pieces of selections)
        for name, ps in parts:
            d = lens.get(name, sum(p["b"] - p["a"] for p in ps))      # the vornic's wide camera lies UNDER the medium one
            ps = [None] * counts.get(name, len(ps))
            rows.append(f"<tr><td>{i18n.T(name)}</td><td align='right'>{len(ps)}</td><td align='right'>{int(d // 60)}:{int(d % 60):02d}</td></tr>")
        total = sum(L for _, L, _ in layout) if layout else None
        head = f"<tr><td><b>{i18n.T('Part')}</b></td><td><b>{i18n.T('Shots')}</b></td><td><b>{i18n.T('Duration')}</b></td></tr>"
        tail = (f"<br>{i18n.T('Built. The long film is about {} min long (without the teaser and the party). Press Export XML.').format(max(1, round(total / 60)))}"
                if total is not None else f"<br>{i18n.T('Press Build.')}")
        self.parts_lbl.setText(f"<table cellspacing='8'>{head}{''.join(rows)}</table>{tail}")

    def _mode_changed(self):
        """Auto or Blueprint: one or the other; the teaser card belongs to Auto (a blueprint brings its own opening)."""
        self.layout_, self.bp_edit = None, None
        self.teaser_card.parentWidget().setEnabled(self.bpbox.current() is None)
        if self.pieces:
            self.parts_lbl.setText(i18n.T("Press Build."))
        self._buttons()

    def build(self):
        b = self.bpbox.current()
        if b:
            pieces = self.pieces

            def job_bp(progress=None):
                if progress:
                    progress("Refilling your film with this wedding…", 0.5)
                return blueprint.build(pieces, b, seed=1)
            self._run("Building the long film…", job_bp, lambda e, b=b: self._built_bp(e, b))
            return
        t = self._cur()
        pieces = self.pieces
        use_v = bool(t.get("vornic"))
        photo = t.get("photo")
        tid = t.get("teaser")
        tpro = next((x for x in self.store.app.get("teaser_projects", []) if x["id"] == tid), None)
        base = self.store.dir

        def job(progress=None):
            trs, layout = longfilm.build_film(pieces, progress, cancel=lambda: self._stop)
            tz = None
            if tpro and tpro.get("footage") and tpro.get("music") and tpro.get("bounds"):
                if progress:
                    progress("Building the teaser from Teaser Studio…", 0.5)
                tps, _ = teaser.load_footage(tpro["footage"])
                tz = longfilm.teaser_part(tps, teaser.load_music(tpro["music"]), tpro["bounds"])
            parts = [(n, [it[2] for it in its]) for n, _, its in layout]
            return parts, layout, tz, 0

        self._run("Building the long film…", job, self._built)

    def _built(self, r):
        parts, self.layout_, self.tz, nv = r
        self.bp_edit = None
        self._show(parts, self.layout_)
        notify("Long film ready", took="lf")

    def _built_bp(self, e, b):
        self.bp_edit, self.bp_used = e, b
        self.layout_ = []                                 # Export XML is enabled (the blueprint edit is exported)
        holes = [k for *_, k in e["gaps"] if k != "interview"]
        inter = sum(1 for *_, k in e["gaps"] if k == "interview")
        txt = i18n.T("{} shots from the blueprint {}, no moment used twice.").format(len(e["shots"]), b["name"])
        if inter:
            txt += "<br>" + i18n.T("{} places for your interviews (marker Interview here).").format(inter)
        txt += "<br>" + i18n.T("The party stays the Multicam edit (marker).")
        if holes:
            txt += (f'<br><span style="color:{C["FAIR"]}">' + i18n.T("{} cuts have no footage left of their colour (marker): label more clips.").format(len(holes)) + "</span>")
        self.parts_lbl.setText(txt)
        notify("Long film ready", took="lf")
        logging.info("long film blueprint %s: %d shots, %d holes", b["name"], len(e["shots"]), len(holes))

    def export(self, target="premiere"):
        if self.layout_ is None:
            return
        start = resolve.name_for(str(Path(self._cur().get("footage") or ".").parent / f"{self._cur()['name']} - long film.xml"), target)
        out, _ = QFileDialog.getSaveFileName(self, "Save XML", start, "XML (*.xml)")
        if not out:
            return
        try:
            if getattr(self, "bp_edit", None):
                b = self.bp_used
                n = blueprint.export_xml(self.bp_edit, b, out, Path(out).stem)
                gone = sorted({x["name"] for x in b["audio"] if not Path(x["path"]).exists()})
                if gone:
                    notify(f"{len(gone)} sounds of the blueprint were not found on this computer, e.g. {gone[0]}", error=True)
            else:
                n, marks = longfilm.export_xml(self.layout_, out, Path(out).stem, self.tz)
            for_target(out, target)
            self.parts_lbl.setText(self.parts_lbl.text() + "<br>" + i18n.T("Saved {} clips to {}. Premiere: File > Import · DaVinci: File > Import > Timeline.").format(n, out))
            notify(f"XML saved: {Path(out).name}")
            logging.info("long film exported: %s (%d clips)", out, n)
        except Exception as e:
            logging.exception("long film export failed")
            notify(f"Export failed: {e}", error=True)


# ---------------------------------------------------------------- Card offload

class _UpdWorker(QThread):
    """Update check / download off the UI thread (updater.py)."""
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(object, object)

    def __init__(self, what, release=None):
        super().__init__()
        self.what, self.release = what, release

    def run(self):
        try:
            if self.what == "check":
                self.done.emit(updater.latest())
            else:
                self.done.emit(updater.download(self.release["url"], self.release["tag"],
                                                lambda g, t: self.progress.emit(g, t)))
        except Exception as e:
            self.failed.emit(str(e))


class _ClaudeWorker(QThread):
    """The story request to the Claude API, off the UI thread."""
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, text, key):
        super().__init__()
        self.text, self.key = text, key

    def run(self):
        try:
            self.done.emit(story.ask_claude(self.text, self.key))
        except Exception as e:
            logging.warning("claude story failed: %s", e)
            self.failed.emit(str(e))


class _ProbeWorker(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, float)

    def __init__(self, cams, stop):
        super().__init__()
        self.cams, self.stop = cams, stop

    def run(self):
        try:
            self.done.emit(projectsetup.read_all(self.cams, lambda t, f: self.progress.emit(t, f), self.stop))
        except Exception as e:
            if not isinstance(e, InterruptedError):
                logging.exception("create project failed")
            self.failed.emit(str(e))


def _premiere_app():
    """The newest Premiere Pro installed (Mac: the .app, Windows: the .exe), or ""."""
    import glob
    if sys.platform == "darwin":
        found = glob.glob("/Applications/Adobe Premiere Pro*/Adobe Premiere Pro*.app")
    elif os.name == "nt":
        found = glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Adobe",
                                       "Adobe Premiere Pro*", "Adobe Premiere Pro.exe"))
    else:
        found = []
    return sorted(found)[-1] if found else ""


def _bridge_ok():
    """The Premiere bridge can be used here (Mac with Premiere installed; installed at the start of the app)."""
    return sys.platform == "darwin" and bool(_premiere_app()) and bool(bridge.installed_version())


_BRIDGE_JOBS = {}


def to_premiere(xml, name, crop, status=None):
    """Hand an exported XML to the Premiere bridge: Premiere imports it into the open project, opens the sequence and
    puts an adjustment layer with Crop on top. The answer comes back as a notification."""
    try:
        jid = bridge.send(xml, name, crop)
    except Exception as e:
        logging.exception("bridge send failed")
        notify(i18n.T("Could not send the XML to Premiere: {}").format(str(e)), error=True)
        return
    app_path = _premiere_app()
    if app_path and sys.platform == "darwin":
        updater.launch(["open", "-a", app_path])
    msg = i18n.T("Sent to Premiere: it imports the film into the open project and puts the adjustment layer with the crop on top.")
    if status is not None:
        status.setText(msg)
    notify(msg)
    t0 = time.time()
    tm = QTimer()
    _BRIDGE_JOBS[jid] = tm

    def check():
        r = bridge.result(jid)
        waited = time.time() - t0
        if r is None and waited < 1800:
            if waited > 25 and not bridge.alive(10) and not getattr(tm, "warned", False):
                tm.warned = True
                notify(i18n.T("Premiere has not picked up the film yet: open Premiere with your project (restart it once "
                              "after the first install of MoneyMakingMachine)."), error=True)
            return
        tm.stop()
        _BRIDGE_JOBS.pop(jid, None)
        if r is None:
            bridge.cancel(jid)
            notify(i18n.T("Premiere did not take the film in 30 min: import the XML by hand."), error=True)
        elif r.get("ok"):
            notify(i18n.T("In Premiere: {}").format(i18n.T(r.get("msg", ""))))
        else:
            notify(i18n.T("Premiere: {}").format(i18n.T(r.get("msg", ""))), error=True)
    tm.timeout.connect(check)
    tm.start(1500)


class CreateProjectPage(QWidget):
    """The wedding folder -> one timeline the way he lays out the footage for the selection (see projectsetup.py)."""

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.cfg = store.app.setdefault("create_project", dict(folder="", name=""))
        self.worker, self._stop, self.cams = None, False, []
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(lbl("Create Project", "h1"))
        top.addStretch()
        self.b_go = btn("Create the project", "primary", self.start)
        top.addWidget(self.b_go)
        v.addLayout(top)
        v.addWidget(lbl("Choose the wedding folder and give the project a name: a new Premiere Pro project with one bin for "
                        "every folder and a sequence. Chronological: the cameras one after the other (camera A, B, C…, then "
                        "the drone), every camera's clips in the order they were filmed. Timecode synchronized sequence: "
                        "every camera on its own track, every clip at its timecode, as if you labelled the cameras and made "
                        "a multi-camera source sequence synced by timecode. Clips whole, with their sound.", "muted", True))
        mr = QHBoxLayout()
        mr.setSpacing(18)
        mr.addWidget(lbl("MODE", "section"))
        self.m_auto = QRadioButton(i18n.T("Chronological"))
        self.m_custom = QRadioButton(i18n.T("Timecode synchronized sequence"))
        (self.m_custom if self.cfg.get("mode") == "custom" else self.m_auto).setChecked(True)
        for rb_ in (self.m_auto, self.m_custom):
            rb_.setStyleSheet("QRadioButton{spacing:8px;padding:4px 0}"
                              "QRadioButton::indicator{width:15px;height:15px;border:1px solid #8a8a8a;border-radius:8px;"
                              "background:#232323}"
                              f"QRadioButton::indicator:checked{{background:qradialgradient(cx:0.5,cy:0.5,radius:0.5,fx:0.5,fy:0.5,"
                              f"stop:0 {C['HOT']},stop:0.55 {C['HOT']},stop:0.6 #232323,stop:1 #232323);"
                              f"border:1px solid {C['HOT']}}}")
            rb_.toggled.connect(self._mode_changed)
            mr.addWidget(rb_)
        mr.addStretch()
        v.addLayout(mr)
        v.addSpacing(6)
        body = QHBoxLayout()
        body.setSpacing(24)
        v.addLayout(body, 1)
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(lbl("WEDDING FOLDER", "section"))
        fr = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText(i18n.T("No folder chosen"))
        fr.addWidget(self.folder, 1)
        fr.addWidget(btn("Choose folder", slot=self.pick))
        left.addLayout(fr)
        left.addSpacing(6)
        left.addWidget(lbl("PROJECT NAME", "section"))
        self.name = QLineEdit()
        self.name.setPlaceholderText(i18n.T("e.g. Florin and Miruna"))
        self.name.textChanged.connect(lambda t: (self.cfg.update(project=t), self.store.save_app()))
        left.addWidget(self.name)
        self.seq_lbl = lbl(i18n.T("The sequence is called \"{}\".").format(self._seq_name()), "muted", True)
        left.addWidget(self.seq_lbl)
        left.addSpacing(6)
        left.addWidget(lbl("CAMERAS", "section"))
        self.cam_help = lbl("", "muted", True)
        left.addWidget(self.cam_help)
        self.list = QTableWidget(0, 2)
        self.list.setHorizontalHeaderLabels([i18n.T("Folder"), i18n.T("Camera")])
        self.list.verticalHeader().hide()
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list.setSelectionMode(QAbstractItemView.NoSelection)
        self.list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.list.setStyleSheet(f"QTableWidget{{background:#181818;border:1px solid {C['BORDER']};border-radius:6px}}")
        left.addWidget(self.list, 1)
        self.sound = lbl("", "muted", True)
        left.addWidget(self.sound)
        left.addSpacing(6)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(lbl("PUT IT IN YOUR PROJECT", "section"))
        how = QLabel()
        how.setWordWrap(True)
        how.setTextFormat(Qt.RichText)
        how.setStyleSheet(f"background:#181818;border:1px solid {C['BORDER']};border-radius:6px;padding:12px;line-height:140%")
        how.setText("<b>Premiere Pro, a new project:</b> press <b>Open in Premiere Pro</b>, or in Premiere's start screen "
                    "File &gt; Open and choose the XML. The project opens with one bin per camera and the selects "
                    "sequence; save it (Cmd+S / Ctrl+S) next to the XML with the same name."
                    "<br><br><b>Into a project you already have open:</b> drag the XML into the Project panel (or File "
                    "&gt; Import): a bin with the project's name appears, with the camera bins and the sequence inside."
                    "<br><br><b>DaVinci Resolve:</b> File &gt; Import &gt; Timeline and choose the XML."
                    "<br><br>The XML is saved in the wedding folder; <b>Show in Finder</b> opens it there.")
        right.addWidget(how)
        right.addWidget(only_note("Bins and Open in Premiere Pro: Premiere Pro only. DaVinci Resolve gets the sequence "
                                  "and puts the clips in its Media Pool by itself."))
        right.addWidget(davinci_tick(self.store, self.cfg))
        right.addSpacing(6)
        self.result = lbl("", "", True)
        self.result.setTextFormat(Qt.RichText)
        right.addWidget(self.result)
        rb = QHBoxLayout()
        self.b_open = btn("Open in Premiere Pro", "primary", self.open_premiere)
        self.b_open.hide()
        rb.addWidget(self.b_open)
        self.b_show = btn("Show in Finder", slot=self.show_file)
        self.b_show.hide()
        rb.addWidget(self.b_show)
        rb.addStretch()
        right.addLayout(rb)
        self.pp = ProgressPanel()
        self.pp.allow_cancel(self.cancel)
        right.addWidget(self.pp)
        right.addStretch()
        body.addLayout(right, 1)
        self.out = None
        start = self.cfg.get("folder", "")
        oc = store.app.get("offload", {})
        guess = Path(oc.get("dest", "") or ".") / oc.get("wedding", "") if oc.get("dest") and oc.get("wedding") else None
        if guess and guess.is_dir() and (not start or not Path(start).is_dir()):
            start = str(guess)                        # the wedding Card Offload copied last
        if start and Path(start).is_dir():
            self.load(start)
        self._mode_changed()
        self._ui()

    def _drop(self, paths):
        """Finder drop: the wedding folder (a file dropped = its folder)."""
        if self._busy():
            return
        q = Path(paths[0])
        self.load(str(q if q.is_dir() else q.parent))

    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _seq_name(self):
        return "selectie" if i18n.LANG == "ro" else "select"

    def _sync_name(self):
        return "sincronizare timecode" if i18n.LANG == "ro" else "timecode sync"

    def _custom(self):
        return self.m_custom.isChecked()

    def _mode_changed(self, *_):
        c = self._custom()
        self.cfg["mode"] = "custom" if c else "auto"
        self.store.save_app()
        self.cam_help.setText(i18n.T(
            "For every folder choose which camera it is (its camera label): camera A gets the first track, B the next, "
            "then the drone; the sound folders (lavaliere, recorder) go into the project as bins, not on the timeline; "
            "\"Leave out\" keeps a folder out of the project.") if c else i18n.T(
            "For every folder choose which camera it is: the sequence goes A, B, C…, then the drone, 20 minutes apart; "
            "the sound folders (lavaliere, recorder) go into the project as bins, not on the timeline; \"Leave out\" keeps "
            "a folder out of the project."))
        self.seq_lbl.setText(i18n.T("The sequence \"{}\": every camera on its own track (its label = the letter you choose), "
                                    "every clip at its timecode, like a multi-camera source sequence synced by timecode.")
                             .format(self._sync_name()) if c else
                             i18n.T("The sequence \"{}\": the cameras one after the other, every camera's clips in the order "
                                    "they were filmed (only the position in the timeline, no timecode).").format(self._seq_name()))

    def _ui(self):
        busy = self._busy()
        self.b_go.setEnabled(not busy and bool(self.cams))
        self.list.setEnabled(not busy)

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Choose the wedding folder", self.cfg.get("folder", ""))
        if d:
            self.load(d)

    def load(self, folder):
        self.cfg["folder"] = folder
        self.store.save_app()
        self.folder.setText(folder)
        self.result.setText("")
        self.b_show.hide()
        self.b_open.hide()
        if self.cfg.get("project_for") != folder or not self.cfg.get("project"):
            self.name.setText(Path(folder).name)        # a new wedding: its folder name, changed at will
            self.cfg["project_for"] = folder
            self.store.save_app()
        else:
            self.name.setText(self.cfg.get("project", ""))
        self.cams = projectsetup.all_folders(folder)
        saved = self.cfg.get("slots", {}) if self.cfg.get("slots_for") == folder else {}
        slots = [saved.get(c["folder"], d) for c, d in zip(self.cams, projectsetup.default_slots(self.cams))]
        choices = [(s, i18n.T("Camera {}").format(s)) for s in projectsetup.SLOTS] + \
            [("drone", i18n.T("Drone")), ("sound", i18n.T("Sound")), ("out", i18n.T("Leave out"))]
        self.list.setRowCount(len(self.cams))
        self.combos = []
        for r, (c, sl) in enumerate(zip(self.cams, slots)):
            n = len(c["files"])
            it = QTableWidgetItem(i18n.T("{}  ·  {} clips").format(c["name"], n) if n != 1 else
                                  i18n.T("{}  ·  1 clip").format(c["name"]))
            it.setToolTip(c["folder"])
            self.list.setItem(r, 0, it)
            cb = QComboBox()
            for key, text in choices:
                cb.addItem(text, key)
            cb.setCurrentIndex(max(0, cb.findData(sl)))
            cb.currentIndexChanged.connect(self._slots_changed)
            cb.setMinimumWidth(150)
            self.list.setCellWidget(r, 1, cb)
            self.list.setRowHeight(r, max(40, cb.sizeHint().height() + 6))
            self.combos.append(cb)
        self.list.resizeColumnsToContents()
        self.list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.sound.setText("")
        if not self.cams:
            notify(i18n.T("No video found in this folder."), error=True)
        self._ui()

    def _slots_changed(self):
        self.cfg["slots_for"] = self.cfg.get("folder", "")
        self.cfg["slots"] = {c["folder"]: cb.currentData() for c, cb in zip(self.cams, self.combos)}
        self.store.save_app()

    def chosen(self):
        """[(camera, slot)] in the order of their places (A, B, … then the drone)."""
        return projectsetup.by_slot(self.cams, [cb.currentData() for cb in getattr(self, "combos", [])])

    def start(self):
        cams = self.chosen()
        if not cams or self._busy():
            if not cams:
                notify(i18n.T("Choose a camera for at least one folder."), error=True)
            return
        self._stop = False
        self.result.setText("")
        self.b_show.hide()
        self.pp.start(i18n.T("Reading the clips…"))
        extra = []
        self.worker = _ProbeWorker([c for c, _ in cams] + extra, lambda: self._stop)
        self.worker.progress.connect(lambda t, f: self.pp.set(i18n.T(t), f))
        self.worker.done.connect(lambda infos, cams=cams, extra=extra: self._done(cams, infos, extra))
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._ui)          # done/failed run while the thread is still running
        job_mark("project")
        self.worker.start()
        self._ui()

    def cancel(self):
        self._stop = True

    def _failed(self, why):
        self.pp.hide()
        self._ui()
        if why == "Cancelled":
            notify(i18n.T("Cancelled"), error=True)
        else:
            notify(i18n.T("Create Project failed: {}").format(i18n.T(why)), error=True)

    def _done(self, cams, infos, extra=()):
        self.pp.hide()
        self._ui()
        name = self._seq_name()
        base = Path(self.cfg["folder"])
        project = self.name.text().strip() or base.name
        if self._custom():
            return self._done_custom(cams, infos, extra, base, project)
        binned = [dict(c, name=(i18n.T("Drone") if sl == "drone" else i18n.T("Sound") if sl == "sound" else
                                i18n.T("Camera {}").format(sl)) + f" - {c['name']}") for c, sl in cams]
        # owner: only the cameras and the drone on the timeline; lavaliere / recorder only as bins
        lay, bad = projectsetup.layout([b for b, (_c, sl) in zip(binned, cams) if sl != "sound"], infos)
        sound_bins = [(b["name"], projectsetup.chrono([f for f in b["files"] if infos.get(f, {}).get("dur")], infos))
                      for b, (_c, sl) in zip(binned, cams) if sl == "sound"]
        if not lay:
            notify(i18n.T("None of the clips could be read."), error=True)
            return
        safe = re.sub(r'[\\/:*?"<>|]+', "-", project).strip() or "project"
        out = projectsetup.free_path(base / f"{safe}.xml")
        try:
            r = projectsetup.export_xml(lay, infos, out, name, project=project, bins_only=sound_bins)
        except OSError:
            alt, _ = QFileDialog.getSaveFileName(self, "Save the XML", str(Path.home() / out.name), "XML (*.xml)")
            if not alt:
                return
            out = Path(alt)
            try:
                r = projectsetup.export_xml(lay, infos, out, name, project=project, bins_only=sound_bins)
            except Exception as e:
                logging.exception("create project export")
                notify(i18n.T("Create Project failed: {}").format(i18n.T(str(e))), error=True)
                return
        except Exception as e:
            logging.exception("create project export")
            notify(i18n.T("Create Project failed: {}").format(i18n.T(str(e))), error=True)
            return
        self.out = str(out)
        cams_txt = ", ".join(f"{c} {n}" for c, n in r["cameras"])
        txt = (i18n.T("{} clips on the timeline ({}), {} of footage.").format(r["clips"], cams_txt, hms(r["seconds"])) +
               "<br>" + i18n.T("Saved: {}").format(escape(out.name)))
        if bad:
            txt += f'<br><span style="color:{C["POOR"]}">' + i18n.T("{} files could not be read and were left out: {}").format(
                len(bad), escape(", ".join(Path(b).name for b in bad[:6]) + (" …" if len(bad) > 6 else ""))) + "</span>"
        txt += self._davinci_copy(out)
        self.result.setText(txt)
        self.b_show.show()
        self.b_open.setVisible(bool(_premiere_app()) and target() == "premiere")
        notify(i18n.T("Project ready: {} clips in {} bins and the sequence \"{}\". Open it in Premiere Pro.").format(
            r["clips"], len(r["cameras"]) + sum(1 for _n, fs in sound_bins if fs), name), took="project")
        logging.info("create project %s: %s clips, %s unreadable", out, r["clips"], len(bad))

    def _done_custom(self, cams, infos, extra, base, project):
        """Timecode synced sequence: every camera (its label = the picker's letter) on its own track, clips at their
        timecode; the sound folders only as bins."""
        name = self._sync_name()
        lab = lambda c, sl: (i18n.T("Drone") if sl == "drone" else i18n.T("Sound") if sl == "sound" else
                             i18n.T("Camera {}").format(sl)) + f" - {c['name']}"
        okf = lambda c: projectsetup.chrono([f for f in c["files"] if infos.get(f, {}).get("dur")], infos)
        cams_ = [(lab(c, sl), okf(c)) for c, sl in cams if sl != "sound"]
        snd = [(lab(c, sl), okf(c)) for c, sl in cams if sl == "sound"]
        bad = [f for c, _sl in cams for f in c["files"] if not infos.get(f, {}).get("dur")]
        safe = re.sub(r'[\\/:*?"<>|]+', "-", project).strip() or "project"
        out = projectsetup.free_path(base / f"{safe}.xml")
        try:
            try:
                r = projectsetup.export_synced(cams_, infos, out, name, project=project, bins_only=snd)
            except OSError:
                alt, _ = QFileDialog.getSaveFileName(self, "Save the XML", str(Path.home() / out.name), "XML (*.xml)")
                if not alt:
                    return
                out = Path(alt)
                r = projectsetup.export_synced(cams_, infos, out, name, project=project, bins_only=snd)
        except Exception as e:
            logging.exception("create project timecode")
            notify(i18n.T("Create Project failed: {}").format(i18n.T(str(e))), error=True)
            return
        self.out = str(out)
        nb = len(cams_) + sum(1 for _n, fs in snd if fs)
        txt = (i18n.T("{} clips, every camera on its own track ({} tracks), placed by timecode.").format(r["clips"], r["tracks"]) +
               "<br>" + escape(", ".join(f"{c} {k}" for c, k in r["cameras"])) + "<br>" + i18n.T("Saved: {}").format(escape(out.name)))
        if r["untimed"]:
            txt += f'<br><span style="color:{C["FAIR"]}">' + i18n.T("{} clips have no timecode: they are at the end of the sequence: {}").format(
                len(r["untimed"]), escape(", ".join(Path(b).name for b in r["untimed"][:6]))) + "</span>"
        if bad:
            txt += f'<br><span style="color:{C["POOR"]}">' + i18n.T("{} files could not be read and were left out: {}").format(
                len(bad), escape(", ".join(Path(b).name for b in bad[:6]) + (" …" if len(bad) > 6 else ""))) + "</span>"
        txt += self._davinci_copy(out)
        self.result.setText(txt)
        self.b_show.show()
        self.b_open.setVisible(bool(_premiere_app()) and target() == "premiere")
        notify(i18n.T("Project ready: {} clips in {} bins and the sequence \"{}\", synced by timecode. Open it in Premiere Pro.")
               .format(r["clips"], nb, name), took="project")
        logging.info("create project timecode %s: %s clips", out, r["clips"])

    def _davinci_copy(self, out):
        """Only when he works in DaVinci Resolve (top-right switch): the same timeline for Resolve, made and checked."""
        if target() != "davinci":
            return ""
        dv = projectsetup.free_path(Path(resolve.name_for(str(out), "davinci")))
        QTimer.singleShot(0, lambda: for_target(str(dv), "davinci", src=str(out)))
        return "<br>" + i18n.T("DaVinci Resolve: {} (File > Import > Timeline)").format(escape(Path(dv).name))

    def open_premiere(self):
        app = _premiere_app()
        if not (self.out and app):
            return
        try:
            if sys.platform == "darwin":
                updater.launch(["open", "-a", app, self.out])
            else:
                updater.launch([app, self.out])
            notify(i18n.T("Premiere Pro is opening the project. Save it with Cmd+S / Ctrl+S."))
        except Exception as e:
            logging.exception("open premiere")
            notify(i18n.T("Premiere Pro could not be opened: {}").format(e), error=True)

    def show_file(self):
        if not self.out:
            return
        try:
            if sys.platform == "darwin":
                updater.launch(["open", "-R", self.out])
            elif os.name == "nt":
                updater.launch(["explorer", "/select,", self.out])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.out).parent)))
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.out).parent)))


class _OffloadWorker(QThread):
    """One card in its own thread (every card at once): copied, or only checked against its twin's copy."""
    moved = Signal(int, float, float)          # card index, done bytes, total bytes
    ended = Signal(int, object, str)           # card index, summary, error ("" when fine)

    def __init__(self, k, source, dest, opts, stop, check_only=False):
        super().__init__()
        self.k, self.source, self.dest, self.opts, self.stop, self.check_only = k, source, dest, opts, stop, check_only

    def run(self):
        try:
            prog = lambda d, t, name: self.moved.emit(self.k, float(d), float(max(1, t)))
            win = self.opts.get("window")
            if self.check_only:
                r = offload.verify_only(self.source, self.dest, progress=prog, cancel=self.stop, window=win,
                                        keep_folders=self.opts["folders"])
            else:
                r = offload.offload(self.source, self.dest, verify=self.opts["verify"], keep_folders=self.opts["folders"],
                                    skip_proxies=self.opts["proxies"], report=self.opts["report"], progress=prog,
                                    cancel=self.stop, window=win)
            self.ended.emit(self.k, r, "")
        except InterruptedError:
            self.ended.emit(self.k, None, "Cancelled")
        except Exception as e:
            logging.exception("offload failed")
            self.ended.emit(self.k, None, str(e))


class _BackupWorker(QThread):
    """The whole wedding folder copied again to the backup drive (offload.backup)."""
    moved = Signal(float, float)
    ended = Signal(object, str)

    def __init__(self, root, dest, verify, stop):
        super().__init__()
        self.root, self.dest, self.verify, self.stop = root, dest, verify, stop

    def run(self):
        try:
            r = offload.backup(self.root, self.dest, verify=self.verify,
                               progress=lambda d, t, name: self.moved.emit(float(d), float(max(1, t))), cancel=self.stop)
            self.ended.emit(r, "")
        except InterruptedError:
            self.ended.emit(None, "Cancelled")
        except Exception as e:
            logging.exception("backup failed")
            self.ended.emit(None, str(e))


class _CardLook(QThread):
    """Reads what a card is (camera, size, speed, its clips) without blocking the window."""
    seen = Signal(str, object)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        for p in self.paths:
            try:
                what, folder = offload.identify(p)
                info = dict(what=what, folder=folder, **offload.media_info(p), sig=offload.signature(p),
                            speed=offload.read_speed(p), times=offload.media_times(p))
            except Exception as e:
                logging.warning("card look failed %s: %s", p, e)
                info = dict(what="", folder="", total=0, used=0, kind="", sig=set(), speed=0.0, times=[])
            self.seen.emit(str(p), info)


CHECK_ONLY = "check only (backup)"
OTHER = "Other folder…"


class OffloadPage(QWidget):
    """Copy the cards to the drive, every card at once, verified file by file (see offload.py)."""

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.cfg = store.app.setdefault("offload", dict(dest="", verify=True, folders=True, proxies=False, report=True,
                                                        eject=False, twins=True))
        self.cfg.setdefault("twins", True)
        self.extra, self.workers, self.state, self._stop = [], [], {}, False
        self.bworker = None
        self.looks, self.info, self.choice, self.looker = {}, {}, {}, None
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(lbl("Card Offload", "h1"))
        top.addStretch()
        self.b_cancel = btn("Cancel", slot=self.cancel)
        self.b_start = btn("Copy the ticked cards", "primary", self.start)
        top.addWidget(self.b_cancel)
        top.addWidget(self.b_start)
        v.addLayout(top)
        v.addWidget(lbl("Every ticked card is copied at the same time and every file is checked after copying. The cards are "
                        "only read: nothing on them is changed, renamed or deleted, and nothing at the destination is "
                        "overwritten.", "muted", True))
        v.addSpacing(14)
        body = QHBoxLayout()
        body.setSpacing(24)
        v.addLayout(body, 1)
        left = QVBoxLayout()
        left.addWidget(lbl("WEDDING", "section"))
        left.addSpacing(4)
        wr = QHBoxLayout()
        wr.setSpacing(8)
        today = datetime.now()
        months = offload.MONTHS if i18n.LANG == "ro" else offload.MONTHS_EN
        self.w_day, self.w_month, self.w_year = QComboBox(), QComboBox(), QComboBox()
        self.w_day.addItems([str(d) for d in range(1, 32)])
        self.w_month.addItems([m.capitalize() for m in months])
        self.w_year.addItems([str(y) for y in range(today.year - 1, today.year + 3)])
        self.w_day.setCurrentIndex(today.day - 1)
        self.w_month.setCurrentIndex(today.month - 1)
        self.w_year.setCurrentText(str(today.year))
        self.w_day.setMinimumWidth(92)
        self.w_month.setMinimumWidth(150)
        self.w_year.setMinimumWidth(110)
        self.w_bride, self.w_groom = QLineEdit(), QLineEdit()
        self.w_bride.setPlaceholderText(i18n.T("Bride"))
        self.w_groom.setPlaceholderText(i18n.T("Groom"))
        for wdg in (self.w_day, self.w_month, self.w_year, self.w_bride, self.w_groom):
            wr.addWidget(wdg)
        left.addLayout(wr)
        for c_ in (self.w_day, self.w_month, self.w_year):
            c_.currentIndexChanged.connect(self._name_from_fields)
        self.w_bride.textChanged.connect(self._name_from_fields)
        self.w_groom.textChanged.connect(self._name_from_fields)
        left.addSpacing(6)
        self.wedding = QLineEdit(self.cfg.get("wedding", ""))
        self.wedding.setPlaceholderText(offload.wedding_name(4, 7, "Alexandra", "Vlad", 2026, i18n.LANG))
        self.wedding.textChanged.connect(lambda t: (self.cfg.update(wedding=t), self._where()))
        left.addWidget(self.wedding)
        left.addSpacing(8)
        tw = QHBoxLayout()
        tw.setSpacing(8)
        self.only_this = QCheckBox(i18n.T("Only what was filmed at this wedding"))
        self.only_this.setChecked(self.cfg.get("only_this", True))
        self.t_from, self.t_to = QComboBox(), QComboBox()
        for c_ in (self.t_from, self.t_to):
            c_.addItems([f"{h:02d}:00" for h in range(24)])
            c_.setCurrentIndex(5)
            c_.setMinimumWidth(112)
            c_.currentIndexChanged.connect(lambda _=None: self._rows())
        self.t_from.setCurrentIndex(self.cfg.get("from_h", 5))
        self.t_to.setCurrentIndex(self.cfg.get("to_h", 5))
        self.only_this.toggled.connect(lambda on: (self.cfg.update(only_this=on), self._rows()))
        left.addWidget(self.only_this)
        left.addSpacing(4)
        tw.addSpacing(26)
        tw.addWidget(lbl("from", "muted"))
        tw.addWidget(self.t_from)
        tw.addWidget(lbl("to the next day at", "muted"))
        tw.addWidget(self.t_to)
        tw.addStretch()
        left.addLayout(tw)
        left.addSpacing(8)
        left.addWidget(lbl("CARDS", "section"))
        self.card_box = QVBoxLayout()
        self.card_box.setSpacing(0)
        self.card_box.setContentsMargins(0, 0, 8, 0)
        lw = QWidget()
        lw.setLayout(self.card_box)
        cs = QScrollArea()                                # many cards: they scroll, every row keeps its height
        cs.setWidgetResizable(True)
        cs.setFrameShape(QFrame.NoFrame)
        cs.setWidget(lw)
        left.addWidget(cs, 1)
        rr = QHBoxLayout()
        rr.addWidget(btn("Refresh", "link", lambda: self.refresh(force=True)))
        af = btn("+  Add a folder (not a card)", "link", lambda: self.add_folder())
        af.setToolTip(i18n.T("Footage that is not on a card: a folder on the computer, a backup on another drive, a card reader that does not show up by itself."))
        rr.addWidget(af)
        rr.addStretch()
        left.addLayout(rr)
        body.addLayout(left, 3)
        right = QVBoxLayout()
        right.addWidget(lbl("DESTINATION", "section"))
        dr = QHBoxLayout()
        self.dest_lbl = lbl("", "muted", True)
        dr.addWidget(self.dest_lbl, 1)
        dr.addWidget(btn("Choose", slot=lambda: self.pick_dest()))
        right.addLayout(dr)
        self.where = QLabel("")
        self.where.setTextFormat(Qt.RichText)
        self.where.setWordWrap(True)
        right.addWidget(self.where)
        right.addSpacing(8)
        right.addWidget(lbl("BACKUP", "section"))
        br = QHBoxLayout()
        self.backup_lbl = lbl("", "muted", True)
        br.addWidget(self.backup_lbl, 1)
        br.addWidget(btn("Choose", slot=lambda: self.pick_backup()))
        self.b_backup = btn("Back up now", slot=lambda: self.start_backup())
        self.b_backup.setToolTip(i18n.T("Copies the wedding folder above (every camera and sound folder) to the backup drive now."))
        br.addWidget(self.b_backup)
        right.addLayout(br)
        right.addSpacing(8)
        right.addWidget(lbl("OPTIONS", "section"))
        self.opts = {}
        for key, text in (("verify", "Check every file after copying (reads the copy back)"),
                          ("twins", "Backup cards (the same clips): copy only the fastest, only check the other"),
                          ("folders", "Keep the card's folders"),
                          ("proxies", "Skip the camera proxies (.LRF, .LRV, .THM)"),
                          ("report", "Write a report next to the footage"),
                          ("eject", "Eject the cards when everything is copied"),
                          ("project", "Then make the Premiere project (Create Project, in the mode chosen there)"),
                          ("backup", "At the end, copy the whole wedding folder to the backup drive too")):
            cb = QCheckBox(text)
            cb.setChecked(bool(self.cfg.get(key)))
            cb.toggled.connect(lambda on, k=key: (self.cfg.update({k: on}), self.store.save_app(), self._plan(), self._where()))
            self.opts[key] = cb
            right.addWidget(cb)
        right.addSpacing(8)
        self.pp = ProgressPanel()
        right.addWidget(self.pp)
        self.status = QLabel("")
        self.status.setTextFormat(Qt.RichText)
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        right.addStretch()
        body.addLayout(right, 2)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.isVisible() and not self._busy() and
                                   not any(c.view().isVisible() for c in getattr(self, "row_combos", [])) and self.refresh())
        self.timer.start(3000)
        self._where()
        self.refresh()
        self._buttons()

    # ---- the wedding's folder name
    def _drop(self, paths):
        """Finder drop on the page: folders to copy (footage that is not on a card)."""
        dirs = [p for p in paths if Path(p).is_dir()]
        if not dirs:
            notify(i18n.T("Drop a folder here."), error=True)
            return
        for d in dirs:
            self.add_folder(d)

    def _drop_dest(self, paths):
        """Finder drop on the destination: where the footage goes."""
        q = Path(paths[0])
        self.pick_dest(str(q if q.is_dir() else q.parent))

    def _name_from_fields(self, *_):
        b, g = self.w_bride.text().strip(), self.w_groom.text().strip()
        if b and g:
            self.wedding.setText(offload.wedding_name(self.w_day.currentIndex() + 1, self.w_month.currentIndex() + 1, b, g,
                                                      int(self.w_year.currentText()), i18n.LANG))
        self._rows()

    def _window(self):
        """The wedding's hours: from the wedding day at "from" to the next day at "to" (None when not asked)."""
        if not self.only_this.isChecked():
            return None
        try:
            d = datetime(int(self.w_year.currentText()), self.w_month.currentIndex() + 1, self.w_day.currentIndex() + 1)
        except ValueError:
            return None
        self.cfg.update(from_h=self.t_from.currentIndex(), to_h=self.t_to.currentIndex())
        start = d.replace(hour=self.t_from.currentIndex())
        end = (d + timedelta(days=1)).replace(hour=self.t_to.currentIndex())
        return start.timestamp(), end.timestamp()

    # ---- cards
    def _sources(self):
        return [*offload.cards(), *[Path(x) for x in self.extra]]

    def refresh(self, force=False):
        srcs = [str(s) for s in self._sources()]
        if force:
            self.info = {}
        for k in list(self.info):
            if k not in srcs:
                self.info.pop(k)
        new = [s for s in srcs if s not in self.info and s not in self.looks]
        if new and not (self.looker and self.looker.isRunning()):
            for s in new:
                self.looks[s] = True
            self.looker = _CardLook([Path(s) for s in new])
            self.looker.seen.connect(self._seen)
            self.looker.start()
        self.order = srcs
        self._plan()

    def _seen(self, path, info):
        self.looks.pop(path, None)
        self.info[path] = info
        self._plan()

    def _plan(self):
        """Folder of every card: lavaliers in turn (lav 1, lav 2), backup twins -> the fastest copied, the others checked."""
        order = [s for s in getattr(self, "order", []) if s in self.info]
        folder, twin_of = {}, {}
        lav = 0
        for s in order:
            f = self.info[s]["folder"] or Path(s).name
            if f == "lavaliere":
                lav += 1
                f = f"lavaliere/lav {lav}"
            folder[s] = f
        if self.opts["twins"].isChecked():
            groups = []
            for s in order:
                if self.info[s]["folder"] == "lavaliere":          # two lavaliers are never each other's backup
                    continue
                g = next((g for g in groups if offload.same_clips(self.info[g[0]]["sig"], self.info[s]["sig"])), None)
                (g.append(s) if g else groups.append([s]))
            for g in groups:
                if len(g) > 1:
                    best = max(g, key=lambda x: self.info[x]["speed"])
                    for s in g:
                        if s != best:
                            twin_of[s] = best
        self.auto_folder, self.twin_of = folder, twin_of
        self._rows()

    def _rows(self):
        if not hasattr(self, "only_this"):
            return
        win = self._window()
        key = (tuple(getattr(self, "order", [])), tuple(sorted(self.info)), tuple(sorted(self.twin_of.items())) if hasattr(self, "twin_of") else (),
               win, tuple(sorted(self.choice.items())))
        if key == getattr(self, "_rows_key", None) or any(c.view().isVisible() for c in getattr(self, "row_combos", [])):
            self._where()
            return                                       # nothing changed / a list is open: do not rebuild under the mouse
        self._rows_key = key
        ticked = {cb.property("src"): cb.isChecked() for cb in getattr(self, "row_cbs", [])}
        self.row_cbs, self.row_combos = [], []
        while self.card_box.count():
            it = self.card_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        srcs = getattr(self, "order", [])
        if not srcs:
            self.card_box.addWidget(lbl("No card found. Put a card in (it appears here by itself) or add a folder.", "muted", True))
        for s in srcs:
            row = QFrame()
            row.setStyleSheet(f"QFrame{{border-bottom:1px solid {C['BORDER']};}} QLabel{{border:none;}}")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 10, 4, 10)
            h.setSpacing(10)
            cb = QCheckBox()
            cb.setProperty("src", s)
            cb.setChecked(ticked.get(s, True))
            self.row_cbs.append(cb)
            cb.toggled.connect(lambda _=None: (self._where(), self._buttons()))
            h.addWidget(cb, 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(3)
            inf = self.info.get(s)
            title = f"<b>{escape(Path(s).name or s)}</b>"
            if inf and inf["kind"]:
                title += f' <span style="color:{C["MUTED"]}">· {escape(inf["kind"])}</span>'
            col.addWidget(QLabel(title))
            if inf:
                bits = []
                if inf["total"]:
                    bits.append(i18n.T("{} GB card").format(f"{inf['total'] / 1e9:.0f}"))
                    bits.append(i18n.T("{} GB used").format(f"{inf['used'] / 1e9:.0f}"))
                if inf["what"]:
                    bits.append(i18n.T(inf["what"]))
                if inf["speed"] > 1:
                    bits.append(f"~{inf['speed']:.0f} MB/s")
                col.addWidget(lbl(" · ".join(bits), "muted"))
                if win and inf.get("times"):
                    ins = sum(1 for t in inf["times"] if win[0] <= t < win[1])
                    out = len(inf["times"]) - ins
                    msg = i18n.T("{} clips from this wedding").format(ins)
                    if out:
                        msg += " · " + i18n.T("{} from other days stay on the card").format(out)
                    note = QLabel(f'<span style="color:{C["GOOD"] if ins else C["POOR"]}">{msg}</span>')
                    note.setWordWrap(True)
                    col.addWidget(note)
                if s in self.twin_of:
                    note = QLabel(f'<span style="color:{C["FAIR"]}">' + i18n.T("The same clips as {} (a backup): only checked, the faster card is copied").format(
                        escape(Path(self.twin_of[s]).name)) + "</span>")
                    note.setWordWrap(True)
                    col.addWidget(note)
            else:
                col.addWidget(lbl("Reading the card…", "muted"))
            h.addLayout(col, 1)
            combo = QComboBox()
            combo.setMinimumWidth(200)
            want = self.choice.get(s) or (CHECK_ONLY if s in self.twin_of else self.auto_folder.get(s, ""))
            items = list(offload.FOLDERS)
            if want and want not in items and want != CHECK_ONLY:
                items.append(want)                       # a folder he typed, or one the app found (fx30, a7s3...)
            values = items + [CHECK_ONLY, OTHER]
            combo.addItems([i18n.T(x) if x in (CHECK_ONLY, OTHER) else x for x in values])
            combo.setCurrentIndex(values.index(want) if want in values else 0)
            fcol = QVBoxLayout()
            fcol.addWidget(combo)
            other = QLineEdit()
            other.setPlaceholderText(i18n.T("Name of the camera folder"))
            other.setVisible(False)
            fcol.addWidget(other)

            def picked(i, s=s, values=values, other=other):
                if values[i] == OTHER:
                    other.setVisible(True)
                    other.setFocus()
                else:
                    other.setVisible(False)
                    self.choice[s] = values[i]
                    self._where()
            combo.currentIndexChanged.connect(picked)
            other.editingFinished.connect(lambda s=s, other=other: other.text().strip() and (
                self.choice.__setitem__(s, other.text().strip()), self._rows()))
            self.row_combos.append(combo)
            h.addLayout(fcol)
            self.card_box.addWidget(row)
        self.card_box.addStretch()
        self._where()
        self._buttons()

    def _folder(self, s):
        return self.choice.get(s) or (CHECK_ONLY if s in self.twin_of else self.auto_folder.get(s, "")) or Path(s).name

    def add_folder(self, d=None):
        if not d:
            d = QFileDialog.getExistingDirectory(self, "A folder to copy (a card reader, a backup)")
        if d and d not in self.extra:
            self.extra.append(d)
            self.refresh()

    def pick_dest(self, d=None):
        if not d:
            d = QFileDialog.getExistingDirectory(self, "Where the footage goes (your drive)", self.cfg.get("dest", ""))
        if d:
            self.cfg["dest"] = d
            self.store.save_app()
            self._where()
            self._buttons()

    def pick_backup(self, d=None):
        if not d:
            d = QFileDialog.getExistingDirectory(self, "Where the backup copy goes (your backup drive)",
                                                 self.cfg.get("backup_dest", ""))
        if d:
            self.cfg["backup_dest"] = d
            self.store.save_app()
            self._where()
            self._buttons()

    def start_backup(self, root=None):
        """Copy the wedding folder again to the backup drive (also after an offload, when the option is ticked)."""
        if self._busy():
            notify("Wait for the current copy to finish (or Cancel it).", error=True)
            return
        dest = self.cfg.get("backup_dest")
        if not dest:
            notify("Choose the backup drive first.", error=True)
            return
        root = Path(root) if root else self._root() if self.cfg.get("dest") else None
        if not root or not root.is_dir():
            notify("The wedding folder is not there yet: copy the cards first (or check the wedding name).", error=True)
            return
        if not Path(dest).exists():
            notify(i18n.T("The backup drive is not connected: {}").format(dest), error=True)
            return
        self._stop = False
        self.bworker = _BackupWorker(root, dest, self.opts["verify"].isChecked(), lambda: self._stop)
        self.bworker.moved.connect(lambda d, t: self.pp.set(i18n.T("Backup: copying and checking {}%").format(int(100 * d / t)), d / t))
        self.bworker.ended.connect(self._backup_ended)
        self.bworker.finished.connect(self._buttons)
        self._backup_root = root
        self.pp.start(i18n.T("Backup of {}…").format(root.name))
        self.pp.allow_cancel(self.cancel)
        job_mark("backup")
        self.bworker.start()
        self._buttons()
        logging.info("backup of %s to %s", root, dest)

    def _backup_ended(self, r, err):
        self.pp.hide()
        self.pp.allow_cancel(None)
        dest = Path(self.cfg.get("backup_dest", "")) / self._backup_root.name
        if err == "Cancelled":
            notify("Backup stopped: what is copied is kept", error=True)
            line = f'<span style="color:{C["POOR"]}">' + i18n.T("Backup stopped: what is copied is kept") + "</span>"
        elif err:
            notify(i18n.T("Backup failed: {}").format(i18n.T(err)), error=True)
            line = f'<span style="color:{C["POOR"]}">' + i18n.T("Backup failed: {}").format(escape(i18n.T(err))) + "</span>"
        elif r["failed"]:
            notify(i18n.T("Backup finished with problems: {} files failed").format(r["failed"]), error=True)
            line = f'<span style="color:{C["POOR"]}">' + i18n.T("Backup finished with problems: {} files failed").format(r["failed"]) + "</span>"
        else:
            notify(i18n.T("Backup done and checked: {} files in {}").format(r["files"], str(dest)), took="backup")
            line = (f'<b style="color:{C["GOOD"]}">✓</b> ' + i18n.T("Backup: {} files, {} GB · {} checked, {} already there").format(
                r["files"], f"{r['bytes'] / 1e9:.1f}", r["verified"], r["already"]) + f" → {escape(str(dest))}")
        self._backup_line = line
        self._show()
        self._buttons()

    def _root(self):
        return Path(self.cfg["dest"]) / ((self.cfg.get("wedding") or "").strip() or time.strftime("Offload %Y-%m-%d"))

    def _where(self):
        d = self.cfg.get("dest") or ""
        self.dest_lbl.setText(d or i18n.T("No destination yet."))
        b = self.cfg.get("backup_dest") or ""
        self.backup_lbl.setText((b + "/" + ((self.cfg.get("wedding") or "").strip() or "…")) if b else
                                i18n.T("No backup drive yet."))
        if not d:
            self.where.setText("")
            return
        lines = [f"<b>{escape((self.cfg.get('wedding') or '').strip() or '…')}</b>"]
        for s in self._ticked_paths():
            f = self._folder(s)
            if f != CHECK_ONLY:
                lines.append(f"&nbsp;&nbsp;&nbsp;{escape(f)} &larr; {escape(Path(s).name)}")
        self.where.setText("<br>".join(lines))

    def _ticked_paths(self):
        return [cb.property("src") for cb in getattr(self, "row_cbs", []) if cb.isChecked()]

    def _ticked(self):
        return [Path(s) for s in self._ticked_paths()]

    def _busy(self):
        return any(w.isRunning() for w in self.workers) or bool(self.bworker and self.bworker.isRunning())

    def _buttons(self):
        busy = self._busy()
        self.b_start.setEnabled(not busy and bool(self.cfg.get("dest")) and bool(self._ticked()))
        self.b_backup.setEnabled(not busy and bool(self.cfg.get("backup_dest")) and bool(self.cfg.get("dest")))
        self.b_cancel.setVisible(busy)

    # ---- copying
    def start(self):
        root = self._root()
        opts = {k: cb.isChecked() for k, cb in self.opts.items()}
        opts["window"] = self._window()
        self._stop = False
        self.workers, self.state, self.waiting = [], {}, {}
        self._reported = False                           # the end of this offload is reported once
        self._backup_line = ""
        jobs = []
        for s in self._ticked_paths():
            f = self._folder(s)
            if f == CHECK_ONLY:
                twin = self.twin_of.get(s)
                if twin is None or twin not in self._ticked_paths():
                    notify("A backup card to check has no ticked twin to compare with", error=True)
                    return
                jobs.append((s, root / self._folder(twin), True, twin))
            else:
                jobs.append((s, root / f, False, None))
        for k, (s, dest, check, twin) in enumerate(jobs):
            w = _OffloadWorker(k, Path(s), dest, opts, lambda: self._stop, check_only=check)
            w.moved.connect(self._moved)
            w.ended.connect(self._ended)
            w.finished.connect(self._maybe_all_done)    # 'ended' runs while the thread is still running
            self.state[k] = dict(name=Path(s).name, src=s, folder=dest.relative_to(root), done=0.0, total=1.0, result=None,
                                 error=None, check=check, twin=twin)
            self.workers.append(w)
        self.pp.start(i18n.T("Copying {} cards…").format(len(jobs)))
        self.pp.allow_cancel(self.cancel)
        job_mark("offload")
        for k, w in enumerate(self.workers):
            if not self.state[k]["check"]:
                w.start()                                  # a backup card is checked when its twin's copy is finished
        self._show()
        self._buttons()
        logging.info("offload of %d cards to %s", len(jobs), root)

    def cancel(self):
        self._stop = True

    def _moved(self, k, d, t):
        self.state[k].update(done=d, total=t)
        D = sum(s["done"] for s in self.state.values())
        T = sum(s["total"] for s in self.state.values())
        self.pp.set(i18n.T("Copying and checking: {}%").format(int(100 * D / max(1, T))), D / max(1, T))
        self._show()

    def _ended(self, k, result, error):
        self.state[k].update(result=result, error=error)
        for j, s in self.state.items():                    # its backup twins can be checked now
            if s["check"] and s["twin"] == self.state[k]["src"] and not self.workers[j].isRunning() and s["result"] is None and not s["error"]:
                if error:
                    s["error"] = "Its twin could not be copied"
                else:
                    self.workers[j].start()
        self._maybe_all_done()
        self._show()

    def _maybe_all_done(self):
        if not self._busy() and self.state and all(s["result"] is not None or s["error"] for s in self.state.values()):
            QTimer.singleShot(100, self._all_done)
        self._buttons()

    def _all_done(self):
        if self._busy() or getattr(self, "_reported", True):
            return
        self._reported = True                            # once per offload, whichever signal comes last
        self.pp.hide()
        self.pp.allow_cancel(None)
        failed = sum((s["result"] or {}).get("failed", 0) + (s["result"] or {}).get("different", 0) +
                     (s["result"] or {}).get("missing", 0) for s in self.state.values())
        bad = [s["name"] for s in self.state.values() if s["error"] and s["error"] != "Cancelled"]
        if any(s["error"] == "Cancelled" for s in self.state.values()):
            notify("Offload stopped: what is copied is kept", error=True)
        elif failed or bad:
            notify(f"Offload finished with problems: {failed} files failed", error=True)
        else:
            n = sum((s["result"] or {}).get("files", 0) for s in self.state.values() if not s["check"])
            notify(f"Every card copied and checked: {n} files", took="offload")
            if self.opts["project"].isChecked() and hasattr(self.window(), "auto_project"):
                root = str(self._root())
                QTimer.singleShot(1200, lambda: self.window().auto_project(root))
            if self.opts["backup"].isChecked():
                if self.cfg.get("backup_dest"):
                    QTimer.singleShot(800, lambda: self.start_backup(self._root()))
                else:
                    notify("Choose the backup drive first.", error=True)
            if self.opts["eject"].isChecked():
                for s in self.state.values():
                    if str(s["src"]).startswith("/Volumes/"):
                        offload.eject(s["src"])
                QTimer.singleShot(1500, lambda: self.refresh(force=True))
        self._show()
        self._buttons()

    def _show(self):
        rows = []
        for s in self.state.values():
            r = s["result"]
            head = f'<b>{escape(s["name"])}</b> → {escape(str(s["folder"]))}'
            if r and s["check"]:
                ok = r["different"] == 0 and r["missing"] == 0
                txt = i18n.T("backup checked: {} of {} files the same as the copy").format(r["same"], r["files"])
                if r.get("added"):
                    txt += " · " + i18n.T("{} files were only on this card: copied from it").format(r["added"])
                if not ok:
                    txt += f' · <span style="color:{C["POOR"]}">' + i18n.T("{} different, {} missing").format(r["different"], r["missing"]) + "</span>"
                rows.append(f'<b style="color:{C["GOOD"] if ok else C["POOR"]}">{"✓" if ok else "✕"}</b> {head}: {txt}')
            elif r:
                ok = r["failed"] == 0
                txt = (i18n.T("{} files, {} GB · {} checked, {} already there").format(r["files"], f"{r['bytes'] / 1e9:.1f}", r["verified"], r["already"])
                       + (f' · {i18n.T("{} renamed (a different file had the name)").format(r["renamed"])}' if r["renamed"] else "")
                       + (f' · <span style="color:{C["POOR"]}">{i18n.T("{} FAILED (see the report)").format(r["failed"])}</span>' if r["failed"] else ""))
                rows.append(f'<b style="color:{C["GOOD"] if ok else C["POOR"]}">{"✓" if ok else "✕"}</b> {head}: {txt}')
            elif s["error"]:
                rows.append(f'<b style="color:{C["POOR"]}">✕</b> {head}: {escape(i18n.T(s["error"]))}')
            elif s["check"] and not s["done"]:
                rows.append(f'<span style="color:{C["MUTED"]}">…</span> {head}: ' + i18n.T("waiting for its twin's copy, then checked"))
            else:
                rows.append(f'<span style="color:{C["MUTED"]}">…</span> {head}: {int(100 * s["done"] / max(1, s["total"]))}%')
        if getattr(self, "_backup_line", ""):
            rows.append(self._backup_line)
        self.status.setText("<br>".join(rows))


# ---------------------------------------------------------------- Transcribe

class _TranscribeWorker(QThread):
    progress = Signal(str, float)
    one = Signal(str, object, str)                 # path, segments, error
    qual = Signal(str, object)                     # path, quality report (measured)
    ended = Signal(str)                            # "" or the reason it stopped

    def __init__(self, paths, base, lang, quality, stop, names=()):
        super().__init__()
        self.paths, self.base, self.lang, self.quality, self.stop = paths, base, lang, quality, stop
        self.names = list(names)

    def run(self):
        try:
            model = transcribe.load_model(self.base, self.quality, lambda t, f: self.progress.emit(t, f))
        except Exception as e:
            logging.exception("speech model failed")
            self.ended.emit(str(e))
            return
        for k, p in enumerate(self.paths):
            if self.stop():
                self.ended.emit("Cancelled")
                return
            try:
                keep = {}
                segs = transcribe.transcribe(p, model, self.lang, lambda t, f, k=k: self.progress.emit(
                    f"{k + 1} / {len(self.paths)} · {t}", (k + f) / len(self.paths)), self.stop, self.names, keep)
                q = transcribe.quality(segs, keep.get(p))
                transcribe.write_files(p, segs, q, i18n.T)
                self.qual.emit(p, q)
                self.one.emit(p, segs, "")
            except InterruptedError:
                self.ended.emit("Cancelled")
                return
            except Exception as e:
                logging.exception("transcription failed: %s", p)
                self.one.emit(p, None, str(e))
        self.ended.emit("")


class _WeddingTestWorker(QThread):
    """The quality test on several weddings (qualitytest.py): transcribe + measure every wedding of the test folder."""
    progress = Signal(str, float)
    ended = Signal(str)
    done = Signal(object)

    def __init__(self, folder, base, lang, quality, stop):
        super().__init__()
        self.folder, self.base, self.lang, self.quality, self.stop = folder, base, lang, quality, stop

    def run(self):
        import qualitytest
        try:
            model = transcribe.load_model(self.base, self.quality, lambda t, f: self.progress.emit(t, f))
            out = qualitytest.run_all(self.folder, model, self.lang, VER, lambda t, f: self.progress.emit(t, f), self.stop,
                                      i18n.T)
            self.done.emit(out)
            self.ended.emit("")
        except InterruptedError:
            self.ended.emit("Cancelled")
        except Exception as e:
            logging.exception("wedding test failed")
            self.ended.emit(str(e))


class TranscribePage(QWidget):
    """Local speech-to-text for interviews, speeches, the vornic, the sermon (see transcribe.py)."""

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.cfg = store.app.setdefault("transcribe", dict(files=[], lang="ro", quality="fast"))
        self.worker, self._stop = None, False
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(lbl("Transcribe", "h1"))
        top.addStretch()
        self.b_go = btn("Transcribe", "primary", self.start)
        top.addWidget(self.b_go)
        v.addLayout(top)
        v.addWidget(lbl("Interviews, speeches, the vornic, the sermon: the speech becomes text, on this computer (nothing is "
                        "uploaded). Next to every file you get a .txt with the times and a .srt (subtitles). From the bride's and the "
                        "groom's interviews Claude can make ONE story they tell together (below). The first time the "
                        "speech model is downloaded once (1.5-3 GB).", "muted", True))
        v.addSpacing(10)
        self.why = lbl("", "muted", True)
        v.addWidget(self.why)
        body = QHBoxLayout()
        body.setSpacing(20)
        v.addLayout(body, 1)
        left = QVBoxLayout()
        left.addWidget(lbl("FILES", "section"))
        self.list = QListWidget()
        self.list.setMinimumWidth(340)
        box = (f"background:#181818;border:1px solid {C['BORDER']};border-radius:6px;padding:6px;")
        self.list.setStyleSheet(f"QListWidget{{{box}}} QListWidget::item{{padding:6px 4px}}")
        self.list.currentRowChanged.connect(self._show)
        self.list.itemChanged.connect(self._ticked)
        self.list.keyPressEvent = self._list_key
        self.list.setStyleSheet(self.list.styleSheet() +
                                "QListWidget::indicator{width:16px;height:16px;border:1px solid #6a6a6a;border-radius:4px;background:#232323}"
                                f"QListWidget::indicator:checked{{background:{C['HOT']};border-color:{C['HOT']};image:url({_check_png()})}}")
        left.addWidget(self.list, 1)
        fr = QHBoxLayout()
        fr.addWidget(btn("+  Add files", slot=lambda: self.add()))
        fr.addWidget(btn("Import XML", slot=lambda: self.import_xml()))
        fr.addWidget(btn("Remove", slot=self.remove))
        fr.addStretch()
        left.addLayout(fr)
        wr = QHBoxLayout()
        self.l_who = lbl("Who is speaking", "muted")
        wr.addWidget(self.l_who)
        self.c_who = QComboBox()
        self.c_who.setProperty("i18n", True)
        self.c_who.addItems(["Not set", "The bride", "The groom", "The bride and the groom", "Someone else"])
        self.c_who.setMinimumWidth(220)
        self.c_who.currentIndexChanged.connect(self._who)
        wr.addWidget(self.c_who)
        self.e_name = QLineEdit()
        self.e_name.setPlaceholderText(i18n.T("First name"))
        self.e_name.setMaximumWidth(180)
        self.e_name.editingFinished.connect(self._name)
        wr.addWidget(self.e_name)
        wr.addStretch()
        left.addLayout(wr)
        opt = QHBoxLayout()
        opt.addWidget(lbl("Language", "muted"))
        self.c_lang = QComboBox()
        self.c_lang.setProperty("i18n", True)
        self.c_lang.addItems(["Romanian", "English", "Detect it"])
        self.c_lang.setMinimumWidth(150)
        self.c_lang.setCurrentIndex(["ro", "en", "auto"].index(self.cfg.get("lang", "ro")))
        self.c_lang.currentIndexChanged.connect(lambda i: (self.cfg.update(lang=["ro", "en", "auto"][i]), self.store.save_app()))
        opt.addWidget(self.c_lang)
        opt.addWidget(lbl("Precision", "muted"))
        self.c_q = QComboBox()
        self.c_q.setProperty("i18n", True)
        self.c_q.addItems(["Fast (large-v3-turbo)", "The most precise (large-v3, slower)"])
        self.c_q.setMinimumWidth(280)
        self.c_q.setCurrentIndex(0 if self.cfg.get("quality", "fast") == "fast" else 1)
        self.c_q.currentIndexChanged.connect(lambda i: (self.cfg.update(quality=["fast", "best"][i]), self.store.save_app()))
        opt.addWidget(self.c_q)
        left.addLayout(opt)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        right.addWidget(lbl("TEXT", "section"))
        self.text = QTextBrowser()
        self.text.setStyleSheet(f"QTextBrowser{{background:#181818;border:1px solid {C['BORDER']};border-radius:6px;padding:10px}}")
        right.addWidget(self.text, 1)
        self.q_lbl = lbl("", "muted", True)
        right.addWidget(self.q_lbl)
        rb = QHBoxLayout()
        self.b_copy = btn("Copy the text", slot=self.copy)
        self.b_qrep = btn("Quality report", slot=self.quality_report)
        self.b_test = btn("Test on several weddings…", slot=self.wedding_test)
        self.b_test.setToolTip(i18n.T("A folder with one sub-folder per wedding (the interviews + the source XML): every "
                                      "wedding is transcribed and measured, and compared with the previous version."))
        self.b_xml = btn("Export XML with markers", slot=self.export)
        self.b_xml.hide()                          # owner: one interview with markers is not useful (the story is)
        rb.addWidget(self.b_copy)
        rb.addWidget(self.b_qrep)
        rb.addWidget(self.b_xml)
        rb.addStretch()
        rb.addWidget(self.b_test)
        right.addLayout(rb)
        right.addSpacing(8)
        right.addWidget(lbl("THE STORY OF THE INTERVIEWS (WITH CLAUDE)", "section"))
        self.story_help = lbl("", "muted", True)
        right.addWidget(self.story_help)
        sb = QHBoxLayout()                       # own row: both buttons fit in Romanian too
        self.b_ask = btn("1. Copy for Claude", "primary", self.ask_claude)
        self.b_answer = btn("2. Paste Claude's answer", slot=self.claude_answer)
        sb.addWidget(self.b_ask)
        sb.addWidget(self.b_answer)
        sb.addStretch()
        right.addLayout(sb)
        right.addWidget(davinci_tick(self.store, self.cfg))
        self.story_status = lbl("", "muted", True)
        right.addWidget(self.story_status)
        self.pp = ProgressPanel()
        right.addWidget(self.pp)
        body.addLayout(right, 2)
        miss = transcribe.available()
        if miss:
            self.why.setText(f'<span style="color:{C["POOR"]}">' + i18n.T("The speech engine is missing from this build ({}).").format(miss) + "</span>")
        self._fill()

    def _drop(self, paths):
        """Finder drop: an XML = your sequence with the interviews (Import XML); sound / video files and folders are
        added."""
        xmls, rest = _xml_or_rest(paths)
        if xmls:
            self.import_xml(xmls[0])
        media = []
        for p in rest:
            q = Path(p)
            cands = sorted(q.rglob("*")) if q.is_dir() else [q]
            media += [str(c) for c in cands if c.is_file() and not c.name.startswith(".") and not is_proxy(c)
                      and c.suffix.lower() in (core.VIDEO_EXT | sync.AUDIO_EXT)]
        if media:
            self.add(media)
        elif rest and not xmls:
            notify(i18n.T("No sound or video files in what you dropped."), error=True)

    def _files(self):
        return self.cfg["files"]

    def _fill(self, select=None):
        self.list.blockSignals(True)
        self.list.clear()
        names = {"bride": "The bride", "groom": "The groom", "both": "The bride and the groom", "other": "Someone else"}
        for f in self._files():
            mark = (("✓" if f.get("tv", 0) >= transcribe.VERSION else "↻") if f.get("segs") is not None
                    else ("✕" if f.get("error") else "·"))
            who = (f"  ·  {i18n.T(names[f['who']])}" if f.get("who") in names else "") + \
                (f" {f['name']}" if (f.get("name") or "").strip() else "")
            longs = [i for i, sg in enumerate(f.get("segs") or [], 1) if sg[1] - sg[0] > transcribe.MAX_PIECE]
            warn = ("  ·  " + i18n.T("⚠ {} pieces over 8 s").format(len(longs))) if longs else ""
            glued = len((f.get("quality") or {}).get("glued") or [])
            if glued and f.get("tv", 0) >= transcribe.VERSION:
                warn += "  ·  " + i18n.T("⚠ {} questions glued").format(glued)
            it = QListWidgetItem(f"{mark}  {Path(f['path']).name}{who}{warn}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if f.get("story", True) else Qt.Unchecked)
            it.setToolTip(i18n.T("Ticked = goes into the story") + (
                "\n" + i18n.T("Pieces over 8 s: {}").format(", ".join(map(str, longs[:12]))) if longs else ""))
            self.list.addItem(it)
        self.list.blockSignals(False)
        if self._files():
            self.list.setCurrentRow(select if select is not None else 0)
        self._show(self.list.currentRow())
        self._buttons()

    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _buttons(self):
        f = self._cur()
        self.b_go.setEnabled(not self._busy() and not transcribe.available() and bool(self._todo()))
        self.b_copy.setEnabled(bool(f and f.get("segs")))
        self.b_qrep.setEnabled(bool(f and f.get("quality") and f.get("segs") is not None))
        self.b_test.setEnabled(not self._busy() and not transcribe.available())
        self.b_xml.setEnabled(bool(f and f.get("segs")))
        self.b_ask.setEnabled(not self._busy() and bool(self._story_files()))
        self.b_answer.setEnabled(not self._busy() and bool(self.cfg.get("story_paths")))
        n = len(self._story_files())
        auto = bool(self._key())
        self.b_ask.setText(i18n.T("Make the story with Claude") if auto else i18n.T("1. Copy for Claude"))
        self.b_answer.setVisible(not auto)
        self.story_help.setText(i18n.T(
            "Automatic (your Claude API key, Settings): tick the interviews, set who is speaking and press Make the story "
            "with Claude. Claude weaves them theme by theme and the XML is saved next to the first interview.") if auto else i18n.T(
            "Tick the interviews in the list (who is speaking is optional: Claude finds the groom and the bride). 1: the app "
            "copies the transcripts and opens a new Claude chat: paste (Cmd+V) and send. 2: copy Claude's whole answer and "
            "press Paste Claude's answer: you get an XML with the story."))
        old = [f for f in self._files() if f.get("segs") and f.get("tv", 0) < transcribe.VERSION]
        if self._busy():
            st = i18n.T("Wait: the app is working.")
        elif old:
            st = i18n.T("{} files were transcribed by an older version (long pieces, marked ↻): press Transcribe to redo "
                        "them in short sentences, so they can be interleaved.").format(len(old))
        elif auto and n:
            st = i18n.T("Ready: {} interviews ticked. Press Make the story with Claude.").format(n)
        elif not n:
            st = i18n.T("Step 1 is ready once an interview is transcribed (✓) and ticked.")
        elif self.cfg.get("story_paths"):
            st = i18n.T("Sent to Claude at {} ({} interviews). When Claude has answered, press step 2 and paste its answer.").format(
                self.cfg.get("story_sent", "?"), len(self.cfg["story_paths"]))
        else:
            st = i18n.T("Ready: {} interviews ticked. Press step 1.").format(n)
        self.story_status.setText(st)
        self.c_who.blockSignals(True)
        self.c_who.setEnabled(f is not None)
        self.l_who.setStyleSheet("" if f is not None else "color:#5e5e5e")
        self.c_who.setToolTip("" if f is not None else i18n.T("Add a file and select it in the list first."))
        self.c_who.setCurrentIndex(["", "bride", "groom", "both", "other"].index(f.get("who") or "") if f else 0)
        self.c_who.blockSignals(False)
        self.e_name.blockSignals(True)
        self.e_name.setEnabled(f is not None)
        self.e_name.setText((f.get("name") or "") if f else "")
        self.e_name.blockSignals(False)

    def _cur(self):
        r = self.list.currentRow()
        return self._files()[r] if 0 <= r < len(self._files()) else None

    def add(self, fs=None):
        if fs is None:
            fs, _ = QFileDialog.getOpenFileNames(self, "Files to transcribe (sound or video)", "",
                                                 "Sound / video (*.wav *.WAV *.mp3 *.m4a *.aif *.aiff *.flac *.mp4 *.MP4 *.mov *.MOV *.mxf *.MXF);;All files (*)")
        have = {f["path"] for f in self._files()}
        for f in fs:
            if f not in have:
                self._files().append(dict(path=f, segs=None))
        self.store.save_app()
        self._fill(select=len(self._files()) - 1 if fs else None)

    def remove(self):
        """Takes the selected file off the list (the file and its .txt / .srt stay on the disk)."""
        r = self.list.currentRow()
        if self._busy():
            notify(i18n.T("Wait: the app is working."), error=True)
            return
        if not (0 <= r < len(self._files())):
            notify(i18n.T("Select a file in the list first."), error=True)
            return
        gone = self._files()[r]["path"]
        del self._files()[r]
        if gone in self.cfg.get("story_paths", []):
            self.cfg.pop("story_paths", None)              # the codes A, B... would point to other files
        self.store.save_app()
        self._fill(select=min(r, len(self._files()) - 1) if self._files() else None)

    def _list_key(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove()
        else:
            QListWidget.keyPressEvent(self.list, e)

    def import_xml(self, path=None):
        """The interviews of a Premiere / DaVinci timeline (FCP7 XML), in the timeline's order."""
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Import XML", "", "XML (*.xml)")
        if not path:
            return
        try:
            found, missing = xmlimport.interviews(path)    # one file per interview segment (camera or lavalier)
        except Exception as ex:
            logging.exception("transcribe xml import")
            notify(i18n.T("Import XML failed: {}").format(i18n.T(str(ex))), error=True)
            return
        have = {f["path"]: f for f in self._files()}
        new = [p for p in found if p not in have]
        for p in new:
            self._files().append(dict(path=p, segs=None, src_xml=path))
        for p in found:
            if p in have:
                have[p]["src_xml"] = path                    # the story copies its clips from this sequence
        self.store.save_app()
        self._fill(select=len(self._files()) - 1 if new else None)
        if not found:
            notify(i18n.T("None of the clips in this XML were found on this computer (e.g. {}). Is the footage disk connected?")
                   .format(missing[0] if missing else "?"), error=True)
        elif missing:
            notify(i18n.T("{} clips added from the XML, in its order. {} clips are not on this computer and were skipped.")
                   .format(len(new), len(missing)), error=True, ms=9000)
        elif not new:
            notify(i18n.T("Every clip of this XML is already in the list."))
        else:
            notify(i18n.T("{} clips added from the XML, in its order.").format(len(new)))

    def _ticked(self, it):
        r = self.list.row(it)
        if 0 <= r < len(self._files()):
            self._files()[r]["story"] = it.checkState() == Qt.Checked
            self.store.save_app()
            self._buttons()

    def _who(self, i):
        f = self._cur()
        if f is not None:
            f["who"] = ["", "bride", "groom", "both", "other"][i]
            self.store.save_app()
            self._fill(select=self.list.currentRow())

    def _name(self):
        f = self._cur()
        if f is not None and (f.get("name") or "") != self.e_name.text().strip():
            f["name"] = self.e_name.text().strip()
            self.store.save_app()
            self._fill(select=self.list.currentRow())

    def _story_files(self):
        """Ticked and transcribed by this version (sentence pieces: an older transcript cannot be interleaved)."""
        return [f for f in self._files() if f.get("story", True) and f.get("segs") and f.get("tv", 0) >= transcribe.VERSION]

    def _key(self):
        return ""        # owner: no Claude API key (the story goes through his Claude subscription, copy / paste)

    def ask_claude(self):
        if self._key():
            return self._auto_story()
        fs = self._story_files()
        if not fs:
            notify(i18n.T("Transcribe and tick at least one interview first."), error=True)
            return
        if len(fs) > len(story.LETTERS):
            notify(i18n.T("Too many interviews ticked (at most {}).").format(len(story.LETTERS)), error=True)
            return
        text = story.prompt(fs, i18n.LANG)
        self.cfg["story_paths"] = [f["path"] for f in fs]      # the codes A, B... belong to these files
        self.cfg["story_sent"] = datetime.now().strftime("%H:%M")
        self.store.save_app()
        QApplication.clipboard().setText(text)
        QDesktopServices.openUrl(QUrl("https://claude.ai/new"))
        notify(i18n.T("Copied. In the new Claude chat paste it (Cmd+V) and send; then copy the whole answer and press "
                      "Paste Claude's answer."), ms=12000)
        self._buttons()

    def _auto_story(self):
        """With his Claude API key: prompt -> Claude -> story XML, in one press (in the background)."""
        fs = self._story_files()
        if not fs or self._busy():
            if not fs:
                notify(i18n.T("Transcribe and tick at least one interview first."), error=True)
            return
        if len(fs) > len(story.LETTERS):
            notify(i18n.T("Too many interviews ticked (at most {}).").format(len(story.LETTERS)), error=True)
            return
        text = story.prompt(fs, i18n.LANG)
        self.pp.start(i18n.T("Claude is writing the story… (usually 1-3 minutes)"))
        self.worker = _ClaudeWorker(text, self._key())
        self.worker.done.connect(lambda ans, fs=fs: (self.pp.hide(), self._make_story(fs, ans, auto=True)))
        self.worker.failed.connect(lambda m: (self.pp.hide(), notify(i18n.T("Claude could not make the story: {}").format(
            i18n.T(m)), error=True, ms=10000)))
        self.worker.finished.connect(self._buttons)
        self.worker.start()
        self._buttons()

    def claude_answer(self):
        by = {f["path"]: f for f in self._files()}
        fs = [by.get(p) for p in self.cfg.get("story_paths", [])]
        if not fs or any(f is None or not f.get("segs") for f in fs):
            notify(i18n.T("The interviews sent to Claude are no longer in the list: press Copy for Claude again."), error=True)
            return
        ans = self._paste_dialog()
        if ans is None:
            return
        if "=== INTERVI" in ans:                      # still the text for Claude, not its answer
            notify(i18n.T("The clipboard still holds the text for Claude. Send it in Claude, then copy Claude's answer."),
                   error=True, ms=10000)
            return
        self._make_story(fs, ans, auto=False)

    def _make_story(self, fs, ans, auto):
        """Claude's answer -> checks -> the story XML (owner's final spec: with an ERROR nothing is written, warnings
        are listed in a short report)."""
        pieces, errors, warnings = story.parse_checked(ans, fs)
        if not pieces and not errors:
            errors = ["The answer has no STORY_START / STORY_END list."]
        if errors:
            self._report(errors, warnings, written=None)
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            infos = {f["path"]: projectsetup.probe(f["path"]) for f in fs}
        finally:
            QApplication.restoreOverrideCursor()
        if any(infos[f["path"]].get("dur", 0) <= 0 for f in fs):
            notify(i18n.T("An interview file cannot be read any more. Is the disk connected?"), error=True)
            return
        durs = [infos[f["path"]]["dur"] for f in fs]
        used = {p[0] for p in pieces}
        audio = {}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for fi in used:                              # the cuts go into real pauses of the sound
                try:
                    audio[fi] = transcribe.read_audio(fs[fi]["path"])
                except Exception:
                    logging.exception("audio for the cuts: %s", fs[fi]["path"])
        finally:
            QApplication.restoreOverrideCursor()
        cuts = story.cut_times(pieces, fs, durs, audio=audio)
        e2, w2 = story.check_cuts(cuts, pieces, fs, durs)
        errors, warnings = errors + e2, warnings + w2
        if errors:
            self._report(errors, warnings, written=None)
            return
        names = {"bride": "Bride", "groom": "Groom", "both": "Bride and groom", "other": "Someone else"}
        found = story.parse_who(ans, len(fs))          # Claude says who is who when he did not set it
        labels = {}
        for k, f in enumerate(fs):
            w = f.get("who") or found.get(k)
            if w in names:
                labels[k] = i18n.T(names[w]) + (f" {f['name'].strip()}" if (f.get("name") or "").strip() else "")
            if not f.get("who") and found.get(k):
                f["who"] = found[k]                     # remembered (shown in the list)
        if found:
            self.store.save_app()
            self._fill(select=self.list.currentRow())
        first = Path(fs[0]["path"])
        base = Path(fs[0].get("src_xml") or first).stem if fs[0].get("src_xml") else i18n.T("Interview story")
        seqname = f"{base} - {i18n.T('STORY')}" if fs[0].get("src_xml") else base
        start = str(projectsetup.free_path(first.with_name(seqname + ".xml")))
        if auto:
            out = start
        else:
            out, _ = QFileDialog.getSaveFileName(self, "Save XML", start, "XML (*.xml)")
            if not out:
                return
        src = {f.get("src_xml") for f in fs}
        src = src.pop() if len(src) == 1 else None
        same = bool(src and Path(src).exists())         # all from the sequence he imported: copy HIS clips (his sound)
        tmp = str(out) + ".checking"

        def write(o):
            if same:
                return story.export_from_source(cuts, fs, src, o, seqname, labels)
            return story.export_xml(cuts, fs, infos, o, seqname, labels)
        try:
            r = write(tmp)
        except OSError:
            out, _ = QFileDialog.getSaveFileName(self, "Save XML", str(Path.home() / Path(start).name), "XML (*.xml)")
            if not out:
                return
            tmp = str(out) + ".checking"
            r = write(tmp)
        except Exception as e:
            logging.exception("story export failed")
            notify(i18n.T("Export failed: {}").format(i18n.T(str(e))), error=True)
            return
        x_err = story.check_xml(tmp)                    # links, clipindex, ticks, complete <file> first
        if x_err:
            Path(tmp).unlink(missing_ok=True)
            self._report(x_err, warnings, written=None)
            return
        os.replace(tmp, out)
        if target() == "davinci":              # he works in DaVinci Resolve: the same story for Resolve, made and checked
            QTimer.singleShot(0, lambda o=str(out): for_target(resolve.name_for(o, "davinci"), "davinci", src=o))
        n_in = good = 0
        speech = []
        for j, (fi, t0, t1, _t) in enumerate(cuts, 1):   # measured: does every cut fall into a real pause?
            for side, tt in (("in", t0), ("out", t1)):
                ok = transcribe.in_pause(audio.get(fi), tt)
                if ok is None:
                    continue
                n_in += 1
                good += bool(ok)
                if not ok:
                    speech.append(f"{j} {side} ({transcribe._at(tt)})")
        pct = round(100.0 * good / n_in, 1) if n_in else None
        rep_lines = [i18n.T("Story report: {}").format(Path(out).name),
                     i18n.T("Pieces: {}").format(len(cuts)),
                     (i18n.T("Cut in / out points in a real pause (target 95 % or more): {} % of {}").format(f"{pct:g}", n_in)
                      if pct is not None else i18n.T("Cut points in a real pause: not measured (no sound)"))]
        if speech:
            rep_lines.append(i18n.T("Cut points that fall in speech: {}").format(", ".join(speech[:40])))
        rep_lines.append(i18n.T("XML: links, overlaps, ticks, complete file: OK"))
        rep_lines += [i18n.T(w) for w in warnings]
        try:
            Path(out).with_name(Path(out).stem + "_raport.txt").write_text("\n".join(rep_lines) + "\n", encoding="utf-8")
        except OSError:
            pass
        if pct is not None and pct < 95:
            warnings = warnings + [f"Cut points that fall in speech: {', '.join(speech[:20])}"]
        pos, lines = 0.0, []
        for fi, t0, t1, txt in cuts:
            who = labels.get(fi) or f"{story.LETTERS[fi]}"
            lines.append(f"[{story._mmss(pos)}] {who}: {txt}")
            pos += t1 - t0
        self.text.setPlainText(i18n.T("The story ({} pieces, {}):").format(r["pieces"], story._mmss(r["seconds"])) +
                               "\n\n" + "\n\n".join(lines) + "\n\n" + "\n".join(rep_lines))
        self.story_out = str(out)
        msg = i18n.T("Story XML saved: {} pieces, {} long.").format(r["pieces"], story._mmss(r["seconds"]))
        if not same:
            msg += " " + i18n.T("For your exact sound tracks (mic and lavalier), import your Premiere sequence with Import XML (or drag it into the list).")
        if warnings:
            self._report([], warnings, written=out)
        notify(msg, ms=9000)

    def _report(self, errors, warnings, written):
        """The check report: errors (nothing was written) and / or warnings (the XML was written)."""
        d = QDialog(self)
        d.setWindowTitle(i18n.T("Story check"))
        d.resize(660, 440)
        v = QVBoxLayout(d)
        head = ("The XML was NOT written: fix these with Claude (ask it again) and paste the new answer." if errors
                else "The XML was written ({}). Have a look at these:".format(Path(written).name))   # lbl translates
        v.addWidget(lbl(head, "", True))
        box = QPlainTextEdit()
        box.setReadOnly(True)
        txt = ""
        if errors:
            txt += i18n.T("ERRORS") + "\n" + "\n".join("• " + i18n.T(e) for e in errors) + "\n\n"
        if warnings:
            txt += i18n.T("WARNINGS") + "\n" + "\n".join("• " + i18n.T(w) for w in warnings)
        box.setPlainText(txt.strip())
        v.addWidget(box, 1)
        row = QHBoxLayout()
        row.addStretch()
        if errors:
            row.addWidget(btn("Copy for Claude", slot=lambda: (QApplication.clipboard().setText(
                "Please fix your list, these codes are wrong:\n" + "\n".join(errors) +
                "\nAnswer again with the whole list between STORY_START and STORY_END."), notify(i18n.T("Copied.")))))
        row.addWidget(btn("OK", "primary", d.accept))
        v.addLayout(row)
        if errors:
            notify(i18n.T("The story has errors: the XML was not written."), error=True)
        d.exec()

    def _paste_dialog(self):
        """A window where he pastes Claude's answer (already filled when the clipboard holds it)."""
        d = QDialog(self)
        d.setWindowTitle(i18n.T("Claude's answer"))
        d.resize(640, 480)
        v = QVBoxLayout(d)
        v.addWidget(lbl("Paste here Claude's whole answer (Cmd+V), then press Make the story XML.", "muted", True))
        box = QPlainTextEdit()
        clip = QApplication.clipboard().text()
        if "STORY_START" in clip and "=== INTERVI" not in clip:
            box.setPlainText(clip)
        v.addWidget(box, 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn("Cancel", slot=d.reject))
        row.addWidget(btn("Make the story XML", "primary", d.accept))
        v.addLayout(row)
        box.setFocus()
        return box.toPlainText() if d.exec() == QDialog.Accepted else None

    def _show(self, r):
        f = self._files()[r] if 0 <= r < len(self._files()) else None
        if not f:
            self.text.setPlainText("")
        elif f.get("segs") is not None:
            qs = story.qflags(f)
            spk = f.get("spk") or []
            measured = any(lab in ("c", "v", "1", "2") for lab in spk)
            mark = lambda i: ("[" + i18n.T("QUESTION") + "] " if qs[i] else "") + \
                ("(?) " if len(spk) == len(qs) and spk[i] == "?" and measured else "")
            self.text.setPlainText("\n".join(f"[{int(a // 60)}:{a % 60:04.1f}] {mark(i)}{t}"
                                              for i, (a, b, t) in enumerate(f["segs"])) or i18n.T("No speech found."))
        elif f.get("error"):
            self.text.setPlainText(i18n.T("Error: {}").format(i18n.T(f["error"])))
        else:
            self.text.setPlainText(i18n.T("Not transcribed yet: press Transcribe."))
        q = f.get("quality") if f and f.get("segs") is not None and f.get("tv", 0) >= transcribe.VERSION else None
        if q:
            bad = q["over8"] or q["glued"] or (q.get("pause_pct") is not None and q["pause_pct"] < 95)
            self.q_lbl.setText(f'<span style="color:{C["POOR"] if bad else C["GOOD"]}">' + i18n.T("Quality") + ": " +
                               transcribe.quality_line(q, i18n.T) + "</span>")
        else:
            self.q_lbl.setText("")
        self._buttons()

    def _todo(self):
        """Not transcribed yet, or transcribed by an older version (long pieces, before the sentence split)."""
        return [f["path"] for f in self._files() if f.get("segs") is None or f.get("tv", 0) < transcribe.VERSION]

    def start(self):
        todo = self._todo()
        if not todo or self._busy():
            return
        self._stop = False
        names = [f["name"] for f in self._files() if (f.get("name") or "").strip()]
        self.worker = _TranscribeWorker(todo, self.store.dir, self.cfg.get("lang", "ro"), self.cfg.get("quality", "fast"),
                                        lambda: self._stop, names)
        self.worker.progress.connect(self.pp.set)
        self.worker.qual.connect(self._qual)
        self.worker.one.connect(self._one)
        self.worker.ended.connect(self._ended)
        self.pp.start(i18n.T("Transcribing {} files…").format(len(todo)))
        self.pp.allow_cancel(lambda: setattr(self, "_stop", True))
        self.worker.finished.connect(self._buttons)     # 'ended' runs while the thread is still running
        job_mark("transcribe")
        self.worker.start()
        self._buttons()

    def _qual(self, path, q):
        f = next((x for x in self._files() if x["path"] == path), None)
        if f is not None:
            f["quality"] = q

    def quality_report(self):
        f = self._cur()
        if not f or not f.get("quality"):
            return
        k = self._story_files().index(f) if f in self._story_files() else -1
        q = dict(f["quality"])
        if k >= 0:                                       # the codes as Claude sees them (A, B...)
            L = story.LETTERS[k]
            for key in ("over8", "under08", "glued"):
                q[key] = [L + c for c in q[key]]
            for key in ("in_speech", "forced"):
                q[key] = [" / ".join(L + y for y in x.split(" ")[0].split("/")) + " " + x.split(" ", 1)[1]
                          for x in q.get(key, [])]
        self._text_dialog(i18n.T("Quality report"), transcribe.quality_text(Path(f["path"]).name, q, i18n.T) + "\n" +
                          i18n.T("Saved next to the file: {}").format(Path(f["path"]).stem + "_raport.txt"))

    def _text_dialog(self, title, text, table=None):
        d = QDialog(self)
        d.setWindowTitle(title)
        d.resize(1180 if table else 660, 600 if table else 420)
        v = QVBoxLayout(d)
        if table is not None:
            v.addWidget(table)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        v.addWidget(box, 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn("Copy", slot=lambda: (QApplication.clipboard().setText(text), notify(i18n.T("Copied.")))))
        row.addWidget(btn("OK", "primary", d.accept))
        v.addLayout(row)
        d.exec()

    def wedding_test(self):
        if self._busy():
            return
        folder = QFileDialog.getExistingDirectory(self, i18n.T("The test folder (one sub-folder per wedding)"),
                                                  self.cfg.get("test_dir", str(Path.home())))
        if not folder:
            return
        import qualitytest
        plist = qualitytest.projects(folder)
        if not plist:
            notify(i18n.T("No wedding found: put one sub-folder per wedding (the interviews + the source XML) in it."),
                   error=True)
            return
        self.cfg["test_dir"] = folder
        self.store.save_app()
        self._stop = False
        self.worker = _WeddingTestWorker(folder, self.store.dir, self.cfg.get("lang", "ro"), self.cfg.get("quality", "fast"),
                                         lambda: self._stop)
        self.worker.progress.connect(self.pp.set)
        self.worker.done.connect(self._test_done)
        self.worker.ended.connect(self._test_ended)
        self.pp.start(i18n.T("Testing {} weddings…").format(len(plist)))
        self.pp.allow_cancel(lambda: setattr(self, "_stop", True))
        self.worker.finished.connect(self._buttons)
        self.worker.start()
        self._buttons()

    def _test_ended(self, why):
        self.pp.hide()
        self.pp.allow_cancel(None)
        if why and why != "Cancelled":
            notify(i18n.T("The test stopped: {}").format(i18n.T(why)), error=True)
        self._buttons()

    def _test_done(self, out):
        import qualitytest
        res, text, worse, prev, old = out
        cols = list(qualitytest.METRICS)
        t = QTableWidget(len(res), len(cols) + 1)
        t.setHorizontalHeaderLabels([i18n.T("Wedding")] + [i18n.T(qualitytest.METRICS[c][0]) for c in cols])
        t.verticalHeader().hide()
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for r, (name, m) in enumerate(res.items()):
            t.setItem(r, 0, QTableWidgetItem(name))
            for c, key in enumerate(cols, 1):
                val = m.get(key)
                o = (old.get(name) or {}).get(key)
                txt = "—" if val is None else f"{val:g}"
                if "error" in m:
                    txt = i18n.T("failed") if c == 1 else ""
                if o is not None and val is not None and o != val:
                    txt += f"  ({o:g})"
                got_worse = any(w.startswith(f"{name}: {i18n.T(qualitytest.METRICS[key][0])} ") for w in worse)
                it = QTableWidgetItem(("▼ " if got_worse else "") + txt)
                if got_worse or qualitytest.fails(key, val):
                    it.setForeground(QColor(C["POOR"]))
                t.setItem(r, c, it)
        t.resizeColumnsToContents()
        head = (i18n.T("WORSE than {}:").format(prev) + "\n" + "\n".join(worse) if worse else
                i18n.T("Nothing got worse than {}.").format(prev) if prev else
                i18n.T("First run: the next version will be compared with these numbers."))
        notify(head.split("\n")[0], error=bool(worse), ms=9000)
        self._text_dialog(i18n.T("Test on several weddings"), head + "\n\n" + text, table=t)

    def _one(self, path, segs, err):
        f = next((x for x in self._files() if x["path"] == path), None)
        if f is not None:
            f["segs"] = [list(s) for s in segs] if segs is not None else None
            f["spk"] = list(getattr(segs, "spk", None) or []) if segs is not None else []
            f["error"] = err or None
            if segs is not None:
                f["tv"] = transcribe.VERSION
            self.store.save_app()
        self._fill(select=self.list.currentRow())

    def _ended(self, why):
        self.pp.hide()
        self.pp.allow_cancel(None)
        if why and why != "Cancelled":
            notify(f"Transcription stopped: {why}", error=True)
        elif not why:
            bad = sum(1 for f in self._files() if f.get("error"))
            notify("Transcription finished" + (f": {bad} files failed" if bad else ""), error=bool(bad), took="transcribe")
        self._buttons()

    def copy(self):
        f = self._cur()
        if f and f.get("segs"):
            QApplication.clipboard().setText(self.text.toPlainText())
            notify("Text copied")

    def export(self):
        f = self._cur()
        if not f or not f.get("segs"):
            return
        start = str(Path(f["path"]).with_name(Path(f["path"]).stem + " - transcript.xml"))
        out, _ = QFileDialog.getSaveFileName(self, "Save XML", start, "XML (*.xml)")
        if out:
            try:
                n = transcribe.export_markers(f["path"], [tuple(s) for s in f["segs"]], out)
                notify(f"XML saved: {Path(out).name} ({n} markers)")
            except Exception as e:
                logging.exception("transcript export failed")
                notify(f"Export failed: {e}", error=True)


# ---------------------------------------------------------------- project pages for Teaser Studio / Long Film

class _LF2Worker(QThread):
    """Long Film v2 build: reads the media (analyses, priest, first look, vornic, party sync + music)."""
    progress = Signal(str, float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, xml_path, vornic, cache, jobs, base, colours=None):
        super().__init__()
        self.xml_path, self.vornic, self.cache, self.jobs, self.base, self._stop = xml_path, vornic, cache, jobs, base, False
        self.colours = colours

    def run(self):
        try:
            made = None
            if Path(self.xml_path).is_dir():    # straight from the wedding folder: make the sequence first
                made = longfilm2.folder_xml(self.xml_path, lambda s, f: self.progress.emit(s, 0.04 * f),
                                            lambda: self._stop, jobs=max(2, self.jobs * 2))
                self.xml_path = made
            lo = 0.04 if made else 0.0      # the folder step first, then the Build: one bar that never goes back
            r = longfilm2.build(self.xml_path, self.vornic, self.cache, lambda s, f: self.progress.emit(s, lo + (1 - lo) * f),
                                lambda: self._stop, self.jobs, self.base, self.colours)
            if made:
                r["footage_xml"] = made
            self.done.emit(r)
        except InterruptedError:
            self.failed.emit("Cancelled")
        except Exception as e:
            logging.exception("long film v2 build failed")
            self.failed.emit(str(e))


class LongFilm2Page(QWidget):
    """Long Film (v4.6.0: the old v2, no BETA any more): the long film from the wedding folder (automatic) or from the
    labelled sequence of Create Project, every colour its own way."""
    back = Signal()
    DROPS = [1, 2, 4, 8, 16]
    KEY = "long2"                    # store.app["<KEY>_projects"] / "<KEY>_current"
    BETA = False
    DESC = ("The long film from the wedding folder or from the sequence of Create Project. With your colours every colour "
            "is handled its own way; without colours the AI looks at every clip and finds the moments of the day itself "
            "(getting ready, first look, church, couple, venue, party). Then Edit the film to correct it. "
            "One 25 fps 1920x1080 sequence.")

    def __init__(self, store):
        super().__init__()
        self.store, self.worker, self.r, self.an, self.parts, self.info = store, None, None, {}, [], {}
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(btn("←  Projects", "link", lambda: self.back.emit()))
        self.pname = lbl("", "h2")
        top.addWidget(self.pname)
        badge = QLabel("BETA")
        badge.setStyleSheet(f"background:{C['POOR']};color:white;font-size:10px;font-weight:800;border-radius:9px;padding:2px 8px")
        top.addWidget(badge)
        badge.setVisible(self.BETA)
        top.addStretch()
        self.b_edit = btn("Edit the film", slot=self.edit_film)
        self.b_exp = ExportPair(self.export)
        self.b_build = btn("Build", slot=self.build)
        self.b_be = btn("Build + Edit", "primary", self.build_edit)
        self.b_be.setToolTip("Build, and the editor opens by itself as soon as the film is ready (good overnight).")
        self._then_edit = False
        top.addWidget(self.b_edit)
        top.addWidget(self.b_exp)
        top.addWidget(self.b_build)
        top.addWidget(self.b_be)
        v.addLayout(top)
        v.addWidget(lbl(self.DESC, "muted", True))
        v.addSpacing(8)
        body = QHBoxLayout()
        body.setSpacing(18)
        v.addLayout(body, 1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFixedWidth(430)
        lw = QWidget()
        left = QVBoxLayout(lw)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(10)
        self._left, self._cards = left, {}

        def card(n, title):
            f = QFrame()
            f.setObjectName("card")
            l = QVBoxLayout(f)
            l.setContentsMargins(16, 14, 16, 16)
            l.setSpacing(10)
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
            self._cards[title] = (f, num)
            return l
        self._card = card
        l1 = card(1, "Your wedding")
        l1.addWidget(lbl("<b>Automatic:</b> choose the wedding folder (the one Card Offload made). The app makes the "
                         "sequence itself (every camera + the recorder and the lavalieres) and finds the moments: getting "
                         "ready (the groom is filmed first, the faces tell groom and bride apart), the church (its long "
                         "clips), the venue (no faces) and the couple after it, the party, the drone. An XML of Create "
                         "Project without colours works the same way.<br><br>"
                         "<b>With your colours:</b> export from Premiere the sequence with your labels as XML (put the "
                         "recorder files in it too, for the party). Only the labelled cameras are used. The colours:<br>"
                         "• Blue groom, Rose bride: selection (Auto, minimum cut 2 s, threshold 60), in the order they were "
                         "filmed;<br>"
                         "• Teal first look: synced, the cameras one above the other;<br>"
                         "• Forest vornic: 2 cameras synced by their sound, cut automatically (switch below);<br>"
                         "• Brown church: selection; the priest's shot (at least 1 minute on him) stays whole;<br>"
                         "• Yellow venue, Purple couple, Violet drone: selection;<br>"
                         "• Iris or Cerulean party: multicam of every camera + the recorder, cut by the Auto Director;<br>"
                         "• Tan and the other colours are not used.<br>"
                         "The order of the parts = the order of the colours on camera A (V1 of a timecode sequence, the "
                         "first camera of a chronological one); the party always comes last.", "muted", True))
        r1 = QHBoxLayout()
        r1.addWidget(btn("Wedding folder…", "primary", self.pick_folder))
        r1.addWidget(btn("Import XML", slot=self.pick_xml))
        r1.addStretch()
        l1.addLayout(r1)
        self.foot_lbl = QLabel("")
        self.foot_lbl.setWordWrap(True)
        self.foot_lbl.setTextFormat(Qt.RichText)
        l1.addWidget(self.foot_lbl)
        l2 = card(2, "Vornic")
        vr = QHBoxLayout()
        vr.addWidget(lbl("This wedding has a vornic (Forest)", "", True), 1)
        self.sw_v = Switch(True)
        self.sw_v.toggled.connect(self._vornic)
        vr.addWidget(self.sw_v, 0, Qt.AlignTop)
        l2.addLayout(vr)
        l2.addWidget(lbl("ON: the Forest shots of 2 cameras are synced by their own sound: the main camera whole on V1, the "
                         "second camera whole on V2 (switched off), the cut version on V3. OFF: no vornic, Forest is not "
                         "used.", "muted", True))
        l2.addSpacing(8)
        l2.addWidget(lbl("Getting ready (groom and bride)"))
        rr = QHBoxLayout()
        self.b_ri = btn("Interleaved", "seg", lambda: self._ready("interleave"))
        self.b_rs = btn("One after the other", "seg", lambda: self._ready("sequential"))
        rr.addWidget(self.b_ri)
        rr.addWidget(self.b_rs)
        rr.addStretch()
        l2.addLayout(rr)
        l2.addWidget(lbl("Interleaved: groom and bride told in parallel (a big block of each, then turns of 3-5 shots). One "
                         "after the other: all the shots of the side filmed first, then the other side.", "muted", True))
        l4 = card(3, "Colour")
        cr = QHBoxLayout()
        cr.addWidget(lbl("Put my look on every clip", "", True), 1)
        self.sw_col = Switch(False)
        self.sw_col.toggled.connect(lambda on: self._look("on", on))
        cr.addWidget(self.sw_col, 0, Qt.AlignTop)
        l4.addLayout(cr)
        l4.addWidget(only_note("Premiere Pro only (Lumetri). For DaVinci Resolve the XML has no look and no crop: put "
                               "your LUT on Resolve's Color page."))
        self.cb_crop = QCheckBox("Crop 10 % at the top and at the bottom")
        self.cb_crop.toggled.connect(lambda on: self._look("crop", on))
        l4.addWidget(self.cb_crop)
        self.cb_layer = QCheckBox("Crop on an adjustment layer (straight into the open Premiere project)")
        self.cb_layer.toggled.connect(lambda on: self._look("layer", on))
        l4.addWidget(self.cb_layer)
        l4.addWidget(lbl("Like WarpAutomation's button: Export XML → Premiere imports the film into the project open in "
                         "Premiere, opens it and puts an adjustment layer with Crop 10 % on top of everything. Off: the crop "
                         "goes on every clip.", "muted", True))
        self.lut_rows = {}
        for k, title in (("1", "LUT"), ("2", "Second LUT (optional)")):
            l4.addWidget(lbl(title))
            rr = QHBoxLayout()
            name = lbl("None", "muted")
            rr.addWidget(name, 1)
            rr.addWidget(btn("Choose…", slot=lambda _=False, k=k: self._pick_lut(k)))
            rr.addWidget(btn("✕", "link", lambda _=False, k=k: self._look("lut" + k, None)))
            l4.addLayout(rr)
            sl = SliderRow("Intensity", "Like Premiere's Look intensity: 100 = the LUT as it is, up to 200.", 100, lo=0, hi=200)
            sl.changed.connect(lambda x, k=k: self._look("int" + k, x))
            l4.addWidget(sl)
            self.lut_rows[k] = (name, sl)
        l4.addWidget(lbl("The look (Lumetri) goes on every clip: to change it later, change the Lumetri of one clip in "
                         "Premiere, then paste its attributes on the others.", "muted", True))
        lc = card(4, "Clip colours")
        self.colcard = ColourCard()
        self.colcard.changed.connect(lambda c: (self.store.app.__setitem__("colours", dict(c)), self._remember(colours=c)))
        lc.addWidget(self.colcard)
        l3 = card(5, "Party · Auto Director")
        self.d_rows = {}
        for key, title, sub, lo, hi, suf in (
                ("minshot", "Minimum shot", "No shot is shorter than this.", 1, 10, " s"),
                ("maxshot", "Maximum shot", "After this the edit prefers to cut to another camera.", 4, 120, " s"),
                ("pace", "Cut pace", "Calm (few cuts) ↔ fast (many cuts).", 0, 100, ""),
                ("energy", "Static  ↔  Handheld", "Left = prefer the static cameras, right = prefer the handheld ones.", 0, 100, "")):
            r = SliderRow(title, sub, longfilm2.PARTY[key], lo=lo, hi=hi, suffix=suf)
            r.changed.connect(lambda x, k=key: self.set_d(k, x))
            self.d_rows[key] = r
            l3.addWidget(r)
        l3.addWidget(lbl("On a drop, change camera every"))
        self.c_drop = QComboBox()
        self.c_drop.setProperty("i18n", True)
        self.c_drop.addItems(["1 beat", "2 beats", "1 bar (4 beats)", "2 bars", "4 bars"])
        self.c_drop.currentIndexChanged.connect(lambda i: self.set_d("drop_beats", self.DROPS[i]))
        l3.addWidget(self.c_drop)
        l3.addWidget(lbl("Build-up before a drop"))
        self.c_build = QComboBox()
        self.c_build.setProperty("i18n", True)
        self.c_build.addItems(["Hold one shot until the drop", "Cut faster and faster"])
        self.c_build.currentIndexChanged.connect(lambda i: self.set_d("buildup", "hold" if i == 0 else "accelerate"))
        l3.addWidget(self.c_build)
        self.syncopt = SyncOptions(store)
        l3.addWidget(self.syncopt)
        l3.addWidget(lbl("Video track of every party camera (Auto: the static camera on V1, the main camera on top)",
                         "muted", True))
        self.trk_box = QFrame()
        self.trk_box.setObjectName("trkbox")
        self.trk_box.setStyleSheet(f"QFrame#trkbox{{background:{C['BG']};border:1px solid {C['BORDER']};border-radius:6px}}")
        self.trk_grid = QVBoxLayout(self.trk_box)
        self.trk_grid.setContentsMargins(0, 2, 0, 2)
        self.trk_grid.setSpacing(0)
        l3.addWidget(self.trk_box)
        l3.addWidget(btn("Back to my party settings", "link", self.reset_d), 0, Qt.AlignLeft)
        left.addStretch()
        sc.setWidget(lw)
        body.addWidget(sc)
        rsc = QScrollArea()                     # the right column scrolls too (nothing squeezed on small screens)
        rsc.setWidgetResizable(True)
        rsc.setFrameShape(QFrame.NoFrame)
        rw = QWidget()
        right = QVBoxLayout(rw)
        right.setContentsMargins(0, 0, 8, 0)
        right.addWidget(lbl("YOUR LONG FILM", "section"))
        self.table = QTableWidget(0, 3)
        self.table.setMinimumHeight(300)
        self.table.setHorizontalHeaderLabels(["Part", "Shots", "Length"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.table)
        self.status = lbl("Import your labelled XML, then press Build.", "muted", True)
        right.addWidget(self.status)
        self.pp = ProgressPanel()
        right.addWidget(self.pp)
        right.addSpacing(6)
        self._party_w = [lbl("PARTY", "section"),
                         lbl("Slower cuts (the hora): drag on the map to mark a zone; there the cuts follow your hora settings "
                             "(longer shots, not on the bars). Drag an edge to move it, right-click or Delete to remove it.",
                             "muted", True)]
        for w_ in self._party_w:
            right.addWidget(w_)
        self.map = SyncMap()
        self.map.zones_changed.connect(self._zones)
        right.addWidget(self.map)
        self.stats = lbl("", "muted", True)
        right.addWidget(self.stats)
        right.addStretch()
        right.addWidget(lbl("HOW YOUR SEQUENCE SHOULD LOOK", "section"))
        right.addWidget(lbl("The sequence of Create Project, every clip labelled by its MOMENT (not by camera): the "
                            "order of the colours on camera A gives the order of the film, the party always comes last. Put "
                            "the recorder files in the sequence too. Clips without a colour are not used.", "muted", True))
        self.smap = SelectsMap(SelectsMap.GROUPS_V2)
        right.addWidget(self.smap)
        rsc.setWidget(rw)
        body.addWidget(rsc, 1)
        self.timer = QTimer(singleShot=True, interval=300)
        self.timer.timeout.connect(self.recompute)
        self._buttons()

    # ---- project
    def _cur(self):
        pid = self.store.app.get(f"{self.KEY}_current")
        return next((p for p in self.store.app.setdefault(f"{self.KEY}_projects", []) if p["id"] == pid), None)

    def _remember(self, **kw):
        p = self._cur()
        if p is not None:
            p.update(kw, when=datetime.now().isoformat(timespec="seconds"))
            self.store.save_app()

    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _dir(self):
        p = self._cur() or {}
        return {**longfilm2.PARTY, **p.get("dir", {})}

    def open_project(self):
        p = self._cur()
        if p is None:
            return
        self.pname.setText(p["name"])
        d = self._dir()
        for k, r in self.d_rows.items():
            r.set(int(d[k]))
        for w_, i in ((self.c_drop, self.DROPS.index(d["drop_beats"]) if d["drop_beats"] in self.DROPS else 2),
                      (self.c_build, 0 if d["buildup"] == "hold" else 1)):
            w_.blockSignals(True)
            w_.setCurrentIndex(i)
            w_.blockSignals(False)
        self.sw_v.set(p.get("vornic", True))
        self._ready_ui()
        self._show_look()
        self.colcard.load(p.get("colours") or self.store.app.get("colours"))
        self.map.set_zones(p.get("zones", []))
        blob = self.store.load_blob(p["id"]) if p.get("built") else {}
        self.r = blob.get("result")
        self.an = {}
        for k, c in (blob.get("cache") or {}).items():
            try:
                self.an[k] = core.Analysis.from_json(c["a"])
            except Exception:
                pass
        self._cache = blob.get("cache") or {}
        self._summary()
        self.recompute()

    def _summary(self):
        p = self._cur() or {}
        f = p.get("footage")
        if not f:
            self.foot_lbl.setText("")
            return
        if Path(f).is_dir():
            self.foot_lbl.setText(f"<b>{escape(Path(f).name)}</b><br>" + i18n.T(
                "Wedding folder. Press Build: the app makes the sequence (every camera, the recorder and the lavalieres), "
                "syncs the cameras on the recorder, looks at the faces and finds the moments. It can take a few hours: "
                "leave it overnight."))
            return
        try:
            L = longfilm2.load(f)
        except Exception as e:
            self.foot_lbl.setText(f'<span style="color:{C["POOR"]}">' + i18n.T("Could not read the XML: {}").format(i18n.T(str(e))) + "</span>")
            return
        cnt = {}
        for q in L["pieces"]:
            cnt[q["label"]] = cnt.get(q["label"], 0) + 1
        cams = "<br>".join(f'{i18n.T("Camera")} {"ABCDEFGH"[i] if i < 8 else i + 1}: {escape(c["name"])}'
                           for i, c in enumerate(L["cams"]))
        lay = i18n.T("Timecode synchronized sequence") if L["layout"] == "timecode" else i18n.T("Chronological")
        if L.get("auto"):
            txt = (f"<b>{escape(Path(f).name)}</b><br>{lay} · " +
                   i18n.T("{} clips without colours · {} sound files").format(len(L["pieces"]), len(L["recorder"])) +
                   "<br>" + cams + "<br>" + i18n.T("The moments will be found automatically when you press Build."))
            self.foot_lbl.setText(txt)
            return
        txt = (f"<b>{escape(Path(f).name)}</b><br>{lay} · " +
               i18n.T("{} labelled clips · {} recorder files").format(len(L["pieces"]), len(L["recorder"])) + "<br>" + cams +
               "<br>" + " · ".join(f"{i18n.T(k)} {n}" for k, n in sorted(cnt.items())) + "<br>" +
               i18n.T("Order: {}").format(" → ".join(i18n.T(longfilm2.PART_NAMES[x]) for x in L["order"])))
        if L["skipped"]:
            txt += "<br>" + i18n.T("Not used: {}").format(", ".join(f"{i18n.T(k)} {n}" for k, n in L["skipped"].items()))
        if any(q["kind"] == "party" for q in L["pieces"]) and not L["recorder"]:
            txt += f'<br><span style="color:{C["FAIR"]}">' + i18n.T("No recorder file in the sequence: the party is synced on the longest party clip.") + "</span>"
        self.foot_lbl.setText(txt)

    def _drop(self, paths):
        xmls, rest = _xml_or_rest(paths)
        dirs = [x for x in rest if Path(x).is_dir()]
        if not xmls and not dirs:
            notify(i18n.T("Drop the wedding folder or the XML of your sequence here."), error=True)
            return
        self._set_xml(xmls[0] if xmls else dirs[0])

    def pick_folder(self):
        p = self._cur() or {}
        start = str(Path(p["footage"]).parent) if p.get("footage") else (self.store.app.get("offload", {}) or {}).get("dest", "")
        d = QFileDialog.getExistingDirectory(self, "The wedding folder", start)
        if d:
            self._set_xml(d)

    # ---- colour
    def _look_s(self):
        p = self._cur() or {}
        return {**(self.store.app.get("look") or {}), **(p.get("look") or {})}

    def _look(self, k, x):
        p = self._cur()
        if p is None:
            return
        lk = self._look_s()
        lk[k] = x
        p["look"] = lk
        self.store.app["look"] = dict(lk)       # the next project starts with the same look
        self.store.save_app()
        self._show_look()

    def _pick_lut(self, k):
        cur = self._look_s().get("lut" + k) or self._look_s().get("lut1") or str(Path.home() / "Documents")
        f, _ = QFileDialog.getOpenFileName(self, "Choose a LUT", str(Path(cur).parent if Path(cur).suffix else cur),
                                           "LUT (*.cube *.look *.3dl)")
        if f:
            self._look("lut" + k, f)
            if not self._look_s().get("on"):
                self._look("on", True)

    def _show_look(self):
        lk = self._look_s()
        for w_, val in ((self.sw_col, bool(lk.get("on"))),):
            w_.set(val)
        self.cb_crop.blockSignals(True)
        self.cb_crop.setChecked(bool(lk.get("crop", True)) if "crop" in lk else True)
        self.cb_crop.blockSignals(False)
        self.cb_layer.blockSignals(True)
        self.cb_layer.setChecked(bool(lk.get("layer", True)))
        self.cb_layer.setEnabled(bool(lk.get("on")) and bool(lk.get("crop", True)) and _bridge_ok())
        self.cb_layer.blockSignals(False)
        if "crop" not in lk and self._cur() is not None:
            (self._cur().setdefault("look", {}))["crop"] = True
        for k, (name, sl) in self.lut_rows.items():
            f = lk.get("lut" + k)
            name.setText(Path(f).stem if f else i18n.T("None"))
            name.setToolTip(f or "")
            sl.set(int(lk.get("int" + k, 100)))

    def pick_xml(self):
        p = self._cur() or {}
        f, _ = QFileDialog.getOpenFileName(self, "Your labelled sequence (XML from Premiere)",
                                           str(Path(p["footage"]).parent) if p.get("footage") else "", "XML (*.xml)")
        if f:
            self._set_xml(f)

    def _set_xml(self, f):
        if self._busy():
            notify("Wait for the current job to finish (or Cancel it).", error=True)
            return
        self._remember(footage=f, built=False, edits={}, timeline=None, hidden=[], muted=[])
        self.r, self.an = None, {}
        self._summary()
        self.recompute()
        notify(i18n.T("Folder chosen: {}").format(Path(f).name) if Path(f).is_dir() else i18n.T("XML loaded: {}").format(Path(f).name))

    # ---- settings
    def set_d(self, k, x):
        p = self._cur()
        if p is None:
            return
        p.setdefault("dir", {})[k] = x
        self.store.save_app()
        self.timer.start()

    def reset_d(self):
        keep = {k: v for k, v in ((self._cur() or {}).get("dir") or {}).items() if k == "tracks"}
        self._remember(dir=keep)
        self.open_project()

    def _tracks_ui(self):
        """One drop-down per party camera: Auto or V1..Vn (p["dir"]["tracks"] = {camera name: track})."""
        while self.trk_grid.count():
            w = self.trk_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        tr = (self.info or {}).get("tracks") or {}
        user = ((self._cur() or {}).get("dir") or {}).get("tracks") or {}
        n = len(tr)
        for row, (name, t) in enumerate(sorted(tr.items(), key=lambda x: -x[1])):
            self.trk_grid.addWidget(track_row(name, t, n, user.get(name), lambda k, nm=name: self._set_track(nm, k),
                                              first=row == 0))
        self.trk_box.setVisible(n > 0)

    def _set_track(self, name, k):
        p = self._cur()
        if p is None:
            return
        from PySide6.QtWidgets import QMessageBox
        if p.get("timeline") and QMessageBox.question(
                self, "Video tracks", "The film was changed in the editor. Use the new tracks and throw away the "
                "editor's changes?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            QTimer.singleShot(0, self._tracks_ui)
            return
        d = p.setdefault("dir", {})
        u = {a: b for a, b in (d.get("tracks") or {}).items() if a != name and (not k or b != k)}
        if k:
            u[name] = k
        d["tracks"] = u
        self.store.save_app()
        if p.get("timeline"):
            self._remember(timeline=None, hidden=[], muted=[])
        QTimer.singleShot(0, self.recompute)

    def _ready(self, mode):
        p = self._cur()
        if p is None:
            return
        if p.get("timeline") and QMessageBox.question(
                self, "Getting ready", "The film was changed in the editor. Change the getting ready and throw away the "
                "editor's changes?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._remember(ready_mode=mode, **({"timeline": None, "hidden": [], "muted": []} if p.get("timeline") else {}))
        self._ready_ui()
        self.recompute()

    def _ready_ui(self):
        m = (self._cur() or {}).get("ready_mode", "interleave")
        for b_, on in ((self.b_ri, m == "interleave"), (self.b_rs, m == "sequential")):
            b_.setProperty("active", on)
            b_.style().unpolish(b_)
            b_.style().polish(b_)

    def _vornic(self, on):
        self._remember(vornic=on)
        if on and self.r and not self.r.get("vornic", [0, []])[1] and any(q["kind"] == "vornic" for q in self.r["pieces"]):
            self.status.setText(i18n.T("Press Build to sync the vornic."))
        self.timer.start()

    def _zones(self, zones):
        self._remember(zones=[list(z) for z in zones])
        self.timer.start()

    def _buttons(self):
        p = self._cur() or {}
        busy = self._busy()
        self.b_build.setEnabled(bool(p.get("footage")) and not busy)
        self.b_be.setEnabled(bool(p.get("footage")) and not busy)
        self.b_exp.setEnabled(bool(self.parts) and not busy)
        self.b_edit.setEnabled(bool(self.parts) and not busy)
        _p = self._cur() or {}
        self.b_edit.setText(i18n.T("Continue editing") if _p.get("timeline") else i18n.T("Edit the film"))
        self.b_edit.setToolTip(i18n.T("Opens the editor on the built film. No new Build is needed: your saved edit is "
                                      "kept in the project, even after closing the app."))

    # ---- build
    def build_edit(self):
        self._then_edit = True
        self.build()
        if not self._busy():
            self._then_edit = False

    def build(self):
        p = self._cur()
        if p is None or not p.get("footage") or self._busy():
            return
        self.pp.start("Starting…")
        self.pp.allow_cancel(lambda: self.worker and setattr(self.worker, "_stop", True))
        self.worker = _LF2Worker(p["footage"], p.get("vornic", True), dict(getattr(self, "_cache", {}) or {}),
                                 self.store.app.get("jobs", 2), str(self.store.dir), p.get("colours"))
        self._job_p = p
        if not hasattr(self, "_awake"):
            self._awake = Awake()
        self._awake.on()                       # a Build can take hours: the Mac stays awake
        self.worker.progress.connect(self.pp.set)
        self.worker.finished.connect(self._after_build)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._buttons)
        self.worker.finished.connect(self._awake.off)
        job_mark(("lf2", p["id"]))
        self.worker.start()
        self._buttons()

    def _done(self, r):
        p = self._job_p
        cache = self.worker.cache
        try:
            r = json.loads(json.dumps(r, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
        except Exception:
            logging.exception("long film v2: result not saved")
        self.store.save_blob(p["id"], dict(result=r, cache=cache))
        p.update(built=True, edits={}, timeline=None, hidden=[], muted=[], when=datetime.now().isoformat(timespec="seconds"))
        if r.get("footage_xml"):
            p["footage"] = r["footage_xml"]     # the sequence made from the wedding folder
        self.store.save_app()
        self.pp.hide()
        self.pp.allow_cancel(None)
        if p is self._cur():
            self.r, self._cache = r, cache
            self.an = {}
            for k, c in cache.items():
                try:
                    self.an[k] = core.Analysis.from_json(c["a"])
                except Exception:
                    pass
            self.recompute()
        if r.get("missing"):
            notify(i18n.T("{} clips not found on this computer: connect the disk with the footage.").format(len(r["missing"])), error=True)
        notify(i18n.T("Long Film ready: {}").format(p["name"]), took=("lf2", p["id"]))

    def _after_build(self):
        """Build + Edit the film: the editor opens by itself when the Build ended well."""
        go, self._then_edit = self._then_edit, False
        if go and self.parts and self._job_p is self._cur():
            QTimer.singleShot(200, self.edit_film)

    def _failed(self, m):
        self._then_edit = False
        self.pp.hide()
        self.pp.allow_cancel(None)
        self.status.setText(i18n.T("Stopped: ") + i18n.T(m))
        if m != "Cancelled":
            notify(i18n.T("Long Film failed: {}").format(i18n.T(m)), error=True)

    # ---- the film
    def recompute(self):
        p = self._cur() or {}
        self.parts, self.info = [], {}
        if self.r:
            try:
                self.parts, self.info = longfilm2.assemble(self.r, self.an, self._dir(), p.get("zones", []),
                                                           marker=i18n.T, vornic_on=p.get("vornic", True),
                                                           edits=p.get("edits") or None,
                                                           ready=p.get("ready_mode", "interleave"))
            except Exception as e:
                logging.exception("long film v2 assemble failed")
                self.status.setText(i18n.T("Error: {}").format(str(e)))
        self._fill()
        self._buttons()

    def _fill(self):
        self._tracks_ui()
        rows = [(n, len(its), ln) for n, ln, its, _rec in self.parts]
        self.table.setRowCount(len(rows))
        self.table.setFixedHeight(self.table.horizontalHeader().height() + 32 * max(1, len(rows)) + 6)
        for i, (n, k, ln) in enumerate(rows):
            self.table.setRowHeight(i, 32)
            for c, t in enumerate((n, str(k), fmt_hms(ln))):
                it = QTableWidgetItem(t)
                self.table.setItem(i, c, it)
        if self.r:
            tot = sum(ln for _n, ln, _i, _r in self.parts)
            extra = ""
            if self.r.get("priests"):
                extra += "  " + i18n.T("The priest found in {} church clips (kept whole).").format(len(self.r["priests"]))
            if self.r.get("auto"):
                a = self.r["auto"]
                extra += "  " + i18n.T("Moments found automatically: {}.").format(
                    ", ".join(f"{i18n.T(k)} {n}" for k, n in sorted((a.get("counts") or {}).items())))
                if not a.get("faces"):
                    extra += " " + i18n.T("(without faces: the face model could not be loaded)")
            if (self._cur() or {}).get("timeline"):
                extra += "  " + i18n.T("Edited by you in the editor: Export XML writes your version.")
            self.status.setText(i18n.T("Ready: the long film is {} long. Press Export XML.").format(fmt_hms(tot)) + extra)
        elif (self._cur() or {}).get("footage"):
            self.status.setText(i18n.T("Press Build."))
        self._map()

    def _map(self):
        ps = (self.r or {}).get("party")
        if not ps:
            self.map.set_data([], [])
            self.stats.setText("")
            return
        masters, res = ps["masters"], ps["results"]
        starts = sync.master_starts(masters)
        spans = [(starts[i], starts[i] + m["duration"]) for i, m in enumerate(masters)]
        rows = []
        for ci, cam in enumerate(self.r["cams"]):
            bl = []
            for q in self.r["pieces"]:
                if q["kind"] == "party" and q["cam"] == ci and (x := res.get(q["path"])) and x["conf"] != "fail":
                    g = starts[x["master"]] + x["offset"]
                    bl.append((g + q["a"], g + q["b"], x["conf"]))
            if bl:
                role = (self.info.get("roles") or {}).get(ci, "Handheld")
                rows.append((f"{cam['name'].split('  ·  ')[0]}  ({role[0]})", director.CAM_COLORS[ci % 8], bl))
        edit, shots = [], 0
        for e in self.info.get("edits") or []:
            if e:
                g = starts[e["master"]]
                edit += [(g + t0, g + t1, director.CAM_COLORS[ci % 8]) for t0, t1, ci in e["segs"]]
                shots += e["stats"]["shots"]
        mus = [(starts[i], m["music"]) for i, m in enumerate(masters) if m.get("music")]
        self.map.set_data(spans, rows, edit, mus)
        fails = sum(1 for q in self.r["pieces"] if q["kind"] == "party" and (res.get(q["path"]) or {}).get("conf") not in ("high", "medium"))
        self.stats.setText(i18n.T("Party: {} shots").format(shots) +
                           (("  ·  " + i18n.T("{} party clips could not be synced by the sound").format(fails)) if fails else ""))

    def _lane_name(self, ak):
        cams = [c["name"] for c in (self.r or {}).get("cams", [])]
        if ak and ak[0] == "cam":
            return cams[ak[1]] if ak[1] < len(cams) else f"Camera {ak[1] + 1}"
        return "Recorder" if not ak or ak[1] == 0 else f"Sound {ak[1] + 1}"

    def edit_film(self):
        """The Premiere-like editor (editor.py) on the whole film: every track, every part, the party included."""
        p = self._cur()
        if not p or not self.parts:
            return
        import editor
        tl = p.get("timeline") or longfilm2.timeline(self.parts, marker=i18n.T)
        def keep(dlg):
            self._remember(timeline=dlg.timeline(), hidden=sorted(dlg.m.hidden), muted=dlg.m.muted)
            notify(i18n.T("Your changes are saved."))

        dlg = editor.Editor(self, tl, self.r["infos"], PR_LABEL, self._lane_name, str(self.store.dir / "thumbs"),
                            p.get("hidden", []), p.get("muted", []), on_save=keep,
                            keys=self.store.app.get("editor_keys"),
                            on_keys=lambda k: (self.store.app.__setitem__("editor_keys", k), self.store.save_app()))
        dlg.exec()
        dlg.deleteLater()                          # the player and the readers let go of the footage (disk eject)
        if dlg.reset:
            self._remember(timeline=None, hidden=[], muted=[], edits={})
            notify(i18n.T("The automatic film is back."))
        self.recompute()

    def export(self, target="premiere"):
        p = self._cur()
        if not p or not self.parts:
            return
        d = Path(p["footage"]) if p.get("footage") and Path(p["footage"]).is_dir() else \
            (Path(p["footage"]).parent if p.get("footage") else Path.home())
        f, _ = QFileDialog.getSaveFileName(self, "Export XML", resolve.name_for(str(d / f"{p['name']} - Long Film.xml"), target),
                                           "XML (*.xml)")
        if not f:
            return
        look = self._look_s()
        layer = (target != "davinci" and look.get("on") and look.get("crop", True) and look.get("layer", True)
                 and _bridge_ok())
        if layer:
            look = {**look, "crop": False}         # the crop goes on the adjustment layer, not on every clip
        try:
            if p.get("timeline"):                  # the film as he edited it in the editor
                n, nv, na = longfilm2.export_timeline(p["timeline"], self.r["infos"], f, f"{p['name']} - Long Film",
                                                      look=look, hidden=p.get("hidden", []),
                                                      muted=p.get("muted", []),
                                                      labels=longfilm2.labels_out(p.get("colours"), target))
            else:
                n, nv, na = longfilm2.export_xml(self.parts, self.r["infos"], [c["name"] for c in self.r["cams"]], f,
                                                 f"{p['name']} - Long Film", marker=lambda s: s, look=look,
                                                 labels=longfilm2.labels_out(p.get("colours"), target))
            for_target(f, target)
        except Exception as e:
            logging.exception("long film v2 export failed")
            notify(i18n.T("Export failed: {}").format(str(e)), error=True)
            return
        self.status.setText(i18n.T("Saved {} clips ({} video, {} audio tracks) to {}. Premiere: File > Import.").format(n, nv, na, f)
                            if target != "davinci" else
                            i18n.T("Saved {} clips ({} video, {} audio tracks) to {}. DaVinci Resolve: File > Import > Timeline. "
                                   "The LUT is not in this file: put it in Resolve's Color page.").format(n, nv, na, f))
        notify(i18n.T("XML saved: {}").format(Path(f).name))
        if layer:
            to_premiere(f, f"{p['name']} - Long Film", colour.CROP, self.status)


class LongFilmBPPage(LongFilm2Page):
    """Long Film Blueprint (BETA): one of his finished long films is the template (cuts, music, sound effects, pacing);
    every cut is refilled with a shot of the same moment of this wedding. The wedding is read like Long Film (folder
    or labelled XML, moments found by the day model when there are no colours)."""
    KEY = "longbp"
    BETA = True
    DESC = ("One of your finished long films is the template: its cuts, music, sound effects and pacing stay, and every "
            "cut is refilled with a shot of the same moment from this wedding (the wedding folder or your labelled "
            "sequence, read like Long Film). Build, then Export XML.")
    CAT = {"groom": "groom", "bride": "bride", "firstlook": "couple", "couple": "couple", "church": "church",
           "civil": "church", "venue": "venue", "drone": "drone", "party": "party", "vornic": "vornic"}

    def __init__(self, store):
        self.bp_edit = None
        super().__init__(store)
        l = self._card(2, "Your finished film (the blueprint)")
        f = self._cards["Your finished film (the blueprint)"][0]
        self._left.removeWidget(f)
        self.bpbox = BlueprintBox(store, "long", "")
        self.bpbox.b_auto.hide()
        self.bpbox.b_bp.hide()
        self.bpbox.changed.connect(self.recompute)
        l.addWidget(self.bpbox)
        self._left.insertWidget(1, f)
        for title in ("Vornic", "Party · Auto Director", "Colour", "Clip colours"):
            if title in self._cards:
                self._cards[title][0].hide()
        self.b_edit.hide()
        self.b_be.hide()
        for w_ in self._party_w + [self.map, self.stats]:     # the party comes from the blueprint's own cuts
            w_.hide()

    def open_project(self):
        super().open_project()
        p = self._cur()
        if p is not None:
            p["mode"] = "blueprint"
            self.bpbox.load(p)

    def _pool(self):
        """The pieces the blueprint can take: every selected (good) part of the clips, by moment, on the day's clock."""
        r = self.r or {}
        infos = r.get("infos") or {}
        sel = r.get("sel") or {}
        out = []
        for i, p in enumerate(r.get("pieces") or []):
            cat = self.CAT.get(p.get("kind"))
            if not cat:
                continue
            inf = infos.get(p["path"]) or {}
            rngs = sel.get(longfilm2.key_of(p)) or ([(p["a"], p["b"])] if longfilm2.part_of(p["kind"]) not in longfilm2.SELECT
                                                   else [])
            for a, b in rngs:
                if b - a < 0.5:
                    continue
                for c in ((cat, "location") if cat in ("groom", "bride") else (cat,)):
                    # his older films: Teal = shots of the getting-ready place -> taken from the getting ready
                    # (the pool never uses one moment twice, whatever the category)
                    out.append(dict(path=p["path"], a=a, b=b, cat=c, label=teaser.LABEL_OF.get(cat),
                                    order=i * 10 + len(out),
                                    clock=(p.get("t") + a - p["a"]) if p.get("t") is not None else None,
                                    fps=inf.get("fps", 25.0), fdur=inf.get("dur", b) or b, w=inf.get("w", 1920),
                                    h=inf.get("h", 1080)))
        if out and any(x["clock"] is None for x in out):
            for x in out:
                x["clock"] = None
        return out

    def recompute(self):
        p = self._cur() or {}
        self.parts, self.info, self.bp_edit = [], {}, None
        b = self.bpbox.current() if p else None
        if self.r and b:
            try:
                self.bp_edit = blueprint.build(self._pool(), b, seed=1)
                by = {}
                for t0, t1, q in self.bp_edit["shots"]:
                    n, ln = by.get(q["cat"], (0, 0.0))
                    by[q["cat"]] = (n + 1, ln + t1 - t0)
                self.parts = [(i18n.T(teaser.CAT_NAME.get(c, c)), ln, [None] * n, []) for c, (n, ln) in by.items()]
            except Exception as e:
                logging.exception("long film blueprint failed")
                self.status.setText(i18n.T("Error: {}").format(str(e)))
        self._fill()
        if self.r and not b:
            self.status.setText(i18n.T("Add one of your finished long films (XML) as the blueprint."))
        elif self.bp_edit is not None:
            gaps = sum(1 for g in self.bp_edit["gaps"] if g[2] != "interview")
            self.status.setText(i18n.T("Ready: your film refilled with this wedding, {} shots.").format(
                len(self.bp_edit["shots"])) + ("  " + i18n.T("{} places without footage (marked in the XML).").format(gaps)
                                               if gaps else ""))
        self._buttons()

    def _buttons(self):
        super()._buttons()
        self.b_exp.setEnabled(self.bp_edit is not None and not self._busy())

    def export(self, target="premiere"):
        p = self._cur()
        b = self.bpbox.current()
        if not p or self.bp_edit is None or not b:
            return
        d = Path(p["footage"]) if p.get("footage") and Path(p["footage"]).is_dir() else \
            (Path(p["footage"]).parent if p.get("footage") else Path.home())
        f, _ = QFileDialog.getSaveFileName(self, "Export XML", resolve.name_for(str(d / f"{p['name']} - Long Film Blueprint.xml"),
                                                                              target), "XML (*.xml)")
        if not f:
            return
        try:
            n = blueprint.export_xml(self.bp_edit, b, f, f"{p['name']} - Long Film Blueprint")
            for_target(f, target)
        except Exception as e:
            logging.exception("long film blueprint export failed")
            notify(i18n.T("Export failed: {}").format(str(e)), error=True)
            return
        self.status.setText(i18n.T("Saved {} clips to {}.").format(n, f))
        notify(i18n.T("XML saved: {}").format(Path(f).name))


class SyncOptions(QWidget):
    """The two sync choices, shown where the sync happens (Synchronize / Multicam, Long Film's party), not in Settings:
    which track of a recorder take with several files, and the sync engine (New = recommended). Saved for all projects."""
    TAKES = ["auto", "mix", "1", "2", "3"]

    def __init__(self, store):
        super().__init__()
        self.store = store
        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        g.addWidget(lbl("Sync engine", "muted"), 0, 0)
        self.c_eng = QComboBox()
        self.c_eng.setProperty("i18n", True)
        self.c_eng.addItems(["New (recommended)", "Classic"])
        self.c_eng.setToolTip(i18n.T("New: every file is compared with every other one (cameras with each other too, like "
                                     "Align / Syncaila), the whole group is placed at once, ~5x faster and it finds more "
                                     "clips. Classic: every clip is searched in the recorder only (the engine before v4.4.0)."))
        g.addWidget(self.c_eng, 1, 0)
        g.addWidget(lbl("Recorder with several tracks", "muted"), 2, 0)
        self.c_take = QComboBox()
        self.c_take.setProperty("i18n", True)
        self.c_take.addItems(["Automatic (the cleanest track)", "The mix", "Track 1", "Track 2", "Track 3"])
        self.c_take.setToolTip(i18n.T("A Tascam / Zoom writes every take as several files: a safe (auto) track, a manual "
                                      "track and their mix. Only one of them is used for the sync and the export. "
                                      "Automatic = the cleanest track (no clipping, the stronger signal), never the mix."))
        g.addWidget(self.c_take, 3, 0)
        g.setColumnStretch(0, 1)
        self._load()
        self.c_eng.currentIndexChanged.connect(self._eng)
        self.c_take.currentIndexChanged.connect(self._take)

    def _load(self):
        for w, v in ((self.c_eng, 1 if self.store.app.get("sync_engine", "graph") == "classic" else 0),
                     (self.c_take, self.TAKES.index(self.store.app.get("rec_take", "auto"))
                      if self.store.app.get("rec_take", "auto") in self.TAKES else 0)):
            w.blockSignals(True)
            w.setCurrentIndex(v)
            w.blockSignals(False)

    def showEvent(self, e):
        self._load()                         # the other page may have changed it
        super().showEvent(e)

    def _eng(self, i):
        self.store.app["sync_engine"] = "classic" if i else "graph"
        self.store.save_app()
        notify(i18n.T("Sync engine: {}").format(i18n.T(self.c_eng.currentText())) + ". " +
               i18n.T("Press Sync again on the projects that should use it."))

    def _take(self, i):
        self.store.app["rec_take"] = self.TAKES[i]
        self.store.save_app()
        notify(i18n.T("Recorder track: {}").format(i18n.T(self.c_take.currentText())) + ". " +
               i18n.T("Press Sync again on the projects that should use it."))


def cam_title(name):
    """'fx6 · #_SERJFX#.MXF' -> ('fx6', 'SERJFX · MXF'): the camera folder, then what its files look like (no # signs)."""
    head, _, pat = str(name).partition(" · ")
    if not pat:
        return head, ""
    stem, _, ext = pat.rpartition(".")
    words = [w for w in re.split(r"[#_\-\s]+", stem) if w]
    return head, " · ".join(words + ([ext.upper()] if ext else []))


def track_row(name, auto_track, n, chosen, on_change, first=False):
    """One camera in the video-track list: the camera name (big), its files (small, grey), a small V1..Vn list whose
    first item is 'V3 · auto' (what Auto gives now)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(12, 7, 10, 7)
    h.setSpacing(10)
    if not first:
        w.setStyleSheet(f"border-top:1px solid {C['BORDER']}")
    t, sub = cam_title(name)
    col = QVBoxLayout()
    col.setSpacing(0)
    a = QLabel(t)
    a.setStyleSheet("font-weight:600;color:#ececec;border:none")
    col.addWidget(a)
    if sub:
        b = QLabel(sub)
        b.setStyleSheet(f"font-size:10px;color:{C['MUTED']};border:none")
        col.addWidget(b)
    h.addLayout(col, 1)
    cb = QComboBox()
    cb.addItem(i18n.T("V{} · auto").format(auto_track))
    cb.addItems([f"V{k}" for k in range(1, n + 1)])
    cb.setCurrentIndex(chosen if isinstance(chosen, int) and 1 <= chosen <= n else 0)
    cb.setFixedWidth(104)
    cb.setStyleSheet("QComboBox{padding:2px 8px;border-radius:4px}")
    cb.setToolTip(i18n.T("The video track of this camera in Export XML. Auto: the static camera on V1, the main camera on top."))
    cb.currentIndexChanged.connect(on_change)
    h.addWidget(cb, 0, Qt.AlignVCenter)
    return w


class ElideLabel(QLabel):
    """One line that is cut with "…" to the width it gets (a long file name never makes its card wider)."""

    def __init__(self, text=""):
        super().__init__()
        self._full = text
        self.setToolTip(text)
        self.setMinimumWidth(10)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._show()

    def setFull(self, text):
        self._full = text
        self.setToolTip(text)
        self._show()

    def _show(self):
        super().setText(self.fontMetrics().elidedText(i18n.T(self._full), Qt.ElideRight, max(10, self.width())))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._show()


class StudioCard(QFrame):
    opened = Signal(str)
    deleted = Signal(str)

    def __init__(self, p, badge, colour, lines):
        super().__init__()
        self.pid, self.pname = p["id"], p["name"]
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(104)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 8, 10)
        v.setSpacing(3)
        top = QHBoxLayout()
        b = QLabel(badge)
        b.setStyleSheet(f"background:{colour};color:white;font-size:9px;font-weight:700;border-radius:3px;padding:1px 6px")
        top.addWidget(b)
        top.addStretch()
        d = btn("✕", "del", self.ask_delete)
        d.setFixedSize(22, 22)
        top.addWidget(d)
        v.addLayout(top)
        name = ElideLabel(p["name"])
        name.setStyleSheet("font-size:13px;font-weight:700;color:#ececec")
        v.addWidget(name)
        for t in lines:
            e = ElideLabel(t)
            e.setProperty("class", "muted")
            e.setStyleSheet(f"color:{C['MUTED']}")
            v.addWidget(e)
        v.addStretch()
        self.setMinimumWidth(200)

    def ask_delete(self):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Delete project",
                                f"Delete \"{self.pname}\"?\nYour video files are not touched, only the project is removed.") == QMessageBox.Yes:
            self.deleted.emit(self.pid)

    def mousePressEvent(self, _):
        self.opened.emit(self.pid)


class StudioHub(QWidget):
    """Teaser Studio / Long Film: a page of project cards (like Projects), the studio opens on a card."""

    def __init__(self, store, studio, title, key, badge, colour, lines):
        super().__init__()
        self.store, self.studio, self.key, self.badge, self.colour, self.lines = store, studio, key, badge, colour, lines
        self.stack = QStackedWidget()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.stack)
        g = QWidget()
        gv = QVBoxLayout(g)
        gv.setContentsMargins(28, 22, 28, 22)
        head = QHBoxLayout()
        head.addWidget(lbl(title, "h1"))
        head.addStretch()
        head.addWidget(btn("+  New Project", "primary", self.new_project))
        gv.addLayout(head)
        self.empty = lbl("No projects yet. Press New Project: one per wedding.", "muted", True)
        gv.addWidget(self.empty)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        gv.addWidget(self.scroll, 1)
        self.stack.addWidget(g)
        self.stack.addWidget(studio)
        studio.back.connect(self.show_grid)
        self.refresh()

    def projects(self):
        return self.store.app.setdefault(f"{self.key}_projects", [])

    def refresh(self):
        ps = self.projects()
        self.empty.setVisible(not ps)
        w = QWidget()
        gl = QGridLayout(w)
        gl.setAlignment(Qt.AlignTop)
        gl.setSpacing(14)
        for i, p in enumerate(reversed(ps)):
            c = StudioCard(p, self.badge, self.colour, self.lines(p))
            c.opened.connect(self.open)
            c.deleted.connect(self.delete)
            gl.addWidget(c, i // 3, i % 3)          # owner: 3 per row, then the next row (never a side scroll)
        for col in range(3):
            gl.setColumnStretch(col, 1)
        self.scroll.setWidget(w)

    def show_grid(self):
        self.refresh()
        self.stack.setCurrentIndex(0)

    def open(self, pid):
        if self.studio._busy():
            self.stack.setCurrentIndex(1)
            notify("Wait for the current job to finish (or Cancel it).", error=True)
            return
        self.store.app[f"{self.key}_current"] = pid
        self.store.save_app()
        self.studio.open_project()
        self.stack.setCurrentIndex(1)

    def new_project(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Project", "Name (e.g. the couple):")
        if not ok or not name.strip():
            return
        p = dict(id=uuid.uuid4().hex, name=name.strip(), when=datetime.now().isoformat(timespec="seconds"))
        self.projects().append(p)
        self.store.save_app()
        self.open(p["id"])

    def delete(self, pid):
        if self.studio._busy() and self.store.app.get(f"{self.key}_current") == pid:
            notify("Wait for the current job to finish (or Cancel it).", error=True)
            return
        ps = self.projects()
        ps[:] = [p for p in ps if p["id"] != pid]
        if self.store.app.get(f"{self.key}_current") == pid:
            self.store.app[f"{self.key}_current"] = None
        self.store.save_app()
        self.refresh()


# ---------------------------------------------------------------- main window

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        self.resize(1400, 820)
        self.setMinimumSize(1100, 680)
        self.store = Store()
        i18n.set_lang(self.store.app.get("ui_lang", "en"))     # every text below appears in this language
        self.store.app.setdefault("lang", self.store.app.get("ui_lang", "en"))
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
        self.nav = {"offload": btn("Card Offload", "nav", lambda: self.go("offload")),
                    "project": btn("Create Project", "nav", lambda: self.go("project")),
                    "dash": btn("Selection", "nav", lambda: self.go("dash")),
                    "syncdash": btn("Synchronize", "nav", lambda: self.go("syncdash")),
                    "mcdash": btn("Multicam", "nav", lambda: self.go("mcdash")),
                    "long": btn("Long Film (old)", "nav", lambda: self.go("long")),
                    "long2": btn("Long Film", "nav", lambda: self.go("long2")),
                    "longbp": btn("Long Film Blueprint", "nav", lambda: self.go("longbp")),
                    "teaser": btn("Teaser Studio", "nav", lambda: self.go("teaser")),
                    "transcribe": btn("Transcribe", "nav", lambda: self.go("transcribe")),
                    "queue": btn("Analysis Queue", "nav", lambda: self.go("queue")),
                    "settings": btn("Settings", "nav", lambda: self.go("settings")),
                    "info": btn("Info / How to use", "nav", lambda: self.go("info"))}
        for b in self.nav.values():
            sv.addWidget(b)
        self.nav["long"].hide()     # v4.6.0 (owner): the old Long Film is hidden; its projects stay in the data
        for key in ("teaser", "longbp"):     # owner: no NEW on Card Offload / Transcribe / Create Project any more
            nb = QHBoxLayout(self.nav[key])
            nb.setContentsMargins(0, 0, 8, 0)
            nb.addStretch()
            new = QLabel("BETA" if key == "longbp" else "NEW")
            new.setStyleSheet(f"background:{C['POOR']};color:white;font-size:8px;font-weight:800;border-radius:5px;padding:0px 4px")
            new.setAttribute(Qt.WA_TransparentForMouseEvents)
            new.setFixedSize(30, 14)
            new.setAlignment(Qt.AlignCenter)
            nb.addWidget(new, 0, Qt.AlignVCenter)
        sv.addStretch()
        sv.addWidget(lbl("Local workspace", "muted"))
        h.addWidget(side)
        set_target(self.store.app.get("target", "premiere"))
        right = QWidget()
        rv_ = QVBoxLayout(right)
        rv_.setContentsMargins(0, 0, 0, 0)
        rv_.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 8, 18, 0)
        bar.addStretch()
        self.target_sw = TargetSwitch(self.store)
        bar.addWidget(self.target_sw)
        rv_.addLayout(bar)
        self.stack = QStackedWidget()
        rv_.addWidget(self.stack, 1)
        h.addWidget(right, 1)
        self.setCentralWidget(central)

        self.dash, self.proj = Dashboard("footage"), ProjectPage(self.store)
        self.mcdash = Dashboard("multicam")
        self.syncdash = Dashboard("sync")
        self.anl, self.res, self.queue = AnalyzingPage(), ResultsPage(self.store), QueuePage()
        self.mc = MulticamPage(self.store)
        self.settings = SettingsPage(self.store)
        self.info = InfoPage(self.store)
        self.teaser = TeaserPage(self.store)
        self.long = LongFilmPage(self.store, self.teaser)
        name_of = lambda f: Path(f).name if f else i18n.T("No footage yet")
        self.teaser_hub = StudioHub(self.store, self.teaser, "Teaser Studio", "teaser", "TEASER", "#e5534b",
                                    lambda p: [name_of(p.get("footage")), f"{i18n.T('Updated')} {nice_date(p.get('when', ''))}"])
        self.offload = OffloadPage(self.store)
        self.transcribe = TranscribePage(self.store)
        self.cproject = CreateProjectPage(self.store)
        self.long_hub = StudioHub(self.store, self.long, "Long Film", "long", "LONG FILM", "#2e9e6a",
                                  lambda p: [name_of(p.get("footage")),
                                             (i18n.T("with vornic") + " · " if p.get("vornic") else "") +
                                             f"{i18n.T('Updated')} {nice_date(p.get('when', ''))}"])
        self.long2 = LongFilm2Page(self.store)
        self.long2_hub = StudioHub(self.store, self.long2, "Long Film", "long2", "LONG FILM", "#2e9e6a",
                                   lambda p: [name_of(p.get("footage")), f"{i18n.T('Updated')} {nice_date(p.get('when', ''))}"])
        self.longbp = LongFilmBPPage(self.store)
        self.longbp_hub = StudioHub(self.store, self.longbp, "Long Film Blueprint", "longbp", "BLUEPRINT", "#c2410c",
                                    lambda p: [name_of(p.get("footage")), f"{i18n.T('Updated')} {nice_date(p.get('when', ''))}"])
        self.toast = Toast(self)
        global _NOTIFY
        _NOTIFY = lambda text, error=False, ms=None, extra="": self.toast.show_msg(text, ms, error, extra)
        self._drops = [enable_drops(pg, pg._drop) for pg in (self.proj, self.mc, self.teaser, self.long, self.offload,
                                                              self.transcribe, self.cproject, self.long2, self.longbp)]
        dd = _Drops(self.offload._drop_dest, self.offload)  # the destination area takes the destination folder
        for w_ in (self.offload.dest_lbl, self.offload.where):
            w_.installEventFilter(dd)
        self._drops.append(dd)
        self.res.export_done = lambda name: (self.toast.show_msg(f"XML saved: {name}"), logging.info("footage export %s", name))
        self.teaser.notify.connect(self.toast.show_msg)
        for w in (self.dash, self.mcdash, self.syncdash, self.proj, self.anl, self.res, self.queue, self.mc, self.settings, self.info, self.teaser_hub, self.long_hub, self.long2_hub, self.longbp_hub, self.offload, self.transcribe, self.cproject):
            self.stack.addWidget(w)
        for d_ in (self.dash, self.mcdash, self.syncdash):
            d_.new_project.connect(lambda k=d_.kind: self.new_project(k))
            d_.open_project.connect(self.open_project)
            d_.delete_project.connect(self.delete_project)
        self.proj.back.connect(lambda: self.go("dash"))
        self.mc.back.connect(lambda: self.go("syncdash" if (self.mc.p or {}).get("sync_only") else "mcdash"))
        self.proj.analyze.connect(self.start_analysis)
        self.proj.open_history.connect(self.show_history)
        self.anl.back.connect(lambda: self.show_page(self.proj))
        self.anl.pause.connect(lambda on: self.worker and self.worker.pause(on))
        self.anl.cancel.connect(lambda: self.worker and self.worker.cancel())
        self.res.back.connect(lambda: self.show_page(self.proj))
        self.queue.open_job.connect(self._open_job)
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
        lr = getattr(self.long, "runner", None)
        if lr and lr.isRunning():
            jobs["long"] = ("Long Film (old)", self.long.pp.title.text(), self.long.pp.bar.value() / 1000)
        if self.long2._busy():
            jobs["long2"] = ("Long Film", self.long2.pp.title.text(), self.long2.pp.bar.value() / 1000)
        if self.longbp._busy():
            jobs["longbp"] = ("Long Film Blueprint", self.longbp.pp.title.text(), self.longbp.pp.bar.value() / 1000)
        if self.offload._busy():
            jobs["offload"] = ("Card Offload", self.offload.pp.title.text(), self.offload.pp.bar.value() / 1000)
        if self.cproject._busy():
            jobs["project"] = ("Create Project", self.cproject.pp.title.text(), self.cproject.pp.bar.value() / 1000)
        if self.transcribe._busy():
            jobs["transcribe"] = ("Transcribe", self.transcribe.pp.title.text(), self.transcribe.pp.bar.value() / 1000)
        running_here = bool(self.worker and self.worker.isRunning() and self.job and self.proj.p is self.job["p"])
        self.proj.b_an.setText("View analysis" if running_here else "Analyze Footage")
        self.queue.set_jobs(jobs)
        self.nav["queue"].setText(f"Analysis Queue ({len(jobs)})" if jobs else "Analysis Queue")

    def _open_job(self, k):
        if k == "teaser":
            self.teaser_hub.stack.setCurrentIndex(1)
            self.show_page(self.teaser_hub)
        elif k == "long":
            self.long_hub.stack.setCurrentIndex(1)
            self.show_page(self.long_hub)
        elif k == "long2":
            self.long2_hub.stack.setCurrentIndex(1)
            self.show_page(self.long2_hub)
        elif k == "longbp":
            self.longbp_hub.stack.setCurrentIndex(1)
            self.show_page(self.longbp_hub)
        elif k in ("offload", "project", "transcribe"):
            self.go(k)
        else:
            self.show_page({"footage": self.anl}.get(k, self.mc))

    def closeEvent(self, e):
        self.store.flush()
        # stop the background jobs cleanly (what is analysed so far is kept), so quitting never ends in a crash report
        if self.transcribe._busy():
            self.transcribe._stop = True
            self.transcribe.worker.wait(10000)
        if self.cproject._busy():
            self.cproject._stop = True
            self.cproject.worker.wait(10000)
        if self.offload._busy():                       # copies stop cleanly (no half file is left)
            self.offload._stop = True
            for w_ in self.offload.workers:
                w_.wait(10000)
        for pg in (self.long2, self.longbp):
            if pg._busy():
                pg.worker._stop = True
                pg.worker.wait(10000)
        for pg in (self.teaser, self.long):
            r = getattr(pg, "runner", None)
            if r and r.isRunning():
                pg._stop = True
                r.wait(5000)
        for w_ in (getattr(self, "worker", None), getattr(self.mc, "worker", None)):
            if w_ is not None and w_.isRunning():
                try:
                    w_.cancel()
                except Exception:
                    pass
                w_.wait(5000)
        super().closeEvent(e)

    # navigation
    def show_page(self, w):
        self.stack.setCurrentWidget(w)
        for k, b in self.nav.items():
            b.setProperty("active", (k == "dash" and w in (self.dash, self.proj, self.res)) or
                          (k == "mcdash" and (w is self.mcdash or (w is self.mc and not (self.mc.p or {}).get("sync_only")))) or
                          (k == "syncdash" and (w is self.syncdash or (w is self.mc and bool((self.mc.p or {}).get("sync_only"))))) or (k == "long2" and w is getattr(self, "long2_hub", None)) or (k == "longbp" and w is getattr(self, "longbp_hub", None)) or (k == "queue" and w in (self.queue, self.anl))
                          or (k == "settings" and w is self.settings) or (k == "info" and w is self.info) or (k == "teaser" and w is self.teaser_hub) or (k == "long" and w is self.long_hub)
                          or (k == "offload" and w is self.offload) or (k == "transcribe" and w is self.transcribe)
                          or (k == "project" and w is self.cproject))
            repolish(b)

    def auto_project(self, folder):
        """After Card Offload: Create Project on the copied wedding, in the mode chosen on its page (runs in the queue)."""
        cp = self.cproject
        if cp._busy() or not Path(folder).is_dir():
            return
        cp.load(folder)
        if not cp.chosen():
            notify(i18n.T("Create Project: no camera folder with video in {}").format(Path(folder).name), error=True)
            return
        notify(i18n.T("Making the Premiere project of {}…").format(Path(folder).name))
        cp.start()

    def go(self, where):
        if where == "dash":
            self.dash.refresh(self.store.projects)
            self.show_page(self.dash)
        elif where == "mcdash":
            self.mcdash.refresh(self.store.projects)
            self.show_page(self.mcdash)
        elif where == "syncdash":
            self.syncdash.refresh(self.store.projects)
            self.show_page(self.syncdash)
        elif where == "long2":
            self.long2_hub.show_grid()
            self.show_page(self.long2_hub)
        elif where == "longbp":
            self.longbp_hub.show_grid()
            self.show_page(self.longbp_hub)
        elif where == "settings":
            self.show_page(self.settings)
        elif where == "info":
            self.show_page(self.info)
        elif where == "transcribe":
            self.show_page(self.transcribe)
        elif where == "project":
            self.show_page(self.cproject)
        elif where == "offload":
            self.offload.refresh()
            self.show_page(self.offload)
        elif where == "teaser":
            self.teaser_hub.show_grid()
            self.show_page(self.teaser_hub)
        elif where == "long":
            self.long_hub.show_grid()
            self.show_page(self.long_hub)
        else:
            self.show_page(self.queue)

    # projects
    def new_project(self, kind=None):
        d = NewProjectDialog(self, kind)
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
        self.mcdash.refresh(self.store.projects)
        self.syncdash.refresh(self.store.projects)

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
        job_mark(("fs", p["id"]))
        w.start()
        self.show_page(self.anl)

    def on_done(self, i, a):
        self.job["an"][i] = a
        self.anl.finished(i, True)

    def on_failed(self, i, msg):
        if msg == "Cancelled":
            self.job["cancelled"] = True
        else:
            logging.error("footage analysis failed: %s", msg)
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
        failed = len(job.get("paths", [])) - len(job["an"]) if job.get("paths") else 0
        if not job["cancelled"]:
            notify(f"Analysis finished: {len(job['an'])} clips" + (f", {failed} failed" if failed > 0 else ""), error=failed > 0,
                   took=("fs", job["p"]["id"]))
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

    shown = {"open": False, "last": {}}

    def hook(t, v, tb):
        logging.error("unexpected error", exc_info=(t, v, tb))
        key = f"{t.__name__}: {v}"[:200]
        now = time.time()
        # a repeating error (e.g. from a timer) must never stack dialogs: one at a time, the same one once a minute
        if shown["open"] or now - shown["last"].get(key, 0) < 60:
            return
        shown["last"][key] = now
        shown["open"] = True
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, APP, f"Something went wrong: {v}\n\nSettings > Save error report, then send it to Claude.")
        except Exception:
            pass
        finally:
            shown["open"] = False
    sys.excepthook = hook


def _arrow_png():
    """A small chevron for the drop-down lists (drawn once, kept in the data folder)."""
    from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
    path = Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation)) / "mmm_arrow.png"
    if not path.exists():
        pm = QPixmap(20, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#b8b8b8"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline([QPoint(3, 3), QPoint(10, 9), QPoint(17, 3)])
        p.end()
        pm.save(str(path))
    return str(path).replace("\\", "/")


def _check_png():
    """The tick inside a ticked list row (Create Project cameras)."""
    path = Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation)) / "mmm_check.png"
    if not path.exists():
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("white"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline([QPoint(4, 8), QPoint(7, 11), QPoint(12, 5)])
        p.end()
        pm.save(str(path))
    return str(path).replace("\\", "/")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    i18n.install()
    ic = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "icon.png"
    if ic.exists():
        app.setWindowIcon(QIcon(str(ic)))
    app.setStyleSheet(STYLE.replace("@ARROW", _arrow_png()))
    if sys.platform == "darwin" and _premiere_app() and not os.environ.get("MMM_NO_BRIDGE"):
        try:                                     # the Premiere bridge (adjustment layer + crop), installed / updated once
            if bridge.install():
                logging.info("premiere bridge %s installed", bridge.VERSION)
        except Exception:
            logging.exception("premiere bridge install failed")
    w = Main()
    setup_logging(w.store.dir)
    appnap.disable()        # minimised in the Dock, macOS used to throttle the jobs (App Nap): "the process is very slow"
    w.show()
    w.settings.update_found.connect(lambda tag: w.toast.show_msg(i18n.T("New version {} available: Settings > Download and install").format(tag), 6000))
    QTimer.singleShot(5000, lambda: w.settings.check_updates(True))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
