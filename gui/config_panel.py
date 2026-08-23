from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, QTimer

# AD9833 DDS output limit = half its 25 MHz clock (Core/Inc/ad9833.h AD9833_MCLK).
# Firmware rejects SET_START_FREQ/SET_STOP_FREQ above this (Core/Src/main.c).
AD9833_MAX_FREQ_HZ = 12_500_000

# Range where the fixed 256-sample acquisition window and ~486.5 kHz effective
# ADC sample rate (Core/Inc/impedance.h) give a reliable sine/cosine fit.
RECOMMENDED_MIN_FREQ_HZ = 5_000
RECOMMENDED_MAX_FREQ_HZ = 100_000


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

        self.start_freq = QLineEdit("5000")
        self.stop_freq  = QLineEdit("100000")
        self.step_freq  = QLineEdit("1000")

        sweep_form.addRow("Start freq (Hz):", self.start_freq)
        sweep_form.addRow("Stop freq (Hz):",  self.stop_freq)
        sweep_form.addRow("Step freq (Hz):",  self.step_freq)

        self.apply_btn = QPushButton("Apply settings")
        self.apply_btn.clicked.connect(self._on_apply)
        sweep_form.addRow(self.apply_btn)

        sweep_group.setLayout(sweep_form)
        layout.addWidget(sweep_group)

        # --- PCB5 Hardware (fixed values) ---
        hw_group = QGroupBox("PCB5 Hardware")
        hw_form = QFormLayout()
        hw_form.setSpacing(4)

        lbl_rf = QLabel("1 kΩ  (R5, fixed)")
        lbl_rf.setStyleSheet("color: grey;")
        lbl_cf = QLabel("3.3 nF  (C11, fixed)")
        lbl_cf.setStyleSheet("color: grey;")

        hw_form.addRow("TIA feedback R:", lbl_rf)
        hw_form.addRow("TIA feedback C:", lbl_cf)

        hw_group.setLayout(hw_form)
        layout.addWidget(hw_group)

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
            start = int(self.start_freq.text())
            stop  = int(self.stop_freq.text())
            step  = int(self.step_freq.text())
        except ValueError:
            self.apply_btn.setText("Invalid input!")
            QTimer.singleShot(2000, lambda: self.apply_btn.setText("Apply settings"))
            return

        if start <= 0 or stop <= 0 or step <= 0:
            QMessageBox.critical(
                self, "Invalid settings",
                "Start freq, stop freq, and step freq must all be greater than 0."
            )
            return
        if stop < start:
            QMessageBox.critical(
                self, "Invalid settings",
                "Stop frequency must be greater than or equal to start frequency."
            )
            return
        if start > AD9833_MAX_FREQ_HZ or stop > AD9833_MAX_FREQ_HZ:
            QMessageBox.critical(
                self, "Invalid settings",
                f"Start and stop frequency must not exceed {AD9833_MAX_FREQ_HZ:,} Hz "
                "(AD9833 DDS output limit — half its 25 MHz clock). The firmware will "
                "reject anything above this."
            )
            return

        if start < RECOMMENDED_MIN_FREQ_HZ or stop > RECOMMENDED_MAX_FREQ_HZ:
            choice = QMessageBox.warning(
                self, "Frequency outside recommended range",
                "Measurement accuracy is only validated in roughly "
                f"{RECOMMENDED_MIN_FREQ_HZ:,}–{RECOMMENDED_MAX_FREQ_HZ:,} Hz.\n\n"
                "Below ~5 kHz, the fixed 256-sample acquisition window captures too few "
                "cycles of the excitation tone and the sine/cosine fit error can exceed "
                "100%. Above ~100 kHz, there are too few ADC samples per cycle "
                "(~486.5 kHz effective sample rate) for a reliable fit.\n\n"
                "Apply these settings anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if choice != QMessageBox.Yes:
                return

        settings = {
            'start_freq': start,
            'stop_freq':  stop,
            'step_freq':  step,
        }
        self.settings_applied.emit(settings)

    def sync_from_status(self, start, stop, step):
        """Update sweep fields to match values reported by firmware STATUS."""
        self.start_freq.setText(str(start))
        self.stop_freq.setText(str(stop))
        self.step_freq.setText(str(step))

    def set_controls_locked(self, locked):
        """Disable/enable sweep config controls during an active sweep."""
        self.start_freq.setEnabled(not locked)
        self.stop_freq.setEnabled(not locked)
        self.step_freq.setEnabled(not locked)
        self.apply_btn.setEnabled(not locked)

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
