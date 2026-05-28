/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Main header file
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/

#include "stm32f3xx_hal.h"
#include <stdint.h>
#include <stdio.h>

/* =========================================================
   AD9833 CONNECTIONS
   ========================================================= */

#define AD9833_FSYNC_Pin           GPIO_PIN_4
#define AD9833_FSYNC_GPIO_Port     GPIOA

#define AD9833_SCK_Pin             GPIO_PIN_5
#define AD9833_SCK_GPIO_Port       GPIOA

#define AD9833_MISO_Pin            GPIO_PIN_6
#define AD9833_MISO_GPIO_Port      GPIOA

#define AD9833_MOSI_Pin            GPIO_PIN_7
#define AD9833_MOSI_GPIO_Port      GPIOA

/* =========================================================
   UART (CP2102)
   ========================================================= */

#define UART_TX_Pin                GPIO_PIN_9
#define UART_TX_GPIO_Port          GPIOA

#define UART_RX_Pin                GPIO_PIN_10
#define UART_RX_GPIO_Port          GPIOA

/* =========================================================
   ADC INPUTS
   ========================================================= */

/* Reference signal from AD9833 buffer */

#define ADC_REF_Pin                GPIO_PIN_0
#define ADC_REF_GPIO_Port          GPIOA

/* TIA output signal */

#define ADC_SIG_Pin                GPIO_PIN_1
#define ADC_SIG_GPIO_Port          GPIOA

/* =========================================================
   SPI FLASH (W25Q32)
   ========================================================= */

#define W25Q32_CS_Pin              GPIO_PIN_12
#define W25Q32_CS_GPIO_Port        GPIOB

/* =========================================================
   SWD DEBUG
   ========================================================= */

#define SWDIO_Pin                  GPIO_PIN_13
#define SWDIO_GPIO_Port            GPIOA

#define SWCLK_Pin                  GPIO_PIN_14
#define SWCLK_GPIO_Port            GPIOA

#define SWO_Pin                    GPIO_PIN_3
#define SWO_GPIO_Port              GPIOB

/* =========================================================
   STATUS LED
   ========================================================= */

#define STATUS_LED_Pin             GPIO_PIN_13
#define STATUS_LED_GPIO_Port       GPIOC

/* =========================================================
   FREQUENCY SWEEP SETTINGS
   ========================================================= */

/* Default sweep start frequency */

#define SWEEP_START_FREQUENCY      1000.0f

/* Default sweep stop frequency */

#define SWEEP_STOP_FREQUENCY       100000.0f

/* Default sweep step frequency */

#define SWEEP_STEP_FREQUENCY       1000.0f

/* Delay between frequency steps */

#define SWEEP_DELAY_MS             100

/* =========================================================
   FUNCTION PROTOTYPES
   ========================================================= */

void Error_Handler(void);

/* =========================================================
   GLOBAL HANDLES
   ========================================================= */

extern UART_HandleTypeDef huart1;

extern SPI_HandleTypeDef hspi1;

extern ADC_HandleTypeDef hadc1;

extern DMA_HandleTypeDef hdma_adc1;

void Process_Start_Command(void);
void Process_Stop_Command(void);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
