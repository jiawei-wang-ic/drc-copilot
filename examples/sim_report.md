# Simulation regression triage

- Runs: **114** — COMPILE_ERROR 12, FAIL 78, PASS 24
- Failing runs grouped into **16** failure signatures (build + first symptom)

| # | Build | Design | Signature | Runs | Baseline line | Model line |
|---|---|---|---|---|---|---|
| 1 | `a_and_or` | alu | first mismatch on y [op=2] | 6 | 17 | 17 |
| 2 | `a_carry_lost` | alu | first mismatch on carry [op=0] | 6 | 15 | 15 |
| 3 | `a_sub_add` | alu | first mismatch on y [op=1] | 6 | 16 | 16 |
| 4 | `a_syntax` | alu | compile error: syntax error (line 12) | 6 | 12 | 10 |
| 5 | `c_en_ignored` | counter | first mismatch on count | 6 | 13 | — |
| 6 | `c_rst_val` | counter | first mismatch on count | 6 | 13 | 13 |
| 7 | `c_syntax` | counter | compile error: syntax error (line 16) | 6 | 16 | 15 |
| 8 | `c_wrap_off1` | counter | first mismatch on wrap | 6 | 9 | 9 |
| 9 | `f_cnt_dec` | fifo | first mismatch on empty | 3 | 17 | 34 |
| 10 | `f_cnt_dec` | fifo | first mismatch on full | 3 | 16 | 34 |
| 11 | `f_full_off1` | fifo | first mismatch on full | 6 | 16 | 16 |
| 12 | `f_rptr_stuck` | fifo | first mismatch on dout | 6 | 18 | 31 |
| 13 | `f_wr_when_full` | fifo | first mismatch on dout | 6 | 18 | 26 |
| 14 | `s_hit_state` | seqdet | first mismatch on hit | 6 | 11 | 11 |
| 15 | `s_no_overlap` | seqdet | first mismatch on hit | 6 | 11 | 19 |
| 16 | `s_wrong_trans` | seqdet | first mismatch on hit | 6 | 11 | 18 |

## 1. `a_and_or` · first mismatch on y [op=2]

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [alu] y mismatch at 1000 ns (op=2): expected 0 got 56; a=0 b=56
ERROR: [alu] zero mismatch at 1000 ns (op=2): expected 1 got 0
ERROR: [alu] y mismatch at 13000 ns (op=2): expected 131 got 215; a=195 b=151
ERROR: [alu] y mismatch at 14000 ns (op=2): expected 0 got 246; a=246 b=0
```
**Candidate RTL lines:**
```verilog
 17:             3'd2: y = a | b;
```
**Baseline (no model):** line 17
**Model suspect line:** 17
**Hypothesis:** op=2 is implemented as bitwise OR but the expected results match bitwise AND (e.g., 195&151=131 expected vs 195|151=215 got; 0&56=0 expected vs 0|56=56 got), so the operator is wrong.
**Fix:** `3'd2: y = a & b;`
**Next step:** Re-run one failing seed while dumping a, b, and y in the wave at 1000 ns and verify y now equals a & b (0) for op=2.

## 2. `a_carry_lost` · first mismatch on carry [op=0]

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [alu] carry mismatch at 25000 ns (op=0): expected 1 got 0
ERROR: [alu] carry mismatch at 30000 ns (op=0): expected 1 got 0
ERROR: [alu] carry mismatch at 44000 ns (op=0): expected 1 got 0
ERROR: [alu] carry mismatch at 45000 ns (op=0): expected 1 got 0
```
**Candidate RTL lines:**
```verilog
 15:             3'd0: y = a + b;
```
**Baseline (no model):** line 15
**Model suspect line:** 15
**Hypothesis:** The add case assigns the full a+b result to y, which is only as wide as the operands, so the carry-out bit is silently truncated and carry stays 0 even when the addition overflows. The result should be captured into {carry, y}.
**Fix:** `3'd0: {carry, y} = a + b;`
**Next step:** In the waveform at 25000 ns, dump a, b, y, and carry for op=0 and confirm that a+b overflows into a 17th (carry) bit while carry remains 0; after the fix, re-run and verify carry matches the expected value on all 6 seeds.

