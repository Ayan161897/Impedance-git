/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : ad9833.h
  * @brief          : AD9833 DDS Driver Header File
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef __AD9833_H
#define __AD9833_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/

#include "stm32f3xx_hal.h"
#include <stdint.h>

/* =========================================================
   AD9833 PIN DEFINITIONS
   ========================================================= */

#define AD9833_FSYNC_Pin           GPIO_PIN_4
#define AD9833_FSYNC_GPIO_Port     GPIOA

/* =========================================================
   AD9833 CONTROL REGISTER DEFINITIONS
   ========================================================= */

#define AD9833_B28                 0x2000
#define AD9833_HLB                 0x1000
#define AD9833_FSEL0               0x0000
#define AD9833_FSEL1               0x0800
#define AD9833_PSEL0               0x0000
#define AD9833_PSEL1               0x0400
#define AD9833_RESET               0x0100
#define AD9833_SLEEP1              0x0080
#define AD9833_SLEEP12             0x0040
#define AD9833_OPBITEN             0x0020
#define AD9833_SIGNPIB             0x0010
#define AD9833_DIV2                0x0008
#define AD9833_MODE                0x0002

/* =========================================================
   FREQUENCY REGISTER DEFINITIONS
   ========================================================= */

#define AD9833_FREQ0_REGISTER      0x4000
#define AD9833_FREQ1_REGISTER      0x8000

/* =========================================================
   PHASE REGISTER DEFINITIONS
   ========================================================= */

#define AD9833_PHASE0_REGISTER     0xC000
#define AD9833_PHASE1_REGISTER     0xE000

/* =========================================================
   WAVEFORM MODE ENUM
   ========================================================= */

typedef enum
{
    AD9833_SINE = 0,

    AD9833_TRIANGLE,

    AD9833_SQUARE

} AD9833_Mode;

/* =========================================================
   FUNCTION PROTOTYPES
   ========================================================= */

/* Initialize AD9833 */

void AD9833_Init(void);

/* Reset AD9833 */

void AD9833_Reset(void);

/* Set output frequency */

void AD9833_SetFrequency(uint32_t frequency);

/* Set output phase */

void AD9833_SetPhase(uint16_t phase);

/* Set waveform type */

void AD9833_SetWaveform(AD9833_Mode mode);

/* Set sine wave output */

void AD9833_SetSineOutput(void);

/* Set triangle wave output */

void AD9833_SetTriangleOutput(void);

/* Frequency sweep */

void AD9833_FrequencySweep(uint32_t start_freq,
                           uint32_t stop_freq,
                           uint32_t step_freq,
                           uint32_t delay_ms);

/* Write 16-bit register */

void AD9833_WriteRegister(uint16_t data);

#ifdef __cplusplus
}
#endif

#endif /* __AD9833_H */
