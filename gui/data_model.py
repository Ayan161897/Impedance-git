import csv
import math
from dataclasses import dataclass
from typing import List


@dataclass
class ImpedancePoint:
    freq: float
    magnitude: float
    phase: float
    real: float
    imag: float


class DataModel:
    def __init__(self):
        self.points: List[ImpedancePoint] = []

    def add_point(self, freq, magnitude, phase, real=None, imag=None):
        if real is None:
            real = magnitude * math.cos(math.radians(phase))
        if imag is None:
            imag = magnitude * math.sin(math.radians(phase))
        self.points.append(ImpedancePoint(freq, magnitude, phase, real, imag))

    def clear(self):
        self.points = []

    def count(self):
        return len(self.points)

    def get_arrays(self):
        if not self.points:
            return [], [], [], [], []
        freqs  = [p.freq      for p in self.points]
        mags   = [p.magnitude for p in self.points]
        phases = [p.phase     for p in self.points]
        reals  = [p.real      for p in self.points]
        imags  = [p.imag      for p in self.points]
        return freqs, mags, phases, reals, imags

    def export_csv(self, filepath):
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Frequency (Hz)', '|Z| (Ohm)',
                'Phase (deg)', 'Re(Z) (Ohm)', 'Im(Z) (Ohm)'
            ])
            for p in self.points:
                writer.writerow([p.freq, p.magnitude, p.phase, p.real, p.imag])
