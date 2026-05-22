#ifndef IMPEDANCE_H
#define IMPEDANCE_H

#include "stm32f3xx_hal.h"

typedef struct {
    float magnitude;     // |Z| in Ohm
    float phaseDeg;      // Phase in degrees
} BodePoint;

void Imp_Init(void);
BodePoint Imp_MeasureAtFrequency(uint32_t freqHz, float Rf, float Vin_peak);

#endif
