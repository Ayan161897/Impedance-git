"""Emulator main window — identical layout to gui/main.py, wired to VirtualEISDevice.

All toolbar buttons (Connect, Start sweep, Stop, Status, Flash status, Dump
flash, Erase flash, Export CSV, Clear plots) work exactly as with real PCB5
hardware.  An extra "Simulated DUT" section at the bottom of the left panel
lets you choose and parameterise the impedance model the virtual board presents.

No virtual COM port is needed — the virtual device runs in-process.

Usage:
    python sim/run_simulator.py
"""
import cmath
import os
import queue
import re
import subprocess
import sys

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QPointF, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QTextEdit,
    QToolBar, QVBoxLayout, QWidget,
)

# Reuse real GUI components unchanged — nothing under gui/ is modified.
_GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gui')
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

from config_panel import ConfigPanel   # noqa: E402
from data_model import DataModel       # noqa: E402
from plot_widget import PlotWidget     # noqa: E402

from circuit_model import (            # noqa: E402
    z_from_table, z_randles, z_rc_parallel, z_resistor,
)
from virtual_device import VirtualEISDevice  # noqa: E402


# ---------------------------------------------------------------------------
# Schematic simulation — defaults match PCB5 hardware (circuit_model.py)
# ---------------------------------------------------------------------------

_SCHEMATIC_DEFAULTS = {
    'R5':   1000.0,    # TIA feedback resistor Rf   Ω
    'C11':  3.3e-9,    # TIA feedback capacitor     F
    'R15':  10_000.0,  # bias divider VREF side     Ω
    'R16':  10_000.0,  # bias divider GND side      Ω
    'R200': 200.0,     # AD9833 series resistor     Ω
}
_PREVIEW_FREQS = np.logspace(1, 5, 60)   # 10 Hz → 100 kHz, 60 log-spaced

# ---------------------------------------------------------------------------
# KiCad SVG rendering — real schematic as dialog background
# ---------------------------------------------------------------------------

_KICAD_CLI = r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe"
_SCH_FILE  = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'PCB5', 'Impedance-measurement-3', 'Project-1.kicad_sch'))
_SVG_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pcb5_schematic.svg')
_SVG_W, _SVG_H = 297.0022, 210.0072   # A4 landscape, SVG viewBox in mm

# KiCad schematic mm-coordinates of editable components (from Project-1.kicad_sch)
_COMP_POS = {
    'R200': (52.07,  69.85),
    'R5':   (80.01, 137.16),
    'C11':  (73.66, 132.08),
    'R15':  (236.22, 142.24),
    'R16':  (250.19, 142.24),
}
_OW, _OH = 12.0, 5.5   # clickable overlay width / height in SVG mm units


def _ensure_svg():
    """Generate pcb5_schematic.svg from KiCad CLI if it does not exist."""
    if os.path.exists(_SVG_CACHE):
        return True
    if not os.path.exists(_KICAD_CLI) or not os.path.exists(_SCH_FILE):
        return False
    try:
        sim_dir = os.path.dirname(os.path.abspath(__file__))
        r = subprocess.run(
            [_KICAD_CLI, 'sch', 'export', 'svg', '--output', sim_dir, _SCH_FILE],
            capture_output=True, timeout=60)
        generated = os.path.join(sim_dir, 'Project-1.svg')
        if r.returncode == 0 and os.path.exists(generated):
            os.rename(generated, _SVG_CACHE)
            return True
    except Exception:
        pass
    return False


def _fmt_val(ref, val):
    """Human-readable component value string."""
    if ref in ('R5', 'R15', 'R16', 'R200'):
        if val >= 1e6:
            return f"{val/1e6:.3g}MΩ"
        if val >= 1e3:
            return f"{val/1e3:.3g}kΩ"
        return f"{val:.3g}Ω"
    # C11 — capacitance
    if val >= 1e-6:
        return f"{val*1e6:.3g}uF"
    if val >= 1e-9:
        return f"{val*1e9:.3g}nF"
    return f"{val*1e12:.3g}pF"


# ---------------------------------------------------------------------------
# _ClickableComp — a blue, hover-sensitive component in the schematic scene
# ---------------------------------------------------------------------------

class _ClickableComp(QGraphicsRectItem):
    """QGraphicsRectItem that highlights on hover and fires a callback on click."""

    def __init__(self, ref, on_click, x, y, w, h, transparent=False):
        super().__init__(x, y, w, h)
        self._ref = ref
        self._on_click = on_click
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        if transparent:
            self._brush_normal = QBrush(QColor(80, 160, 255, 70))
            self._brush_hover  = QBrush(QColor(80, 160, 255, 160))
            self.setPen(QPen(QColor(20, 80, 220, 220), 0.8))
        else:
            self._brush_normal = QBrush(QColor('#c4dcff'))
            self._brush_hover  = QBrush(QColor('#7ab4ff'))
            self.setPen(QPen(QColor('#1a50a8'), 1.5))
        self.setBrush(self._brush_normal)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click(self._ref)

    def hoverEnterEvent(self, event):
        self.setBrush(self._brush_hover)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(self._brush_normal)
        super().hoverLeaveEvent(event)


# ---------------------------------------------------------------------------
# _ZoomView — QGraphicsView with Ctrl+scroll zoom
# ---------------------------------------------------------------------------

class _ZoomView(QGraphicsView):
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)


# ---------------------------------------------------------------------------
# SchematicDialog — interactive PCB5 front-end schematic + preview plots
# ---------------------------------------------------------------------------

