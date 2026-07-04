"""Literal Python port of ``Core/Src/impedance.c``.

Same constants and same least-squares sine/cosine fit as the firmware
(``Estimate_Tone``, ``Process_Impedance``, ``Imp_MeasureAtFrequency``), so
this can be used both by the simulator and as a standalone way to validate
the firmware's algorithm against known ground truth.
"""
import numpy as np

SAMPLE_COUNT = 256

# impedance.h:19-26
IMP_ADC_CLOCK_HZ = 72_000_000.0
IMP_ADC_SAMPLE_CYCLES = 61.5
IMP_ADC_CONVERSION_CYCLES = 12.5
IMP_ADC_CHANNEL_COUNT = 2.0
IMP_SAMPLE_RATE_HZ = IMP_ADC_CLOCK_HZ / (
    (IMP_ADC_SAMPLE_CYCLES + IMP_ADC_CONVERSION_CYCLES) * IMP_ADC_CHANNEL_COUNT
)

ADC_VREF = 3.3
ADC_MAX = 4095.0


def _estimate_tone(samples, frequency_hz):
    """Port of ``Estimate_Tone`` (impedance.c:41-97)."""
    i = np.arange(SAMPLE_COUNT)
    angle = 2.0 * np.pi * frequency_hz * (i / IMP_SAMPLE_RATE_HZ)
    cos_v = np.cos(angle)
    sin_v = np.sin(angle)

    sum_cc = float(np.sum(cos_v * cos_v))
    sum_ss = float(np.sum(sin_v * sin_v))
    sum_cs = float(np.sum(cos_v * sin_v))
    sum_sample_cos = float(np.sum(samples * cos_v))
    sum_sample_sin = float(np.sum(samples * sin_v))

    determinant = (sum_cc * sum_ss) - (sum_cs * sum_cs)
    if abs(determinant) < 1e-6:
        return 0.0, 0.0

    cos_coeff = ((sum_sample_cos * sum_ss) - (sum_sample_sin * sum_cs)) / determinant
    sin_coeff = ((sum_sample_sin * sum_cc) - (sum_sample_cos * sum_cs)) / determinant

    magnitude = float(np.hypot(cos_coeff, sin_coeff))
    phase_rad = float(np.arctan2(sin_coeff, cos_coeff))
    return magnitude, phase_rad


def process_impedance(ref_counts, sig_counts, frequency_hz):
    """Port of ``Process_Impedance`` (impedance.c:113-176), taking raw ADC
    counts instead of driving real hardware DMA."""
    ref = (np.asarray(ref_counts, dtype=np.float64) * ADC_VREF) / ADC_MAX
    sig = (np.asarray(sig_counts, dtype=np.float64) * ADC_VREF) / ADC_MAX

    ref = ref - ref.mean()
    sig = sig - sig.mean()

    ref_mag, ref_phase = _estimate_tone(ref, frequency_hz)
    sig_mag, sig_phase = _estimate_tone(sig, frequency_hz)

    phase_deg = (sig_phase - ref_phase) * (180.0 / np.pi)
    while phase_deg > 180.0:
        phase_deg -= 360.0
    while phase_deg < -180.0:
        phase_deg += 360.0

    return {
        'magnitude': sig_mag,
        'reference_magnitude': ref_mag,
        'phase_deg': phase_deg,
    }


def measure_at_frequency(ref_counts, sig_counts, freq_hz, rf):
    """Port of ``Imp_MeasureAtFrequency`` (impedance.c:182-218)."""
    tone = process_impedance(ref_counts, sig_counts, float(freq_hz))

    phase_rad = tone['phase_deg'] * (np.pi / 180.0)
    current_peak = tone['magnitude'] / rf

    if current_peak > 1e-6 and tone['reference_magnitude'] > 1e-6:
        magnitude = tone['reference_magnitude'] / current_peak
    else:
        magnitude = 999999.0

    return {
        'magnitude': magnitude,
        'phase_deg': tone['phase_deg'],
        'real': magnitude * np.cos(phase_rad),
        'imag': magnitude * np.sin(phase_rad),
    }
