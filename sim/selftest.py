"""Standalone checks for the virtual EIS device — no serial port needed.

Run: python sim/selftest.py
"""
import protocol
from circuit_model import synthesize_adc_samples, z_randles, z_resistor
from impedance_model import measure_at_frequency
from virtual_device import VirtualEISDevice


def check_protocol_formats():
    # Six-field DATA line: freq, mag, phase, real, imag
    line = protocol.format_data_line(1000, 50.2549, -12.3456, 49.1234, -10.6789)
    assert line == "DATA,1000,50.25,-12.35,49.12,-10.68\r\n", line

    # Positive real and imag
    line = protocol.format_data_line(5000, 100.0, 0.0, 100.0, 0.0)
    assert line == "DATA,5000,100.00,0.00,100.00,0.00\r\n", line

    line = protocol.format_status_line("IDLE", 1000, 100000, 1000, 10000.0, 0)
    assert line == "STATUS,IDLE,START=1000,STOP=100000,STEP=1000,RF=10000.00,FLASH_COUNT=0\r\n", line

    print("protocol formatting: OK")


def check_command_handling():
    lines = []
    device = VirtualEISDevice(z_fn=lambda f: z_resistor(f, 5000.0), emit=lines.append)

    device.handle_line("STATUS")
    device.handle_line("SET_RF,4700")
    device.handle_line("SET_START_FREQ,0")
    device.handle_line("NOT_A_COMMAND")

    assert lines[0].startswith("STATUS,IDLE,"), lines[0]
    assert lines[1] == "OK SET_RF\r\n", lines[1]
    assert lines[2] == "ERROR,BAD_VALUE\r\n", lines[2]
    assert lines[3] == "ERROR,UNKNOWN_COMMAND\r\n", lines[3]

    print("command handling: OK")


def check_resistor_recovery():
    # PCB5 physical Rf = 1 kΩ (R5_1Kohms1).  With vexc_peak = 0.30 V and
    # Z_dut = 5 kΩ, v_sig_peak = 0.30 * 1000 / 5000 = 60 mV — well within
    # ADC range (vbias ± 1.65 V).
    z = z_resistor(10000.0, 5000.0)
    ref, sig = synthesize_adc_samples(10000.0, z, rf=1000.0, noise_std_v=0.0)
    result = measure_at_frequency(ref, sig, 10000, 1000.0)

    assert abs(result['magnitude'] - 5000.0) < 50.0, result
    assert abs(result['phase_deg']) < 1.0, result

    print(f"resistor recovery: |Z|={result['magnitude']:.1f} ohm, "
          f"phase={result['phase_deg']:.2f} deg  OK")


def check_randles_recovery():
    # Frequencies chosen where the 256-sample/~486 kHz acquisition window
    # captures at least a few cycles of the tone (>=~2.6 cycles at 5 kHz).
    # Near the sweep's default start frequency (1 kHz) the window covers
    # under 0.6 cycles and the sine/cosine fit is not reliable — a real
    # firmware/algorithm limitation, not a simulator artifact (see README).
    #
    # PCB5 Rf = 1 kΩ.  DUT parameters chosen so |Z| > 500 Ω at all test
    # frequencies, keeping v_sig_peak = 0.30 * 1000 / 500 = 0.60 V within
    # the ADC input range (vbias ± 1.65 V).
    for freq in (5000.0, 10000.0, 50000.0):
        z_true = z_randles(freq, rs=500.0, rct=5000.0, cdl=1e-6)
        ref, sig = synthesize_adc_samples(freq, z_true, rf=1000.0, noise_std_v=0.0)
        result = measure_at_frequency(ref, sig, freq, 1000.0)
        z_meas = complex(result['real'], result['imag'])
        err = abs(z_meas - z_true) / abs(z_true)

        assert err < 0.02, (freq, z_true, z_meas, err)
        print(f"randles @ {freq:>7.0f} Hz: true={z_true:.1f}  measured={z_meas:.1f}  "
              f"err={err * 100:.2f}%")


if __name__ == "__main__":
    check_protocol_formats()
    check_command_handling()
    check_resistor_recovery()
    check_randles_recovery()
    print("\nAll self-tests passed.")
