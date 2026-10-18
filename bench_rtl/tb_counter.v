// Self-checking testbench: random enable / reset, compared against a reference model.
`timescale 1ns/1ps
module tb_counter;
    reg clk = 0, rst = 1, en = 0;
    wire [3:0] count;
    wire wrap;
    reg  [3:0] ref_count;
    integer seed, cycle, errors;

    counter dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));
    always #5 clk = ~clk;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        errors = 0;
        ref_count = 0;
        @(negedge clk); rst = 0;
        for (cycle = 0; cycle < 200; cycle = cycle + 1) begin
            en  = ($random(seed) % 4) != 0;
            rst = ($random(seed) % 50) == 0;
            @(posedge clk);
            if (rst) ref_count = 0; else if (en) ref_count = ref_count + 1;
            @(negedge clk);
            if (count !== ref_count) begin
                $display("ERROR: [counter] count mismatch at %0t ns: expected %0d got %0d", $time, ref_count, count);
                errors = errors + 1;
            end
            if (wrap !== (en && ref_count == 15)) begin
                $display("ERROR: [counter] wrap mismatch at %0t ns: expected %0d got %0d", $time, (en && ref_count == 15), wrap);
                errors = errors + 1;
            end
            if (errors >= 5) cycle = 200;
        end
        if (errors == 0) $display("TEST PASSED");
        else $display("TEST FAILED: %0d errors", errors);
        $finish;
    end
    initial begin #100000 $display("FATAL: [counter] timeout"); $finish; end
endmodule
