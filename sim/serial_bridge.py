"""Feeds a VirtualEISDevice from a real (virtual) COM port.

Replicates the firmware's line-buffered UART RX (``UART_RxCpltCallback``,
uart_comm.c:139-160 — a full command ends at the first '\\r' or '\\n', empty
lines are dropped) so command framing matches exactly what real hardware
would see.
"""
import threading
import time

import serial
import serial.tools.list_ports


class SerialBridge:
    def __init__(self, device, on_line=None):
        self.device = device
        self.on_line = on_line
        self._serial = None
        self._running = False
        self._thread = None
        self._write_lock = threading.Lock()

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port, baud=115200):
        self._serial = serial.Serial(port, baud, timeout=0.1)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass

    def write_line(self, line):
        with self._write_lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.write(line.encode('ascii'))
                except Exception:
                    pass

    def _run(self):
        buf = b''
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    buf += self._serial.read(self._serial.in_waiting)
                    while b'\r' in buf or b'\n' in buf:
                        idx_r = buf.find(b'\r')
                        idx_n = buf.find(b'\n')
                        candidates = [x for x in (idx_r, idx_n) if x != -1]
                        idx = min(candidates)
                        line, buf = buf[:idx], buf[idx + 1:]
                        text = line.decode('ascii', errors='ignore').strip()
                        if text:
                            if self.on_line:
                                self.on_line(text)
                            self.device.handle_line(text)
                else:
                    time.sleep(0.01)
            except Exception:
                break
