#ifndef IMPEDANCE_H
#define IMPEDANCE_H

#include "stm32f3xx_hal.h"
#include <stdint.h>

/* =========================================================
   SAMPLE CONFIGURATION
   ========================================================= */

#define SAMPLE_COUNT 256

/* =========================================================
   IMPEDANCE RESULT STRUCTURE
   ========================================================= */

typedef struct
{
    float magnitude;

    float phaseDeg;

    float realPart;

    float imagPart;

} BodePoint;

/* =========================================================
   GLOBAL ADC BUFFERS
   ========================================================= */

extern uint16_t adc_buffer[2 * SAMPLE_COUNT];

extern float ref_samples[SAMPLE_COUNT];

extern float sig_samples[SAMPLE_COUNT];

/* =========================================================
   FUNCTION PROTOTYPES
   ========================================================= */

/* Initialize impedance module */

void Imp_Init(void);

/* Process ADC samples */

void Process_Impedance(float frequency);

/* Measure impedance at one frequency */

BodePoint Imp_MeasureAtFrequency(uint32_t freqHz,
                                 float Rf,
                                 float Vin_peak);

/* Get calculated phase */

float Imp_GetPhase(void);

/* Get magnitude */

float Imp_GetMagnitude(void);

#endif
