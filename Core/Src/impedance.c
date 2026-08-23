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

volatile uint8_t adc_dma_done = 0;

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if(hadc->Instance == ADC1)
    {
        adc_dma_done = 1;
    }
}

typedef struct
{
    float magnitude;
    float phaseRad;
} ToneEstimate;

static ToneEstimate Estimate_Tone(const float *samples, float frequency, float t_offset_s)
{
    ToneEstimate estimate;
    float sumCosCos = 0.0f;
    float sumSinSin = 0.0f;
    float sumCosSin = 0.0f;
    float sumSampleCos = 0.0f;
    float sumSampleSin = 0.0f;

    for(uint32_t i = 0; i < SAMPLE_COUNT; i++)
    {
        /* t_offset_s corrects for sequential ADC scan timing:
           CH1 (ref) is sampled first, CH2 (sig) is sampled one
           conversion period later (T_conv = 74/72MHz ≈ 1.028 µs).
           Pass 0.0f for the reference channel and T_conv for signal. */
        float angle =
            2.0f *
            (float)M_PI *
            frequency *
            (((float)i / IMP_SAMPLE_RATE_HZ) + t_offset_s);

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

    /* Model: x = cosCoeff*cos(ωt) + sinCoeff*sin(ωt)
       where cosCoeff = A*cos(φ), sinCoeff = -A*sin(φ).
       Therefore φ = atan2(-sinCoeff, cosCoeff). */
    estimate.phaseRad =
        atan2f(-sinCoeff, cosCoeff);

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

    adc_dma_done = 0;

    HAL_ADC_Start_DMA(&hadc1,
                      (uint32_t*)adc_buffer,
                      2 * SAMPLE_COUNT);

    /* Wait for exactly 2*SAMPLE_COUNT conversions to complete (one-shot DMA).
       At ~486.5 kHz effective rate this takes ~0.53 ms; 10 ms is a safe timeout. */
    uint32_t t_start = HAL_GetTick();
    while(!adc_dma_done)
    {
        if((HAL_GetTick() - t_start) >= 10U)
        {
            break;
        }
    }

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

    /* One ADC conversion period — the delay between CH1 and CH2 in scan mode.
       T_conv = (sample_cycles + conversion_cycles) / ADC_clock
              = (61.5 + 12.5) / 72,000,000 = 1/(2 * IMP_SAMPLE_RATE_HZ)       */
    const float T_conv = 1.0f / (2.0f * IMP_SAMPLE_RATE_HZ);

    ToneEstimate refTone = Estimate_Tone(ref_samples, frequency, 0.0f);
    ToneEstimate sigTone = Estimate_Tone(sig_samples, frequency, T_conv);

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

BodePoint Imp_MeasureAtFrequency(uint32_t freqHz)
{
    BodePoint p;

    Process_Impedance((float)freqHz);

    /*
       PCB5 TIA feedback network: R5 (TIA_RF_OHM) in parallel with C11 (TIA_CF_F).
       Complex feedback impedance:
           Zf = TIA_RF_OHM / (1 + j*omega*TIA_RF_OHM*TIA_CF_F)

       TIA input-output relationship (inverting amplifier):
           Vsig = -IDUT * Zf   =>   ZDUT = -Zf * (Vref / Vsig)

       In magnitude/phase form:
           |ZDUT| = |Zf| * (|Vref| / |Vsig|)
           ∠ZDUT = ∠Zf - measured_phase + 180°   (180° from TIA inversion)
    */

    float omega    = 2.0f * (float)M_PI * (float)freqHz;
    float rc       = omega * TIA_RF_OHM * TIA_CF_F;
    float zf_mag   = TIA_RF_OHM / sqrtf(1.0f + rc * rc);
    float zf_phase_deg = -atanf(rc) * (180.0f / (float)M_PI);

    if((magnitude > 0.000001f) && (referenceMagnitude > 0.000001f))
    {
        p.magnitude = zf_mag * (referenceMagnitude / magnitude);
    }
    else
    {
        p.magnitude = 999999.0f;
    }

    p.phaseDeg = zf_phase_deg - phaseDeg + 180.0f;

    while(p.phaseDeg >  180.0f) p.phaseDeg -= 360.0f;
    while(p.phaseDeg < -180.0f) p.phaseDeg += 360.0f;

    float phaseRad = p.phaseDeg * ((float)M_PI / 180.0f);
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
