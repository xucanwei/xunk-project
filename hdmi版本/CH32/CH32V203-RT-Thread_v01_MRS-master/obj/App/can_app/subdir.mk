################################################################################
# MRS Version: 1.9.0
# 自动生成的文件。不要编辑！
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../App/can_app/can_app.c 

OBJS += \
./App/can_app/can_app.o 

C_DEPS += \
./App/can_app/can_app.d 


# Each subdirectory must supply rules for building sources it contributes
App/can_app/%.o: ../App/can_app/%.c
	@	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized  -g -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\can_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\kv_storage_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\adc_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\io_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\uWLKV-master\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\io_input_filter-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\at24cxx-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\finsh" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\libcpu\risc-v\common" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Debug" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Core" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\User" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Peripheral\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"
	@	@

