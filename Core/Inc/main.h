/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Main header file
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f3xx_hal.h"
#include <stdint.h>
#include <stdio.h>

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */
extern UART_HandleTypeDef huart1;
extern SPI_HandleTypeDef hspi1;
extern ADC_HandleTypeDef hadc1;
extern DMA_HandleTypeDef hdma_adc1;

void Process_Start_Command(void);
void Process_Stop_Command(void);
void Process_Status_Command(void);
void Process_FlashStatus_Command(void);
void Process_EraseFlash_Command(void);
void Process_DumpFlash_Command(void);
void Process_SetStartFrequency(uint32_t value);
void Process_SetStopFrequency(uint32_t value);
void Process_SetStepFrequency(uint32_t value);
void Process_SetFeedbackResistor(float value);
/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define AD9833_FSYNC_Pin GPIO_PIN_4
#define AD9833_FSYNC_GPIO_Port GPIOA
#define W25Q32_CS_Pin GPIO_PIN_12
#define W25Q32_CS_GPIO_Port GPIOB
#define STATUS_LED_Pin GPIO_PIN_13
#define STATUS_LED_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */
/* Frequency Sweep Settings */

#define SWEEP_START_FREQUENCY     1000U
#define SWEEP_STOP_FREQUENCY      100000U
#define SWEEP_STEP_FREQUENCY      1000U

#define SWEEP_DELAY_MS            100
/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
