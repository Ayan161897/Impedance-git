import sys
import re
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QComboBox, QLabel, QPushButton, QTextEdit,
    QSplitter, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QFont

from serial_worker import SerialWorker
from data_model import DataModel
from plot_widget import PlotWidget
from config_panel import ConfigPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EIS Analyzer — STM32F303CCT6")
        self.resize(1280, 800)

        self.serial = SerialWorker()
        self.data = DataModel()
        self._connected = False
        self._sweep_running = False
        self._total_points = 0
        self._points_done = 0

        self._setup_ui()
        self._connect_signals()
        self._refresh_ports()

    # ------------------------------------------------------------------ UI --

    def _setup_ui(self):
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)

        tb.addWidget(QLabel("  Port "))
        self.port_combo = QComboBox()
        self.port_combo.setFixedWidth(90)
        tb.addWidget(self.port_combo)

        self.refresh_btn = QPushButton("↺")
        self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setToolTip("Refresh port list")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        tb.addWidget(self.refresh_btn)

        tb.addWidget(QLabel("  Baud "))
        self.baud_combo = QComboBox()
        self.baud_combo.addItem("115200")
        self.baud_combo.setFixedWidth(80)
        tb.addWidget(self.baud_combo)

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
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left sidebar
        self.config_panel = ConfigPanel()
        self.config_panel.setFixedWidth(230)
        self.config_panel.settings_applied.connect(self._on_settings_applied)

        # Right: plots + serial log
        right_splitter = QSplitter(Qt.Vertical)

        self.plot_widget = PlotWidget()
        right_splitter.addWidget(self.plot_widget)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 9))
        self.console.setFixedHeight(140)
        right_splitter.addWidget(self.console)

        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 1)

        layout.addWidget(self.config_panel)
        layout.addWidget(right_splitter, stretch=1)

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

    # ----------------------------------------------------------- signals --

    def _connect_signals(self):
        self.serial.line_received.connect(self._on_line_received)
        self.serial.connected_sig.connect(self._on_serial_connected)
        self.serial.disconnected_sig.connect(self._on_serial_disconnected)
        self.serial.error_sig.connect(self._on_serial_error)

    # --------------------------------------------------------- port mgmt --

    def _refresh_ports(self):
        ports = SerialWorker.list_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports if ports else ["(no ports)"])

    def _on_connect_toggle(self):
        if not self._connected:
            port = self.port_combo.currentText()
            baud = int(self.baud_combo.currentText())
            self.serial.connect_port(port, baud)
        else:
            self.serial.disconnect_port()

    def _on_serial_connected(self, port):
        self._connected = True
        self.connect_btn.setText("Disconnect")
        self.lbl_conn.setText("  ● Connected  ")
        self.lbl_port_info.setText(f"Port: {port}")
        for btn in [self.start_btn, self.stop_btn, self.status_btn,
                    self.flash_status_btn, self.dump_flash_btn,
                    self.erase_flash_btn]:
            btn.setEnabled(True)
        self._log("Connected to " + port, "system")

    def _on_serial_disconnected(self):
        self._connected = False
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

    # ---------------------------------------------------------- commands --

    def _send(self, cmd):
        self.serial.send_command(cmd)
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
            "This will permanently erase all stored sweep records from the W25Q32 flash. Continue?",
            QMessageBox.Yes | QMessageBox.No
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
            self, "Export sweep data", "eis_sweep.csv", "CSV files (*.csv)"
        )
        if path:
            self.data.export_csv(path)
            self._log(f"Exported {self.data.count()} points to {path}", "system")

    def _on_clear(self):
        self.data.clear()
        self.plot_widget.clear_plots()
        self._points_done = 0
        self.lbl_pts_info.setText("Points: 0")
        self.export_btn.setEnabled(False)

    # -------------------------------------------------- incoming parsing --

    def _on_line_received(self, line):
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
            self.config_panel.update_status("RUNNING")
            self._log("← " + line, "rx")
        elif line.startswith("SWEEP,DONE"):
            self._sweep_running = False
            self.config_panel.update_status(
                "IDLE",
                points_done=self._points_done,
                total_points=self._points_done
            )
            self._log("← " + line, "rx")
        elif line.startswith("ERROR"):
            self._log("← " + line, "error")
        else:
            self._log("← " + line, "rx")

    def _parse_data(self, line):
        # DATA,<freq>,<mag>.<xx>,<[+-]phase>.<xx>
        parts = line.split(',')
        if len(parts) >= 4:
            try:
                freq  = float(parts[1])
                mag   = float(parts[2])
                phase = float(parts[3])
                real  = mag * math.cos(math.radians(phase))
                imag  = mag * math.sin(math.radians(phase))

                self.data.add_point(freq, mag, phase, real, imag)
                self._points_done += 1

                self.config_panel.update_last_point(freq, mag, phase, real, imag)
                self.config_panel.update_status(
                    "RUNNING",
                    current_freq=int(freq),
                    points_done=self._points_done,
                    total_points=self._total_points
                )

                freqs, mags, phases, reals, imags = self.data.get_arrays()
                self.plot_widget.update_plots(freqs, mags, phases, reals, imags)

                self.lbl_pts_info.setText(f"Points: {self._points_done}")
                self.export_btn.setEnabled(True)
            except (ValueError, IndexError):
                pass

    def _parse_flash_data(self, line):
        # FLASH_DATA,<freq>,<mag_x100>,<phase_x100>,<real_x100>,<imag_x100>
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

                freqs, mags, phases, reals, imags = self.data.get_arrays()
                self.plot_widget.update_plots(freqs, mags, phases, reals, imags)

                self.lbl_pts_info.setText(f"Points: {self._points_done}")
                self.export_btn.setEnabled(True)
            except (ValueError, IndexError):
                pass

    def _parse_status(self, line):
        # STATUS,IDLE/RUNNING,START=...,STOP=...,STEP=...,RF=...,FLASH_COUNT=...
        m_state = re.search(r'STATUS,(IDLE|RUNNING)', line)
        m_flash = re.search(r'FLASH_COUNT=(\d+)', line)

        state = m_state.group(1) if m_state else "IDLE"
        flash_count = int(m_flash.group(1)) if m_flash else None

        self.config_panel.update_status(state, flash_count=flash_count)
        if flash_count is not None:
            self.lbl_flash_sb.setText(f"Flash: {flash_count} records")

    def _parse_flash_status(self, line):
        # FLASH_STATUS,COUNT=N,CAPACITY=M
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

    # ----------------------------------------------------------- console --

    def _log(self, text, kind="rx"):
        color_map = {
            "rx":     "#2d8a4e",
            "tx":     "#1a6dbf",
            "error":  "#c0392b",
            "system": "#888888",
        }
        color = color_map.get(kind, "#555555")
        self.console.append(f'<span style="color:{color};">{text}</span>')
        self.console.moveCursor(QTextCursor.End)

    # ----------------------------------------------------------- cleanup --

    def closeEvent(self, event):
        self.serial.disconnect_port()
        self.serial.wait(1000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
