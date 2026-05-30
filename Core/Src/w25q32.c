#include "w25q32.h"

static SPI_HandleTypeDef *flash_spi;

/* =========================================================
   CS CONTROL
   ========================================================= */

#define FLASH_CS_LOW() \
HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, \
                  W25Q32_CS_Pin, \
                  GPIO_PIN_RESET)

#define FLASH_CS_HIGH() \
HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, \
                  W25Q32_CS_Pin, \
                  GPIO_PIN_SET)

/* =========================================================
   INIT
   ========================================================= */

void W25Q32_Init(SPI_HandleTypeDef *spi)
{
    flash_spi = spi;

    FLASH_CS_HIGH();

    HAL_Delay(10);
}

/* =========================================================
   WRITE ENABLE
   ========================================================= */

void W25Q32_WriteEnable(void)
{
    uint8_t cmd =
        W25Q32_CMD_WRITE_ENABLE;

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    FLASH_CS_HIGH();
}

/* =========================================================
   STATUS REGISTER
   ========================================================= */

uint8_t W25Q32_ReadStatus(void)
{
    uint8_t cmd =
        W25Q32_CMD_READ_STATUS1;

    uint8_t status = 0;

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    &status,
                    1,
                    HAL_MAX_DELAY);

    FLASH_CS_HIGH();

    return status;
}

/* =========================================================
   WAIT BUSY
   ========================================================= */

void W25Q32_WaitBusy(void)
{
    while(W25Q32_ReadStatus() & 0x01)
    {
    }
}

/* =========================================================
   READ JEDEC ID
   ========================================================= */

uint32_t W25Q32_ReadID(void)
{
    uint8_t cmd =
        W25Q32_CMD_JEDEC_ID;

    uint8_t id[3];

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    id,
                    3,
                    HAL_MAX_DELAY);

    FLASH_CS_HIGH();

    return ((uint32_t)id[0] << 16) |
           ((uint32_t)id[1] << 8)  |
           ((uint32_t)id[2]);
}

/* =========================================================
   SECTOR ERASE
   ========================================================= */

void W25Q32_SectorErase(uint32_t address)
{
    uint8_t cmd[4];

    W25Q32_WriteEnable();

    cmd[0] =
        W25Q32_CMD_SECTOR_ERASE;

    cmd[1] =
        (address >> 16) & 0xFF;

    cmd[2] =
        (address >> 8) & 0xFF;

    cmd[3] =
        address & 0xFF;

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     cmd,
                     4,
                     HAL_MAX_DELAY);

    FLASH_CS_HIGH();

    W25Q32_WaitBusy();
}

/* =========================================================
   CHIP ERASE
   ========================================================= */

void W25Q32_ChipErase(void)
{
    uint8_t cmd =
        W25Q32_CMD_CHIP_ERASE;

    W25Q32_WriteEnable();

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    FLASH_CS_HIGH();

    W25Q32_WaitBusy();
}

/* =========================================================
   PAGE PROGRAM
   ========================================================= */

void W25Q32_WritePage(uint32_t address,
                      uint8_t *data,
                      uint16_t length)
{
    uint8_t header[4];

    W25Q32_WriteEnable();

    header[0] =
        W25Q32_CMD_PAGE_PROGRAM;

    header[1] =
        (address >> 16) & 0xFF;

    header[2] =
        (address >> 8) & 0xFF;

    header[3] =
        address & 0xFF;

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     header,
                     4,
                     HAL_MAX_DELAY);

    HAL_SPI_Transmit(flash_spi,
                     data,
                     length,
                     HAL_MAX_DELAY);

    FLASH_CS_HIGH();

    W25Q32_WaitBusy();
}

/* =========================================================
   READ DATA
   ========================================================= */

void W25Q32_ReadData(uint32_t address,
                     uint8_t *data,
                     uint16_t length)
{
    uint8_t header[4];

    header[0] =
        W25Q32_CMD_READ_DATA;

    header[1] =
        (address >> 16) & 0xFF;

    header[2] =
        (address >> 8) & 0xFF;

    header[3] =
        address & 0xFF;

    FLASH_CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     header,
                     4,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    data,
                    length,
                    HAL_MAX_DELAY);

    FLASH_CS_HIGH();
}
