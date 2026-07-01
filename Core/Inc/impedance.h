#ifndef IMPEDANCE_H
#define IMPEDANCE_H

#include "stm32f3xx_hal.h"
#include <stdint.h>

/* =========================================================
   SAMPLE CONFIGURATION
   ========================================================= */

#define SAMPLE_COUNT 256

/*
 * ADC1 runs from a 72 MHz async clock. Each channel uses 61.5 sample
 * cycles plus 12.5 conversion cycles, and the scan sequence has two
 * channels. This is the effective sample rate for each interleaved
 * reference/signal pair in adc_buffer.
 */
#define IMP_ADC_CLOCK_HZ              72000000.0f
#define IMP_ADC_SAMPLE_CYCLES         61.5f
#define IMP_ADC_CONVERSION_CYCLES     12.5f
#define IMP_ADC_CHANNEL_COUNT         2.0f
#define IMP_SAMPLE_RATE_HZ            (IMP_ADC_CLOCK_HZ / \
                                      ((IMP_ADC_SAMPLE_CYCLES + \
                                        IMP_ADC_CONVERSION_CYCLES) * \
                                       IMP_ADC_CHANNEL_COUNT))

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
                                 float Rf);

/* Get calculated phase */

float Imp_GetPhase(void);

/* Get magnitude */

float Imp_GetMagnitude(void);

#endif
