# Virtual EIS hardware simulator

Lets you run the real `gui/main.py`, unmodified, against a Python
"virtual device" instead of the physical board. The virtual device speaks
the exact same UART protocol as the STM32 firmware and runs a Python port
of its impedance-fitting algorithm against a DUT (device under test)
impedance model you choose — a resistor, an RC network, a Randles cell, or
a custom CSV table.

No files under `Core/` or `gui/` are modified by this.

**Hardware reference: PCB5** (`PCB5/Impedance-measurement-3/`).
The analog front-end model (`circuit_model.py`) reflects the PCB5 schematic:
OPA4141AID quad op-amp, AD9833BRMZ on a 25 MHz oscillator, W25Q32JVSSIQ
SPI flash (CS on PB13), ISL21080CIH333Z-TK 3.3 V ADC reference.

**Important — Rf mismatch:** the physical TIA feedback resistor on PCB5 is
R5\_1Kohms1 = **1 kΩ**. The firmware default and the GUI's "Rf (Ω)" field
both start at 10 kΩ. When running against real PCB5 hardware, set the GUI's
Rf field to **1000** before starting a sweep, otherwise all |Z| results will
be 10× too large. The simulator is internally consistent regardless of the
Rf value chosen (it uses the same value for synthesis and fitting).

## One-time setup: virtual COM port pair

The simulator needs a null-modem-style virtual COM port pair so the real
GUI can connect to "hardware" that's actually this Python process on the
other end.

1. Install a null-modem virtual COM port driver. Options:
   - [com0com](https://sourceforge.net/projects/com0com/) — free, but not
     in winget; its driver is unsigned on stock installs, so Windows may
     require enabling test-signing mode (`bcdedit /set testsigning on`,
     needs a reboot) or using a WHQL-signed fork before it'll load.
   - `winget install HHDSoftware.VirtualSerialPortTools` or
     `winget install ElectronicTeam.VirtualSerialPortDriver` — properly
     signed, installable without touching driver-signing settings, but
     check whether their free/trial tier covers an unrestricted virtual
     pair before relying on it.
2. Create a linked pair, e.g. COM10 <-> COM11 (com0com: via its Setup
   Command Prompt, `command> install PortName=COM10 PortName=COM11`; the
   other tools have their own pairing UI).
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
- **Worth a closer look on the firmware/hardware side:** the fixed
  256-sample acquisition window at the ADC's ~486 kHz effective sample
  rate (`impedance.c` `SAMPLE_COUNT`/`IMP_SAMPLE_RATE_HZ`) captures only
  ~0.53 cycles of the excitation tone at the sweep's default *start*
  frequency of 1 kHz (`SWEEP_START_FREQUENCY` in `main.h`). The self-test
  (`sim/selftest.py`) shows the sine/cosine fit's error exploding to
  >100% at 1 kHz and only settling down above roughly 5 kHz (~2.6 cycles).
  This showed up while porting the algorithm to Python, not from any
  change made here — worth checking on real hardware whether low-end
  sweep points are actually usable, or whether `SAMPLE_COUNT` / the ADC
  timing needs revisiting for accuracy near 1 kHz. Flagging this per our
  usual practice of surfacing cross-domain issues rather than changing
  firmware code without asking first.
