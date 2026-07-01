#ifndef FLASH_LOG_H
#define FLASH_LOG_H

#include "impedance.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    FLASH_LOG_OK = 0,
    FLASH_LOG_FULL,
    FLASH_LOG_BAD_INDEX,
    FLASH_LOG_BAD_RECORD
} FlashLogStatus;

typedef struct
{
    uint32_t magic;
    uint32_t index;
    uint32_t freq_hz;
    float magnitude;
    float phase_deg;
    float real;
    float imag;
} FlashLogRecord;

void FlashLog_Init(void);
FlashLogStatus FlashLog_BeginSweep(void);
FlashLogStatus FlashLog_Erase(void);
FlashLogStatus FlashLog_WritePoint(uint32_t freq_hz, const BodePoint *point);
FlashLogStatus FlashLog_ReadRecord(uint32_t index, FlashLogRecord *record);
uint32_t FlashLog_GetRecordCount(void);
uint32_t FlashLog_GetCapacity(void);

#ifdef __cplusplus
}
#endif

#endif /* FLASH_LOG_H */