## 3. `a_sub_add` · first mismatch on y [op=1]

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [alu] y mismatch at 3000 ns (op=1): expected 211 got 185; a=198 b=243
ERROR: [alu] y mismatch at 6000 ns (op=1): expected 35 got 255; a=145 b=110
ERROR: [alu] y mismatch at 24000 ns (op=1): expected 221 got 161; a=191 b=226
ERROR: [alu] y mismatch at 55000 ns (op=1): expected 180 got 158; a=169 b=245
```
**Candidate RTL lines:**
```verilog
 16:             3'd1: {carry, y} = {1'b0, a} + {1'b0, b};
```
**Baseline (no model):** line 16
**Model suspect line:** 16
**Hypothesis:** The expected values match a-b mod 256 (198-243=-45→211, 145-110=35, 191-226=-35→221, 169-245=-76→180), but line 16 implements an adder for op=1, producing a+b mod 256 (185, 255, 161, 158), which is exactly what the DUT returns. So op=1 is decoded to the wrong operation: addition instead of subtraction.
**Fix:** `3'd1: {carry, y} = {1'b0, a} - {1'b0, b};`
**Next step:** In the waveform at 3000 ns, probe a, b, y, and the carry bit: confirm the DUT outputs 185 (9-bit sum 441 = 9'b110111001, carry=1) instead of 211, then check the testbench/golden model stimulus to verify op=1 is defined as SUB and that carry/borrow polarity matches after the fix.

## 4. `a_syntax` · compile error: syntax error (line 12)

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
alu.v:12: syntax error
alu.v:10: error: Syntax error in left side of continuous assignment.
alu.v:15: syntax error
alu.v:15: error: Invalid module item.
```
**Candidate RTL lines:**
```verilog
 10:     assign zero = (y == 8'd0)
 11: 
 12:     always @(*) begin
 13:         carry = 1'b0;
 14:         case (op)
```
**Baseline (no model):** line 12
**Model suspect line:** 10
**Hypothesis:** Line 10 is missing a terminating semicolon, so the parser treats the continuous assignment as continuing and only reports 'syntax error' at line 12 (and cascades to 'Invalid module item' at line 15). The line-10 message 'Syntax error in left side of continuous assignment' plus the downstream errors on the next statement are the classic signature of a missing ';'.
**Fix:** `assign zero = (y == 8'd0);`
**Next step:** Add the semicolon and recompile: if the errors at lines 12 and 15 disappear without any other changes, the missing ';' was confirmed; alternately, diff alu.v against the last passing version of the module to see line 10 changed in isolation.

## 5. `c_en_ignored` · first mismatch on count

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [counter] count mismatch at 20000 ns: expected 0 got 1
ERROR: [counter] count mismatch at 30000 ns: expected 1 got 2
ERROR: [counter] count mismatch at 40000 ns: expected 2 got 3
ERROR: [counter] count mismatch at 50000 ns: expected 3 got 4
```
**Candidate RTL lines:**
```verilog
 12:         if (rst)
 13:             count <= 4'd0;
 14:         else
 15:             count <= count + 4'd1;
```
**Baseline (no model):** line 13
_Model unavailable: GLM request failed: timeout_

## 6. `c_rst_val` · first mismatch on count

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [counter] count mismatch at 20000 ns: expected 0 got 1
ERROR: [counter] count mismatch at 30000 ns: expected 1 got 2
ERROR: [counter] count mismatch at 40000 ns: expected 2 got 3
ERROR: [counter] count mismatch at 50000 ns: expected 3 got 4
```
**Candidate RTL lines:**
```verilog
 12:         if (rst)
 13:             count <= 4'd1;
 14:         else if (en)
 15:             count <= count + 4'd1;
```
**Baseline (no model):** line 13
**Model suspect line:** 13
**Hypothesis:** The reset value is off by one: count is loaded with 4'd1 instead of 4'd0, so after reset every subsequent value is exactly one greater than expected, matching all four log mismatches.
**Fix:** `count <= 4'd0;`
**Next step:** In the waveform, probe count at the clock edge where rst deasserts (~before 20000 ns) and confirm it holds 1 after reset instead of 0.

## 7. `c_syntax` · compile error: syntax error (line 16)

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
counter.v:16: syntax error
tb_counter.v:3: error: Malformed statement
tb_counter.v:4: syntax error
tb_counter.v:4: Syntax in assignment statement l-value.
```
**Candidate RTL lines:**
```verilog
 14:         else if (en)
 15:             count <= count + 4'd1
 16:     end
 17: endmodule
```
**Baseline (no model):** line 16
**Model suspect line:** 15
**Hypothesis:** Line 15 is missing the terminating semicolon after the nonblocking assignment, so the parser reaches 'end' on line 16 while still trying to complete the statement and reports the syntax error there instead.
**Fix:** `count <= count + 4'd1;`
**Next step:** Add the semicolon and recompile counter.v; the line-16 syntax error and the cascading tb_counter.v errors should all disappear, confirming this was the root cause.

## 8. `c_wrap_off1` · first mismatch on wrap

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [counter] wrap mismatch at 190000 ns: expected 0 got 1
ERROR: [counter] wrap mismatch at 200000 ns: expected 1 got 0
ERROR: [counter] wrap mismatch at 450000 ns: expected 0 got 1
ERROR: [counter] wrap mismatch at 460000 ns: expected 1 got 0
```
**Candidate RTL lines:**
```verilog
  9:     assign wrap = en && (count == 4'd14);
 12:         if (rst)
 13:             count <= 4'd0;
 14:         else if (en)
 15:             count <= count + 4'd1;
```
**Baseline (no model):** line 9
**Model suspect line:** 9
**Hypothesis:** The wrap comparator fires one count value early: wrap asserts while count==14, but the reference model expects wrap when the 4-bit counter actually rolls over (count==15). This one-cycle/one-count offset makes the checker see wrap=1 when it expects 0 and wrap=0 when it expects 1 on consecutive cycles, matching the alternating 'expected 0 got 1 / expected 1 got 0' errors at each wrap event.
**Fix:** `assign wrap = en && (count == 4'd15);`
**Next step:** In the waveform at 190000 ns, probe count and wrap together: confirm wrap pulses while count is 14 (and is 0 when count is 15), then rerun with the corrected compare value and verify wrap aligns with the 15-to-0 rollover.

## 9. `f_cnt_dec` · first mismatch on empty

**Runs:** 3 (seeds 1, 2, 6)  
**Evidence:**
```
ERROR: [fifo] empty mismatch at 70000 ns: expected 1 got 0
ERROR: [fifo] empty mismatch at 100000 ns: expected 1 got 0
ERROR: [fifo] empty mismatch at 130000 ns: expected 1 got 0
ERROR: [fifo] dout mismatch at 140000 ns: expected 169 got 143
```
**Candidate RTL lines:**
```verilog
 17:     assign empty = (cnt == 3'd0);
 21:         if (rst) begin
 24:             cnt  <= 3'd0;
 30:             if (rd_en && !empty)
 33:                 2'b10: cnt <= cnt + 3'd1;
 34:                 2'b01: cnt <= cnt;
 35:                 default: cnt <= cnt;
```
**Baseline (no model):** line 17
**Model suspect line:** 34
**Hypothesis:** The read-only case (2'b01) leaves cnt unchanged instead of decrementing it, so after any read the count never returns to 0. This keeps empty asserted low (expected 1, got 0) and eventually causes dout mismatches as the read pointer walks past valid data.
**Fix:** `2'b01: cnt <= cnt - 3'd1;`
**Next step:** In the waveform at ~70000 ns, probe cnt and rd_en: trigger a read when cnt==1 and confirm cnt fails to drop to 0 and empty stays 0 on that clock edge.

## 10. `f_cnt_dec` · first mismatch on full

**Runs:** 3 (seeds 3, 4, 5)  
**Evidence:**
```
ERROR: [fifo] full mismatch at 100000 ns: expected 0 got 1
ERROR: [fifo] full mismatch at 110000 ns: expected 0 got 1
ERROR: [fifo] full mismatch at 120000 ns: expected 0 got 1
ERROR: [fifo] full mismatch at 130000 ns: expected 0 got 1
```
**Candidate RTL lines:**
```verilog
 16:     assign full  = (cnt == 3'd4);
 21:         if (rst) begin
 24:             cnt  <= 3'd0;
 30:             if (rd_en && !empty)
 33:                 2'b10: cnt <= cnt + 3'd1;
 34:                 2'b01: cnt <= cnt;
 35:                 default: cnt <= cnt;
```
**Baseline (no model):** line 16
**Model suspect line:** 34
**Hypothesis:** The read-only case holds cnt instead of decrementing it, so after reads the occupancy never drops below 4 and full (cnt == 3'd4) stays asserted, giving expected 0 got 1 on full.
**Fix:** `2'b01: cnt <= cnt - 3'd1;`
**Next step:** Waveform-probe cnt, rd_en, and wr_en around the first mismatch at 100000 ns: confirm cnt stays at 4 across cycles where only rd_en is asserted.

## 11. `f_full_off1` · first mismatch on full

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [fifo] full mismatch at 200000 ns: expected 0 got 1
ERROR: [fifo] dout mismatch at 290000 ns: expected 103 got 1
ERROR: [fifo] dout mismatch at 300000 ns: expected 103 got 1
ERROR: [fifo] dout mismatch at 310000 ns: expected 103 got 1
```
**Candidate RTL lines:**
```verilog
 16:     assign full  = (cnt == 3'd3);
 21:         if (rst) begin
 24:             cnt  <= 3'd0;
 30:             if (rd_en && !empty)
 33:                 2'b10: cnt <= cnt + 3'd1;
 34:                 2'b01: cnt <= cnt - 3'd1;
 35:                 default: cnt <= cnt;
```
**Baseline (no model):** line 16
**Model suspect line:** 16
**Hypothesis:** full compares cnt against 3'd3, an off-by-one for a 4-deep FIFO whose entry count runs 0..4; full asserts one entry early, so the writer stalls or drops data while a slot is still free, and subsequent reads return stale data (dout=1 instead of the expected 103).
**Fix:** `assign full  = (cnt == 3'd4);`
**Next step:** In the waveform just before 200000 ns, probe cnt together with wr_en/rd_en and count the entries actually pushed: full goes high at cnt==3 with a free slot remaining; a directed test pushing 4 items should show full rising only after the 4th write.

## 12. `f_rptr_stuck` · first mismatch on dout

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [fifo] dout mismatch at 80000 ns: expected 143 got 137
ERROR: [fifo] dout mismatch at 90000 ns: expected 143 got 137
ERROR: [fifo] dout mismatch at 110000 ns: expected 0 got 137
ERROR: [fifo] dout mismatch at 120000 ns: expected 49 got 137
```
**Candidate RTL lines:**
```verilog
 18:     assign dout  = mem[rptr];
 21:         if (rst) begin
 23:             rptr <= 2'd0;
 26:             if (wr_en && !full) begin
 27:                 mem[wptr] <= din;
 30:             if (rd_en && !empty)
 31:                 rptr <= rptr;
```
**Baseline (no model):** line 18
**Model suspect line:** 31
**Hypothesis:** The read pointer never advances because line 31 assigns rptr to itself instead of incrementing it, so dout stays frozen at the same memory location. This explains dout returning the constant stale value 137 while the expected data (143, 0, 49) changes as the testbench pops successive entries.
**Fix:** `rptr <= rptr + 2'd1;`
**Next step:** In the waveform around 80000 ns, probe rptr across multiple asserted rd_en cycles: it will hold a constant value (never incrementing) while wptr advances, confirming the read pointer is stuck.

## 13. `f_wr_when_full` · first mismatch on dout

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [fifo] dout mismatch at 240000 ns: expected 152 got 224
ERROR: [fifo] dout mismatch at 250000 ns: expected 184 got 165
ERROR: [fifo] dout mismatch at 260000 ns: expected 184 got 165
ERROR: [fifo] dout mismatch at 270000 ns: expected 184 got 165
```
**Candidate RTL lines:**
```verilog
 18:     assign dout  = mem[rptr];
 21:         if (rst) begin
 23:             rptr <= 2'd0;
 26:             if (wr_en) begin
 27:                 mem[wptr] <= din;
 30:             if (rd_en && !empty)
 31:                 rptr <= rptr + 2'd1;
```
**Baseline (no model):** line 18
**Model suspect line:** 26
**Hypothesis:** The write branch checks only wr_en, with no !full qualifier, unlike the symmetric !empty guard on the read at line 30. When the FIFO is full, wptr has wrapped onto rptr, so each extra write overwrites the oldest unread entry; subsequent reads then return the newer word (e.g., 165) instead of the expected older word (184), producing repeated dout mismatches while the FIFO stays full.
**Fix:** `if (wr_en && !full) begin`
**Next step:** In the waveform around 240000 ns, probe full, wr_en, wptr, and rptr: confirm that at the first mismatch the write that landed at address rptr occurred while full was asserted (wptr == rptr), overwriting the entry the reader expected.

## 14. `s_hit_state` · first mismatch on hit

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [seqdet] hit mismatch at 90000 ns: expected 0 got 1; last 8 input bits 00000101
ERROR: [seqdet] hit mismatch at 100000 ns: expected 1 got 0; last 8 input bits 00001011
ERROR: [seqdet] hit mismatch at 150000 ns: expected 0 got 1; last 8 input bits 01111101
ERROR: [seqdet] hit mismatch at 160000 ns: expected 1 got 0; last 8 input bits 11111011
```
**Candidate RTL lines:**
```verilog
 11:     assign hit = (state == S101);
 15:             S0:      next = din ? S1    : S0;
 16:             S1:      next = din ? S1    : S10;
 17:             S10:     next = din ? S101  : S0;
 18:             S101:    next = din ? S1011 : S10;
 19:             S1011:   next = din ? S1    : S10;
 20:             default: next = S0;
 25:         if (rst) state <= S0;
 26:         else     state <= next;
```
**Baseline (no model):** line 11
**Model suspect line:** 11
**Hypothesis:** hit is asserted on state S101 instead of S1011, so it fires one bit early: any input ending in '101' gives a false hit (expected 0 got 1), and a true '1011' match leaves the machine in S1011 where hit is 0 (expected 1 got 0). The next-state transitions are all correct KMP-style moves for detecting 1011 with overlap, so the output decode is the faulty line.
**Fix:** `assign hit = (state == S1011);`
**Next step:** In the waveform at 90000 ns, probe state and hit with the input trace 00000101: confirm state reaches S101 on the final bit while hit pulses high, whereas with the fix hit should rise only in the cycle where state == S1011 (e.g., after the 00001011 sequence at 100000 ns).

## 15. `s_no_overlap` · first mismatch on hit

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [seqdet] hit mismatch at 1650000 ns: expected 1 got 0; last 8 input bits 10111011
```
**Candidate RTL lines:**
```verilog
 11:     assign hit = (state == S1011);
 15:             S0:      next = din ? S1    : S0;
 16:             S1:      next = din ? S1    : S10;
 17:             S10:     next = din ? S101  : S0;
 18:             S101:    next = din ? S1011 : S10;
 19:             S1011:   next = din ? S0    : S10;
 20:             default: next = S0;
 25:         if (rst) state <= S0;
 26:         else     state <= next;
```
**Baseline (no model):** line 11
**Model suspect line:** 19
**Hypothesis:** In state S1011 (full '1011' matched), a subsequent din=1 leaves the trailing '1' as a potential new match start, but the FSM goes to S0 instead of S1, dropping overlap history. For the stream ...10111011, the second '1011' ends with hit expected 1, but the state path is broken (S0→S0→S1→S1) so hit is 0.
**Fix:** `S1011:   next = din ? S1    : S10;`
**Next step:** Replay the failing seed and dump state/din around 1649990-1650000 ns: you should see state==S1011 when din goes 1, then state transitions to S0 (wrong) instead of S1, which redirects the FSM away from the second S1011 hit.

## 16. `s_wrong_trans` · first mismatch on hit

**Runs:** 6 (seeds 1, 2, 3, 4, 5, 6)  
**Evidence:**
```
ERROR: [seqdet] hit mismatch at 220000 ns: expected 1 got 0; last 8 input bits 11101011
ERROR: [seqdet] hit mismatch at 2140000 ns: expected 1 got 0; last 8 input bits 00101011
ERROR: [seqdet] hit mismatch at 2200000 ns: expected 1 got 0; last 8 input bits 11101011
ERROR: [seqdet] hit mismatch at 2850000 ns: expected 1 got 0; last 8 input bits 00101011
```
**Candidate RTL lines:**
```verilog
 11:     assign hit = (state == S1011);
 15:             S0:      next = din ? S1    : S0;
 16:             S1:      next = din ? S1    : S10;
 17:             S10:     next = din ? S101  : S0;
 18:             S101:    next = din ? S1011 : S0;
 19:             S1011:   next = din ? S1    : S10;
 20:             default: next = S0;
 25:         if (rst) state <= S0;
 26:         else     state <= next;
```
**Baseline (no model):** line 11
**Model suspect line:** 18
**Hypothesis:** Line 18 sends S101 to S0 on din=0, but after matching '101' and seeing a 0 the history '1010' still contains the prefix '10', so the FSM should fall back to S10 for overlapping detection. Because it resets to S0, sequences ending in '...101011' never reach S1011, so hit stays 0 when the checker expects 1 (matching '11101011' and '00101011' failures).
**Fix:** `            S101:    next = din ? S1011 : S10;`
**Next step:** Replay the logged window (e.g., din = 11101011) in a waveform and probe state/din around 220000 ns: confirm that after S101 samples din=0 the state jumps to S0 instead of S10, which then prevents S1011 (and hit) on the final two 1s.
