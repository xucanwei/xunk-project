################################################################################
# MRS Version: 2.5.0
# Automatically-generated file. Do not edit!
################################################################################
-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include rt-thread/src/subdir.mk
-include rt-thread/libcpu/risc-v/common/subdir.mk
-include rt-thread/components/finsh/subdir.mk
-include rt-thread/components/drivers/watchdog/subdir.mk
-include rt-thread/components/drivers/serial/subdir.mk
-include rt-thread/components/drivers/misc/subdir.mk
-include rt-thread/components/drivers/ipc/subdir.mk
-include rt-thread/components/drivers/i2c/subdir.mk
-include rt-thread/components/drivers/can/subdir.mk
-include rt-thread/subdir.mk
-include drivers/subdir.mk
-include User/subdir.mk
-include Startup/subdir.mk
-include Peripheral/src/subdir.mk
-include Core/subdir.mk
-include subdir.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(S_DEPS)),)
-include $(S_DEPS)
endif
ifneq ($(strip $(S_UPPER_DEPS)),)
-include $(S_UPPER_DEPS)
endif
ifneq ($(strip $(ASM_DEPS)),)
-include $(ASM_DEPS)
endif
ifneq ($(strip $(ASM_UPPER_DEPS)),)
-include $(ASM_UPPER_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
ifneq ($(strip $(C_UPPER_DEPS)),)
-include $(C_UPPER_DEPS)
endif
ifneq ($(strip $(CC_DEPS)),)
-include $(CC_DEPS)
endif
ifneq ($(strip $(C++_DEPS)),)
-include $(C++_DEPS)
endif
ifneq ($(strip $(CXX_DEPS)),)
-include $(CXX_DEPS)
endif
ifneq ($(strip $(CPP_DEPS)),)
-include $(CPP_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables 
SECONDARY_FLASH += \
CH32V203-RT-Thread_v01.hex \

SECONDARY_LIST += \
CH32V203-RT-Thread_v01.lst \

SECONDARY_SIZE += \
CH32V203-RT-Thread_v01.siz \


# All Target
all: 
	$(MAKE) --no-print-directory main-build 

main-build: CH32V203-RT-Thread_v01.elf secondary-outputs

# Tool invocations
CH32V203-RT-Thread_v01.elf: $(OBJS) $(USER_OBJS_ESCAPE)
	@	riscv-none-embed-g++ -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8 -msave-restore -fmax-errors=20 -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized -g -T "c:\Users\22841\Desktop\company\K230\ÈËÁ³ÑÛÇò\CH32\CH32V203-RT-Thread_v01_MRS-master\Ld\Link.ld" -nostartfiles -Xlinker --gc-sections -L"c:\Users\22841\Desktop\company\K230\ÈËÁ³ÑÛÇò\CH32\CH32V203-RT-Thread_v01_MRS-master\LD" -Wl,-Map,"CH32V203-RT-Thread_v01.map" --specs=nano.specs --specs=nosys.specs -o "CH32V203-RT-Thread_v01.elf" $(OBJS) $(LIBS)
CH32V203-RT-Thread_v01.hex: CH32V203-RT-Thread_v01.elf
	@	riscv-none-embed-objcopy -O ihex "CH32V203-RT-Thread_v01.elf" "CH32V203-RT-Thread_v01.hex"
CH32V203-RT-Thread_v01.lst: CH32V203-RT-Thread_v01.elf
	@	riscv-none-embed-objdump --all-headers --demangle --debugging --disassemble -M xw "CH32V203-RT-Thread_v01.elf" > "CH32V203-RT-Thread_v01.lst"
CH32V203-RT-Thread_v01.siz: CH32V203-RT-Thread_v01.elf
	riscv-none-embed-size --format=berkeley -x "CH32V203-RT-Thread_v01.elf"

# Other Targets
clean:
	-$(RM) $(DIR_OBJS) $(SECONDARY_FLASH)$(SECONDARY_LIST)$(SECONDARY_SIZE) CH32V203-RT-Thread_v01.elf
	-$(RM) $(DIR_EXPANDS) $(CALLGRAPH_DOT)
	-$(RM) $(DIR_DEPS)
secondary-outputs: $(SECONDARY_FLASH) $(SECONDARY_LIST) $(SECONDARY_SIZE)

.PHONY: all clean dependents

-include ../makefile.targets