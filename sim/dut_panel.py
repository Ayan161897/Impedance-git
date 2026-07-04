"""Graphical control panel for the virtual EIS hardware.

Lets you pick a simulated DUT (device under test) impedance model, connect
the virtual device to one end of a virtual COM port pair, and watch a
ground-truth Bode/Nyquist preview — while the real, unmodified
``gui/main.py`` connects to the other end exactly as it would to a physical
board.
"""
import os
import sys

import numpy as np
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QSplitter, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget
)

# Reuse the real GUI's plot widget unmodified, for a consistent-looking
# ground-truth preview, without altering anything under gui/.
_GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gui')
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)
from plot_widget import PlotWidget  # noqa: E402

from circuit_model import z_from_table, z_randles, z_rc_parallel, z_resistor  # noqa: E402
from serial_bridge import SerialBridge  # noqa: E402
from virtual_device import VirtualEISDevice  # noqa: E402


class _LogSignal(QObject):
    """Cross-thread-safe bridge: background device/bridge threads emit
    through this signal instead of touching Qt widgets directly."""
    logged = pyqtSignal(str, str)


class DutPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EIS Virtual Hardware — Simulated DUT")
        self.resize(1150, 780)

        self._log_signal = _LogSignal()
        self._log_signal.logged.connect(self._log)

        self.bridge = None
        self._custom_table = None  # (freqs, res, ims)
        self.device = VirtualEISDevice(z_fn=self._z_at)

        self._setup_ui()
        self._refresh_ports()
        self._on_apply_dut()

    # ------------------------------------------------------------------ UI --

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        left = QWidget()
        left.setFixedWidth(290)
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(self._build_connection_group())
        left_layout.addWidget(self._build_dut_group())
        left_layout.addWidget(self._build_sim_options_group())
        left_layout.addStretch()

        right_splitter = QSplitter(Qt.Vertical)
        self.plot_widget = PlotWidget()
        right_splitter.addWidget(self.plot_widget)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        self.console.setFixedHeight(170)
        right_splitter.addWidget(self.console)
        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 1)

        layout.addWidget(left)
        layout.addWidget(right_splitter, stretch=1)

    def _build_connection_group(self):
        group = QGroupBox("Simulator <-> virtual COM port")
        form = QFormLayout()

        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_combo)
        port_row.addWidget(self.refresh_btn)
        form.addRow("Port:", self._wrap(port_row))

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_toggle)
        form.addRow(self.connect_btn)

        group.setLayout(form)
        return group

    def _build_dut_group(self):
        group = QGroupBox("Simulated DUT (input)")
        dut_layout = QVBoxLayout()

        self.topology_combo = QComboBox()
        self.topology_combo.addItems(["Resistor", "RC parallel", "Randles cell", "Custom (CSV)"])
        self.topology_combo.currentIndexChanged.connect(self._on_topology_changed)
        dut_layout.addWidget(self.topology_combo)

        self.param_stack = QStackedWidget()
        self.param_stack.addWidget(self._build_resistor_form())
        self.param_stack.addWidget(self._build_rc_form())
        self.param_stack.addWidget(self._build_randles_form())
        self.param_stack.addWidget(self._build_custom_form())
        dut_layout.addWidget(self.param_stack)

        self.apply_dut_btn = QPushButton("Apply DUT")
        self.apply_dut_btn.clicked.connect(self._on_apply_dut)
        dut_layout.addWidget(self.apply_dut_btn)

        group.setLayout(dut_layout)
        return group

    def _build_sim_options_group(self):
        group = QGroupBox("Simulation options")
        form = QFormLayout()
        self.speed_edit = QLineEdit("1")
        self.noise_edit = QLineEdit("0.5")
        form.addRow("Speed multiplier:", self.speed_edit)
        form.addRow("ADC noise (mV rms):", self.noise_edit)
        self.apply_sim_btn = QPushButton("Apply")
        self.apply_sim_btn.clicked.connect(self._on_apply_sim_opts)
        form.addRow(self.apply_sim_btn)
        group.setLayout(form)
        return group

    def _wrap(self, inner_layout):
        w = QWidget()
        w.setLayout(inner_layout)
        return w

    def _build_resistor_form(self):
        w = QWidget()
        form = QFormLayout(w)
        self.r_value = QLineEdit("5000")
        form.addRow("R (ohm):", self.r_value)
        return w

    def _build_rc_form(self):
        w = QWidget()
        form = QFormLayout(w)
        self.rc_r = QLineEdit("5000")
        self.rc_c = QLineEdit("100e-9")
        form.addRow("R (ohm):", self.rc_r)
        form.addRow("C (F):", self.rc_c)
        return w

    def _build_randles_form(self):
        w = QWidget()
        form = QFormLayout(w)
        self.rand_rs = QLineEdit("100")
        self.rand_rct = QLineEdit("2000")
        self.rand_cdl = QLineEdit("1e-6")
        self.rand_warburg = QLineEdit("0")
        form.addRow("Rs (ohm):", self.rand_rs)
        form.addRow("Rct (ohm):", self.rand_rct)
        form.addRow("Cdl (F):", self.rand_cdl)
        form.addRow("Warburg sigma:", self.rand_warburg)
        return w

    def _build_custom_form(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.custom_path_lbl = QLabel("No file loaded")
        self.custom_path_lbl.setWordWrap(True)
        load_btn = QPushButton("Load CSV (freq,re,im)")
        load_btn.clicked.connect(self._on_load_csv)
        layout.addWidget(load_btn)
        layout.addWidget(self.custom_path_lbl)
        return w

    # ------------------------------------------------------------ DUT model --

    def _on_topology_changed(self, index):
        self.param_stack.setCurrentIndex(index)

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load DUT impedance table", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            data = np.genfromtxt(path, delimiter=',', names=True)
            freqs = np.asarray(data[data.dtype.names[0]], dtype=float)
            res = np.asarray(data[data.dtype.names[1]], dtype=float)
            ims = np.asarray(data[data.dtype.names[2]], dtype=float)
            order = np.argsort(freqs)
            self._custom_table = (freqs[order], res[order], ims[order])
            self.custom_path_lbl.setText(os.path.basename(path))
            self._log("Loaded custom DUT table: " + os.path.basename(path), "system")
        except Exception as e:
            self._log(f"Failed to load CSV: {e}", "error")

    def _z_at(self, freq_hz):
        topo = self.topology_combo.currentIndex()
        try:
            if topo == 0:
                return z_resistor(freq_hz, float(self.r_value.text()))
            if topo == 1:
                return z_rc_parallel(freq_hz, float(self.rc_r.text()), float(self.rc_c.text()))
            if topo == 2:
                return z_randles(freq_hz, float(self.rand_rs.text()), float(self.rand_rct.text()),
                                  float(self.rand_cdl.text()), float(self.rand_warburg.text() or 0.0))
            if topo == 3 and self._custom_table is not None:
                return z_from_table(freq_hz, *self._custom_table)
        except ValueError:
            pass
        return z_resistor(freq_hz, 1.0)

    def _on_apply_dut(self):
        freqs = np.logspace(np.log10(max(self.device.start_freq, 1)),
                             np.log10(max(self.device.stop_freq, 1)), 200)
        zs = [self._z_at(f) for f in freqs]
        mags = [abs(z) for z in zs]
        phases = [float(np.degrees(np.angle(z))) for z in zs]
        reals = [z.real for z in zs]
        imags = [z.imag for z in zs]
        self.plot_widget.update_plots(list(freqs), mags, phases, reals, imags)
        self._log("DUT model applied — ground-truth preview updated", "system")

    def _on_apply_sim_opts(self):
        try:
            self.device.speed = max(float(self.speed_edit.text()), 0.001)
            self.device.noise_std_v = max(float(self.noise_edit.text()), 0.0) / 1000.0
            self._log("Simulation options applied", "system")
        except ValueError:
            self._log("Invalid simulation option value", "error")

    # ------------------------------------------------------------ connection --

    def _refresh_ports(self):
        ports = SerialBridge.list_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports if ports else ["(no ports)"])

    def _on_connect_toggle(self):
        if self.bridge is None:
            port = self.port_combo.currentText()
            try:
                bridge = SerialBridge(
                    self.device,
                    on_line=lambda text: self._log_signal.logged.emit("<- " + text, "rx"))
                bridge.connect(port)
            except Exception as e:
                self._log(f"ERROR: {e}", "error")
                return

            self.bridge = bridge
            self.device.emit = self._make_emit(bridge)
            self.connect_btn.setText("Disconnect")
            self._log(f"Listening on {port} as virtual hardware", "system")
        else:
            self.bridge.disconnect()
            self.bridge = None
            self.device.emit = lambda line: None
            self.connect_btn.setText("Connect")
            self._log("Disconnected", "system")

    def _make_emit(self, bridge):
        def emit(line):
            bridge.write_line(line)
            self._log_signal.logged.emit("-> " + line.strip(), "tx")
        return emit

    def _log(self, text, kind="rx"):
        color_map = {"rx": "#2d8a4e", "tx": "#1a6dbf", "error": "#c0392b", "system": "#888888"}
        color = color_map.get(kind, "#555555")
        self.console.append(f'<span style="color:{color};">{text}</span>')

    def closeEvent(self, event):
        if self.bridge is not None:
            self.bridge.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DutPanel()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
