#!/usr/bin/env python3
"""Generate the bring-up boot image for the V30 test harness.

Produces hdl/rtl/boot_even.hex / boot_odd.hex ($readmemh, one byte per line)
for test_mem.sv: 64 KB split into even (AD7:0) and odd (AD15:8) lanes.

The 1 MB address space mirrors into 64 KB, so the reset vector FFFF0h lands
at offset 0xFFF0.

Bring-up program: far-jump from the reset vector to 0000:0100, then a small
loop that exercises word write, byte read, and a backwards jump -- enough to
observe code fetch, memory read/write, and queue-flush behavior in the
capture buffer.
"""
from pathlib import Path

SIZE = 1 << 16
mem = bytearray([0x90] * SIZE)  # NOP fill

def put(addr, data):
    mem[addr:addr + len(data)] = data

# Reset vector (FFFF0h -> 0xFFF0): JMP FAR 0000:0100
put(0xFFF0, bytes([0xEA, 0x00, 0x01, 0x00, 0x00]))

# Program at 0000:0100
put(0x0100, bytes([
    0xB8, 0x34, 0x12,        # MOV AW,1234h
    0xBB, 0x00, 0x20,        # MOV BW,2000h
    0x89, 0x07,              # MOV [BW],AW      ; word write to 02000h (even)
    0xA0, 0x00, 0x20,        # MOV AL,[2000h]   ; byte read
    0xA1, 0x01, 0x20,        # MOV AW,[2001h]   ; odd-address word read (split access)
    0x90,                    # NOP
    0xEB, 0xEF,              # JMP 0100h        ; loop (queue flush); disp = 0100h - 0111h

]))

def write_mif(path, data):
    lines = [
        f"WIDTH=8;",
        f"DEPTH={len(data)};",
        "ADDRESS_RADIX=HEX;",
        "DATA_RADIX=HEX;",
        "CONTENT BEGIN",
    ]
    lines += [f"{a:X} : {b:02X};" for a, b in enumerate(data)]
    lines.append("END;")
    path.write_text("\n".join(lines) + "\n")

out = Path(__file__).resolve().parent.parent / "hdl" / "rtl"
even = mem[0::2]
odd = mem[1::2]
# $readmemh images for simulation
(out / "boot_even.hex").write_text("\n".join(f"{b:02x}" for b in even) + "\n")
(out / "boot_odd.hex").write_text("\n".join(f"{b:02x}" for b in odd) + "\n")
# .mif images for the altsyncram init_file (synthesis)
write_mif(out / "boot_even.mif", even)
write_mif(out / "boot_odd.mif", odd)
print(f"wrote boot_even/odd .hex and .mif to {out} ({SIZE} bytes total)")
