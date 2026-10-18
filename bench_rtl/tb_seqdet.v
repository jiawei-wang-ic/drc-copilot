// Self-checking testbench: random bit stream, reference = last four bits equal 1011.
`timescale 1ns/1ps
module tb_seqdet;
    reg clk = 0, rst = 1, din = 0;
    wire hit;
    reg [3:0] hist;
    reg [7:0] h8;
    integer seed, cycle, errors, seen;

    seqdet dut (.clk(clk), .rst(rst), .din(din), .hit(hit));
    always #5 clk = ~clk;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        errors = 0; hist = 0; h8 = 0; seen = 0;
        @(negedge clk); rst = 0;
        for (cycle = 0; cycle < 400; cycle = cycle + 1) begin
            din = ($random(seed) % 2) != 0;
            @(posedge clk);
            hist = {hist[2:0], din};
            h8   = {h8[6:0], din};
            seen = seen + 1;
            @(negedge clk);
            if (hit !== (seen >= 4 && hist == 4'b1011)) begin
                $display("ERROR: [seqdet] hit mismatch at %0t ns: expected %0d got %0d; last 8 input bits %b", $time, (seen >= 4 && hist == 4'b1011), hit, h8);
                errors = errors + 1;
            end
            if (errors >= 5) cycle = 400;
        end
        if (errors == 0) $display("TEST PASSED");
        else $display("TEST FAILED: %0d errors", errors);
        $finish;
    end
    initial begin #100000 $display("FATAL: [seqdet] timeout"); $finish; end
endmodule