class SchematicDialog(QDialog):
    """Modal dialog showing the PCB5 analog front-end as an interactive schematic.

    Clicking any blue component opens a value editor.  The right-hand preview
    shows Bode magnitude, phase and Nyquist for both the ideal DUT model and
    what the firmware would actually measure given the current R5/C11 values.

    Values are reset to _SCHEMATIC_DEFAULTS when the emulator closes (never
    written to disk — session-only storage).
    """

    values_saved = pyqtSignal(dict)

    def __init__(self, current_values, z_fn, parent=None):
        super().__init__(parent)
        self._values        = dict(current_values)
        self._z_fn          = z_fn
        self._val_texts     = {}   # ref → QGraphicsTextItem (manual) or None (SVG)
        self._overlay_items = {}   # ref → _ClickableComp (SVG mode)
        self._vbias_txt     = None
        self._value_bar     = None
        self._view          = None
        self._use_svg       = os.path.exists(_SVG_CACHE) or _ensure_svg()

        if self._use_svg:
            self.setWindowTitle("Simulate Schematic — PCB5 (KiCad schematic)")
            self.resize(1240, 720)
        else:
            self.setWindowTitle("Simulate Schematic — PCB5 Analog Front-End")
            self.resize(1090, 550)

        self._setup_ui()
        self._refresh_value_labels()
        self._refresh_plots()

    def showEvent(self, event):
        super().showEvent(event)
        if self._view is not None and self._use_svg:
            self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    # ------------------------------------------------------------------ setup

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # ── LEFT: schematic + value bar + buttons ──────────────────────────
        left = QVBoxLayout()
        left.setSpacing(4)

        if self._use_svg:
            hint_txt = ("Click any blue highlighted component to edit its value  "
                        "|  Ctrl+scroll to zoom  |  drag to pan")
        else:
            hint_txt = "Click any blue component to edit its value  (hover to highlight)"
        hint = QLabel(hint_txt)
        hint.setStyleSheet("color:#555; font-size:10px;")
        left.addWidget(hint)

        self._scene = QGraphicsScene()
        if self._use_svg:
            self._scene.setSceneRect(0, 0, _SVG_W, _SVG_H)
            self._draw_schematic_svg()
            view_w, view_h = 800, 545
        else:
            self._scene.setSceneRect(0, 0, 562, 318)
            self._draw_schematic()
            view_w, view_h = 580, 336

        view = _ZoomView(self._scene)
        view.setFixedSize(view_w, view_h)
        view.setRenderHint(QPainter.Antialiasing)
        view.setBackgroundBrush(QBrush(QColor('#f4f6fa')))
        view.setDragMode(QGraphicsView.ScrollHandDrag)
        if self._use_svg:
            view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._view = view
        left.addWidget(view)

        if self._use_svg:
            self._value_bar = QLabel()
            self._value_bar.setStyleSheet(
                "background:#eef2ff; border:1px solid #aab; "
                "padding:4px 6px; font-size:11px;")
            left.addWidget(self._value_bar)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save current values")
        save_btn.setToolTip(
            "Applies R5 as the TIA feedback resistance for the next sweep.\n"
            "C11 effect is visible in the preview plots.")
        save_btn.clicked.connect(self._on_save)
        restore_btn = QPushButton("Restore original values")
        restore_btn.setToolTip("Resets all components to PCB5 hardware defaults.")
        restore_btn.clicked.connect(self._on_restore)
        btns.addWidget(save_btn)
        btns.addWidget(restore_btn)
        left.addLayout(btns)

        root.addLayout(left)

        # ── RIGHT: preview plots ───────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(QLabel(
            "Impedance preview  │  "
            "<span style='color:#2176c7'>─── ideal DUT</span>  "
            "<span style='color:#e07820'>- - - with front-end effects (R5, C11)</span>"))

        fig_w = 3.8 if self._use_svg else 4.8
        self._fig = Figure(figsize=(fig_w, 6.8), tight_layout=True)
        self._ax_mag   = self._fig.add_subplot(311)
        self._ax_phase = self._fig.add_subplot(312)
        self._ax_nyq   = self._fig.add_subplot(313)
        self._canvas = FigureCanvas(self._fig)
        right.addWidget(self._canvas, stretch=1)

        root.addLayout(right, stretch=1)

    # -------------------------------------------------------- schematic drawing

    def _draw_schematic_svg(self):
        """Load KiCad-exported SVG as background with transparent clickable overlays."""
        try:
            from PyQt5.QtSvg import QGraphicsSvgItem
        except ImportError:
            self._use_svg = False
            self._draw_schematic()
            return

        s = self._scene
        svg_item = QGraphicsSvgItem(_SVG_CACHE)
        svg_item.setZValue(0)
        s.addItem(svg_item)

        # Bounding rect gives actual scene pixel dimensions (SVG mm → 96 DPI px)
        br = svg_item.boundingRect()
        s.setSceneRect(br)

        # Scale from KiCad mm coords (= SVG viewBox units) → scene pixel coords
        sx = br.width()  / _SVG_W
        sy = br.height() / _SVG_H

        for ref, (kx, ky) in _COMP_POS.items():
            ow = _OW * sx
            oh = _OH * sy
            item = _ClickableComp(
                ref, self._on_comp_click,
                kx * sx - ow / 2, ky * sy - oh / 2, ow, oh,
                transparent=True)
            item.setZValue(10)
            s.addItem(item)
            self._overlay_items[ref] = item
            self._val_texts[ref] = None

    def _draw_schematic(self):
        s = self._scene
        wp = QPen(QColor('#262626'), 1.5)
        wp.setCapStyle(Qt.RoundCap)

        def wire(x1, y1, x2, y2):
            s.addLine(x1, y1, x2, y2, wp)

        def dot(x, y):
            s.addEllipse(x - 3.0, y - 3.0, 6.0, 6.0,
                         QPen(Qt.NoPen), QBrush(QColor('#262626')))

        def txt(t, x, y, sz=7, bold=False, col='#1a1a1a'):
            it = QGraphicsTextItem(t)
            f = QFont('Arial', sz)
            f.setBold(bold)
            it.setFont(f)
            it.setDefaultTextColor(QColor(col))
            it.setPos(x, y)
            s.addItem(it)
            return it

        def ic_box(x1, y1, x2, y2, label=''):
            s.addRect(x1, y1, x2 - x1, y2 - y1,
                      QPen(QColor('#555'), 1.2), QBrush(QColor('#e6e6f4')))
            if label:
                txt(label, x1 + 3, y1 + 3, sz=7)

        def opamp(xL, yT, yB, xR, name=''):
            """Triangle pointing right: inputs at left edge, output at apex."""
            yM = (yT + yB) / 2.0
            poly = QPolygonF([QPointF(xL, yT), QPointF(xL, yB), QPointF(xR, yM)])
            s.addPolygon(poly, QPen(QColor('#444'), 1.5), QBrush(QColor('#e8f4e8')))
            if name:
                txt(name, xL + 5, yM - 10, sz=7)

        def comp(ref, x1, y1, x2, y2, name_lbl):
            """Add a clickable (blue) component box + name label above it."""
            txt(name_lbl, x1, y1 - 13, sz=7, bold=True, col='#1a50a8')
            item = _ClickableComp(ref, self._on_comp_click,
                                  x1, y1, x2 - x1, y2 - y1)
            s.addItem(item)
            # Value label: inside box for horizontal, right-of-box for vertical
            if (y2 - y1) > (x2 - x1):          # vertical component
                vt = txt('', x2 + 4, (y1 + y2) / 2.0 - 7, sz=6)
            else:                               # horizontal component
                vt = txt('', x1 + 3, y1 + 2, sz=6)
            self._val_texts[ref] = vt

        # ── title ──────────────────────────────────────────────────────────
        txt('PCB5 Analog Front-End  —  click blue components to edit',
            10, 2, sz=9, bold=True, col='#222244')

        # ── AD9833 signal generator ────────────────────────────────────────
        ic_box(10, 50, 92, 80, 'AD9833\nSig. Gen.')
        wire(92, 65, 110, 65)

        # ── R200 (series resistor) ─────────────────────────────────────────
        comp('R200', 110, 55, 170, 75, 'R200')
        wire(170, 65, 186, 65)

        # ── U1A unity-gain buffer ──────────────────────────────────────────
        opamp(186, 48, 82, 222, 'U1A')
        txt('+', 189, 51, sz=7, col='#333')
        txt('−', 189, 67, sz=7, col='#333')
        # Internal feedback: OUT→ short path→ −IN (shows it's a voltage follower)
        wire(222, 65, 228, 65)
        wire(228, 65, 228, 74)
        wire(228, 74, 186, 74)
        # PA0 output wire (continues to right edge)
        wire(222, 65, 540, 65)
        txt('PA0 (REF)', 494, 56, sz=8, col='#334466')
        dot(290, 65)    # branch node: signal also goes to DUT

        # ── DUT block ──────────────────────────────────────────────────────
        wire(290, 65, 290, 108)
        ic_box(255, 108, 325, 175, 'DUT\n(Z_dut)')
        wire(290, 175, 290, 215)

        # Wire from DUT bottom to TIA −IN
        wire(290, 215, 350, 215)
        dot(338, 215)   # junction: feedback left rail meets this wire

        # ── TIA U1B (inverting transimpedance amplifier) ───────────────────
        # Triangle: left-edge x=350, y=200 to y=260, apex at (416, 230)
        opamp(350, 200, 260, 416, 'U1B\n(TIA)')
        txt('−', 353, 204, sz=7, col='#333')   # −IN ≈ y=215
        txt('+', 353, 243, sz=7, col='#333')   # +IN ≈ y=245
        # TIA output wire → PA1
        wire(416, 230, 540, 230)
        txt('PA1 (SIG)', 494, 220, sz=8, col='#334466')
        dot(442, 230)   # junction: feedback right rail starts here

        # ── Feedback network: R5 ∥ C11 (two parallel horizontal paths) ─────
        # Right vertical rail: TIA OUT → upward
        wire(442, 230, 442, 105)
        # Left vertical rail: DUT−TIA junction → upward
        wire(338, 215, 338, 105)

        # Upper path — R5
        wire(338, 114, 442, 114)
        comp('R5', 350, 106, 430, 122, 'R5 (Rf)')
        dot(338, 114);  dot(442, 114)

        # Lower path — C11
        wire(338, 132, 442, 132)
        comp('C11', 350, 124, 430, 140, 'C11')
        dot(338, 132);  dot(442, 132)

        # ── Bias divider: R15 / R16 set Vbias for TIA +IN ─────────────────
        # +IN pin at y≈245; wire runs left to divider at x=267
        wire(350, 245, 267, 245)
        dot(267, 245)

        # R15 (top half: divider node → VREF)
        comp('R15', 257, 210, 277, 245, 'R15')
        wire(267, 210, 267, 194)
        txt('VREF\n(3.3 V)', 248, 180, sz=7, col='#886600')

        # R16 (bottom half: divider node → GND)
        comp('R16', 257, 245, 277, 280, 'R16')
        wire(267, 280, 267, 296)

        # GND symbol (three horizontal bars, decreasing width)
        wire(254, 296, 280, 296)
        wire(258, 300, 276, 300)
        wire(262, 304, 272, 304)
        txt('GND', 258, 306, sz=7, col='#555')

        # Vbias computed annotation next to +IN node
        self._vbias_txt = txt('', 292, 237, sz=7, col='#445577')

    # --------------------------------------------------- value labels / plots

    def _refresh_value_labels(self):
        for ref, vt in self._val_texts.items():
            if vt is not None:
                vt.setPlainText(_fmt_val(ref, self._values[ref]))
        # Update tooltips on SVG overlay items
        for ref, item in self._overlay_items.items():
            item.setToolTip(f"{ref}: {_fmt_val(ref, self._values[ref])}\nClick to edit")
        # Value bar shown below the KiCad schematic view
        if self._value_bar is not None:
            R15, R16 = self._values['R15'], self._values['R16']
            denom = R15 + R16
            vbias = 3.3 * R16 / denom if denom > 0 else 1.65
            parts = [f"<b>{r}:</b>&nbsp;{_fmt_val(r, self._values[r])}"
                     for r in ('R5', 'C11', 'R15', 'R16', 'R200')]
            parts.append(f"<b>Vbias:</b>&nbsp;{vbias:.3f}&nbsp;V")
            self._value_bar.setText("   |   ".join(parts))
        # Manual-mode Vbias annotation in scene
        R15, R16 = self._values['R15'], self._values['R16']
        denom = R15 + R16
        vbias = 3.3 * R16 / denom if denom > 0 else 0.0
        if self._vbias_txt is not None:
            self._vbias_txt.setPlainText(f'Vbias = {vbias:.3f} V')

    def _refresh_plots(self):
        R5  = self._values['R5']
        C11 = self._values['C11']

        ideal_mag, ideal_ph, ideal_re, ideal_nim = [], [], [], []
        meas_mag,  meas_ph,  meas_re,  meas_nim  = [], [], [], []

        for freq in _PREVIEW_FREQS:
            try:
                z_true = self._z_fn(freq)
            except Exception:
                z_true = complex(1000.0, 0.0)

            # Ideal DUT (standard EIS convention: -Im on Nyquist y-axis)
            ideal_mag.append(abs(z_true))
            ideal_ph.append(cmath.phase(z_true) * 180.0 / np.pi)
            ideal_re.append(z_true.real)
            ideal_nim.append(-z_true.imag)

            # Measured Z accounting for complex feedback Zf = R5 ∥ Zc11
            # Z_measured = Z_true × (R5 / Zf)  (firmware uses R5 as its rf)
            omega = 2.0 * np.pi * freq
            if C11 > 1e-20:
                zc11 = 1.0 / (1j * omega * C11)
                zf = R5 * zc11 / (R5 + zc11)
            else:
                zf = complex(R5, 0.0)
            z_meas = z_true * (R5 / zf)
            meas_mag.append(abs(z_meas))
            meas_ph.append(cmath.phase(z_meas) * 180.0 / np.pi)
            meas_re.append(z_meas.real)
            meas_nim.append(-z_meas.imag)

        for ax in (self._ax_mag, self._ax_phase, self._ax_nyq):
            ax.clear()

        kw_ideal = dict(color='#2176c7', lw=1.8, label='Ideal DUT')
        kw_meas  = dict(color='#e07820', lw=1.3, ls='--', label='Measured (fw)')

        # Bode magnitude
        ax = self._ax_mag
        ax.loglog(_PREVIEW_FREQS, ideal_mag, **kw_ideal)
        ax.loglog(_PREVIEW_FREQS, meas_mag,  **kw_meas)
        ax.set_xlabel('Frequency (Hz)', fontsize=8)
        ax.set_ylabel('|Z| (Ω)', fontsize=8)
        ax.set_title('Bode — magnitude', fontsize=9, pad=2)
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, which='both', ls='--', lw=0.4, alpha=0.6)
        ax.tick_params(labelsize=7)

        # Bode phase
        ax = self._ax_phase
        ax.semilogx(_PREVIEW_FREQS, ideal_ph, **kw_ideal)
        ax.semilogx(_PREVIEW_FREQS, meas_ph,  **kw_meas)
        ax.set_xlabel('Frequency (Hz)', fontsize=8)
        ax.set_ylabel('Phase (°)', fontsize=8)
        ax.set_title('Bode — phase', fontsize=9, pad=2)
        ax.grid(True, which='both', ls='--', lw=0.4, alpha=0.6)
        ax.tick_params(labelsize=7)

        # Nyquist
        ax = self._ax_nyq
        ax.plot(ideal_re, ideal_nim, **kw_ideal)
        ax.plot(meas_re,  meas_nim,  **kw_meas)
        ax.set_xlabel('Re(Z) (Ω)', fontsize=8)
        ax.set_ylabel('−Im(Z) (Ω)', fontsize=8)
        ax.set_title('Nyquist', fontsize=9, pad=2)
        ax.set_aspect('equal', adjustable='datalim')
        ax.grid(True, ls='--', lw=0.4, alpha=0.6)
        ax.tick_params(labelsize=7)

        self._canvas.draw()

    # ----------------------------------------------------------- interactions

    def _on_comp_click(self, ref):
        if ref in ('R5', 'R15', 'R16', 'R200'):
            cur = self._values[ref]
            val, ok = QInputDialog.getDouble(
                self, f'Edit {ref}', f'{ref} value (Ω):',
                cur, 0.1, 1_000_000.0, 2)
            if ok:
                self._values[ref] = val
        elif ref == 'C11':
            cur_nf = self._values['C11'] * 1e9
            val_nf, ok = QInputDialog.getDouble(
                self, 'Edit C11', 'C11 value (nF):',
                cur_nf, 0.001, 100_000.0, 4)
            if ok:
                self._values['C11'] = val_nf * 1e-9
        self._refresh_value_labels()
        self._refresh_plots()

    def _on_save(self):
        self.values_saved.emit(dict(self._values))
        self.accept()   # close dialog

    def _on_restore(self):
        self._values = dict(_SCHEMATIC_DEFAULTS)
        self.values_saved.emit(dict(self._values))
        self.accept()   # close dialog


