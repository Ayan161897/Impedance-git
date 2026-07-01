/**
 ******************************************************************************
 * @file           : uart_comm.c
 * @brief          : UART Communication layer for PC-GUI interface
 * @project        : Electrochemical Impedance Spectroscopy (Master Thesis)
 ******************************************************************************
 */

#include "uart_comm.h"
#include "main.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

__weak void Process_Start_Command(void)
{
}

__weak void Process_Stop_Command(void)
{
}

__weak void Process_Status_Command(void)
{
}

__weak void Process_FlashStatus_Command(void)
{
}

__weak void Process_EraseFlash_Command(void)
{
}

__weak void Process_DumpFlash_Command(void)
{
}

__weak void Process_SetStartFrequency(uint32_t value)
{
    (void)value;
}

__weak void Process_SetStopFrequency(uint32_t value)
{
    (void)value;
}

__weak void Process_SetStepFrequency(uint32_t value)
{
    (void)value;
}

__weak void Process_SetFeedbackResistor(float value)
{
    (void)value;
}

static UART_CommHandleTypeDef *uart_handle = NULL;

static uint8_t rx_char;
static char rx_buffer[128];
#ifdef HAL_UART_MODULE_ENABLED
static uint8_t rx_index = 0;
#endif
static volatile uint8_t command_ready = 0;

/* ===================================================================
   Initialization
   =================================================================== */
void UART_Comm_Init(UART_CommHandleTypeDef *huart)
{
    uart_handle = huart;
#ifdef HAL_UART_MODULE_ENABLED
    HAL_UART_Receive_IT(uart_handle, &rx_char, 1);
#else
    (void)rx_char;
#endif
    printf("UART Communication Initialized at 115200 baud\r\n");
}

/* ===================================================================
   Send String
   =================================================================== */
void UART_SendString(const char *str)
{
    if (uart_handle == NULL || str == NULL) return;
#ifdef HAL_UART_MODULE_ENABLED
    HAL_UART_Transmit(uart_handle, (uint8_t*)str, strlen(str), HAL_MAX_DELAY);
#else
    (void)str;
#endif
}

/* ===================================================================
   Send Impedance Data
   =================================================================== */
void UART_SendImpedanceData(uint32_t freq, float magnitude, float phase)
{
    char buffer[128];
    uint32_t magnitude_x100;
    int32_t phase_x100;
    uint32_t phase_abs_x100;

    magnitude_x100 = (uint32_t)((magnitude * 100.0f) + 0.5f);

    if(phase >= 0.0f)
    {
        phase_x100 = (int32_t)((phase * 100.0f) + 0.5f);
    }
    else
    {
        phase_x100 = (int32_t)((phase * 100.0f) - 0.5f);
    }

    phase_abs_x100 = (phase_x100 < 0) ?
                     (uint32_t)(-phase_x100) :
                     (uint32_t)phase_x100;

    int len = snprintf(buffer, sizeof(buffer),
                      "DATA,%lu,%lu.%02lu,%s%lu.%02lu\r\n",
                      freq,
                      magnitude_x100 / 100U,
                      magnitude_x100 % 100U,
                      (phase_x100 < 0) ? "-" : "",
                      phase_abs_x100 / 100U,
                      phase_abs_x100 % 100U);

    if (len > 0 && len < (int)sizeof(buffer))
    {
        UART_SendString(buffer);
    }
}

/* ===================================================================
   UART Receive Complete Callback (Interrupt)
   =================================================================== */
#ifdef HAL_UART_MODULE_ENABLED
void UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart == uart_handle)
    {
        if (rx_char == '\n' || rx_char == '\r')
        {
            if (rx_index > 0)
            {
                rx_buffer[rx_index] = '\0';
                command_ready = 1;
            }
            rx_index = 0;
        }
        else if (rx_index < sizeof(rx_buffer) - 1)
        {
            rx_buffer[rx_index++] = rx_char;
        }

        // Re-enable interrupt for next character
        HAL_UART_Receive_IT(uart_handle, &rx_char, 1);
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    UART_RxCpltCallback(huart);
}
#endif

/* ===================================================================
   Process Received Commands from Python GUI
   =================================================================== */
void UART_ProcessCommand(void)
{
    if (!command_ready) return;
    command_ready = 0;

    if (strcmp(rx_buffer, "START") == 0)
    {
        Process_Start_Command();
    }
    else if (strcmp(rx_buffer, "STOP") == 0)
    {
        Process_Stop_Command();
    }
    else if (strcmp(rx_buffer, "STATUS") == 0)
    {
        Process_Status_Command();
    }
    else if (strcmp(rx_buffer, "FLASH_STATUS") == 0)
    {
        Process_FlashStatus_Command();
    }
    else if (strcmp(rx_buffer, "ERASE_FLASH") == 0)
    {
        Process_EraseFlash_Command();
    }
    else if (strcmp(rx_buffer, "DUMP_FLASH") == 0)
    {
        Process_DumpFlash_Command();
    }
    else if (strncmp(rx_buffer, "SET_START_FREQ,", 15) == 0)
    {
        Process_SetStartFrequency((uint32_t)strtoul(&rx_buffer[15], NULL, 10));
    }
    else if (strncmp(rx_buffer, "SET_STOP_FREQ,", 14) == 0)
    {
        Process_SetStopFrequency((uint32_t)strtoul(&rx_buffer[14], NULL, 10));
    }
    else if (strncmp(rx_buffer, "SET_STEP_FREQ,", 14) == 0)
    {
        Process_SetStepFrequency((uint32_t)strtoul(&rx_buffer[14], NULL, 10));
    }
    else if (strncmp(rx_buffer, "SET_RF,", 7) == 0)
    {
        Process_SetFeedbackResistor(strtof(&rx_buffer[7], NULL));
    }
    else
    {
        UART_SendString("ERROR,UNKNOWN_COMMAND\r\n");
    }
}
