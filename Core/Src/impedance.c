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

static float referenceMagnitude = 0.0f;

static float phaseDeg = 0.0f;

static float realPart = 0.0f;

static float imagPart = 0.0f;

typedef struct
{
    float magnitude;
    float phaseRad;
} ToneEstimate;

static ToneEstimate Estimate_Tone(const float *samples, float frequency)
{
    ToneEstimate estimate;
    float sumCosCos = 0.0f;
    float sumSinSin = 0.0f;
    float sumCosSin = 0.0f;
    float sumSampleCos = 0.0f;
    float sumSampleSin = 0.0f;

    for(uint32_t i = 0; i < SAMPLE_COUNT; i++)
    {
        float angle =
            2.0f *
            (float)M_PI *
            frequency *
            ((float)i / IMP_SAMPLE_RATE_HZ);

        float cosVal = cosf(angle);
        float sinVal = sinf(angle);

        sumCosCos += cosVal * cosVal;
        sumSinSin += sinVal * sinVal;
        sumCosSin += cosVal * sinVal;
        sumSampleCos += samples[i] * cosVal;
        sumSampleSin += samples[i] * sinVal;
    }

    float determinant =
        (sumCosCos * sumSinSin) -
        (sumCosSin * sumCosSin);

    if(fabsf(determinant) < 0.000001f)
    {
        estimate.magnitude = 0.0f;
        estimate.phaseRad = 0.0f;
        return estimate;
    }

    float cosCoeff =
        ((sumSampleCos * sumSinSin) -
         (sumSampleSin * sumCosSin)) /
        determinant;

    float sinCoeff =
        ((sumSampleSin * sumCosCos) -
         (sumSampleCos * sumCosSin)) /
        determinant;

    estimate.magnitude =
        sqrtf((cosCoeff * cosCoeff) +
              (sinCoeff * sinCoeff));

    estimate.phaseRad =
        atan2f(sinCoeff, cosCoeff);

    return estimate;
}

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

    ToneEstimate refTone = Estimate_Tone(ref_samples, frequency);
    ToneEstimate sigTone = Estimate_Tone(sig_samples, frequency);

    referenceMagnitude = refTone.magnitude;
    magnitude = sigTone.magnitude;

    phaseDeg =
        (sigTone.phaseRad - refTone.phaseRad) *
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
                                 float Rf)
{
    BodePoint p;

    Process_Impedance((float)freqHz);

    float phaseRad = phaseDeg * ((float)M_PI / 180.0f);

    /*
       magnitude = voltage magnitude from TIA output.
       referenceMagnitude = measured excitation/reference voltage.
       TIA relation: Vout = I * Rf
       Therefore: I = Vout / Rf
       Impedance: Z = Vin / I
    */

    float current_peak = magnitude / Rf;

    if((current_peak > 0.000001f) &&
       (referenceMagnitude > 0.000001f))
    {
        p.magnitude = referenceMagnitude / current_peak;
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
