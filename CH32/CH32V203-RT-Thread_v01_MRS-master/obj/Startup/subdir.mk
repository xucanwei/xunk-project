################################################################################
# MRS Version: 2.5.0
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
S_UPPER_SRCS += \
../Startup/startup_ch32v20x_D6.S 

S_UPPER_DEPS += \
./Startup/startup_ch32v20x_D6.d 

OBJS += \
./Startup/startup_ch32v20x_D6.o 

DIR_OBJS += \
./Startup/*.o \

DIR_DEPS += \
./Startup/*.d \

DIR_EXPANDS += \
./Startup/*.234r.expand \


# Each subdirectory must supply rules for building sources it contributes
Startup/%.o: ../Startup/%.S
	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -fmax-errors=20 -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized -g -x assembler-with-cpp -DCH32V20x_D8W -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/src" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/drivers/include/ipc" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/components/finsh" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/include" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/rt-thread/libcpu/risc-v/common" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/drivers" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Startup" -I"c:/Users/22841/Desktop/company/K230/»À¡≥—€«Ú/CH32/CH32V203-RT-Thread_v01_MRS-master/Peripheral/inc" -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"

