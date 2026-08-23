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

__weak void Process_SetSweepConfig(uint32_t start, uint32_t stop, uint32_t step)
{
    (void)start; (void)stop; (void)step;
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
void UART_SendImpedanceData(uint32_t freq, float magnitude, float phase,
                            float real_part, float imag_part)
{
    char buffer[192];
    uint32_t mag_x100;
    int32_t  phase_x100;
    int32_t  real_x100;
    int32_t  imag_x100;
    uint32_t phase_abs;
    uint32_t real_abs;
    uint32_t imag_abs;
    int len;

    mag_x100   = (uint32_t)((magnitude  * 100.0f) + 0.5f);
    phase_x100 = (phase     >= 0.0f) ?
                 (int32_t)((phase     * 100.0f) + 0.5f) :
                 (int32_t)((phase     * 100.0f) - 0.5f);
    real_x100  = (real_part >= 0.0f) ?
                 (int32_t)((real_part * 100.0f) + 0.5f) :
                 (int32_t)((real_part * 100.0f) - 0.5f);
    imag_x100  = (imag_part >= 0.0f) ?
                 (int32_t)((imag_part * 100.0f) + 0.5f) :
                 (int32_t)((imag_part * 100.0f) - 0.5f);

    phase_abs = (phase_x100 < 0) ? (uint32_t)(-phase_x100) : (uint32_t)phase_x100;
    real_abs  = (real_x100  < 0) ? (uint32_t)(-real_x100)  : (uint32_t)real_x100;
    imag_abs  = (imag_x100  < 0) ? (uint32_t)(-imag_x100)  : (uint32_t)imag_x100;

    len = snprintf(buffer, sizeof(buffer),
                   "DATA,%lu,%lu.%02lu,%s%lu.%02lu,%s%lu.%02lu,%s%lu.%02lu\r\n",
                   (unsigned long)freq,
                   (unsigned long)(mag_x100  / 100U),
                   (unsigned long)(mag_x100  % 100U),
                   (phase_x100 < 0) ? "-" : "",
                   (unsigned long)(phase_abs / 100U),
                   (unsigned long)(phase_abs % 100U),
                   (real_x100  < 0) ? "-" : "",
                   (unsigned long)(real_abs  / 100U),
                   (unsigned long)(real_abs  % 100U),
                   (imag_x100  < 0) ? "-" : "",
                   (unsigned long)(imag_abs  / 100U),
                   (unsigned long)(imag_abs  % 100U));

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
    char cmd_buf[sizeof(rx_buffer)];

    if (!command_ready) return;

    /* Copy rx_buffer under a critical section so the ISR cannot
       overwrite it while UART_ProcessCommand is comparing it. */
    __disable_irq();
    memcpy(cmd_buf, rx_buffer, sizeof(rx_buffer));
    command_ready = 0;
    __enable_irq();

    if (strcmp(cmd_buf, "START") == 0)
    {
        Process_Start_Command();
    }
    else if (strcmp(cmd_buf, "STOP") == 0)
    {
        Process_Stop_Command();
    }
    else if (strcmp(cmd_buf, "STATUS") == 0)
    {
        Process_Status_Command();
    }
    else if (strcmp(cmd_buf, "FLASH_STATUS") == 0)
    {
        Process_FlashStatus_Command();
    }
    else if (strcmp(cmd_buf, "ERASE_FLASH") == 0)
    {
        Process_EraseFlash_Command();
    }
    else if (strcmp(cmd_buf, "DUMP_FLASH") == 0)
    {
        Process_DumpFlash_Command();
    }
    else if (strncmp(cmd_buf, "SET_START_FREQ,", 15) == 0)
    {
        Process_SetStartFrequency((uint32_t)strtoul(&cmd_buf[15], NULL, 10));
    }
    else if (strncmp(cmd_buf, "SET_STOP_FREQ,", 14) == 0)
    {
        Process_SetStopFrequency((uint32_t)strtoul(&cmd_buf[14], NULL, 10));
    }
    else if (strncmp(cmd_buf, "SET_STEP_FREQ,", 14) == 0)
    {
        Process_SetStepFrequency((uint32_t)strtoul(&cmd_buf[14], NULL, 10));
    }
    else if (strncmp(cmd_buf, "SET_RF,", 7) == 0)
    {
        Process_SetFeedbackResistor(strtof(&cmd_buf[7], NULL));
    }
    else if (strncmp(cmd_buf, "SET_SWEEP,", 10) == 0)
    {
        char *p = &cmd_buf[10];
        char *end;
        uint32_t start = (uint32_t)strtoul(p,   &end, 10); if(*end == ',') end++;
        uint32_t stop  = (uint32_t)strtoul(end,  &end, 10); if(*end == ',') end++;
        uint32_t step  = (uint32_t)strtoul(end,  NULL, 10);
        Process_SetSweepConfig(start, stop, step);
    }
    else
    {
        UART_SendString("ERROR,UNKNOWN_COMMAND\r\n");
    }
}
