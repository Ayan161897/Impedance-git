#include "impedance.h"
#include "main.h"

#include <math.h>
#include <stdio.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* =========================================================
   GLOBAL BUFFERS
   ========================================================= */

uint16_t adc_buffer[2 * SAMPLE_COUNT];

float ref_samples[SAMPLE_COUNT];

float sig_samples[SAMPLE_COUNT];

/* =========================================================
   GLOBAL RESULTS
   ========================================================= */

static float magnitude = 0.0f;

static float phaseDeg = 0.0f;

static float realPart = 0.0f;

static float imagPart = 0.0f;

/* =========================================================
   INITIALIZATION
   ========================================================= */

void Imp_Init(void)
{
    HAL_ADCEx_Calibration_Start(&hadc1,
                                ADC_SINGLE_ENDED);
}

/* =========================================================
   PROCESS IMPEDANCE
   ========================================================= */

void Process_Impedance(float frequency)
{
    uint32_t i;

    (void)frequency;

    float sumReRef = 0.0f;
    float sumImRef = 0.0f;
    float sumReSig = 0.0f;
    float sumImSig = 0.0f;

    float refMean = 0.0f;
    float sigMean = 0.0f;

    const float ADC_VREF = 3.3f;
    const float ADC_MAX  = 4095.0f;

    HAL_ADC_Start_DMA(&hadc1,
                      (uint32_t*)adc_buffer,
                      2 * SAMPLE_COUNT);

    HAL_Delay(20);

    HAL_ADC_Stop_DMA(&hadc1);

    for(i = 0; i < SAMPLE_COUNT; i++)
    {
        ref_samples[i] =
            ((float)adc_buffer[2 * i] * ADC_VREF) / ADC_MAX;

        sig_samples[i] =
            ((float)adc_buffer[2 * i + 1] * ADC_VREF) / ADC_MAX;

        refMean += ref_samples[i];
        sigMean += sig_samples[i];
    }

    refMean /= SAMPLE_COUNT;
    sigMean /= SAMPLE_COUNT;

    for(i = 0; i < SAMPLE_COUNT; i++)
    {
        ref_samples[i] -= refMean;
        sig_samples[i] -= sigMean;
    }

    for(i = 0; i < SAMPLE_COUNT; i++)
    {
        float angle =
            2.0f *
            (float)M_PI *
            ((float)i / SAMPLE_COUNT);

        float cosVal = cosf(angle);
        float sinVal = sinf(angle);

        sumReRef += ref_samples[i] * cosVal;
        sumImRef += ref_samples[i] * sinVal;

        sumReSig += sig_samples[i] * cosVal;
        sumImSig += sig_samples[i] * sinVal;
    }

    float magRef =
        (2.0f / SAMPLE_COUNT) *
        sqrtf((sumReRef * sumReRef) +
              (sumImRef * sumImRef));

    float magSig =
        (2.0f / SAMPLE_COUNT) *
        sqrtf((sumReSig * sumReSig) +
              (sumImSig * sumImSig));

    (void)magRef;

    magnitude = magSig;

    float phaseRef = atan2f(sumImRef, sumReRef);
    float phaseSig = atan2f(sumImSig, sumReSig);

    phaseDeg =
        (phaseSig - phaseRef) *
        (180.0f / (float)M_PI);

    while(phaseDeg > 180.0f)
        phaseDeg -= 360.0f;

    while(phaseDeg < -180.0f)
        phaseDeg += 360.0f;

    realPart =
        magnitude *
        cosf(phaseDeg * (float)M_PI / 180.0f);

    imagPart =
        magnitude *
        sinf(phaseDeg * (float)M_PI / 180.0f);

}

/* =========================================================
   COMPLETE IMPEDANCE MEASUREMENT
   ========================================================= */

BodePoint Imp_MeasureAtFrequency(uint32_t freqHz,
                                 float Rf,
                                 float Vin_peak)
{
    BodePoint p;

    Process_Impedance((float)freqHz);

    float phaseRad = phaseDeg * ((float)M_PI / 180.0f);

    /*
       magSig = voltage magnitude from TIA output.
       TIA relation: Vout = I * Rf
       Therefore: I = Vout / Rf
       Impedance: Z = Vin / I
    */

    float current_peak = magnitude / Rf;

    if(current_peak > 0.000001f)
    {
        p.magnitude = Vin_peak / current_peak;
    }
    else
    {
        p.magnitude = 999999.0f;
    }

    p.phaseDeg = phaseDeg;

    p.realPart = p.magnitude * cosf(phaseRad);

    p.imagPart = p.magnitude * sinf(phaseRad);

    return p;
}

/* =========================================================
   GET PHASE
   ========================================================= */

float Imp_GetPhase(void)
{
    return phaseDeg;
}

/* =========================================================
   GET MAGNITUDE
   ========================================================= */

float Imp_GetMagnitude(void)
{
    return magnitude;
}
