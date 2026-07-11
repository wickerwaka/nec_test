MAKEFLAGS+=w

QUARTUS_SH  = quartus_sh
QUARTUS_PGM = quartus_pgm

PROJECT  = nec_test
REVISION = nec_test
OUTDIR   = output_files

# JTAG cable index (see: jtagconfig). The MiSTer/DE10 exposes a "DE-SoC" cable.
CABLE = 1
# Position of the FPGA in the JTAG chain. On the Cyclone V SoC the HPS (SOCVHPS)
# is device 1 and the FPGA fabric is device 2.
DEVICE = 2

SOF = $(OUTDIR)/$(REVISION).sof

rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))

SRCS = \
	$(call rwildcard,sys,*.v *.sv *.vhd *.vhdl *.qip *.sdc) \
	$(call rwildcard,rtl,*.v *.sv *.vhd *.vhdl *.qip *.sdc) \
	$(wildcard *.sdc *.v *.sv *.vhd *.vhdl *.qip *.qsf *.qpf)

all: $(SOF)

$(SOF): $(SRCS)
	$(QUARTUS_SH) --flow compile $(PROJECT) -c $(REVISION)

sof: $(SOF)

# Load the core onto the FPGA over USB (JTAG) without reprogramming flash.
run: $(SOF)
	$(QUARTUS_PGM) -c $(CABLE) -m jtag -o "p;$(SOF)@$(DEVICE)"

# List detected JTAG cables and devices in the chain.
jtag:
	jtagconfig

clean:
	rm -rf $(OUTDIR) db incremental_db

.PHONY: all sof run jtag clean
