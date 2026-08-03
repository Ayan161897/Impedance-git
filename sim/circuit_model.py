"""DUT equivalent-circuit models and analog front-end signal synthesis.

This is the configurable "input" side of the simulation: given a DUT
impedance Z(f), ``synthesize_adc_samples`` builds the same two interleaved
ADC channels (reference / TIA signal) that the real PCB5 analog front end
would present, so ``impedance_model`` (the firmware's own algorithm) can
recover Z(f) from them exactly as it would on real hardware.

PCB5 analog front-end topology (from PCB5/Impedance-measurement-3/netlist_new.xml):
  - Signal generator: AD9833BRMZ (25 MHz oscillator), VOUT → 200 Ω (R200ohms1)
      → OPA4141AID op-amp A unity-gain buffer (+IN_A / -IN_A / OUT_A).
  - Reference channel: OUT_A → Electrode connector pin 2 → PA0 (ADC CH1).
      ``vexc_peak`` ≈ 0.30 V peak, derived from the AD9833 sine output
      amplitude on a 3.3 V supply (~0.6 V pp / 2) with no further attenuation.
  - TIA signal channel: current through DUT → Electrode connector pin 1
      → R5_1Kohms1 (1 kΩ, feedback resistor) / C11-3.3nF (feedback cap)
      → OPA4141AID op-amp B inverting TIA output (OUT_B) → PA1 (ADC CH2).
  - TIA virtual ground: +IN_B biased to VDD/2 = 1.65 V via R15/R16
      (two 10 kΩ resistors from VREF+ and GND), so the TIA output is
      centred at 1.65 V (``vbias``).
  - ADC reference: ISL21080CIH333Z-TK 3.3 V precision reference → VDDA/VREF+.
  - Supply: 3.3 V (TS2940CZ33 regulator, digital) / 5 V VBUS (OPA4141AID V+).

Note on ``rf`` (TIA feedback resistor): the physical component on PCB5 is
R5_1Kohms1 = 1 kΩ.  The firmware's ``feedback_resistor`` parameter (set via
SET_RF from the GUI) should match this value for accurate |Z| recovery.  The
GUI currently defaults to 10 kΩ, which will scale all magnitude results by 10×
on real hardware — update the GUI's Rf field to 1000 Ω when using PCB5.
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


def synthesize_adc_samples(freq_hz, z_dut, rf, vexc_peak=0.30, vbias=1.65,
                            noise_std_v=0.0005, rng=None):
    """Builds the 256-sample reference/signal ADC buffers the PCB5 TIA front
    end would produce for a DUT of impedance ``z_dut`` at ``freq_hz``.

    - reference channel (PA0, ADC CH1): OPA4141AID unity-gain buffer output,
      tracks the AD9833 excitation voltage; used as the phase-0 reference.
    - signal channel (PA1, ADC CH2): OPA4141AID inverting TIA output,
      converts current through DUT to voltage via ``rf`` (PCB5: 1 kΩ),
      phase-shifted by angle(Z_dut), centred on ``vbias`` = 1.65 V.

    Adds Gaussian noise and 12-bit quantisation/clipping, matching ADC1
    configuration: VREF+ = 3.3 V, 0–4095 counts (impedance.c:120-121).
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
