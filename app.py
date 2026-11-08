"""MoneyMakingMachine - AI-free footage pre-selection. Desktop app (PySide6)."""
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QTextBrowser, QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QHeaderView)

import core
import director
import help_text
import xmlimport
import sync

APP, VER = "MoneyMakingMachine", "v2.2.0"
AUTHOR, AUTHOR_URL = "@sergiugabrielcg", "https://www.instagram.com/sergiugabrielcg/"
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


def is_proxy(p):
    """Camera proxies / previews that must never be treated as footage."""
    p = Path(p)
    if p.suffix.lower() in (".lrf", ".lrv"):
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
    pause = Signal(bool)
    cancel = Signal()
    back = Signal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 24, 40, 20)
        ic = QLabel()
        ic.setPixmap(icon_pix("film", 48))
        v.addWidget(ic, 0, Qt.AlignHCenter)
        t = lbl("Analyzing Your Footage", "h2")
        v.addWidget(t, 0, Qt.AlignHCenter)
        v.addWidget(lbl("Now we play the waiting game...", "muted"), 0, Qt.AlignHCenter)
        v.addSpacing(8)
        box = QWidget()
        box.setMaximumWidth(520)
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(lbl("Overall Progress", "muted"))
        row.addStretch()
        self.pct = lbl("0%", "muted")
        row.addWidget(self.pct)
        bv.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        bv.addWidget(self.bar)
        self.count = lbl("0 of 0 videos completed", "muted")
        bv.addWidget(self.count, 0, Qt.AlignHCenter)
        v.addWidget(box, 0, Qt.AlignHCenter)
        br = QHBoxLayout()
        br.setAlignment(Qt.AlignHCenter)
        self.b_pause = btn("Pause Analysis", slot=self._toggle)
        self.paused = False
        br.addWidget(self.b_pause)
        br.addWidget(btn("Cancel", slot=self.cancel.emit))
        v.addLayout(br)
        note = lbl("This analysis will continue in the background.\nYou can safely return to your project and check progress from the Queue or History tab.", "muted")
        note.setAlignment(Qt.AlignCenter)
        note.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        v.addWidget(note, 0, Qt.AlignHCenter)
        v.addWidget(btn("←  Return to project", "link", self.back.emit), 0, Qt.AlignHCenter)
        cols = QHBoxLayout()
        cols.setSpacing(20)
        self.in_l, self.ok_l = QVBoxLayout(), QVBoxLayout()
        self.in_t, self.ok_t = lbl("IN PROGRESS", "section"), lbl("COMPLETED", "section")
        for title, lay in ((self.in_t, self.in_l), (self.ok_t, self.ok_l)):
            c = QVBoxLayout()
            c.addWidget(title)
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            w = QWidget()
            lay.setAlignment(Qt.AlignTop)
            lay.setContentsMargins(0, 0, 8, 0)
            w.setLayout(lay)
            sc.setWidget(w)
            c.addWidget(sc, 1)
            cols.addLayout(c, 1)
        v.addLayout(cols, 1)
        self.cards, self.total, self.fin, self.part = [], 0, 0, []

    def _toggle(self):
        self.paused = not self.paused
        self.b_pause.setText("Resume Analysis" if self.paused else "Pause Analysis")
        self.pause.emit(self.paused)

    def start(self, paths):
        for lay in (self.in_l, self.ok_l):
            while lay.count():
                lay.takeAt(0).widget().deleteLater()
        self.cards = [JobCard(p) for p in paths]
        for c in self.cards:
            self.in_l.addWidget(c)
        self.total, self.fin, self.part = len(paths), 0, [0.0] * len(paths)
        self.paused = False
        self.b_pause.setText("Pause Analysis")
        self._upd()

    def _upd(self):
        f = sum(self.part) / max(1, self.total)
        self.bar.setValue(int(f * 1000))
        self.pct.setText(f"{int(f * 100)}%")
        self.count.setText(f"{self.fin} of {self.total} videos completed")
        self.in_t.setText(f"IN PROGRESS  {self.total - self.fin}")
        self.ok_t.setText(f"COMPLETED  {self.fin}")

    def thumb(self, i, data):
        self.cards[i].set_thumb(data)

    def progress(self, i, f):
        self.part[i] = f
        self.cards[i].set_progress(f)
        self._upd()

    def finished(self, i, ok, msg=""):
        self.part[i] = 1.0
        self.fin += 1
        c = self.cards[i]
        c.finish(ok, msg)
        self.ok_l.insertWidget(0, c)
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
                top.addWidget(btn("Open", slot=lambda k=k: self.open_job.emit(k)))
                cv.addLayout(top)
                s = lbl("", "muted", True)
                cv.addWidget(s)
                b = QProgressBar()
                b.setRange(0, 1000)
                b.setTextVisible(False)
                cv.addWidget(b)
                self.box.addWidget(c)
                self.cards[k] = (c, t, s, b)
            c, t, s, b = self.cards[k]
            t.setText(title)
            s.setText(status)
            b.setValue(int(prog * 1000))
        self.empty.setVisible(not jobs)

