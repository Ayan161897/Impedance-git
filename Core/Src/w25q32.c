#include "w25q32.h"

static SPI_HandleTypeDef *flash_spi;

// ---------------- CS CONTROL ----------------

static void CS_LOW(void)
{
    HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port,
                      W25Q32_CS_Pin,
                      GPIO_PIN_RESET);
}

static void CS_HIGH(void)
{
    HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port,
                      W25Q32_CS_Pin,
                      GPIO_PIN_SET);
}

// ---------------- INIT ----------------

void W25Q32_Init(SPI_HandleTypeDef *spi)
{
    flash_spi = spi;

    CS_HIGH();
}

// ---------------- WRITE ENABLE ----------------

void W25Q32_WriteEnable(void)
{
    uint8_t cmd = CMD_WRITE_ENABLE;

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    CS_HIGH();
}

// ---------------- READ STATUS ----------------

static uint8_t ReadStatus(void)
{
    uint8_t cmd = CMD_READ_STATUS;
    uint8_t status;

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    &status,
                    1,
                    HAL_MAX_DELAY);

    CS_HIGH();

    return status;
}

// ---------------- WAIT BUSY ----------------

static void WaitBusy(void)
{
    while(ReadStatus() & 0x01);
}

// ---------------- READ JEDEC ID ----------------

uint32_t W25Q32_ReadID(void)
{
    uint8_t cmd = CMD_JEDEC_ID;
    uint8_t id[3];

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     &cmd,
                     1,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    id,
                    3,
                    HAL_MAX_DELAY);

    CS_HIGH();

    return (id[0] << 16) |
           (id[1] << 8)  |
            id[2];
}

// ---------------- ERASE SECTOR ----------------

void W25Q32_SectorErase(uint32_t address)
{
    uint8_t cmd[4];

    W25Q32_WriteEnable();

    cmd[0] = CMD_SECTOR_ERASE;
    cmd[1] = (address >> 16) & 0xFF;
    cmd[2] = (address >> 8) & 0xFF;
    cmd[3] = address & 0xFF;

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     cmd,
                     4,
                     HAL_MAX_DELAY);

    CS_HIGH();

    WaitBusy();
}

// ---------------- WRITE PAGE ----------------

void W25Q32_WritePage(uint32_t address,
                      uint8_t *data,
                      uint16_t size)
{
    uint8_t cmd[4];

    W25Q32_WriteEnable();

    cmd[0] = CMD_PAGE_PROGRAM;
    cmd[1] = (address >> 16) & 0xFF;
    cmd[2] = (address >> 8) & 0xFF;
    cmd[3] = address & 0xFF;

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     cmd,
                     4,
                     HAL_MAX_DELAY);

    HAL_SPI_Transmit(flash_spi,
                     data,
                     size,
                     HAL_MAX_DELAY);

    CS_HIGH();

    WaitBusy();
}

// ---------------- READ DATA ----------------

void W25Q32_ReadData(uint32_t address,
                     uint8_t *data,
                     uint16_t size)
{
    uint8_t cmd[4];

    cmd[0] = CMD_READ_DATA;
    cmd[1] = (address >> 16) & 0xFF;
    cmd[2] = (address >> 8) & 0xFF;
    cmd[3] = address & 0xFF;

    CS_LOW();

    HAL_SPI_Transmit(flash_spi,
                     cmd,
                     4,
                     HAL_MAX_DELAY);

    HAL_SPI_Receive(flash_spi,
                    data,
                    size,
                    HAL_MAX_DELAY);

    CS_HIGH();
}
