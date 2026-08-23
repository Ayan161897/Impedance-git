#ifndef __W25Q32_H
#define __W25Q32_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f3xx_hal.h"
#include <stdint.h>

/* =========================================================
   W25Q32 COMMANDS
   ========================================================= */

#define W25Q32_CMD_WRITE_ENABLE       0x06
#define W25Q32_CMD_WRITE_DISABLE      0x04

#define W25Q32_CMD_READ_STATUS1       0x05

#define W25Q32_CMD_PAGE_PROGRAM       0x02

#define W25Q32_CMD_READ_DATA          0x03

#define W25Q32_CMD_SECTOR_ERASE       0x20

#define W25Q32_CMD_CHIP_ERASE         0xC7

#define W25Q32_CMD_JEDEC_ID           0x9F

/* =========================================================
   JEDEC DEVICE ID
   ========================================================= */

#define W25Q32_JEDEC_ID            0x00EF4016UL  /* Winbond W25Q32JV */

/* =========================================================
   CS PIN
   ========================================================= */

#define W25Q32_CS_Pin              GPIO_PIN_13   /* PB13 — verified from PCB5 schematic net M-PB13 */
#define W25Q32_CS_GPIO_Port        GPIOB

/* =========================================================
   FUNCTIONS
   ========================================================= */

void W25Q32_Init(SPI_HandleTypeDef *spi);

uint32_t W25Q32_ReadID(void);

void W25Q32_WriteEnable(void);

uint8_t W25Q32_ReadStatus(void);

uint8_t W25Q32_WaitBusy(uint32_t timeout_ms);

void W25Q32_SectorErase(uint32_t address);

void W25Q32_ChipErase(void);

void W25Q32_WritePage(uint32_t address,
                      uint8_t *data,
                      uint16_t length);

void W25Q32_ReadData(uint32_t address,
                     uint8_t *data,
                     uint16_t length);

#ifdef __cplusplus
}
#endif

#endif
