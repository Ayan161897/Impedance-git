from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox
)
from PyQt5.QtCore import pyqtSignal, QTimer


class ConfigPanel(QWidget):
    settings_applied = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # --- Sweep config ---
        sweep_group = QGroupBox("Sweep config")
        sweep_form = QFormLayout()
        sweep_form.setSpacing(5)

        self.start_freq = QLineEdit("1000")
        self.stop_freq  = QLineEdit("100000")
        self.step_freq  = QLineEdit("1000")
        self.rf_value   = QLineEdit("10000")

        sweep_form.addRow("Start freq (Hz):", self.start_freq)
        sweep_form.addRow("Stop freq (Hz):",  self.stop_freq)
        sweep_form.addRow("Step freq (Hz):",  self.step_freq)
        sweep_form.addRow("Rf (Ω):",          self.rf_value)

        self.apply_btn = QPushButton("Apply settings")
        self.apply_btn.clicked.connect(self._on_apply)
        sweep_form.addRow(self.apply_btn)

        sweep_group.setLayout(sweep_form)
        layout.addWidget(sweep_group)

        # --- Live status ---
        status_group = QGroupBox("Live status")
        status_form = QFormLayout()
        status_form.setSpacing(4)

        self.lbl_state        = QLabel("IDLE")
        self.lbl_current_freq = QLabel("—")
        self.lbl_points       = QLabel("0 / —")
        self.lbl_flash_count  = QLabel("0")
        self.lbl_flash_cap    = QLabel("—")

        status_form.addRow("State:",          self.lbl_state)
        status_form.addRow("Current freq:",   self.lbl_current_freq)
        status_form.addRow("Points:",         self.lbl_points)
        status_form.addRow("Flash records:",  self.lbl_flash_count)
        status_form.addRow("Flash capacity:", self.lbl_flash_cap)

        status_group.setLayout(status_form)
        layout.addWidget(status_group)

        # --- Last point ---
        last_group = QGroupBox("Last measured point")
        last_form = QFormLayout()
        last_form.setSpacing(4)

        self.lbl_last_freq  = QLabel("—")
        self.lbl_last_mag   = QLabel("—")
        self.lbl_last_phase = QLabel("—")
        self.lbl_last_real  = QLabel("—")
        self.lbl_last_imag  = QLabel("—")

        last_form.addRow("Frequency:",  self.lbl_last_freq)
        last_form.addRow("|Z| (Ω):",   self.lbl_last_mag)
        last_form.addRow("Phase (°):",  self.lbl_last_phase)
        last_form.addRow("Re(Z) (Ω):", self.lbl_last_real)
        last_form.addRow("Im(Z) (Ω):", self.lbl_last_imag)

        last_group.setLayout(last_form)
        layout.addWidget(last_group)

        layout.addStretch()

    def _on_apply(self):
        try:
            settings = {
                'start_freq': int(self.start_freq.text()),
                'stop_freq':  int(self.stop_freq.text()),
                'step_freq':  int(self.step_freq.text()),
                'rf':         float(self.rf_value.text()),
            }
            self.settings_applied.emit(settings)
        except ValueError:
            self.apply_btn.setText("Invalid input!")
            QTimer.singleShot(2000, lambda: self.apply_btn.setText("Apply settings"))

    def update_status(self, state, current_freq=None, points_done=None,
                      total_points=None, flash_count=None, flash_cap=None):
        self.lbl_state.setText(state)
        if current_freq is not None:
            self.lbl_current_freq.setText(f"{current_freq:,} Hz")
        if points_done is not None and total_points is not None:
            self.lbl_points.setText(f"{points_done} / {total_points}")
        if flash_count is not None:
            self.lbl_flash_count.setText(str(flash_count))
        if flash_cap is not None:
            self.lbl_flash_cap.setText(str(flash_cap))

    def update_last_point(self, freq, mag, phase, real, imag):
        self.lbl_last_freq.setText(f"{freq:,.0f} Hz")
        self.lbl_last_mag.setText(f"{mag:.2f} Ω")
        self.lbl_last_phase.setText(f"{phase:.2f}°")
        self.lbl_last_real.setText(f"{real:.2f} Ω")
        self.lbl_last_imag.setText(f"{imag:.2f} Ω")
