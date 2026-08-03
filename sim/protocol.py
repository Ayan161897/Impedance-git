"""Byte-exact ports of the firmware's UART reply formatting.

Every function here mirrors a specific piece of ``Core/Src/uart_comm.c`` /
``Core/Src/main.c`` (see file:line references in the docstrings) so the
simulator's wire output is indistinguishable from the real STM32 firmware.
"""


def scale_x100(value):
    """Port of ``Scale_Float_X100`` (main.c:94-102)."""
    if value >= 0.0:
        return int(value * 100.0 + 0.5)
    return int(value * 100.0 - 0.5)


def format_ok(cmd):
    return f"OK {cmd}\r\n"


def format_error(code):
    return f"ERROR,{code}\r\n"


def format_data_line(freq_hz, magnitude, phase_deg, real_part, imag_part):
    """Port of ``UART_SendImpedanceData`` (uart_comm.c:98-145).

    Six-field format: DATA,<freq>,<mag>,<phase>,<real>,<imag>
    All float fields are encoded as signed fixed-point with two decimal places,
    matching the firmware's snprintf pattern exactly.
    """
    mag_x100   = int(magnitude * 100.0 + 0.5)
    phase_x100 = scale_x100(phase_deg)
    real_x100  = scale_x100(real_part)
    imag_x100  = scale_x100(imag_part)

    phase_abs = abs(phase_x100)
    real_abs  = abs(real_x100)
    imag_abs  = abs(imag_x100)

    ps = "-" if phase_x100 < 0 else ""
    rs = "-" if real_x100  < 0 else ""
    is_ = "-" if imag_x100  < 0 else ""

    return (f"DATA,{int(freq_hz)},"
            f"{mag_x100 // 100}.{mag_x100 % 100:02d},"
            f"{ps}{phase_abs // 100}.{phase_abs % 100:02d},"
            f"{rs}{real_abs // 100}.{real_abs % 100:02d},"
            f"{is_}{imag_abs // 100}.{imag_abs % 100:02d}\r\n")


def format_status_line(state, start_freq, stop_freq, step_freq, rf, flash_count):
    """Port of ``Send_Status`` (main.c:80-92)."""
    rf_x100 = int(rf * 100.0 + 0.5)
    return (f"STATUS,{state},START={int(start_freq)},STOP={int(stop_freq)},"
            f"STEP={int(step_freq)},RF={rf_x100 // 100}.{rf_x100 % 100:02d},"
            f"FLASH_COUNT={flash_count}\r\n")


def format_flash_status_line(count, capacity):
    """Port of ``Process_FlashStatus_Command`` (main.c:184-189)."""
    return f"FLASH_STATUS,COUNT={count},CAPACITY={capacity}\r\n"


def format_flash_dump_begin(count):
    return f"FLASH_DUMP,BEGIN,COUNT={count}\r\n"


FLASH_DUMP_FORMAT_HEADER = "FLASH_DUMP,FORMAT,FREQ_HZ,MAG_X100,PHASE_X100,REAL_X100,IMAG_X100\r\n"
FLASH_DUMP_END = "FLASH_DUMP,END\r\n"
SWEEP_BEGIN = "SWEEP,BEGIN\r\n"
SWEEP_DONE = "SWEEP,DONE\r\n"


def format_flash_data_line(freq_hz, magnitude, phase_deg, real, imag):
    """Port of ``Send_Flash_Record`` (main.c:104-117)."""
    magnitude_x100 = int(magnitude * 100.0 + 0.5)
    phase_x100 = scale_x100(phase_deg)
    real_x100 = scale_x100(real)
    imag_x100 = scale_x100(imag)
    return f"FLASH_DATA,{int(freq_hz)},{magnitude_x100},{phase_x100},{real_x100},{imag_x100}\r\n"
