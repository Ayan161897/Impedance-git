"""Port of the AD9833 tuning-word math from ``Core/Src/ad9833.c``.

Reproduces the 28-bit tuning-word quantization the real DDS applies, so the
simulator's excitation frequency has the same tiny rounding error as real
hardware would (see ``ad9833.c:78-107``, ``ad9833.h`` for ``AD9833_MCLK``).
"""

AD9833_MCLK = 25_000_000.0
TWO_POW_28 = 268435456.0


def tuning_word(frequency_hz):
    return int(frequency_hz * TWO_POW_28 / AD9833_MCLK)


def actual_frequency(frequency_hz):
    """The frequency the DDS truly outputs after 28-bit tuning-word rounding."""
    return tuning_word(frequency_hz) * AD9833_MCLK / TWO_POW_28
