################################################################################
# MRS Version: 2.5.0
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../rt-thread/src/clock.c \
../rt-thread/src/components.c \
../rt-thread/src/device.c \
../rt-thread/src/idle.c \
../rt-thread/src/ipc.c \
../rt-thread/src/irq.c \
../rt-thread/src/kservice.c \
../rt-thread/src/mem.c \
../rt-thread/src/object.c \
../rt-thread/src/scheduler_up.c \
../rt-thread/src/thread.c \
../rt-thread/src/timer.c 

C_DEPS += \
./rt-thread/src/clock.d \
./rt-thread/src/components.d \
./rt-thread/src/device.d \
./rt-thread/src/idle.d \
./rt-thread/src/ipc.d \
./rt-thread/src/irq.d \
./rt-thread/src/kservice.d \
./rt-thread/src/mem.d \
./rt-thread/src/object.d \
./rt-thread/src/scheduler_up.d \
./rt-thread/src/thread.d \
./rt-thread/src/timer.d 

OBJS += \
./rt-thread/src/clock.o \
./rt-thread/src/components.o \
./rt-thread/src/device.o \
./rt-thread/src/idle.o \
./rt-thread/src/ipc.o \
./rt-thread/src/irq.o \
./rt-thread/src/kservice.o \
./rt-thread/src/mem.o \
./rt-thread/src/object.o \
./rt-thread/src/scheduler_up.o \
./rt-thread/src/thread.o \
./rt-thread/src/timer.o 

DIR_OBJS += \
./rt-thread/src/*.o \

DIR_DEPS += \
./rt-thread/src/*.d \

DIR_EXPANDS += \
./rt-thread/src/*.234r.expand \


# Each subdirectory must supply rules for building sources it contributes
rt-thread/src/%.o: ../rt-thread/src/%.c
	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -fmax-errors=20 -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized -g -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages/at24cxx-latest" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/finsh" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/src" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/libcpu/risc-v/common" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Debug" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Core" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/User" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Peripheral/inc" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"