# ---------------------------------------------------------------- multicam

CONF_COL = {"high": C["GOOD"], "medium": C["FAIR"], "low": "#f08a3c", "fail": C["POOR"]}
CONF_NAME = {"high": "High", "medium": "Medium", "low": "Check", "fail": "Failed"}
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

    def set_data(self, spans, rows, edit=None):
        """spans: [(t0, t1)] of the recorder files on the common timeline."""
        self.spans, self.rows, self.edit = spans or [], rows, edit or []
        starts = [b[0] for _, _, bl in rows for b in bl] + [s[0] for s in self.spans]
        ends = [b[1] for _, _, bl in rows for b in bl] + [s[1] for s in self.spans]
        self.tmin = min([0.0] + starts)
        self.tmax = max(ends) if ends else 1.0
        self.setMinimumHeight(80 + 26 * (len(rows) + 2))
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

    def __init__(self, mode, files, cache=None, todo=None, jobs=2):
        super().__init__()
        self.mode, self.files, self.cache, self.todo, self.jobs, self._stop = mode, files, cache or {}, todo or [], jobs, False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            if self.mode == "xml":
                self.done.emit(xmlimport.build(self.todo, lambda s, f: self.progress.emit(s, f), lambda: self._stop))
                return
            self.done.emit(self._sync() if self.mode == "sync" else self._analyze())
        except InterruptedError:
            self.failed.emit("Cancelled")
        except Exception as e:
            self.failed.emit(str(e))

    def _sync(self):
        files, n = self.files, max(1, len(self.files))
        infos = {}
        for i, f in enumerate(files):
            if self._stop:
                raise InterruptedError
            self.progress.emit(f"Step 1 · reading files: {i + 1} of {n}", 0.05 * i / n)
            infos[f["path"]] = sync.media_info(f["path"])
        masters, videos, note = sync.classify(files, infos)
        if not masters:
            raise ValueError(note or "No audio master found.")
        withsound = [v for v in videos if infos[v]["audio"]]
        info, res = sync.run_sync(masters, withsound, lambda s, f: self.progress.emit(s, 0.05 + 0.95 * f), lambda: self._stop,
                                  clocks={p: i["clock"] for p, i in infos.items()}, groups={f["path"]: f["group"] for f in files},
                                  jobs=self.jobs)
        for v in videos:
            if v not in res:
                res[v] = dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0,
                              dur=infos[v]["duration"], manual=False, error="No audio stream")
        return dict(infos=infos, masters=info, results=res, note=note)

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
            self.progress.emit(f"Step 2 · analysing video for the auto edit: {done[0]} of {len(left)}", done[0] / max(1, len(left)))

        with ThreadPoolExecutor(max(1, self.jobs)) as ex:
            list(ex.map(one, left))
        if self._stop:
            raise InterruptedError
        return dict(analyses=an, keys=keys)


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
        sc.setWidget(self.map)
        t1v.addWidget(sc, 1)
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
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setTextVisible(False)
        self.pbar.hide()
        mv.addWidget(self.pbar)
        self.status = lbl("", "muted")
        mv.addWidget(self.status)
        body.addWidget(mid, 1)

        # right: auto director
        right = QFrame()
        right.setObjectName("rightpanel")
        right.setFixedWidth(300)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 14, 16, 14)
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
        bq.setToolTip("Moves every cut onto the nearest beat or sound accent of the master audio (within 0.3 s).")
        br.addWidget(bq)
        br.addStretch()
        self.sw_beat = Switch(True)
        self.sw_beat.toggled.connect(lambda v: self.set_d("beat", v))
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
        rv.addSpacing(10)
        self.stats = lbl("Press Auto Edit to build the edit.", "muted", True)
        rv.addWidget(self.stats)
        rv.addStretch()
        rv.addWidget(btn("Export XML", "primary", self.export))
        body.addWidget(right)

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
        self.pbar.setVisible(bool(mine))
        if busy and not mine:
            self.status.setText(f"Another job is running ({self._job_p['name']}). See Analysis Queue.")

    def _start(self, worker, button):
        self._job_p, self.job_status, self.job_progress = self.p, "Starting…", 0.0
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
        todo = [x for c in self.p["cams"] for x in c["clips"]]
        self._start(MCWorker("analyze", None, self.store.load_blob(self.p["id"]), todo, self.store.app["jobs"]), self.b_auto)

    def on_progress(self, text, f):
        self.job_status, self.job_progress = text, f
        if self.p is self._job_p:
            self.status.setText(text)
            self.pbar.setValue(int(f * 1000))

    def _finish(self):
        if self.worker:
            self.worker.wait(2000)
        self._sync_buttons()

    def on_failed(self, msg):
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
                self.status.setText(f"XML imported: {len(r['results'])} clips on {len(r['cams'])} cameras. "
                                    "Press Auto Edit to build the edit, or Export XML.")
        elif "results" in r:   # sync finished
            p["infos"] = r["infos"]
            p["sync"] = dict(masters=r["masters"], clips=r["results"], note=r["note"], when=datetime.now().isoformat(timespec="seconds"))
            cams = sync.auto_cameras(p["files"], r["infos"], r["results"], p.get("cams"))
            for c in cams:
                if not c.get("user"):
                    have = [an_all.get(x) for x in c["clips"]]
                    c["role"] = director.detect_role(have) if all(h is not None for h in have) else "Handheld"
            p["cams"] = cams
            ok = sum(1 for x in r["results"].values() if x["conf"] != "fail")
            msg = (f"Sync finished: {ok} of {len(r['results'])} clips synced. You can export now, "
                                f"or press Auto Edit to let the program build the edit (this analyses the video and takes longer).")
            if here:
                self.status.setText(msg)
        else:                 # analysis finished
            an_all.update(r["analyses"])
            if here:
                self.an.update(r["analyses"])
            blob = self.store.load_blob(p["id"])
            blob.update({k: dict(key=r["keys"].get(k, ""), a=a.to_json()) for k, a in r["analyses"].items()})
            self.store.save_blob(p["id"], blob)
            for c in p["cams"]:
                if not c.get("user"):
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
        self.edits = director.build(self.p["cams"], s["clips"], self.an, s["masters"], self.p["dir"]) if has_an else []
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
                              f"{cnt['low']} to check, {cnt['fail']} failed.")
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
        self.map.set_data(spans, rows, edit)
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
            cb.addItems(["Handheld", "Static"])
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
        self.r_jobs = SliderRow("Parallel jobs", f"How many clips are analysed / read at the same time (your Mac has {self.cores} cores).",
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
        right.addStretch()
        body.addLayout(right, 1)
        v.addLayout(body, 1)
        self.timer = QTimer(interval=2000)
        self.timer.timeout.connect(self.refresh)

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
        self.cards["cpu"].setText(f"{self.cores} cores")
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
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setStyleSheet(f"QTextBrowser{{background:{C['BG']};border:none;color:#c9c9c9;font-size:13px}}")
        self.view.document().setDefaultStyleSheet(
            "h1{font-size:20px;color:#ececec;margin-bottom:6px} h2{font-size:16px;color:#ececec;margin-top:18px}"
            "h3{font-size:13px;color:#d6d6d6;margin-top:10px} li{margin-bottom:4px} b{color:#ececec}")
        v.addWidget(self.view, 1)
        v.addWidget(QLabel(f'<span style="color:{C["MUTED"]}">{APP} {VER} · </span>'
                           f'<a href="{AUTHOR_URL}" style="color:{C["HOT"]};text-decoration:none">by {AUTHOR}</a>'),
                    0, Qt.AlignLeft)
        self.findChildren(QLabel)[-1].setOpenExternalLinks(True)
        self.set_lang(store.app.get("lang", "ro"), save=False)

    def set_lang(self, lang, save=True):
        for b, on in ((self.b_ro, lang == "ro"), (self.b_en, lang == "en")):
            b.setProperty("active", on)
            repolish(b)
        self.view.setHtml(help_text.HELP[lang])
        if save:
            self.store.app["lang"] = lang
            self.store.save_app()


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
                    "settings": btn("Settings", "nav", lambda: self.go("settings")),
                    "info": btn("Info / How to use", "nav", lambda: self.go("info"))}
        for b in self.nav.values():
            sv.addWidget(b)
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
        for w in (self.dash, self.proj, self.anl, self.res, self.queue, self.mc, self.settings, self.info):
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
        self.queue.open_job.connect(lambda k: self.show_page(self.anl if k == "footage" else self.mc))
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
                          or (k == "settings" and w is self.settings) or (k == "info" and w is self.info))
            repolish(b)

    def go(self, where):
        if where == "dash":
            self.dash.refresh(self.store.projects)
            self.show_page(self.dash)
        elif where == "settings":
            self.show_page(self.settings)
        elif where == "info":
            self.show_page(self.info)
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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    ic = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "icon.png"
    if ic.exists():
        app.setWindowIcon(QIcon(str(ic)))
    app.setStyleSheet(STYLE)
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
