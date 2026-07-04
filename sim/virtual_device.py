"""In-process stand-in for the STM32 firmware's command/sweep state machine.

Mirrors ``Core/Src/main.c``'s command handlers and the ``while(1)`` sweep
loop (validation rules, error codes, timing) closely enough that a real
serial link driving this class is indistinguishable from real hardware to
anything upstream (i.e. the unmodified PyQt5 GUI).
"""
import re
import threading
import time

import protocol
from ad9833_model import actual_frequency
from circuit_model import synthesize_adc_samples
from impedance_model import measure_at_frequency

FLASH_CAPACITY = 576  # (16384 - 256) / 28, matches flash_log.c's region/record sizing
ADC_SETTLE_S = 0.020       # main.c:404, Delay_With_Command_Processing(20) after AD9833_SetFrequency
ADC_ACQUIRE_S = 0.020      # impedance.c:127, HAL_Delay(20) during the ADC DMA window
SWEEP_DELAY_S = 0.100      # main.h SWEEP_DELAY_MS


def _parse_uint(text, default=0):
    """Mimics ``strtoul``: parse a leading unsigned integer, default on failure."""
    m = re.match(r'\s*(\d+)', text)
    return int(m.group(1)) if m else default


def _parse_float(text, default=0.0):
    """Mimics ``strtof``: parse a leading float, default on failure."""
    m = re.match(r'\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)', text)
    return float(m.group(1)) if m else default


