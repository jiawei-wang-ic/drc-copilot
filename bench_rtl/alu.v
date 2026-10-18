// 8-bit ALU: add / sub / and / or / xor / shift left, with carry out and zero flag.
module alu (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] op,
    output reg  [7:0] y,
    output reg        carry,
    output wire       zero
);
    assign zero = (y == 8'd0);

    always @(*) begin
        carry = 1'b0;
        case (op)
            3'd0: {carry, y} = {1'b0, a} + {1'b0, b};
            3'd1: {carry, y} = {1'b0, a} - {1'b0, b};
            3'd2: y = a & b;
            3'd3: y = a | b;
            3'd4: y = a ^ b;
            3'd5: {carry, y} = {a, 1'b0};
            default: y = 8'd0;
        endcase
    end
endmodule
