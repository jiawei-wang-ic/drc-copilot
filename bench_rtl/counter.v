// 4-bit up counter with synchronous reset, enable and wrap-around flag.
module counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output reg  [3:0] count,
    output wire       wrap
);
    assign wrap = en && (count == 4'd15);

    always @(posedge clk) begin
        if (rst)
            count <= 4'd0;
        else if (en)
            count <= count + 4'd1;
    end
endmodule