class VirtualEISDevice:
    def __init__(self, z_fn, rf=10000.0, speed_multiplier=1.0, noise_std_v=0.0005, emit=None):
        self.z_fn = z_fn
        self.rf = rf
        self.speed = max(speed_multiplier, 0.001)
        self.noise_std_v = noise_std_v
        self.emit = emit if emit is not None else (lambda line: None)

        self.start_freq = 1000
        self.stop_freq = 100000
        self.step_freq = 1000

        self.running = False
        self.flash = []

        self._flash_lock = threading.Lock()
        self._sweep_thread = None

    # -------------------------------------------------- command dispatch --

    def handle_line(self, line):
        """Port of ``UART_ProcessCommand`` (uart_comm.c:171-220)."""
        cmd = line.strip()
        if not cmd:
            return

        if cmd == "START":
            self._cmd_start()
        elif cmd == "STOP":
            self._cmd_stop()
        elif cmd == "STATUS":
            self._send_status()
        elif cmd == "FLASH_STATUS":
            self._cmd_flash_status()
        elif cmd == "ERASE_FLASH":
            self._cmd_erase_flash()
        elif cmd == "DUMP_FLASH":
            self._cmd_dump_flash()
        elif cmd.startswith("SET_START_FREQ,"):
            self._cmd_set_start(_parse_uint(cmd[len("SET_START_FREQ,"):]))
        elif cmd.startswith("SET_STOP_FREQ,"):
            self._cmd_set_stop(_parse_uint(cmd[len("SET_STOP_FREQ,"):]))
        elif cmd.startswith("SET_STEP_FREQ,"):
            self._cmd_set_step(_parse_uint(cmd[len("SET_STEP_FREQ,"):]))
        elif cmd.startswith("SET_RF,"):
            self._cmd_set_rf(_parse_float(cmd[len("SET_RF,"):]))
        else:
            self.emit(protocol.format_error("UNKNOWN_COMMAND"))

    # ------------------------------------------------------------ config --

    def _config_is_valid(self):
        """Port of ``Sweep_Config_IsValid`` (main.c:119-125)."""
        return (self.start_freq > 0 and self.stop_freq >= self.start_freq
                and self.step_freq > 0 and self.rf > 0.0)

    def _cmd_set_start(self, value):
        if self.running or value == 0 or value > self.stop_freq:
            self.emit(protocol.format_error("BAD_VALUE"))
            return
        self.start_freq = value
        self.emit(protocol.format_ok("SET_START_FREQ"))

    def _cmd_set_stop(self, value):
        if self.running or value < self.start_freq:
            self.emit(protocol.format_error("BAD_VALUE"))
            return
        self.stop_freq = value
        self.emit(protocol.format_ok("SET_STOP_FREQ"))

    def _cmd_set_step(self, value):
        if self.running or value == 0:
            self.emit(protocol.format_error("BAD_VALUE"))
            return
        self.step_freq = value
        self.emit(protocol.format_ok("SET_STEP_FREQ"))

    def _cmd_set_rf(self, value):
        if self.running or value <= 0.0:
            self.emit(protocol.format_error("BAD_VALUE"))
            return
        self.rf = value
        self.emit(protocol.format_ok("SET_RF"))

    # ------------------------------------------------------------- sweep --

    def _cmd_start(self):
        """Port of ``Process_Start_Command`` (main.c:155-171). Note: like the
        firmware, there is no guard against START arriving while already
        running — it re-validates config and re-erases the flash log, which
        is a real (if surprising) firmware behavior, faithfully reproduced
        rather than "fixed" here."""
        if not self._config_is_valid():
            self.emit(protocol.format_error("BAD_CONFIG"))
            return

        self.flash = []  # FlashLog_BeginSweep() -> FlashLog_Erase(), unconditional

        already_running = self.running
        self.running = True
        self.emit(protocol.format_ok("START"))

        if not already_running:
            self._sweep_thread = threading.Thread(target=self._sweep_loop, daemon=True)
            self._sweep_thread.start()

    def _cmd_stop(self):
        self.running = False
        self.emit(protocol.format_ok("STOP"))

    def _sweep_loop(self):
        """Port of the sweep ``while(1)`` block in main.c:381-442."""
        self.emit(protocol.SWEEP_BEGIN)

        freq = self.start_freq
        while freq <= self.stop_freq and self.running:
            true_freq = actual_frequency(freq)  # AD9833_SetFrequency's real quantized output

            self._sleep(ADC_SETTLE_S)
            if not self.running:
                break

            z_dut = self.z_fn(freq)
            ref_counts, sig_counts = synthesize_adc_samples(
                true_freq, z_dut, self.rf, noise_std_v=self.noise_std_v)

            self._sleep(ADC_ACQUIRE_S)

            # Firmware fits against the requested nominal frequency, not the
            # DDS's true quantized output — reproducing this intentionally
            # surfaces the same small measurement error real hardware has.
            result = measure_at_frequency(ref_counts, sig_counts, freq, self.rf)
            self.emit(protocol.format_data_line(freq, result['magnitude'], result['phase_deg']))

            with self._flash_lock:
                if len(self.flash) >= FLASH_CAPACITY:
                    self.emit(protocol.format_error("FLASH_FULL"))
                else:
                    self.flash.append({
                        'freq_hz': freq,
                        'magnitude': result['magnitude'],
                        'phase_deg': result['phase_deg'],
                        'real': result['real'],
                        'imag': result['imag'],
                    })

            self._sleep(SWEEP_DELAY_S)
            freq += self.step_freq

        self.running = False
        self.emit(protocol.SWEEP_DONE)
        self._send_status()

    def _sleep(self, seconds):
        """Sleeps in small increments so STOP takes effect promptly, mirroring
        ``Delay_With_Command_Processing`` (main.c:127-143); scaled by
        ``speed`` so a full sweep doesn't have to take real wall-clock time."""
        remaining = seconds / self.speed
        step = 0.010 / self.speed
        while remaining > 0 and self.running:
            time.sleep(min(step, remaining))
            remaining -= step

    # -------------------------------------------------------------- misc --

    def _send_status(self):
        self.emit(protocol.format_status_line(
            "RUNNING" if self.running else "IDLE",
            self.start_freq, self.stop_freq, self.step_freq,
            self.rf, len(self.flash)))

    def _cmd_flash_status(self):
        self.emit(protocol.format_flash_status_line(len(self.flash), FLASH_CAPACITY))

    def _cmd_erase_flash(self):
        if self.running:
            self.emit(protocol.format_error("BUSY"))
            return
        self.flash = []
        self.emit(protocol.format_ok("ERASE_FLASH"))

    def _cmd_dump_flash(self):
        if self.running:
            self.emit(protocol.format_error("BUSY"))
            return

        with self._flash_lock:
            records = list(self.flash)

        self.emit(protocol.format_flash_dump_begin(len(records)))
        self.emit(protocol.FLASH_DUMP_FORMAT_HEADER)
        for record in records:
            self.emit(protocol.format_flash_data_line(
                record['freq_hz'], record['magnitude'], record['phase_deg'],
                record['real'], record['imag']))
        self.emit(protocol.FLASH_DUMP_END)
