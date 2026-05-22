#include "impedance.h"
#include "main.h"
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define SAMPLES_PER_MEASUREMENT  256

static uint16_t adcVin[SAMPLES_PER_MEASUREMENT];
static uint16_t adcTIA[SAMPLES_PER_MEASUREMENT];

void Imp_Init(void)
{
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    HAL_ADC_Start(&hadc1);
    HAL_ADC_Start(&hadc2);
}

BodePoint Imp_MeasureAtFrequency(uint32_t freqHz, float Rf, float Vin_peak)
{
    BodePoint p = {0.0f, 0.0f};
    float sumReVin = 0.0f, sumImVin = 0.0f;
    float sumReTIA = 0.0f, sumImTIA = 0.0f;

    HAL_Delay(25);  // Settling

    float dt = 1.0f / 100000.0f;           // 100 kSps example
    float omega = 2.0f * (float)M_PI * freqHz;

    for (int i = 0; i < SAMPLES_PER_MEASUREMENT; i++)
    {
        HAL_ADC_Start(&hadc1);
        HAL_ADC_PollForConversion(&hadc1, 20);
        adcVin[i] = HAL_ADC_GetValue(&hadc1);

        HAL_ADC_Start(&hadc2);
        HAL_ADC_PollForConversion(&hadc2, 20);
        adcTIA[i] = HAL_ADC_GetValue(&hadc2);

        float t = i * dt;
        float angle = omega * t;

        float vin  = (adcVin[i]  / 4095.0f) * 3.3f;
        float vout = (adcTIA[i]  / 4095.0f) * 3.3f;

        sumReVin += vin  * cosf(angle);
        sumImVin += vin  * sinf(angle);
        sumReTIA += vout * cosf(angle);
        sumImTIA += vout * sinf(angle);
    }

    float N = (float)SAMPLES_PER_MEASUREMENT;
    float magVin = sqrtf(sumReVin*sumReVin + sumImVin*sumImVin) * 2.0f / N;
    float magTIA = sqrtf(sumReTIA*sumReTIA + sumImTIA*sumImTIA) * 2.0f / N;

    float I_peak = magTIA / Rf;
    p.magnitude = (magVin > 0.001f) ? (Vin_peak / I_peak) : 999999.0f;

    float phaseVin = atan2f(sumImVin, sumReVin) * 180.0f / M_PI;
    float phaseTIA = atan2f(sumImTIA, sumReTIA) * 180.0f / M_PI;
    p.phaseDeg = phaseTIA - phaseVin;

    while (p.phaseDeg > 180.0f)  p.phaseDeg -= 360.0f;
    while (p.phaseDeg < -180.0f) p.phaseDeg += 360.0f;

    return p;
}
