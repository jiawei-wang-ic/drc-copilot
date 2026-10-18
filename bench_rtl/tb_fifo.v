// Self-checking testbench: random pushes / pops against a queue model.
`timescale 1ns/1ps
module tb_fifo;
    reg clk = 0, rst = 1, wr_en = 0, rd_en = 0;
    reg  [7:0] din = 0;
    wire [7:0] dout;
    wire full, empty;
    reg  [7:0] q [0:15];
    integer head, tail, n, seed, cycle, errors;
    reg do_wr, do_rd;

    fifo dut (.clk(clk), .rst(rst), .wr_en(wr_en), .rd_en(rd_en), .din(din), .dout(dout), .full(full), .empty(empty));
    always #5 clk = ~clk;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        errors = 0; head = 0; tail = 0; n = 0;
        @(negedge clk); rst = 0;
        for (cycle = 0; cycle < 300; cycle = cycle + 1) begin
            @(negedge clk);
            if (full !== (n == 4)) begin
                $display("ERROR: [fifo] full mismatch at %0t ns: expected %0d got %0d", $time, (n == 4), full);
                errors = errors + 1;
            end
            if (empty !== (n == 0)) begin
                $display("ERROR: [fifo] empty mismatch at %0t ns: expected %0d got %0d", $time, (n == 0), empty);
                errors = errors + 1;
            end
            if (n > 0 && dout !== q[head % 16]) begin
                $display("ERROR: [fifo] dout mismatch at %0t ns: expected %0d got %0d", $time, q[head % 16], dout);
                errors = errors + 1;
            end
            wr_en = ($random(seed) % 2) != 0;
            rd_en = ($random(seed) % 3) == 0;
            din   = $random(seed);
            do_wr = wr_en && (n < 4);
            do_rd = rd_en && (n > 0);
            @(posedge clk);
            if (do_wr) begin q[tail % 16] = din; tail = tail + 1; end
            if (do_rd) head = head + 1;
            n = n + do_wr - do_rd;
            if (errors >= 5) cycle = 300;
        end
        if (errors == 0) $display("TEST PASSED");
        else $display("TEST FAILED: %0d errors", errors);
        $finish;
    end
    initial begin #100000 $display("FATAL: [fifo] timeout"); $finish; end
endmodule
