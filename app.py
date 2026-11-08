"""ClipSelect - pre-selecție automată a materialului video (interfață desktop)."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QSlider, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView)

import core

COL = {"green": "#2ecc71", "yellow": "#f1c40f", "red": "#e74c3c"}
STYLE = """
QWidget{background:#16181d;color:#e6e8ec;font-size:13px}
QPushButton{background:#262a33;border:1px solid #343944;border-radius:6px;padding:7px 14px}
QPushButton:hover{background:#2f3441} QPushButton:disabled{color:#666}
QPushButton#primary{background:#3b82f6;border:none;font-weight:600} QPushButton#primary:hover{background:#4f90f7}
QTableWidget{background:#1b1e25;border:1px solid #2a2e38;gridline-color:#232730;selection-background-color:#27406e}
QHeaderView::section{background:#20242c;border:none;padding:6px;color:#9aa3b2}
QProgressBar{border:none;background:#262a33;height:6px;text-align:center} QProgressBar::chunk{background:#3b82f6}
QSpinBox{background:#20242c;border:1px solid #343944;padding:3px}
"""


class Worker(QThread):
    progress = Signal(int, float)
    done = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, items):
        super().__init__()
        self.items, self._stop = items, False

    def cancel(self):
        self._stop = True

    def run(self):
        for row, path in self.items:
            if self._stop:
                break
            try:
                a = core.analyze(path, lambda f, r=row: self.progress.emit(r, f), lambda: self._stop)
                self.done.emit(row, a)
            except InterruptedError:
                self.failed.emit(row, "Anulat")
            except Exception as e:
                self.failed.emit(row, str(e))


class Strip(QWidget):
    seek = Signal(float)

    def __init__(self):
        super().__init__()
        self.a, self.segs, self.thr, self.pos = None, [], 60, 0.0
        self.setMinimumHeight(90)

    def set_data(self, a, segs, thr):
        self.a, self.segs, self.thr = a, segs, thr
        self.update()

    def _t(self, x):
        return max(0.0, min(1.0, x / max(1, self.width()))) * (self.a.duration if self.a else 0)

    def mousePressEvent(self, e):
        if self.a:
            self.seek.emit(self._t(e.position().x()))

    mouseMoveEvent = mousePressEvent

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1b1e25"))
        if not self.a or self.a.duration <= 0:
            return
        W, H, D = self.width(), self.height(), self.a.duration
        for t0, t1, s in zip(self.a.t0, self.a.t1, self.a.total):
            x0, x1 = int(t0 / D * W), int(t1 / D * W)
            h = int((H - 22) * max(0.08, s / 100))
            p.fillRect(x0, H - h, max(1, x1 - x0 - 1), h, QColor(COL[core.rating(s, self.thr)]))
        for s, e in self.segs:
            p.fillRect(int(s / D * W), 0, max(2, int((e - s) / D * W)), 8, QColor("#3b82f6"))
        p.setPen(QPen(QColor("white"), 2))
        x = int(self.pos / D * W)
        p.drawLine(x, 0, x, H)


class Main(QMainWindow):
    HEAD = ["", "Clip", "Durată", "Scor", "Claritate", "Stabilitate", "Expunere", "Selecții", "Stare"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClipSelect — pre-selecție video")
        self.resize(1280, 760)
        self.setAcceptDrops(True)
        self.clips, self.worker = [], None
        self.thr, self.minlen = 60, 3

        bar = QHBoxLayout()
        self.b_files = QPushButton("Adaugă fișiere"); self.b_files.clicked.connect(self.pick_files)
        self.b_dir = QPushButton("Adaugă folder"); self.b_dir.clicked.connect(self.pick_dir)
        self.b_run = QPushButton("Analizează"); self.b_run.setObjectName("primary"); self.b_run.clicked.connect(self.start)
        self.b_stop = QPushButton("Oprește"); self.b_stop.clicked.connect(lambda: self.worker and self.worker.cancel())
        self.b_clear = QPushButton("Golește"); self.b_clear.clicked.connect(self.clear)
        self.b_exp = QPushButton("Exportă pentru Premiere (XML)"); self.b_exp.setObjectName("primary"); self.b_exp.clicked.connect(self.export)
        for b in (self.b_files, self.b_dir, self.b_run, self.b_stop, self.b_clear):
            bar.addWidget(b)
        bar.addStretch()
        bar.addWidget(self.b_exp)

        self.table = QTableWidget(0, len(self.HEAD))
        self.table.setHorizontalHeaderLabels(self.HEAD)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)

        self.preview = QLabel("Adaugă clipuri sau trage-le aici")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(420, 236)
        self.preview.setStyleSheet("background:#0e0f13;border:1px solid #2a2e38")
        self.strip = Strip(); self.strip.seek.connect(self.scrub)
        self.info = QLabel(""); self.info.setStyleSheet("color:#9aa3b2")

        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(20, 90); self.sl.setValue(self.thr)
        self.sl_lbl = QLabel(); self.sl.valueChanged.connect(self.settings_changed)
        self.sp = QSpinBox(); self.sp.setRange(1, 30); self.sp.setValue(self.minlen); self.sp.setSuffix(" s")
        self.sp.valueChanged.connect(self.settings_changed)
        st = QHBoxLayout()
        st.addWidget(QLabel("Prag selecție:")); st.addWidget(self.sl, 1); st.addWidget(self.sl_lbl)
        st.addSpacing(16); st.addWidget(QLabel("Lungime minimă:")); st.addWidget(self.sp)

        right = QVBoxLayout()
        right.addWidget(self.preview, 1); right.addWidget(self.strip); right.addWidget(self.info); right.addLayout(st)
        rw = QWidget(); rw.setLayout(right)
        split = QSplitter(); split.addWidget(self.table); split.addWidget(rw); split.setSizes([760, 500])

        self.pbar = QProgressBar(); self.pbar.setRange(0, 1000); self.pbar.setTextVisible(False)
        lay = QVBoxLayout(); lay.addLayout(bar); lay.addWidget(split, 1); lay.addWidget(self.pbar)
        c = QWidget(); c.setLayout(lay); self.setCentralWidget(c)

        self.timer = QTimer(singleShot=True, interval=120); self.timer.timeout.connect(self.show_frame)
        self._t = 0.0
        self.settings_changed()
        self.statusBar().showMessage("Orice format citit de FFmpeg: MXF, MOV, MP4, MTS, MKV, AVI, ProRes, DNxHD, XAVC...")

    # ---- fișiere ----
    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls()])

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Alege clipuri", "", "Toate fișierele (*)")
        self.add_paths(fs)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Alege folder")
        if d:
            self.add_paths([d])

    def add_paths(self, paths):
        have = {c["path"] for c in self.clips}
        found = []
        for p in map(Path, paths):
            if p.is_dir():
                found += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in core.VIDEO_EXT
                                and not f.name.startswith("."))
            elif p.is_file():
                found.append(p)  # fișierele alese manual sunt acceptate indiferent de extensie
        for f in found:
            if str(f) in have:
                continue
            have.add(str(f))
            self.clips.append({"path": str(f), "a": None, "status": "În așteptare"})
            self.table.insertRow(self.table.rowCount())
            self.refresh_row(self.table.rowCount() - 1)

    def clear(self):
        if self.worker and self.worker.isRunning():
            return
        self.clips.clear(); self.table.setRowCount(0); self.strip.set_data(None, [], self.thr)
        self.preview.setText("Adaugă clipuri sau trage-le aici")

    # ---- analiză ----
    def start(self):
        if self.worker and self.worker.isRunning():
            return
        items = [(i, c["path"]) for i, c in enumerate(self.clips) if c["a"] is None]
        if not items:
            return
        self.worker = Worker(items)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.pbar.setValue(0))
        self.worker.start()

    def on_progress(self, row, f):
        self.clips[row]["status"] = f"Analiză {int(f * 100)}%"
        self.table.item(row, 8).setText(self.clips[row]["status"])
        self.pbar.setValue(int(f * 1000))

    def on_done(self, row, a):
        self.clips[row]["a"], self.clips[row]["status"] = a, "Gata"
        self.refresh_row(row)
        if self.table.currentRow() == row:
            self.on_select()

    def on_failed(self, row, msg):
        self.clips[row]["status"] = "Eroare: " + msg
        self.refresh_row(row)

    # ---- afișare ----
    def settings_changed(self):
        self.thr, self.minlen = self.sl.value(), self.sp.value()
        self.sl_lbl.setText(str(self.thr))
        for i in range(len(self.clips)):
            self.refresh_row(i)
        self.on_select()

    def segs(self, c):
        return core.segments(c["a"], self.thr, self.minlen) if c["a"] else []

    def refresh_row(self, r):
        c = self.clips[r]
        a = c["a"]
        cells = ["●", Path(c["path"]).name, "", "", "", "", "", "", c["status"]]
        color = QColor("#555")
        if a:
            sg = self.segs(c)
            color = QColor(COL[core.rating(a.score, self.thr)])
            m, s = divmod(int(a.duration), 60)
            cells[2:8] = [f"{m}:{s:02d}", f"{a.score:.0f}", f"{a.mean(a.sharp):.0f}", f"{a.mean(a.stab):.0f}",
                          f"{a.mean(a.expo):.0f}", f"{len(sg)} ({sum(e - s for s, e in sg):.0f}s)"]
        for col, txt in enumerate(cells):
            it = QTableWidgetItem(txt)
            if col == 0:
                it.setForeground(color)
            if col == 8 and txt.startswith("Eroare"):
                it.setToolTip(txt); it.setForeground(QColor("#e74c3c"))
            self.table.setItem(r, col, it)

    def on_select(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.clips) or not self.clips[r]["a"]:
            return
        c = self.clips[r]
        sg = self.segs(c)
        self.strip.set_data(c["a"], sg, self.thr)
        inf = c["a"].info
        self.info.setText(f"{inf.width}x{inf.height} · {inf.fps:.3f} fps · {len(sg)} selecții")
        self.scrub(sg[0][0] if sg else 0.0)

    def scrub(self, t):
        self.strip.pos = t; self.strip.update()
        self._t = t; self.timer.start()

    def show_frame(self):
        r = self.table.currentRow()
        if r < 0 or not self.clips[r]["a"]:
            return
        img = QImage.fromData(core.frame_jpeg(self.clips[r]["path"], self._t))
        if not img.isNull():
            self.preview.setPixmap(QPixmap.fromImage(img).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---- export ----
    def export(self):
        items = [(c["a"], self.segs(c), core.rating(c["a"].score, self.thr)) for c in self.clips if c["a"]]
        if not any(i[1] for i in items):
            QMessageBox.information(self, "Export", "Nu există selecții. Analizează clipurile sau scade pragul.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Salvează XML", "ClipSelect.xml", "XML (*.xml)")
        if out:
            n = core.export_xmeml(items, out, Path(out).stem)
            QMessageBox.information(self, "Export", f"{n} segmente exportate.\nÎn Premiere: File > Import și alege fișierul XML.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = Main(); w.show()
    sys.exit(app.exec())
