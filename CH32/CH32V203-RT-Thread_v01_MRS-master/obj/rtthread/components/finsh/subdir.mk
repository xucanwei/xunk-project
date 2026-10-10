################################################################################
# MRS Version: 1.9.0
# 自动生成的文件。不要编辑！
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../rtthread/components/finsh/cmd.c \
../rtthread/components/finsh/msh.c \
../rtthread/components/finsh/msh_cmd.c \
../rtthread/components/finsh/msh_file.c \
../rtthread/components/finsh/shell.c \
../rtthread/components/finsh/symbol.c 

OBJS += \
./rtthread/components/finsh/cmd.o \
./rtthread/components/finsh/msh.o \
./rtthread/components/finsh/msh_cmd.o \
./rtthread/components/finsh/msh_file.o \
./rtthread/components/finsh/shell.o \
./rtthread/components/finsh/symbol.o 

C_DEPS += \
./rtthread/components/finsh/cmd.d \
./rtthread/components/finsh/msh.d \
./rtthread/components/finsh/msh_cmd.d \
./rtthread/components/finsh/msh_file.d \
./rtthread/components/finsh/shell.d \
./rtthread/components/finsh/symbol.d 


# Each subdirectory must supply rules for building sources it contributes
rtthread/components/finsh/%.o: ../rtthread/components/finsh/%.c
	@	@	riscv-none-embed-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized  -g -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Debug" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Core" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\User" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\Peripheral\inc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\drivers" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\include\libc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\libcpu\risc-v" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\libcpu\risc-v\common" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\src" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\components\drivers\include" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\components\drivers\misc" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\components\drivers\serial" -I"C:\MRS_DATA\workspace\CH32V203-RT-Thread_v01\rtthread\components\finsh" -std=gnu99 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -c -o "$@" "$<"
	@	@

