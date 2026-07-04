"""DUT equivalent-circuit models and analog front-end signal synthesis.

This is the configurable "input" side of the simulation: given a DUT
impedance Z(f), ``synthesize_adc_samples`` builds the same two interleaved
ADC channels (reference / TIA signal) that the real PCB's analog front end
would present, so ``impedance_model`` (the firmware's own algorithm) can
recover Z(f) from them exactly as it would on real hardware.

``vexc_peak``/``vbias`` are engineering approximations of the excitation
amplitude actually reaching the DUT and the analog front end's DC bias —
the exact OPA2140 gain-network and bias-resistor values weren't recoverable
as plain text from the KiCad schematic. ``vexc_peak`` defaults to 10 mV,
matching standard small-signal EIS practice (keeping the electrochemical
system in its linear regime) and keeping the TIA output in range across a
wide span of DUT impedances at the RF default of 10 kOhm, rather than being
pulled from a specific component value.
"""
import cmath

import numpy as np

from impedance_model import ADC_MAX, ADC_VREF, IMP_SAMPLE_RATE_HZ, SAMPLE_COUNT


def z_resistor(freq_hz, r):
    return complex(r, 0.0)


def z_rc_parallel(freq_hz, r, c):
    if freq_hz <= 0:
        return complex(r, 0.0)
    zc = 1.0 / (1j * 2.0 * cmath.pi * freq_hz * c)
    return (r * zc) / (r + zc)


def z_randles(freq_hz, rs, rct, cdl, warburg_sigma=0.0):
    """Rs + (Rct + Warburg) || Cdl — a standard electrochemistry equivalent circuit."""
    if freq_hz <= 0:
        return complex(rs + rct, 0.0)
    omega = 2.0 * cmath.pi * freq_hz
    zc = 1.0 / (1j * omega * cdl)
    z_faradaic = complex(rct, 0.0)
    if warburg_sigma > 0.0:
        z_faradaic += warburg_sigma * (1.0 - 1j) / (omega ** 0.5)
    z_par = (z_faradaic * zc) / (z_faradaic + zc)
    return rs + z_par


def z_from_table(freq_hz, freqs, res, ims):
    """Log-frequency linear interpolation over a user-supplied freq,Re,Im table."""
    log_f = np.log10(freqs)
    target = np.log10(max(freq_hz, freqs[0]))
    re = float(np.interp(target, log_f, res))
    im = float(np.interp(target, log_f, ims))
    return complex(re, im)


def synthesize_adc_samples(freq_hz, z_dut, rf, vexc_peak=0.01, vbias=1.65,
                            noise_std_v=0.0005, rng=None):
    """Builds the 256-sample reference/signal ADC buffers a real TIA front
    end would produce for a DUT of impedance ``z_dut`` at ``freq_hz``.

    - reference channel: excitation feed-through, used as the phase-0 reference.
    - signal channel: excitation current through the DUT, converted to a
      voltage by the transimpedance feedback resistor ``rf``, phase-shifted
      by angle(Z_dut).

    Adds Gaussian noise and 12-bit quantization/clipping, matching the real
    ADC1 configuration (3.3V, 0-4095 counts, impedance.c:120-121).
    """
    if rng is None:
        rng = np.random.default_rng()

    i = np.arange(SAMPLE_COUNT)
    t = i / IMP_SAMPLE_RATE_HZ
    theta = 2.0 * np.pi * freq_hz * t

    z_mag = abs(z_dut)
    z_phase = cmath.phase(z_dut)
    i_peak = vexc_peak / z_mag if z_mag > 1e-9 else 0.0
    v_sig_peak = i_peak * rf

    ref_v = vbias + vexc_peak * np.cos(theta)
    sig_v = vbias + v_sig_peak * np.cos(theta - z_phase)

    if noise_std_v > 0.0:
        ref_v = ref_v + rng.normal(0.0, noise_std_v, SAMPLE_COUNT)
        sig_v = sig_v + rng.normal(0.0, noise_std_v, SAMPLE_COUNT)

    ref_counts = np.clip(np.round(ref_v / ADC_VREF * ADC_MAX), 0, 4095).astype(np.uint16)
    sig_counts = np.clip(np.round(sig_v / ADC_VREF * ADC_MAX), 0, 4095).astype(np.uint16)
    return ref_counts, sig_counts
