/********************************** (C) COPYRIGHT *******************************
 * File Name          : ch32v20x_it.c
 * Author             : WCH
 * Version            : V1.0.0
 * Date               : 2021/06/06
 * Description        : Main Interrupt Service Routines.
*********************************************************************************
* Copyright (c) 2021 Nanjing Qinheng Microelectronics Co., Ltd.
* Attention: This software (modified or not) and binary are used for 
* microcontroller manufactured by Nanjing Qinheng Microelectronics.
*******************************************************************************/
#include "ch32v20x_it.h"
#include "board.h"
#include <rtthread.h>
void NMI_Handler(void) __attribute__((interrupt()));
void HardFault_Handler(void) __attribute__((interrupt()));

/*********************************************************************
 * @fn      NMI_Handler
 *
 * @brief   This function handles NMI exception.
 *
 * @return  none
 */
void NMI_Handler(void)
{
    GET_INT_SP();
    rt_interrupt_enter();
    rt_kprintf(" NMI Handler\r\n");
    rt_interrupt_leave();
    FREE_INT_SP();
}

/*********************************************************************
 * @fn      HardFault_Handler
 *
 * @brief   This function handles Hard Fault exception.
 *
 * @return  none
 */
void HardFault_Handler(void)
{
    uint32_t mepc = __get_MEPC();
    uint32_t mcause = __get_MCAUSE();
    uint32_t mtval = __get_MTVAL();
    uint32_t sp_val = __get_SP();

    rt_kprintf("\r\n================ [HARDFAULT FATAL] ================\r\n");
    rt_kprintf("  MEPC   (Fault PC)  : 0x%08X\r\n", mepc);
    rt_kprintf("  MCAUSE (Cause Code): 0x%08X", mcause);

    /* 解析 QingKe RISC-V 常见异常码 */
    uint32_t code = mcause & 0x7FFFFFFF;
    switch (code) {
        case 1:  rt_kprintf(" [Instruction access fault / 非法指令访问]\r\n"); break;
        case 2:  rt_kprintf(" [Illegal instruction / 未定义非法指令]\r\n"); break;
        case 4:  rt_kprintf(" [Load address misaligned / 读内存未对齐]\r\n"); break;
        case 5:  rt_kprintf(" [Load access fault / 读内存非法越界]\r\n"); break;
        case 6:  rt_kprintf(" [Store address misaligned / 写内存未对齐]\r\n"); break;
        case 7:  rt_kprintf(" [Store access fault / 写内存非法越界(野指针或栈溢出)]\r\n"); break;
        case 11: rt_kprintf(" [ECALL from M-mode / 环境调用]\r\n"); break;
        default: rt_kprintf(" [Unknown Exception]\r\n"); break;
    }

    rt_kprintf("  MTVAL  (Bad Addr)  : 0x%08X\r\n", mtval);
    rt_kprintf("  SP     (Stack Ptr) : 0x%08X\r\n", sp_val);

    /* 安全获取当前线程信息，防止内存踩坏时再次 crash */
    rt_thread_t cur_th = rt_thread_self();
    if (cur_th != RT_NULL && (uint32_t)cur_th >= 0x20000000 && (uint32_t)cur_th < 0x20005000) {
        rt_kprintf("  Thread (Active)    : %s\r\n", cur_th->name);
        rt_kprintf("  Thread Stack Range : [0x%08X ~ 0x%08X], size: %d, sp: 0x%08X\r\n",
                   (uint32_t)cur_th->stack_addr,
                   (uint32_t)cur_th->stack_addr + cur_th->stack_size,
                   cur_th->stack_size,
                   (uint32_t)cur_th->sp);
    }
    rt_kprintf("====================================================\r\n");

    while (1);
}


