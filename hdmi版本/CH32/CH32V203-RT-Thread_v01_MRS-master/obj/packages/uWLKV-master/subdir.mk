################################################################################
# MRS Version: 1.9.0
# 自动生成的文件。不要编辑！
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../packages/uWLKV-master/entry.c \
../packages/uWLKV-master/map.c \
../packages/uWLKV-master/storage.c \
../packages/uWLKV-master/uwlkv.c 

OBJS += \
./packages/uWLKV-master/entry.o \
./packages/uWLKV-master/map.o \
./packages/uWLKV-master/storage.o \
./packages/uWLKV-master/uwlkv.o 

C_DEPS += \
./packages/uWLKV-master/entry.d \
./packages/uWLKV-master/map.d \
./packages/uWLKV-master/storage.d \
./packages/uWLKV-master/uwlkv.d 


# Each subdirectory must supply rules for building sources it contributes
packages/uWLKV-master/%.o: ../packages/uWLKV-master/%.c
	@	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized  -g -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\example\slave" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\src\ports\rtthread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\osal\src\rtthread\sys" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\example\slaveinfo" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\can_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\kv_storage_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\adc_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\io_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\uWLKV-master\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\io_input_filter-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\at24cxx-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\finsh" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\libcpu\risc-v\common" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Debug" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Core" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\User" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Peripheral\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\osal\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"
	@	@

