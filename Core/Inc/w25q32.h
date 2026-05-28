#ifndef W25Q32_H
#define W25Q32_H

#include "stm32f3xx_hal.h"
#include <stdint.h>

// CS PIN
#define W25Q32_CS_Pin GPIO_PIN_12
#define W25Q32_CS_GPIO_Port GPIOB

// COMMANDS
#define CMD_WRITE_ENABLE      0x06
#define CMD_READ_STATUS       0x05
#define CMD_PAGE_PROGRAM      0x02
#define CMD_READ_DATA         0x03
#define CMD_SECTOR_ERASE      0x20
#define CMD_JEDEC_ID          0x9F

void W25Q32_Init(SPI_HandleTypeDef *spi);

uint32_t W25Q32_ReadID(void);

void W25Q32_WriteEnable(void);

void W25Q32_SectorErase(uint32_t address);

void W25Q32_WritePage(uint32_t address,
                      uint8_t *data,
                      uint16_t size);

void W25Q32_ReadData(uint32_t address,
                     uint8_t *data,
                     uint16_t size);

#endif
