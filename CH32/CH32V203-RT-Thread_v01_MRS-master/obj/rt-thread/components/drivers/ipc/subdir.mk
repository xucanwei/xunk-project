################################################################################
# MRS Version: 2.5.0
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../rt-thread/components/drivers/ipc/completion.c \
../rt-thread/components/drivers/ipc/dataqueue.c \
../rt-thread/components/drivers/ipc/ringblk_buf.c \
../rt-thread/components/drivers/ipc/ringbuffer.c \
../rt-thread/components/drivers/ipc/waitqueue.c \
../rt-thread/components/drivers/ipc/workqueue.c 

C_DEPS += \
./rt-thread/components/drivers/ipc/completion.d \
./rt-thread/components/drivers/ipc/dataqueue.d \
./rt-thread/components/drivers/ipc/ringblk_buf.d \
./rt-thread/components/drivers/ipc/ringbuffer.d \
./rt-thread/components/drivers/ipc/waitqueue.d \
./rt-thread/components/drivers/ipc/workqueue.d 

OBJS += \
./rt-thread/components/drivers/ipc/completion.o \
./rt-thread/components/drivers/ipc/dataqueue.o \
./rt-thread/components/drivers/ipc/ringblk_buf.o \
./rt-thread/components/drivers/ipc/ringbuffer.o \
./rt-thread/components/drivers/ipc/waitqueue.o \
./rt-thread/components/drivers/ipc/workqueue.o 

DIR_OBJS += \
./rt-thread/components/drivers/ipc/*.o \

DIR_DEPS += \
./rt-thread/components/drivers/ipc/*.d \

DIR_EXPANDS += \
./rt-thread/components/drivers/ipc/*.234r.expand \


# Each subdirectory must supply rules for building sources it contributes
rt-thread/components/drivers/ipc/%.o: ../rt-thread/components/drivers/ipc/%.c
	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -fmax-errors=20 -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized -g -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/packages/at24cxx-latest" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/finsh" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/src" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/libcpu/risc-v/common" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Debug" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Core" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/User" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Peripheral/inc" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/ipc" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"

