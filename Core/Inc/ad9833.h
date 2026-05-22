/**
 ******************************************************************************
 * @file           : ad9833.h
 * @brief          : AD9833 DDS Waveform Generator Driver
 ******************************************************************************
 */

#ifndef AD9833_H
#define AD9833_H

#include "stm32f3xx_hal.h"

typedef enum {
    AD9833_SINE = 0,
    AD9833_TRIANGLE,
    AD9833_SQUARE
} AD9833_Mode;

/* Define FSYNC pin — matches MX_GPIO_Init() which sets PA4 as output */
#define AD9833_FSYNC_GPIO_Port   GPIOA
#define AD9833_FSYNC_Pin         GPIO_PIN_4

/* Function Prototypes */
void AD9833_Init(void);
void AD9833_SetFrequency(uint8_t reg, uint32_t freqHz);
void AD9833_SetPhase(uint8_t reg, uint16_t phaseDeg);
void AD9833_SelectFrequencyRegister(uint8_t reg);
void AD9833_SetMode(AD9833_Mode mode);
void AD9833_OutputEnable(uint8_t enable);
void AD9833_FrequencySweep(uint32_t startHz, uint32_t endHz, uint32_t stepHz, uint32_t delayMs);

#endif /* AD9833_H */
/*
 * ad9833.h
 *
 *  Created on: 22 May 2026
 *      Author: ehsan
 */

#ifndef INC_AD9833_H_
#define INC_AD9833_H_



#endif /* INC_AD9833_H_ */
