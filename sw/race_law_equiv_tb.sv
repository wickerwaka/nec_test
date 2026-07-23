module race_law_equiv_tb;
`include "race_law.svh"
reg [15:0] old_rom [0:1023];
integer address;
integer passed;
integer failed;
reg expected;
reg actual;

initial begin
    $readmemh("hdl/rtl/core/int9d_race.hex", old_rom);
    passed = 0;
    failed = 0;
    for (address = 0; address < 16384; address = address + 1) begin
        expected = old_rom[address >> 4][address & 15];
        actual = race_law(address[13:7], address[6:0]);
        if (actual !== expected) begin
            failed = failed + 1;
            if (failed <= 20)
                $display("MISMATCH address=0x%04x pre=0x%02x pop=0x%02x expected=%b actual=%b",
                         address, address[13:7], address[6:0], expected, actual);
        end else begin
            passed = passed + 1;
        end
    end
    $display("OLD-ROM-vs-race_law: pass=%0d/16384 fail=%0d/16384", passed, failed);
    if (failed != 0)
        $fatal(1, "race_law equivalence failed");
    $finish;
end
endmodule
