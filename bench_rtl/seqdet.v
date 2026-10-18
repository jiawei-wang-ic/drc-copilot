// Moore FSM: detect the overlapping bit sequence 1011 on din; hit is high for one cycle.
module seqdet (
    input  wire clk,
    input  wire rst,
    input  wire din,
    output wire hit
);
    localparam S0 = 3'd0, S1 = 3'd1, S10 = 3'd2, S101 = 3'd3, S1011 = 3'd4;
    reg [2:0] state, next;

    assign hit = (state == S1011);

    always @(*) begin
        case (state)
            S0:      next = din ? S1    : S0;
            S1:      next = din ? S1    : S10;
            S10:     next = din ? S101  : S0;
            S101:    next = din ? S1011 : S10;
            S1011:   next = din ? S1    : S10;
            default: next = S0;
        endcase
    end

    always @(posedge clk) begin
        if (rst) state <= S0;
        else     state <= next;
    end
endmodule
