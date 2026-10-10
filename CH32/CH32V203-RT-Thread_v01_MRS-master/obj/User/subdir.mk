################################################################################
# MRS Version: 2.5.0
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../User/app_km.c \
../User/asr_service.c \
../User/bsp_ch32v203.c \
../User/ch32v20x_it.c \
../User/ch32v20x_usbfs_host.c \
../User/main.c \
../User/servo_service.c \
../User/system_ch32v20x.c \
../User/usb_host_hid.c \
../User/usb_host_hub.c \
../User/usb_touch_host.c 

C_DEPS += \
./User/app_km.d \
./User/asr_service.d \
./User/bsp_ch32v203.d \
./User/ch32v20x_it.d \
./User/ch32v20x_usbfs_host.d \
./User/main.d \
./User/servo_service.d \
./User/system_ch32v20x.d \
./User/usb_host_hid.d \
./User/usb_host_hub.d \
./User/usb_touch_host.d 

OBJS += \
./User/app_km.o \
./User/asr_service.o \
./User/bsp_ch32v203.o \
./User/ch32v20x_it.o \
./User/ch32v20x_usbfs_host.o \
./User/main.o \
./User/servo_service.o \
./User/system_ch32v20x.o \
./User/usb_host_hid.o \
./User/usb_host_hub.o \
./User/usb_touch_host.o 

DIR_OBJS += \
./User/*.o \

DIR_DEPS += \
./User/*.d \

DIR_EXPANDS += \
./User/*.234r.expand \


# Each subdirectory must supply rules for building sources it contributes
User/%.o: ../User/%.c
	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -fmax-errors=20 -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized -g -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages/at24cxx-latest" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/finsh" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/src" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/libcpu/risc-v/common" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Debug" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Core" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/User" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Peripheral/inc" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"

