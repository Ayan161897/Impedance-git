"""Emulator main window — identical layout to gui/main.py, wired to VirtualEISDevice.

All toolbar buttons (Connect, Start sweep, Stop, Status, Flash status, Dump
flash, Erase flash, Export CSV, Clear plots) work exactly as with real PCB5
hardware.  An extra "Simulated DUT" section at the bottom of the left panel
lets you choose and parameterise the impedance model the virtual board presents.

No virtual COM port is needed — the virtual device runs in-process.

Usage:
    python sim/run_simulator.py
"""
import os
import queue
import re
import sys

import numpy as np
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
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
