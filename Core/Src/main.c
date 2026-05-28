/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "w25q32.h"
#include "ad9833.h"
#include <string.h>
#include <math.h>

/* Private variables ---------------------------------------------------------*/

ADC_HandleTypeDef hadc1;

SPI_HandleTypeDef hspi1;

UART_HandleTypeDef huart1;

DMA_HandleTypeDef hdma_adc1;

/* Private function prototypes -----------------------------------------------*/

void SystemClock_Config(void);

static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_ADC1_Init(void);
static void MX_SPI1_Init(void);
static void MX_USART1_UART_Init(void);

/* USER CODE BEGIN PV */

uint8_t tx_buffer[64];
uint8_t rx_buffer[64];

uint8_t flash_tx[5] = {1,2,3,4,5};
uint8_t flash_rx[5];

uint32_t flash_id;

uint16_t adc_ref;
uint16_t adc_sig;

/* USER CODE END PV */

/* USER CODE BEGIN 0 */

int __io_putchar(int ch)
{
    HAL_UART_Transmit(&huart1,
                      (uint8_t *)&ch,
                      1,
                      HAL_MAX_DELAY);

    return ch;
}

/* USER CODE END 0 */

int main(void)
{

  /* MCU Configuration--------------------------------------------------------*/

  HAL_Init();

  SystemClock_Config();

  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC1_Init();
  MX_SPI1_Init();
  MX_USART1_UART_Init();

  /* USER CODE BEGIN 2 */

  HAL_ADCEx_Calibration_Start(&hadc1,
                              ADC_SINGLE_ENDED);

  /* SPI FLASH INIT */

  W25Q32_Init(&hspi1);

  flash_id = W25Q32_ReadID();

  printf("FLASH ID = 0x%08lX\r\n",
         flash_id);

  /* FLASH TEST */

  W25Q32_SectorErase(0x000000);

  W25Q32_WritePage(0x000000,
                   flash_tx,
                   5);

  W25Q32_ReadData(0x000000,
                  flash_rx,
                  5);

  printf("FLASH READ: %d %d %d %d %d\r\n",
         flash_rx[0],
         flash_rx[1],
         flash_rx[2],
         flash_rx[3],
         flash_rx[4]);

  /* AD9833 INIT */

  AD9833_Init();

  AD9833_SetFrequency(1000);

  printf("AD9833 Initialized\r\n");

  /* USER CODE END 2 */

  while (1)
  {
      float freq;

      for(freq = SWEEP_START_FREQUENCY;
          freq <= SWEEP_STOP_FREQUENCY;
          freq += SWEEP_STEP_FREQUENCY)
      {
          /* Set DDS frequency */

          AD9833_SetFrequency(freq);

          HAL_Delay(10);

          /* Read ADC signals */

          HAL_ADC_Start(&hadc1);

          HAL_ADC_PollForConversion(&hadc1,
                                    HAL_MAX_DELAY);

          adc_ref = HAL_ADC_GetValue(&hadc1);

          HAL_ADC_PollForConversion(&hadc1,
                                    HAL_MAX_DELAY);

          adc_sig = HAL_ADC_GetValue(&hadc1);

          HAL_ADC_Stop(&hadc1);

          /* Send results over UART */

          printf("FREQ=%.2f Hz  REF=%u  SIG=%u\r\n",
                 freq,
                 adc_ref,
                 adc_sig);

          /* Toggle status LED */

          HAL_GPIO_TogglePin(STATUS_LED_GPIO_Port,
                             STATUS_LED_Pin);

          HAL_Delay(SWEEP_DELAY_MS);
      }
  }
}

/**
  * @brief System Clock Configuration
  * @retval None
  */

void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};

  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  RCC_OscInitStruct.OscillatorType =
      RCC_OSCILLATORTYPE_HSE;

  RCC_OscInitStruct.HSEState =
      RCC_HSE_ON;

  RCC_OscInitStruct.PLL.PLLState =
      RCC_PLL_ON;

  RCC_OscInitStruct.PLL.PLLSource =
      RCC_PLLSOURCE_HSE;

  RCC_OscInitStruct.PLL.PLLMUL =
      RCC_PLL_MUL9;

  HAL_RCC_OscConfig(&RCC_OscInitStruct);

  RCC_ClkInitStruct.ClockType =
      RCC_CLOCKTYPE_HCLK |
      RCC_CLOCKTYPE_SYSCLK |
      RCC_CLOCKTYPE_PCLK1 |
      RCC_CLOCKTYPE_PCLK2;

  RCC_ClkInitStruct.SYSCLKSource =
      RCC_SYSCLKSOURCE_PLLCLK;

  RCC_ClkInitStruct.AHBCLKDivider =
      RCC_SYSCLK_DIV1;

  RCC_ClkInitStruct.APB1CLKDivider =
      RCC_HCLK_DIV2;

  RCC_ClkInitStruct.APB2CLKDivider =
      RCC_HCLK_DIV1;

  HAL_RCC_ClockConfig(&RCC_ClkInitStruct,
                      FLASH_LATENCY_2);

  PeriphClkInit.PeriphClockSelection =
      RCC_PERIPHCLK_USART1 |
      RCC_PERIPHCLK_ADC12;

  PeriphClkInit.Usart1ClockSelection =
      RCC_USART1CLKSOURCE_PCLK2;

  PeriphClkInit.Adc12ClockSelection =
      RCC_ADC12PLLCLK_DIV1;

  HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit);
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */

