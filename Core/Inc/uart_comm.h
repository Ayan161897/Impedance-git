/**
 ******************************************************************************
 * @file           : uart_comm.h
 * @brief          : UART Communication layer for PC-GUI interface
 ******************************************************************************
 */

#ifndef UART_COMM_H
#define UART_COMM_H

#include "stm32f3xx_hal.h"

#ifdef HAL_UART_MODULE_ENABLED
typedef UART_HandleTypeDef UART_CommHandleTypeDef;
#else
typedef void UART_CommHandleTypeDef;
#endif

/* Public Functions */
void UART_Comm_Init(UART_CommHandleTypeDef *huart);
void UART_SendString(const char *str);
void UART_SendImpedanceData(uint32_t freq, float magnitude, float phase);
void UART_ProcessCommand(void);

#endif /* UART_COMM_H */
