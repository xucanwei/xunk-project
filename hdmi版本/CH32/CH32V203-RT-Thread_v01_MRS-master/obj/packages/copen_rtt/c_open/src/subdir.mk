################################################################################
# MRS Version: 1.9.0
# 自动生成的文件。不要编辑！
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../packages/copen_rtt/c_open/src/co_bitmap.c \
../packages/copen_rtt/c_open/src/co_emcy.c \
../packages/copen_rtt/c_open/src/co_heartbeat.c \
../packages/copen_rtt/c_open/src/co_log.c \
../packages/copen_rtt/c_open/src/co_lss.c \
../packages/copen_rtt/c_open/src/co_main.c \
../packages/copen_rtt/c_open/src/co_nmt.c \
../packages/copen_rtt/c_open/src/co_node_guard.c \
../packages/copen_rtt/c_open/src/co_obj.c \
../packages/copen_rtt/c_open/src/co_od.c \
../packages/copen_rtt/c_open/src/co_pdo.c \
../packages/copen_rtt/c_open/src/co_sdo_client.c \
../packages/copen_rtt/c_open/src/co_sdo_server.c \
../packages/copen_rtt/c_open/src/co_sync.c 

OBJS += \
./packages/copen_rtt/c_open/src/co_bitmap.o \
./packages/copen_rtt/c_open/src/co_emcy.o \
./packages/copen_rtt/c_open/src/co_heartbeat.o \
./packages/copen_rtt/c_open/src/co_log.o \
./packages/copen_rtt/c_open/src/co_lss.o \
./packages/copen_rtt/c_open/src/co_main.o \
./packages/copen_rtt/c_open/src/co_nmt.o \
./packages/copen_rtt/c_open/src/co_node_guard.o \
./packages/copen_rtt/c_open/src/co_obj.o \
./packages/copen_rtt/c_open/src/co_od.o \
./packages/copen_rtt/c_open/src/co_pdo.o \
./packages/copen_rtt/c_open/src/co_sdo_client.o \
./packages/copen_rtt/c_open/src/co_sdo_server.o \
./packages/copen_rtt/c_open/src/co_sync.o 

C_DEPS += \
./packages/copen_rtt/c_open/src/co_bitmap.d \
./packages/copen_rtt/c_open/src/co_emcy.d \
./packages/copen_rtt/c_open/src/co_heartbeat.d \
./packages/copen_rtt/c_open/src/co_log.d \
./packages/copen_rtt/c_open/src/co_lss.d \
./packages/copen_rtt/c_open/src/co_main.d \
./packages/copen_rtt/c_open/src/co_nmt.d \
./packages/copen_rtt/c_open/src/co_node_guard.d \
./packages/copen_rtt/c_open/src/co_obj.d \
./packages/copen_rtt/c_open/src/co_od.d \
./packages/copen_rtt/c_open/src/co_pdo.d \
./packages/copen_rtt/c_open/src/co_sdo_client.d \
./packages/copen_rtt/c_open/src/co_sdo_server.d \
./packages/copen_rtt/c_open/src/co_sync.d 


# Each subdirectory must supply rules for building sources it contributes
packages/copen_rtt/c_open/src/%.o: ../packages/copen_rtt/c_open/src/%.c
	@	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized  -g -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\example\slave" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\src\ports\rtthread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\osal\src\rtthread\sys" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\example\slaveinfo" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\can_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\kv_storage_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\adc_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\App\io_app" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\uWLKV-master\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\io_input_filter-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\at24cxx-latest" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\finsh" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\libcpu\risc-v\common" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Debug" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Core" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\User" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Peripheral\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\c_open\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\packages\copen_rtt\osal\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rt-thread\components\drivers\include\ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"
	@	@

