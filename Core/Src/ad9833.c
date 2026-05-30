/**
 ******************************************************************************
 * @file           : ad9833.c
 * @brief          : AD9833 DDS Driver
 ******************************************************************************
 */

#include "ad9833.h"
#include "main.h"

extern SPI_HandleTypeDef hspi1;

/* =========================================================
   FSYNC CONTROL
   ========================================================= */

#define FSYNC_LOW() \
    HAL_GPIO_WritePin(AD9833_FSYNC_GPIO_Port, \
                      AD9833_FSYNC_Pin, \
                      GPIO_PIN_RESET)

#define FSYNC_HIGH() \
    HAL_GPIO_WritePin(AD9833_FSYNC_GPIO_Port, \
                      AD9833_FSYNC_Pin, \
                      GPIO_PIN_SET)

/* =========================================================
   WRITE REGISTER
   ========================================================= */

void AD9833_WriteRegister(uint16_t data)
{
    uint8_t tx[2];

    tx[0] = (data >> 8) & 0xFF;
    tx[1] = data & 0xFF;

    FSYNC_LOW();

    HAL_SPI_Transmit(&hspi1,
                     tx,
                     2,
                     HAL_MAX_DELAY);

    FSYNC_HIGH();
}

/* =========================================================
   RESET
   ========================================================= */

void AD9833_Reset(void)
{
    AD9833_WriteRegister(AD9833_B28 | AD9833_RESET);
}

/* =========================================================
   INITIALIZATION
   ========================================================= */

void AD9833_Init(void)
{
    AD9833_Reset();

    HAL_Delay(10);

    AD9833_SetFrequency(1000);

    AD9833_SetPhase(0);

    AD9833_SetSineOutput();
}

/* =========================================================
   SET FREQUENCY
   ========================================================= */

void AD9833_SetFrequency(uint32_t frequency)
{
    uint32_t freqWord;

    uint16_t lsb;
    uint16_t msb;

    freqWord =
        (uint32_t)((double)frequency *
        268435456.0 /
        AD9833_MCLK);

    lsb =
        AD9833_FREQ0_REGISTER |
        (freqWord & 0x3FFF);

    msb =
        AD9833_FREQ0_REGISTER |
        ((freqWord >> 14) & 0x3FFF);

    AD9833_WriteRegister(
        AD9833_B28 | AD9833_RESET);

    AD9833_WriteRegister(lsb);

    AD9833_WriteRegister(msb);

    AD9833_WriteRegister(
        AD9833_B28);
}

/* =========================================================
   SET PHASE
   ========================================================= */

void AD9833_SetPhase(uint16_t phase)
{
    uint16_t phaseWord;

    phaseWord =
        (uint16_t)((phase * 4096.0f) / 360.0f);

    AD9833_WriteRegister(
        AD9833_PHASE0_REGISTER |
        (phaseWord & 0x0FFF));
}

/* =========================================================
   SET WAVEFORM
   ========================================================= */

void AD9833_SetWaveform(AD9833_Mode mode)
{
    switch(mode)
    {
        case AD9833_TRIANGLE:

            AD9833_WriteRegister(
                AD9833_B28 |
                AD9833_MODE);

            break;

        case AD9833_SQUARE:

            AD9833_WriteRegister(
                AD9833_B28 |
                AD9833_OPBITEN |
                AD9833_DIV2);

            break;

        case AD9833_SINE:
        default:

            AD9833_WriteRegister(
                AD9833_B28);

            break;
    }
}

/* =========================================================
   SINE OUTPUT
   ========================================================= */

void AD9833_SetSineOutput(void)
{
    AD9833_SetWaveform(AD9833_SINE);
}

/* =========================================================
   TRIANGLE OUTPUT
   ========================================================= */

void AD9833_SetTriangleOutput(void)
{
    AD9833_SetWaveform(AD9833_TRIANGLE);
}

/* =========================================================
   SQUARE OUTPUT
   ========================================================= */

void AD9833_SetSquareOutput(void)
{
    AD9833_SetWaveform(AD9833_SQUARE);
}

/* =========================================================
   FREQUENCY SWEEP
   ========================================================= */

void AD9833_FrequencySweep(uint32_t start_freq,
                           uint32_t stop_freq,
                           uint32_t step_freq,
                           uint32_t delay_ms)
{
    uint32_t freq;

    for(freq = start_freq;
        freq <= stop_freq;
        freq += step_freq)
    {
        AD9833_SetFrequency(freq);

        HAL_Delay(delay_ms);
    }
}
