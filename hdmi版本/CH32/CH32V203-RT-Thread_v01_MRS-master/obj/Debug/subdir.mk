################################################################################
# MRS Version: 1.9.0
# 自动生成的文件。不要编辑！
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Debug/debug.c 

C_DEPS += \
./Debug/debug.d 

OBJS += \
./Debug/debug.o 


# Each subdirectory must supply rules for building sources it contributes
Debug/%.o: ../Debug/%.c
	@echo '正在构建文件： $<'
	@echo '正在调用： GNU RISC-V Cross C Compiler'
	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized  -g -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\packages" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\packages\at24cxx-latest" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\components\finsh" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\components\drivers" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\src" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\libcpu\risc-v\common" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\include" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\Debug" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\Core" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\User" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\Peripheral\inc" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\drivers" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\components\drivers\include" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\components\drivers\include\drivers" -I"E:\个人\项目\wch_proj\CH32V203-RT-Thread_v01_MRS_c++\rt-thread\components\drivers\include\ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"
	@echo '已结束构建： $<'
	@

