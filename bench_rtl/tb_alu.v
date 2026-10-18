// Self-checking testbench: random operands and opcodes against a behavioural model.
`timescale 1ns/1ps
module tb_alu;
    reg  [7:0] a, b;
    reg  [2:0] op;
    wire [7:0] y;
    wire carry, zero;
    reg  [8:0] r;
    integer seed, i, errors;

    alu dut (.a(a), .b(b), .op(op), .y(y), .carry(carry), .zero(zero));

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        errors = 0;
        for (i = 0; i < 300; i = i + 1) begin
            a = $random(seed); b = $random(seed); op = $unsigned($random(seed)) % 6;
            case (op)
                3'd0: r = {1'b0, a} + {1'b0, b};
                3'd1: r = {1'b0, a} - {1'b0, b};
                3'd2: r = {1'b0, a & b};
                3'd3: r = {1'b0, a | b};
                3'd4: r = {1'b0, a ^ b};
                default: r = {a, 1'b0};
            endcase
            #1;
            if (y !== r[7:0]) begin
                $display("ERROR: [alu] y mismatch at %0t ns (op=%0d): expected %0d got %0d; a=%0d b=%0d", $time, op, r[7:0], y, a, b);
                errors = errors + 1;
            end
            if (carry !== r[8]) begin
                $display("ERROR: [alu] carry mismatch at %0t ns (op=%0d): expected %0d got %0d", $time, op, r[8], carry);
                errors = errors + 1;
            end
            if (zero !== (r[7:0] == 0)) begin
                $display("ERROR: [alu] zero mismatch at %0t ns (op=%0d): expected %0d got %0d", $time, op, (r[7:0] == 0), zero);
                errors = errors + 1;
            end
            if (errors >= 5) i = 300;
        end
        if (errors == 0) $display("TEST PASSED");
        else $display("TEST FAILED: %0d errors", errors);
        $finish;
    end
endmodule
