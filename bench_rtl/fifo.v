// Synchronous FIFO, 8 bits wide, 4 entries deep.
module fifo (
    input  wire       clk,
    input  wire       rst,
    input  wire       wr_en,
    input  wire       rd_en,
    input  wire [7:0] din,
    output wire [7:0] dout,
    output wire       full,
    output wire       empty
);
    reg [7:0] mem [0:3];
    reg [1:0] wptr, rptr;
    reg [2:0] cnt;

    assign full  = (cnt == 3'd4);
    assign empty = (cnt == 3'd0);
    assign dout  = mem[rptr];

    always @(posedge clk) begin
        if (rst) begin
            wptr <= 2'd0;
            rptr <= 2'd0;
            cnt  <= 3'd0;
        end else begin
            if (wr_en && !full) begin
                mem[wptr] <= din;
                wptr <= wptr + 2'd1;
            end
            if (rd_en && !empty)
                rptr <= rptr + 2'd1;
            case ({wr_en && !full, rd_en && !empty})
                2'b10: cnt <= cnt + 3'd1;
                2'b01: cnt <= cnt - 3'd1;
                default: cnt <= cnt;
            endcase
        end
    end
endmodule
