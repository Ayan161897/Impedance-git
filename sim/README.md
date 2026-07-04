# Virtual EIS hardware simulator

Lets you run the real `gui/main.py`, unmodified, against a Python
"virtual device" instead of the physical board. The virtual device speaks
the exact same UART protocol as the STM32 firmware and runs a Python port
of its impedance-fitting algorithm against a DUT (device under test)
impedance model you choose — a resistor, an RC network, a Randles cell, or
a custom CSV table.

No files under `Core/` or `gui/` are modified by this.

## One-time setup: virtual COM port pair

The simulator needs a null-modem-style virtual COM port pair so the real
GUI can connect to "hardware" that's actually this Python process on the
other end.

1. Install [com0com](https://sourceforge.net/projects/com0com/) (free,
   widely used on Windows for exactly this).
2. Create a linked pair, e.g. COM10 <-> COM11, either via the com0com
   Setup Command Prompt:
   ```
   command> install PortName=COM10 PortName=COM11
   ```
   or via its GUI (`com0com Setup Command Prompt` / `setupg.exe`).
3. Point the simulator at one port (e.g. COM11) and the real GUI at the
   other (COM10).

## Running

```
pip install -r sim/requirements.txt   # numpy, pyserial (PyQt5/matplotlib already needed by gui/)

python sim/run_simulator.py           # opens the "Simulated DUT" panel
python gui/main.py                    # the real, unmodified GUI
```

In the simulator panel: pick the COM port that corresponds to the
"hardware" side of your virtual pair (e.g. COM11) and click Connect. In the
real GUI, pick the other port (COM10), click Connect, then use Start
sweep/Apply settings/Dump flash etc. exactly as with real hardware.

Choose a DUT model and click "Apply DUT" to update the ground-truth
preview shown in the simulator panel — this is the analytic Z(f) the DUT
represents, useful for comparing against what the real GUI's Bode/Nyquist
plots recover once measured through the (simulated) analog front end and
firmware algorithm.

`Speed multiplier` scales the sweep timing (the real firmware/hardware
takes ~140 ms/point); set it above 1 to run sweeps faster than real-time.
`ADC noise` adds Gaussian noise (mV rms) to the simulated ADC samples to
see how the fitting algorithm behaves under realistic noise.

## Verifying the port without any GUI

```
python sim/selftest.py
```

Checks the wire-format functions against known-good strings and recovers a
resistor and a Randles cell from synthesized ADC samples to confirm the
ported firmware algorithm is working correctly.

## Notes / things discovered while porting

- The firmware always erases the flash log at the start of every sweep
  (`FlashLog_BeginSweep` -> `FlashLog_Erase`), and `Process_Start_Command`
  has no guard against `START` arriving while a sweep is already running —
  a second `START` re-erases the flash log mid-sweep. The simulator
  reproduces this faithfully rather than silently fixing it, since it's a
  real firmware behavior reachable from the actual GUI (its Start button
  isn't disabled while a sweep is running).
- The impedance fit uses the *nominal* requested frequency as its
  sine/cosine basis, not the AD9833's true output frequency after 28-bit
  tuning-word rounding. The simulator reproduces this too, so you'll see
  the same small frequency-dependent measurement error real hardware has.
