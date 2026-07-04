from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # Top row: Bode magnitude + Bode phase side by side
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.fig_mag = Figure(figsize=(4, 2.8), tight_layout=True)
        self.ax_mag = self.fig_mag.add_subplot(111)
        self.canvas_mag = FigureCanvas(self.fig_mag)

        self.fig_phase = Figure(figsize=(4, 2.8), tight_layout=True)
        self.ax_phase = self.fig_phase.add_subplot(111)
        self.canvas_phase = FigureCanvas(self.fig_phase)

        top_row.addWidget(self.canvas_mag)
        top_row.addWidget(self.canvas_phase)

        top_widget = QWidget()
        top_widget.setLayout(top_row)

        # Bottom row: Nyquist
        self.fig_nyquist = Figure(figsize=(8, 2.2), tight_layout=True)
        self.ax_nyquist = self.fig_nyquist.add_subplot(111)
        self.canvas_nyquist = FigureCanvas(self.fig_nyquist)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.canvas_nyquist)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(splitter)

        self._init_axes()

    def _style_ax(self, ax, title, xlabel, ylabel):
        ax.set_title(title, fontsize=9, pad=3)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, linestyle='--', linewidth=0.4, alpha=0.5)

    def _init_axes(self):
        self.ax_mag.set_xscale('log')
        self.ax_mag.set_yscale('log')
        self._style_ax(self.ax_mag, 'Bode — magnitude', 'Frequency (Hz)', '|Z| (Ω)')
        self.canvas_mag.draw()

        self.ax_phase.set_xscale('log')
        self._style_ax(self.ax_phase, 'Bode — phase', 'Frequency (Hz)', 'Phase (°)')
        self.canvas_phase.draw()

        self._style_ax(self.ax_nyquist, 'Nyquist', 'Re(Z) (Ω)', '−Im(Z) (Ω)')
        self.canvas_nyquist.draw()

    def update_plots(self, freqs, mags, phases, reals, imags):
        if not freqs:
            return

        neg_imags = [-v for v in imags]

        self.ax_mag.clear()
        self.ax_mag.set_xscale('log')
        self.ax_mag.set_yscale('log')
        self.ax_mag.plot(freqs, mags, color='#2176c7', linewidth=1.2,
                         marker='o', markersize=2)
        self._style_ax(self.ax_mag, 'Bode — magnitude', 'Frequency (Hz)', '|Z| (Ω)')
        self.canvas_mag.draw()

        self.ax_phase.clear()
        self.ax_phase.set_xscale('log')
        self.ax_phase.plot(freqs, phases, color='#1d9e75', linewidth=1.2,
                           marker='o', markersize=2)
        self._style_ax(self.ax_phase, 'Bode — phase', 'Frequency (Hz)', 'Phase (°)')
        self.canvas_phase.draw()

        self.ax_nyquist.clear()
        self.ax_nyquist.plot(reals, neg_imags, color='#d85a30', linewidth=1.2,
                             marker='o', markersize=2)
        self.ax_nyquist.set_aspect('equal', adjustable='datalim')
        self._style_ax(self.ax_nyquist, 'Nyquist', 'Re(Z) (Ω)', '−Im(Z) (Ω)')
        self.canvas_nyquist.draw()

    def clear_plots(self):
        for ax, canvas in [
            (self.ax_mag, self.canvas_mag),
            (self.ax_phase, self.canvas_phase),
            (self.ax_nyquist, self.canvas_nyquist),
        ]:
            ax.clear()
            canvas.draw()
        self._init_axes()