# ---------------------------------------------------------------------------
# SimWorker — drop-in replacement for SerialWorker, no real port needed
# ---------------------------------------------------------------------------

class SimWorker(QThread):
    """Wraps VirtualEISDevice with the same signal interface as SerialWorker.

    Threading model — why this matters:
      VirtualEISDevice runs its sweep in a plain Python ``threading.Thread``.
      Emitting PyQt5 signals directly from that thread is unreliable: PyQt5
      may dispatch them as a direct (same-thread) connection, causing Qt
      widget updates to happen off the GUI thread, which leads to the GUI
      freezing or deadlocking when Stop is clicked.

      Fix: the device's ``emit`` callback puts output into a plain Python
      ``queue.Queue``.  This QThread's ``run()`` loop drains that queue and
      emits ``line_received`` from the QThread itself.  Qt then delivers the
      signal to the main thread as a proper QueuedConnection — safe, async,
      no GUI-thread blocking.
    """
    line_received    = pyqtSignal(str)
    connected_sig    = pyqtSignal(str)
    disconnected_sig = pyqtSignal()
    error_sig        = pyqtSignal(str)

    def __init__(self, device: VirtualEISDevice):
        super().__init__()
        self._device    = device
        self._connected = False
        self._rx_q      = queue.Queue()  # device output  → run() → signal
        self._tx_q      = queue.Queue()  # GUI commands   → run() → handle_line

    # -------------------------------------------------- public interface (GUI thread)

    def connect_port(self, port=None, baud=None):
        if self.isRunning():
            return
        # Route ALL device output into the queue — never touch Qt signals here.
        self._device.emit = self._rx_q.put
        self._connected = True
        self.start()                            # launch run() in its own thread
        self.connected_sig.emit("Emulator")

    def disconnect_port(self):
        if not self._connected:
            return
        self._device.running = False            # stop any active sweep
        self._connected = False
        self._tx_q.put(None)                    # sentinel: wake run() → exit
        self._device.emit = lambda line: None   # discard future device output
        self.disconnected_sig.emit()

    def send_command(self, cmd: str):
        """Non-blocking: posts cmd to the worker thread queue."""
        if self._connected:
            self._tx_q.put(cmd)

    # -------------------------------------------------- QThread body (worker thread)

    def run(self):
        """Processes commands and forwards device responses.

        All ``line_received`` emissions happen here (QThread → main thread =
        automatic QueuedConnection).  No Qt signals are ever emitted from
        VirtualEISDevice's own sweep thread.
        """
        while True:
            # Forward any waiting device output as Qt signals (safe from QThread).
            self._drain_rx()

            # Wait up to 10 ms for a command so rx is drained frequently.
            try:
                cmd = self._tx_q.get(timeout=0.01)
            except queue.Empty:
                if not self._connected:
                    break
                continue

            if cmd is None or not self._connected:
                break

            try:
                self._device.handle_line(cmd)
            except Exception as exc:
                self.error_sig.emit(str(exc))

        # Final drain: forward any output produced just before/after Stop.
        self._drain_rx()

    def _drain_rx(self):
        while True:
            try:
                line = self._rx_q.get_nowait()
                self.line_received.emit(line.strip())
            except queue.Empty:
                break