static void MX_ADC1_Init(void)
{
  ADC_ChannelConfTypeDef sConfig = {0};

  hadc1.Instance = ADC1;

  hadc1.Init.ClockPrescaler =
      ADC_CLOCK_ASYNC_DIV1;

  hadc1.Init.Resolution =
      ADC_RESOLUTION_12B;

  hadc1.Init.DataAlign =
      ADC_DATAALIGN_RIGHT;

  hadc1.Init.ScanConvMode =
      ADC_SCAN_ENABLE;

  hadc1.Init.EOCSelection =
      ADC_EOC_SEQ_CONV;

  hadc1.Init.LowPowerAutoWait =
      DISABLE;

  hadc1.Init.ContinuousConvMode =
      DISABLE;

  hadc1.Init.NbrOfConversion =
      2;

  hadc1.Init.DiscontinuousConvMode =
      DISABLE;

  hadc1.Init.ExternalTrigConv =
      ADC_SOFTWARE_START;

  hadc1.Init.ExternalTrigConvEdge =
      ADC_EXTERNALTRIGCONVEDGE_NONE;

  hadc1.Init.DMAContinuousRequests =
      DISABLE;

  HAL_ADC_Init(&hadc1);

  /* CHANNEL 1 : PA0 */

  sConfig.Channel = ADC_CHANNEL_1;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.SamplingTime =
      ADC_SAMPLETIME_61CYCLES_5;

  HAL_ADC_ConfigChannel(&hadc1,
                        &sConfig);

  /* CHANNEL 2 : PA1 */

  sConfig.Channel = ADC_CHANNEL_2;
  sConfig.Rank = ADC_REGULAR_RANK_2;

  HAL_ADC_ConfigChannel(&hadc1,
                        &sConfig);
}

/**
  * @brief SPI1 Initialization Function
  */

static void MX_SPI1_Init(void)
{
  hspi1.Instance = SPI1;

  hspi1.Init.Mode = SPI_MODE_MASTER;

  hspi1.Init.Direction =
      SPI_DIRECTION_2LINES;

  hspi1.Init.DataSize =
      SPI_DATASIZE_8BIT;

  hspi1.Init.CLKPolarity =
      SPI_POLARITY_LOW;

  hspi1.Init.CLKPhase =
      SPI_PHASE_1EDGE;

  hspi1.Init.NSS =
      SPI_NSS_SOFT;

  hspi1.Init.BaudRatePrescaler =
      SPI_BAUDRATEPRESCALER_8;

  hspi1.Init.FirstBit =
      SPI_FIRSTBIT_MSB;

  hspi1.Init.TIMode =
      SPI_TIMODE_DISABLE;

  hspi1.Init.CRCCalculation =
      SPI_CRCCALCULATION_DISABLE;

  HAL_SPI_Init(&hspi1);
}

/**
  * @brief USART1 Initialization Function
  */

static void MX_USART1_UART_Init(void)
{
  huart1.Instance = USART1;

  huart1.Init.BaudRate = 115200;

  huart1.Init.WordLength =
      UART_WORDLENGTH_8B;

  huart1.Init.StopBits =
      UART_STOPBITS_1;

  huart1.Init.Parity =
      UART_PARITY_NONE;

  huart1.Init.Mode =
      UART_MODE_TX_RX;

  huart1.Init.HwFlowCtl =
      UART_HWCONTROL_NONE;

  huart1.Init.OverSampling =
      UART_OVERSAMPLING_16;

  HAL_UART_Init(&huart1);
}

/**
  * @brief DMA Initialization Function
  */

static void MX_DMA_Init(void)
{
  __HAL_RCC_DMA1_CLK_ENABLE();
}

/**
  * @brief GPIO Initialization Function
  */

static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();

  /* AD9833 FSYNC */

  HAL_GPIO_WritePin(AD9833_FSYNC_GPIO_Port,
                    AD9833_FSYNC_Pin,
                    GPIO_PIN_SET);

  GPIO_InitStruct.Pin =
      AD9833_FSYNC_Pin;

  GPIO_InitStruct.Mode =
      GPIO_MODE_OUTPUT_PP;

  GPIO_InitStruct.Pull =
      GPIO_NOPULL;

  GPIO_InitStruct.Speed =
      GPIO_SPEED_FREQ_HIGH;

  HAL_GPIO_Init(AD9833_FSYNC_GPIO_Port,
                &GPIO_InitStruct);

  /* FLASH CS */

  HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port,
                    W25Q32_CS_Pin,
                    GPIO_PIN_SET);

  GPIO_InitStruct.Pin =
      W25Q32_CS_Pin;

  HAL_GPIO_Init(W25Q32_CS_GPIO_Port,
                &GPIO_InitStruct);

  /* STATUS LED */

  GPIO_InitStruct.Pin =
      STATUS_LED_Pin;

  HAL_GPIO_Init(STATUS_LED_GPIO_Port,
                &GPIO_InitStruct);
}

/**
  * @brief  This function is executed in case of error occurrence.
  */

void Error_Handler(void)
{
  __disable_irq();

  while (1)
  {
  }
}
