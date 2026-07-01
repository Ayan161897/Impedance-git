#include "flash_log.h"
#include "w25q32.h"
#include <string.h>

#define FLASH_LOG_BASE_ADDRESS      0x000000UL
#define FLASH_LOG_SECTOR_SIZE       4096UL
#define FLASH_LOG_SECTOR_COUNT      4UL
#define FLASH_LOG_REGION_SIZE       (FLASH_LOG_SECTOR_SIZE * FLASH_LOG_SECTOR_COUNT)
#define FLASH_LOG_DATA_OFFSET       256UL
#define FLASH_LOG_DATA_ADDRESS      (FLASH_LOG_BASE_ADDRESS + FLASH_LOG_DATA_OFFSET)
#define FLASH_LOG_PAGE_SIZE         256UL

#define FLASH_LOG_HEADER_MAGIC      0x464C4F47UL /* FLOG */
#define FLASH_LOG_RECORD_MAGIC      0x4D454153UL /* MEAS */
#define FLASH_LOG_VERSION           1UL

typedef struct
{
    uint32_t magic;
    uint32_t version;
    uint32_t record_size;
    uint32_t capacity;
} FlashLogHeader;

static uint32_t record_count = 0;
static uint8_t log_ready = 0;

static uint32_t FlashLog_RecordAddress(uint32_t index)
{
    return FLASH_LOG_DATA_ADDRESS + (index * (uint32_t)sizeof(FlashLogRecord));
}

static void FlashLog_WriteBytes(uint32_t address, const uint8_t *data, uint32_t length)
{
    while(length > 0U)
    {
        uint32_t page_offset = address % FLASH_LOG_PAGE_SIZE;
        uint32_t page_space = FLASH_LOG_PAGE_SIZE - page_offset;
        uint16_t chunk = (length < page_space) ? (uint16_t)length : (uint16_t)page_space;

        W25Q32_WritePage(address, (uint8_t *)data, chunk);

        address += chunk;
        data += chunk;
        length -= chunk;
    }
}

static uint8_t FlashLog_HeaderIsValid(const FlashLogHeader *header)
{
    return (header->magic == FLASH_LOG_HEADER_MAGIC) &&
           (header->version == FLASH_LOG_VERSION) &&
           (header->record_size == sizeof(FlashLogRecord)) &&
           (header->capacity == FlashLog_GetCapacity());
}

static uint32_t FlashLog_ScanRecordCount(void)
{
    uint32_t count = 0;

    for(uint32_t i = 0; i < FlashLog_GetCapacity(); i++)
    {
        FlashLogRecord record;

        W25Q32_ReadData(FlashLog_RecordAddress(i),
                        (uint8_t *)&record,
                        sizeof(record));

        if((record.magic != FLASH_LOG_RECORD_MAGIC) || (record.index != i))
        {
            break;
        }

        count++;
    }

    return count;
}

void FlashLog_Init(void)
{
    FlashLogHeader header;

    W25Q32_ReadData(FLASH_LOG_BASE_ADDRESS,
                    (uint8_t *)&header,
                    sizeof(header));

    if(FlashLog_HeaderIsValid(&header))
    {
        log_ready = 1;
        record_count = FlashLog_ScanRecordCount();
    }
    else
    {
        log_ready = 0;
        record_count = 0;
    }
}

FlashLogStatus FlashLog_Erase(void)
{
    FlashLogHeader header;

    for(uint32_t i = 0; i < FLASH_LOG_SECTOR_COUNT; i++)
    {
        W25Q32_SectorErase(FLASH_LOG_BASE_ADDRESS + (i * FLASH_LOG_SECTOR_SIZE));
    }

    header.magic = FLASH_LOG_HEADER_MAGIC;
    header.version = FLASH_LOG_VERSION;
    header.record_size = sizeof(FlashLogRecord);
    header.capacity = FlashLog_GetCapacity();

    FlashLog_WriteBytes(FLASH_LOG_BASE_ADDRESS,
                        (const uint8_t *)&header,
                        sizeof(header));

    log_ready = 1;
    record_count = 0;

    return FLASH_LOG_OK;
}

FlashLogStatus FlashLog_BeginSweep(void)
{
    return FlashLog_Erase();
}

FlashLogStatus FlashLog_WritePoint(uint32_t freq_hz, const BodePoint *point)
{
    FlashLogRecord record;

    if(!log_ready)
    {
        FlashLogStatus status = FlashLog_Erase();

        if(status != FLASH_LOG_OK)
        {
            return status;
        }
    }

    if(record_count >= FlashLog_GetCapacity())
    {
        return FLASH_LOG_FULL;
    }

    memset(&record, 0, sizeof(record));
    record.magic = FLASH_LOG_RECORD_MAGIC;
    record.index = record_count;
    record.freq_hz = freq_hz;
    record.magnitude = point->magnitude;
    record.phase_deg = point->phaseDeg;
    record.real = point->realPart;
    record.imag = point->imagPart;

    FlashLog_WriteBytes(FlashLog_RecordAddress(record_count),
                        (const uint8_t *)&record,
                        sizeof(record));

    record_count++;

    return FLASH_LOG_OK;
}

FlashLogStatus FlashLog_ReadRecord(uint32_t index, FlashLogRecord *record)
{
    if(index >= record_count)
    {
        return FLASH_LOG_BAD_INDEX;
    }

    W25Q32_ReadData(FlashLog_RecordAddress(index),
                    (uint8_t *)record,
                    sizeof(*record));

    if((record->magic != FLASH_LOG_RECORD_MAGIC) || (record->index != index))
    {
        return FLASH_LOG_BAD_RECORD;
    }

    return FLASH_LOG_OK;
}

uint32_t FlashLog_GetRecordCount(void)
{
    return record_count;
}

uint32_t FlashLog_GetCapacity(void)
{
    return (FLASH_LOG_REGION_SIZE - FLASH_LOG_DATA_OFFSET) /
           (uint32_t)sizeof(FlashLogRecord);
}
