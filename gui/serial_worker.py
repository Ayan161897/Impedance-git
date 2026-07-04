import serial
import serial.tools.list_ports
from PyQt5.QtCore import QThread, pyqtSignal


class SerialWorker(QThread):
    line_received = pyqtSignal(str)
    connected_sig = pyqtSignal(str)
    disconnected_sig = pyqtSignal()
    error_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._serial = None
        self._running = False

    def connect_port(self, port, baud=115200):
        try:
            self._serial = serial.Serial(port, baud, timeout=0.1)
            self._running = True
            self.connected_sig.emit(port)
            self.start()
        except Exception as e:
            self.error_sig.emit(str(e))

    def disconnect_port(self):
        self._running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self.disconnected_sig.emit()

    def send_command(self, cmd):
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((cmd + '\r\n').encode('ascii'))
            except Exception as e:
                self.error_sig.emit(str(e))

    def run(self):
        buf = b''
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    buf += self._serial.read(self._serial.in_waiting)
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        text = line.decode('ascii', errors='ignore').strip()
                        if text:
                            self.line_received.emit(text)
                else:
                    self.msleep(10)
            except Exception as e:
                self.error_sig.emit(str(e))
                break

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]