# ---------------------------------------------------------------------------
# EmuWindow — mirrors gui/main.py exactly, plus DUT configuration panel
# ---------------------------------------------------------------------------

class EmuWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EIS Analyzer — STM32F303CCT6 (Emulator)")
        self.resize(1280, 800)

        self._custom_table = None
        self._schematic_values = dict(_SCHEMATIC_DEFAULTS)  # session-only storage

        self.device = VirtualEISDevice(z_fn=self._z_at)
        self.sim    = SimWorker(self.device)
        self.data   = DataModel()

        self._connected     = False
        self._sweep_running = False
        self._total_points  = 0
        self._points_done   = 0
        self._plot_dirty    = False  # set True whenever new data arrives

        self._setup_ui()
        self._connect_signals()

        self._sweep_watchdog = QTimer(self)
        self._sweep_watchdog.setSingleShot(True)
        self._sweep_watchdog.setInterval(5000)
        self._sweep_watchdog.timeout.connect(self._on_sweep_timeout)

        # Plot timer: renders at most 10×/s, completely decoupled from the
        # event queue so incoming DATA/STATUS events are always handled instantly.
        self._plot_timer = QTimer(self)
        self._plot_timer.setInterval(100)
        self._plot_timer.timeout.connect(self._refresh_plots)
        self._plot_timer.start()

    # ---------------------------------------------------------------------- UI

    def _setup_ui(self):
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    def _build_toolbar(self):
        tb: QToolBar = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)

        tb.addWidget(QLabel("  Port "))
        self.port_combo = QComboBox()
        self.port_combo.addItem("(emulator)")
        self.port_combo.setFixedWidth(100)
        tb.addWidget(self.port_combo)

        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedWidth(28)
        refresh_btn.setToolTip("Emulator — no port refresh needed")
        tb.addWidget(refresh_btn)

        tb.addWidget(QLabel("  Baud "))
        baud_combo = QComboBox()
        baud_combo.addItem("115200")
        baud_combo.setFixedWidth(80)
        tb.addWidget(baud_combo)

        tb.addSeparator()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_toggle)
        tb.addWidget(self.connect_btn)

        tb.addSeparator()

        self.start_btn = QPushButton("▶  Start sweep")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)
        tb.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self._send("STOP"))
        tb.addWidget(self.stop_btn)

        tb.addSeparator()

        self.status_btn = QPushButton("Status")
        self.status_btn.setEnabled(False)
        self.status_btn.clicked.connect(lambda: self._send("STATUS"))
        tb.addWidget(self.status_btn)

        self.flash_status_btn = QPushButton("Flash status")
        self.flash_status_btn.setEnabled(False)
        self.flash_status_btn.clicked.connect(lambda: self._send("FLASH_STATUS"))
        tb.addWidget(self.flash_status_btn)

        self.dump_flash_btn = QPushButton("Dump flash")
        self.dump_flash_btn.setEnabled(False)
        self.dump_flash_btn.clicked.connect(lambda: self._send("DUMP_FLASH"))
        tb.addWidget(self.dump_flash_btn)

        self.erase_flash_btn = QPushButton("Erase flash")
        self.erase_flash_btn.setEnabled(False)
        self.erase_flash_btn.clicked.connect(self._on_erase_flash)
        tb.addWidget(self.erase_flash_btn)

        tb.addSeparator()

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export_csv)
        tb.addWidget(self.export_btn)

        self.clear_plots_btn = QPushButton("Clear plots")
        self.clear_plots_btn.clicked.connect(self._on_clear)
        tb.addWidget(self.clear_plots_btn)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- left sidebar (scrollable so DUT section always reachable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(255)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Real GUI's ConfigPanel: Sweep config + Live status + Last point
        self.config_panel = ConfigPanel()
        self.config_panel.settings_applied.connect(self._on_settings_applied)
        sidebar_layout.addWidget(self.config_panel)

        # Emulator-only sections
        sidebar_layout.addWidget(self._build_dut_group())
        sidebar_layout.addWidget(self._build_sim_opts_group())
        sidebar_layout.addStretch()

        scroll.setWidget(sidebar)
        root.addWidget(scroll)

        # ---------- right: plots stacked above console
        right = QSplitter(Qt.Vertical)

        self.plot_widget = PlotWidget()
        right.addWidget(self.plot_widget)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        self.console.setFixedHeight(140)
        right.addWidget(self.console)

        right.setStretchFactor(0, 4)
        right.setStretchFactor(1, 1)

        root.addWidget(right, stretch=1)

    # -------------------------------------------------- DUT configuration group

    def _build_dut_group(self):
        group = QGroupBox("Simulated DUT")
        vbox = QVBoxLayout()

        self.topology_combo = QComboBox()
        self.topology_combo.addItems(
            ["Resistor", "RC parallel", "Randles cell", "Custom CSV"])
        self.topology_combo.currentIndexChanged.connect(self._on_topology_changed)
        vbox.addWidget(self.topology_combo)

        self.param_stack = QStackedWidget()
        self.param_stack.addWidget(self._build_resistor_form())
        self.param_stack.addWidget(self._build_rc_form())
        self.param_stack.addWidget(self._build_randles_form())
        self.param_stack.addWidget(self._build_custom_form())
        vbox.addWidget(self.param_stack)

        # "Simulate Schematic" opens the interactive PCB5 front-end dialog
        self.sim_schematic_btn = QPushButton("Simulate Schematic")
        self.sim_schematic_btn.setToolTip(
            "Open interactive PCB5 schematic — click components to edit values")
        self.sim_schematic_btn.clicked.connect(self._on_simulate_schematic)
        vbox.addWidget(self.sim_schematic_btn)

        self.apply_dut_btn = QPushButton("Apply DUT")
        self.apply_dut_btn.clicked.connect(self._on_apply_dut)
        vbox.addWidget(self.apply_dut_btn)

        group.setLayout(vbox)
        return group

    def _build_resistor_form(self):
        w = QWidget()
        f = QFormLayout(w)
        self.r_value = QLineEdit("5000")
        f.addRow("R (Ω):", self.r_value)
        return w

    def _build_rc_form(self):
        w = QWidget()
        f = QFormLayout(w)
        self.rc_r = QLineEdit("5000")
        self.rc_c = QLineEdit("100e-9")
        f.addRow("R (Ω):", self.rc_r)
        f.addRow("C (F):", self.rc_c)
        return w

    def _build_randles_form(self):
        w = QWidget()
        f = QFormLayout(w)
        self.rand_rs      = QLineEdit("500")
        self.rand_rct     = QLineEdit("5000")
        self.rand_cdl     = QLineEdit("1e-6")
        self.rand_warburg = QLineEdit("0")
        f.addRow("Rs (Ω):",    self.rand_rs)
        f.addRow("Rct (Ω):",   self.rand_rct)
        f.addRow("Cdl (F):",         self.rand_cdl)
        f.addRow("Warburg σ:", self.rand_warburg)
        return w

    def _build_custom_form(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.custom_path_lbl = QLabel("No file loaded")
        self.custom_path_lbl.setWordWrap(True)
        load_btn = QPushButton("Load CSV (freq, Re, Im)")
        load_btn.clicked.connect(self._on_load_csv)
        layout.addWidget(load_btn)
        layout.addWidget(self.custom_path_lbl)
        return w

    def _build_sim_opts_group(self):
        group = QGroupBox("Simulation options")
        f = QFormLayout()
        self.speed_edit = QLineEdit("1")
        self.noise_edit = QLineEdit("0.5")
        f.addRow("Speed ×:", self.speed_edit)
        f.addRow("ADC noise (mV rms):", self.noise_edit)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply_sim_opts)
        f.addRow(apply_btn)
        group.setLayout(f)
        return group

    def _build_statusbar(self):
        sb = self.statusBar()
        self.lbl_conn      = QLabel("  ● Disconnected  ")
        self.lbl_port_info = QLabel("Port: —")
        self.lbl_pts_info  = QLabel("Points: 0")
        self.lbl_flash_sb  = QLabel("Flash: 0 records")
        self.lbl_baud_sb   = QLabel("115200 baud · 8N1  ")
        sb.addWidget(self.lbl_conn)
        sb.addWidget(self.lbl_port_info)
        sb.addWidget(self.lbl_pts_info)
        sb.addWidget(self.lbl_flash_sb)
        sb.addPermanentWidget(self.lbl_baud_sb)

    # --------------------------------------------------------------- signals

    def _connect_signals(self):
        self.sim.line_received.connect(self._on_line_received)
        self.sim.connected_sig.connect(self._on_serial_connected)
        self.sim.disconnected_sig.connect(self._on_serial_disconnected)
        self.sim.error_sig.connect(self._on_serial_error)

    # ------------------------------------------------------------ connection

    def _on_connect_toggle(self):
        if not self._connected:
            self.sim.connect_port()
        else:
            self.sim.disconnect_port()

    def _on_serial_connected(self, port):
        self._connected = True
        self.connect_btn.setText("Disconnect")
        self.lbl_conn.setText("  ● Connected  ")
        self.lbl_port_info.setText(f"Port: {port}")
        for btn in [self.start_btn, self.status_btn,
                    self.flash_status_btn, self.dump_flash_btn,
                    self.erase_flash_btn]:
            btn.setEnabled(True)
        self._log("Connected to emulator (VirtualEISDevice — PCB5 model)", "system")

    def _on_serial_disconnected(self):
        self._connected = False
        self._sweep_running = False
        self._sweep_watchdog.stop()
        self.connect_btn.setText("Connect")
        self.lbl_conn.setText("  ● Disconnected  ")
        self.lbl_port_info.setText("Port: —")
        for btn in [self.start_btn, self.stop_btn, self.status_btn,
                    self.flash_status_btn, self.dump_flash_btn,
                    self.erase_flash_btn]:
            btn.setEnabled(False)
        self._log("Disconnected", "system")

    def _on_serial_error(self, msg):
        self._log("ERROR: " + msg, "error")

    def _on_sweep_timeout(self):
        if self._sweep_running:
            self._sweep_running = False
            self.stop_btn.setEnabled(False)
            self.config_panel.update_status("IDLE")
            self._log(
                "WARNING: No data received for 5 s — sweep timed out", "error")

    # ----------------------------------------------------------- commands

    def _send(self, cmd: str):
        self.sim.send_command(cmd)
        self._log("→ " + cmd, "tx")

    def _on_start(self):
        self.data.clear()
        self.plot_widget.clear_plots()
        self._points_done = 0
        self._compute_total_points()
        self._send("START")

    def _on_erase_flash(self):
        reply = QMessageBox.question(
            self, "Erase flash",
            "This will permanently erase all stored sweep records from the "
            "W25Q32 flash. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._send("ERASE_FLASH")

    def _on_settings_applied(self, s):
        self._send(f"SET_START_FREQ,{s['start_freq']}")
        self._send(f"SET_STOP_FREQ,{s['stop_freq']}")
        self._send(f"SET_STEP_FREQ,{s['step_freq']}")
        self._send(f"SET_RF,{s['rf']:.1f}")

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export sweep data", "eis_sweep.csv", "CSV files (*.csv)")
        if path:
            self.data.export_csv(path)
            self._log(f"Exported {self.data.count()} points to {path}", "system")

    def _on_clear(self):
        self.data.clear()
        self.plot_widget.clear_plots()
        self._points_done = 0
        self._plot_dirty  = False
        self.lbl_pts_info.setText("Points: 0")
        self.export_btn.setEnabled(False)

    # -------------------------------------------------------- DUT model

    def _on_topology_changed(self, index: int):
        self.param_stack.setCurrentIndex(index)

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load DUT impedance table", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            data = np.genfromtxt(path, delimiter=',', names=True)
            freqs = np.asarray(data[data.dtype.names[0]], dtype=float)
            res   = np.asarray(data[data.dtype.names[1]], dtype=float)
            ims   = np.asarray(data[data.dtype.names[2]], dtype=float)
            order = np.argsort(freqs)
            self._custom_table = (freqs[order], res[order], ims[order])
            self.custom_path_lbl.setText(os.path.basename(path))
            self._log("Loaded custom DUT table: " + os.path.basename(path), "system")
        except Exception as exc:
            self._log(f"Failed to load CSV: {exc}", "error")

    def _z_at(self, freq_hz: float):
        topo = self.topology_combo.currentIndex()
        try:
            if topo == 0:
                return z_resistor(freq_hz, float(self.r_value.text()))
            if topo == 1:
                return z_rc_parallel(
                    freq_hz, float(self.rc_r.text()), float(self.rc_c.text()))
            if topo == 2:
                return z_randles(
                    freq_hz,
                    float(self.rand_rs.text()),
                    float(self.rand_rct.text()),
                    float(self.rand_cdl.text()),
                    float(self.rand_warburg.text() or 0.0),
                )
            if topo == 3 and self._custom_table is not None:
                return z_from_table(freq_hz, *self._custom_table)
        except ValueError:
            pass
        return z_resistor(freq_hz, 1.0)

    def _on_apply_dut(self):
        self.device.z_fn = self._z_at
        self._log("DUT model updated — takes effect on next sweep point", "system")

    def _on_apply_sim_opts(self):
        try:
            self.device.speed = max(float(self.speed_edit.text()), 0.001)
            self.device.noise_std_v = (
                max(float(self.noise_edit.text()), 0.0) / 1000.0)
            self._log("Simulation options applied", "system")
        except ValueError:
            self._log("Invalid simulation option value", "error")

    # ------------------------------------------------- Simulate Schematic

    def _on_simulate_schematic(self):
        dlg = SchematicDialog(self._schematic_values, self._z_at, parent=self)
        dlg.values_saved.connect(self._on_schematic_saved)
        dlg.exec_()

    def _on_schematic_saved(self, values: dict):
        self._schematic_values = values
        # Apply R5 as the TIA feedback resistance for all subsequent sweeps
        self.device.rf = values['R5']
        R15, R16 = values['R15'], values['R16']
        denom = R15 + R16
        vbias = 3.3 * R16 / denom if denom > 0 else 1.65
        self._log(
            f"Schematic saved — Rf(R5)={_fmt_val('R5', values['R5'])}, "
            f"C11={_fmt_val('C11', values['C11'])}, "
            f"R15={_fmt_val('R15', R15)}, R16={_fmt_val('R16', R16)}, "
            f"Vbias={vbias:.3f} V",
            "system",
        )
        # Automatically run a sweep with the new values if connected
        if self._connected and not self._sweep_running:
            self._on_start()

    # ---------------------------------------------- incoming line parsing

    def _on_line_received(self, line: str):
        line = line.strip()
        if not line:
            return

        if line.startswith("DATA,"):
            self._parse_data(line)
            self._log("← " + line, "rx")
        elif line.startswith("FLASH_DATA,"):
            self._parse_flash_data(line)
            self._log("← " + line, "rx")
        elif line.startswith("STATUS,"):
            self._parse_status(line)
            self._log("← " + line, "rx")
        elif line.startswith("FLASH_STATUS,"):
            self._parse_flash_status(line)
            self._log("← " + line, "rx")
        elif line.startswith("SWEEP,BEGIN"):
            self._sweep_running = True
            self.stop_btn.setEnabled(True)
            self._sweep_watchdog.start()
            self.config_panel.update_status("RUNNING")
            self._log("← " + line, "rx")
        elif line.startswith("SWEEP,DONE"):
            self._sweep_running = False
            self.stop_btn.setEnabled(False)
            self._sweep_watchdog.stop()
            self._plot_dirty = True   # timer renders the final state within 100 ms
            self.config_panel.update_status(
                "IDLE",
                points_done=self._points_done,
                total_points=self._points_done,
            )
            self._log("← " + line, "rx")
        elif line.startswith("FLASH_DUMP,BEGIN"):
            self.data.clear()
            self.plot_widget.clear_plots()
            self._points_done = 0
            self.lbl_pts_info.setText("Points: 0")
            self.export_btn.setEnabled(False)
            self._log("← " + line, "rx")
        elif line.startswith("ERROR"):
            self._log("← " + line, "error")
        else:
            self._log("← " + line, "rx")

    def _parse_data(self, line: str):
        parts = line.split(',')
        if len(parts) >= 6:
            try:
                freq  = float(parts[1])
                mag   = float(parts[2])
                phase = float(parts[3])
                real  = float(parts[4])
                imag  = float(parts[5])

                self.data.add_point(freq, mag, phase, real, imag)
                self._points_done += 1
                self._sweep_watchdog.start()

                self.config_panel.update_last_point(freq, mag, phase, real, imag)
                self.config_panel.update_status(
                    "RUNNING",
                    current_freq=int(freq),
                    points_done=self._points_done,
                    total_points=self._total_points,
                )
                # Mark plots as needing a redraw; _plot_timer does the actual
                # canvas.draw() calls so this handler stays instant.
                self._plot_dirty = True

                self.lbl_pts_info.setText(f"Points: {self._points_done}")
                self.export_btn.setEnabled(True)
            except (ValueError, IndexError):
                pass

    def _parse_flash_data(self, line: str):
        parts = line.split(',')
        if len(parts) >= 6:
            try:
                freq  = float(parts[1])
                mag   = float(parts[2]) / 100.0
                phase = float(parts[3]) / 100.0
                real  = float(parts[4]) / 100.0
                imag  = float(parts[5]) / 100.0

                self.data.add_point(freq, mag, phase, real, imag)
                self._points_done += 1
                self._plot_dirty = True

                self.lbl_pts_info.setText(f"Points: {self._points_done}")
                self.export_btn.setEnabled(True)
            except (ValueError, IndexError):
                pass

    def _parse_status(self, line: str):
        m_state = re.search(r'STATUS,(IDLE|RUNNING)', line)
        m_flash = re.search(r'FLASH_COUNT=(\d+)', line)
        state       = m_state.group(1) if m_state else "IDLE"
        flash_count = int(m_flash.group(1)) if m_flash else None
        self.config_panel.update_status(state, flash_count=flash_count)
        if flash_count is not None:
            self.lbl_flash_sb.setText(f"Flash: {flash_count} records")

    def _parse_flash_status(self, line: str):
        m_count = re.search(r'COUNT=(\d+)', line)
        m_cap   = re.search(r'CAPACITY=(\d+)', line)
        count = int(m_count.group(1)) if m_count else 0
        cap   = int(m_cap.group(1))   if m_cap   else 0
        self.config_panel.update_status("IDLE", flash_count=count, flash_cap=cap)
        self.lbl_flash_sb.setText(f"Flash: {count} / {cap} records")

    def _compute_total_points(self):
        try:
            start = int(self.config_panel.start_freq.text())
            stop  = int(self.config_panel.stop_freq.text())
            step  = int(self.config_panel.step_freq.text())
            self._total_points = max(1, (stop - start) // step + 1)
        except ValueError:
            self._total_points = 0

    # ------------------------------------------------------------------ plots

    def _refresh_plots(self):
        """Called by _plot_timer every 100 ms. Redraws only when new data arrived.

        Keeping this out of _on_line_received means the event queue is never
        blocked by matplotlib canvas.draw() calls, so STATUS / STOP / any other
        button responds instantly regardless of how fast the sweep is running.
        """
        if self._plot_dirty:
            self._plot_dirty = False
            freqs, mags, phases, reals, imags = self.data.get_arrays()
            if freqs:
                self.plot_widget.update_plots(freqs, mags, phases, reals, imags)

    # ---------------------------------------------------------------- console

    def _log(self, text: str, kind: str = "rx"):
        colors = {
            "rx":     "#2d8a4e",
            "tx":     "#1a6dbf",
            "error":  "#c0392b",
            "system": "#888888",
        }
        color = colors.get(kind, "#555555")
        self.console.append(f'<span style="color:{color};">{text}</span>')
        self.console.moveCursor(QTextCursor.End)

    # --------------------------------------------------------------- cleanup

    def closeEvent(self, event):
        # Schematic values are in-memory only: they reset automatically on close.
        self.device.running = False
        event.accept()


# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = EmuWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
