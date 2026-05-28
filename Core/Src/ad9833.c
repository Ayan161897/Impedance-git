/**
 ******************************************************************************
 * @file           : ad9833.c
 * @brief          : AD9833 DDS Waveform Generator Driver
 ******************************************************************************
 */

#include "ad9833.h"
#include "main.h"
#include <stdio.h>



extern SPI_HandleTypeDef hspi1;

/* FSYNC Pin Control */
#define FSYNC_LOW()   HAL_GPIO_WritePin(AD9833_FSYNC_GPIO_Port, AD9833_FSYNC_Pin, GPIO_PIN_RESET)
#define FSYNC_HIGH()  HAL_GPIO_WritePin(AD9833_FSYNC_GPIO_Port, AD9833_FSYNC_Pin, GPIO_PIN_SET)

static void AD9833_Write(uint16_t data)
{
    FSYNC_LOW();
    HAL_SPI_Transmit(&hspi1, (uint8_t*)&data, 1, HAL_MAX_DELAY);
    FSYNC_HIGH();
}

/**
 * @brief Initialize AD9833
 */
void AD9833_Init(void)
{
    AD9833_Write(0x0100);        // Reset + Control Register
    HAL_Delay(10);
    AD9833_Write(0x0000);        // Clear reset bit
    printf("AD9833 Initialized\r\n");
}

/**
 * @brief Set output frequency
 * @param reg: 0 or 1 (Frequency Register 0 or 1)
 * @param freqHz: Desired frequency in Hz
 */
void AD9833_SetFrequency(uint32_t freqHz)
{
    uint32_t freqWord = (uint32_t)((freqHz * 268435456.0f) / 25000000.0f);  // 25 MHz MCLK

    uint16_t cmdLSB = 0x4000 | (freqWord & 0x3FFF);
    uint16_t cmdMSB = 0x4000 | ((freqWord >> 14) & 0x3FFF);

    AD9833_Write(cmdLSB);
    AD9833_Write(cmdMSB);
}

/**
 * @brief Set phase shift
 * @param reg: 0 or 1 (Phase Register 0 or 1)
 * @param phaseDeg: Phase in degrees (0-360)
 */
void AD9833_SetPhase(uint16_t phaseDeg)
{
    uint16_t phaseWord = (uint16_t)((phaseDeg * 4096.0f) / 360.0f);
    uint16_t cmd = 0xC000 | (phaseWord & 0x0FFF);

    AD9833_Write(cmd);
}

/**
 * @brief Select which frequency register to use
 */
void AD9833_SelectFrequencyRegister(uint8_t reg)
{
    uint16_t control = 0x2000;
    if (reg) control |= 0x0800;     // FSELECT bit
    AD9833_Write(control);
}

/**
 * @brief Set waveform mode (Sine, Triangle, Square)
 */
void AD9833_SetMode(AD9833_Mode mode)
{
    uint16_t control = 0x2000;      // Base control register

    switch (mode)
    {
        case AD9833_TRIANGLE:
            control |= 0x0002;      // MODE bit
            break;

        case AD9833_SQUARE:
            control |= (1 << 5) | (1 << 8);  // OPBITEN + DIV2
            break;

        case AD9833_SINE:
        default:
            // Default is sine wave
            break;
    }

    AD9833_Write(control);
}

/**
 * @brief Enable/Disable output
 */
void AD9833_OutputEnable(uint8_t enable)
{
    if (enable)
        AD9833_Write(0x2000);      // Normal operation
    else
        AD9833_Write(0x2100);      // Sleep mode (reset bit)
}

/**
 * @brief Perform frequency sweep (useful for testing)
 */
void AD9833_FrequencySweep(uint32_t startHz, uint32_t endHz, uint32_t stepHz, uint32_t delayMs)
{
    for (uint32_t f = startHz; f <= endHz; f += stepHz)
    {
        AD9833_SetFrequency(f);
        HAL_Delay(delayMs);
    }
}

