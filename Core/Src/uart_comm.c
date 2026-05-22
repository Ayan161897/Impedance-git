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

__weak void Process_Start_Command(void)
{
}

__weak void Process_Stop_Command(void)
{
}

static UART_CommHandleTypeDef *uart_handle = NULL;

static uint8_t rx_char;
static char rx_buffer[128];
#ifdef HAL_UART_MODULE_ENABLED
static uint8_t rx_index = 0;
#endif
static uint8_t command_ready = 0;

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
   Send Impedance Data (Optimized for float printing)
   =================================================================== */
void UART_SendImpedanceData(uint32_t freq, float magnitude, float phase)
{
    char buffer[128];

    // snprintf with %f is now supported after adding -u _printf_float
    int len = snprintf(buffer, sizeof(buffer),
                      "Freq=%lu, |Z|=%f, Phase=%f\r\n",
                      freq, magnitude, phase);

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
#endif

/* ===================================================================
   Process Received Commands from Python GUI
   =================================================================== */
void UART_ProcessCommand(void)
{
    if (!command_ready) return;
    command_ready = 0;

    // Debug: echo received command
    // printf("Received: %s\r\n", rx_buffer);

    if (strncmp(rx_buffer, "START", 5) == 0)
    {
        UART_SendString("OK START\r\n");
        Process_Start_Command();
    }
    else if (strcmp(rx_buffer, "STOP") == 0)
    {
        UART_SendString("OK STOP\r\n");
        Process_Stop_Command();
    }
    else
    {
        UART_SendString("UNKNOWN COMMAND\r\n");
    }
}
