# Research Note 08 — directed instruction libraries

## riscv_directed_instr_lib.sv

### riscv_directed_instr_stream (base)
Extends `riscv_rand_instr_stream`. After randomize:
- All instructions: `atomic=1`, `has_label=0`.
- First instruction: `comment = "Start <stream_name>"`.
- Last instruction: `comment = "End <stream_name>"`.
- If `label != ""`, first instruction gets that label.

### riscv_jump_instr
Fields: `jump` (JAL/JALR), `addi` (compute target), `la` pseudo, optional `branch`, `gpr` (scratch ≠ reserved/ZERO), `imm ∈ [-1023, 1023]`, `enable_branch`, `mixed_instr_cnt ∈ [5,10]`, `stack_exit_instr[]`, `target_program_label`, `use_jalr`.

Pattern:
```
la gpr, target_program_label
addi gpr, gpr, imm
[if branch: branch to jump_label]
[5–10 random filler instructions]
jump_label: jalr ra, -imm, gpr    # or jal ra, target_program_label
```
Stack exit instructions inserted before unconditional jumps (jump.rd==ZERO or C_JR).

### riscv_jal_instr
`num_of_jump_instr ∈ [10, 30]`. Back-to-back JAL/C_J/C_JAL chain; targets assigned per shuffled `order[]` (forward `f` or backward `b`).

### riscv_push_stack_instr
Params: `stack_len`, `saved_regs[]` (default {RA}), `enable_branch`, `push_start_label`, `num_of_redudant_instr ∈ [3,10]`.
- `addi sp, sp, -stack_len`.
- For each saved reg i: `sw/sd saved_regs[i], (i+1)*(XLEN/8), sp`.
- Optional branch to `push_start_label`.

### riscv_pop_stack_instr
Inverse: loads saved regs then `addi sp, sp, +stack_len`.

### riscv_int_numeric_corner_stream
Corner values `{Zero=0, AllOne='1, NegativeMax=1<<(XLEN-1), NormalValue=random}`. Init `num_of_avail_regs=10` registers with `li reg, 0x<val>`, then emit `num_of_instr ∈ [15,30]` random ARITHMETIC instructions on those regs.

## riscv_load_store_instr_lib.sv

### locality_e
```
NARROW: [-16:16]; HIGH: [-64:64]; MEDIUM: [-256:256]; SPARSE: [-2048:2047]
```

### riscv_mem_access_stream (base)
Pre-randomize picks region: `load_store_shared_memory → amo_region`, `kernel_mode → s_mem_region`, else `mem_region`. Emits `la gpr, h<hart>_<region>+<base>` for init.

### riscv_load_store_base_instr_stream
Fields: `num_load_store`, `num_mixed_instr`, `base`, `offset[]`, `addr[]`, `data_page_id`, `rs1_reg` (∉ reserved ∪ ZERO), `locality`, `max_load_store_offset`, `use_sp_as_rs1` (70% weight when not reserved).

Constraints:
```
data_page_id < max_data_page_id
max_load_store_offset == data_page[data_page_id].size_in_bytes
base ∈ [0, max_offset-1]
```

Per-address: soft locality constraint; `addr == base + offset`; `addr ∈ [0, max_offset-1]`.

Instruction selection by alignment:
- Always include LB/LBU/SB.
- 2-byte aligned → add LH/LHU/SH.
- 4-byte aligned → add LW/SW (+FLW/FSW if FP); if offset ∈ [0,127] and %4==0 and RV32C enabled → add C_LW/C_SW (or C_LWSP/C_SWSP when rs1_reg==SP); (+C_FLW/C_FSW if FP).
- 8-byte aligned (XLEN≥64) → add LWU/LD/SD (+FLD/FSD if FP); similar compressed variants.

### Subclasses
| Class | num_load_store | num_mixed_instr | Notes |
|-------|----------------|-----------------|-------|
| riscv_single_load_store_instr_stream | 1 | <5 | |
| riscv_load_store_stress_instr_stream | [10,30] | 0 | |
| riscv_load_store_shared_mem_stream | [10,30] | 0 | Uses amo_region |
| riscv_load_store_rand_instr_stream | [10,30] | [10,30] | |
| riscv_hazard_instr_stream | [10,30] | [10,30] | Only 6 avail regs |
| riscv_load_store_hazard_instr_stream | [10,20] | [1,7] | hazard_ratio ∈ [20,100]% offset reuse |
| riscv_multi_page_load_store_instr_stream | — | — | 2–8 pages, unique rs1_reg per stream |
| riscv_mem_region_stress_test | — | — | All streams same page |
| riscv_load_store_rand_addr_instr_stream | [5,10] | [5,10] | Unpreloaded 4K-aligned addr; SW pre-init before LW |
| riscv_vector_load_store_instr_stream | — | [0,10] | Vector LS; address modes below |
| riscv_vector_amo_instr_stream | — | — | Vector AMO; address_mode==INDEXED |

### Vector LS address modes
```
UNIT_STRIDED: VLE_V, VSE_V (+VLEFF_V if enable_fault_only_first_load; +VLSEGE_V, VSSEGE_V, VLSEGEFF_V if enable_zvlsseg)
STRIDED: VLSE_V, VSSE_V (+VLSSEGE_V, VSSSEGE_V if zvlsseg)
INDEXED: VLXEI_V, VSXEI_V, VSUXEI_V (+VLXSEGEI_V, VSXSEGEI_V, VSUXSEGEI_V if zvlsseg)
```

### Vector AMO stream
```
allowed = {VAMOSWAPE_V, VAMOADDE_V, VAMOXORE_V, VAMOANDE_V, VAMOORE_V,
           VAMOMINE_V, VAMOMAXE_V, VAMOMINUE_V, VAMOMAXUE_V}
address_mode == INDEXED
```

## riscv_amo_instr_lib.sv

### riscv_amo_base_instr_stream
Fields: `num_amo`, `num_mixed_instr`, `offset[]` (aligned: RV32 %4==0, RV64 %8==0), `rs1_reg[]`, `num_of_rs1_reg` (default 1).
Uses `cfg.amo_region`. Emits LA per rs1_reg.

### riscv_lr_sc_instr_stream
`num_amo==1, num_mixed_instr ∈ [0,15]`. Generates LR+SC pair with base rs1_reg.
Per RISC-V spec §8.3, between LR and SC only base I allowed — filler instructions filtered to exclude LOAD/STORE/BRANCH/FENCE/SYSTEM (override `add_mixed_instr`).

### riscv_amo_instr_stream
`num_amo ∈ [1,10]`, `num_mixed_instr ∈ [0, num_amo]`, `num_of_rs1_reg ∈ [1, min(5, num_amo)]`.
Each AMO: `rs1 ∈ rs1_reg[]`, `rd ∉ rs1_reg[]`, `aq+rl mutex (aq&rl==0)`.

## riscv_loop_instr.sv

### Fields
- `num_of_nested_loop ∈ [1, 2]`.
- `num_of_instr_in_loop ∈ [1, 25]`.
- `loop_cnt_reg[]`, `loop_limit_reg[]`, `loop_init_val[]`, `loop_step_val[]`, `loop_limit_val[]`, `branch_type[]`.

### Constraints
- `branch_type ∈ {BEQ, BNE, BLT, BGE, BLTU, BGEU}` (+ `C_BEQZ, C_BNEZ` if RVC enabled).
- For C_BNEZ/C_BEQZ: `loop_limit_val==0`, `loop_limit_reg==ZERO`, `loop_cnt_reg ∈ compressed_gpr`.
- For equality branches: `(loop_limit - loop_init) % loop_step == 0` AND `loop_init != loop_limit`.
- For BGE: `loop_step < 0` (decrement).
- For BGEU: `loop_step<0`, `loop_init>0`, `loop_step+loop_limit>0`.
- For BLT/BLTU: `loop_step > 0`.
- `loop_init_val ∈ [-10, 10]`, `loop_step_val ∈ [-10, 10]`, `loop_limit_val ∈ [-20, 20]`.
- If `loop_init < loop_limit`: step>0 else step<0.

### Per loop i generation
1. `addi loop_cnt_reg[i], x0, loop_init_val[i]`.
2. `addi loop_limit_reg[i], x0, loop_limit_val[i]` (unless compressed branches).
3. Random branch-target instruction at label `<stream>_<i>_t`.
4. `addi loop_cnt_reg[i], loop_cnt_reg[i], loop_step_val[i]`.
5. Inner-loop body (inlined previous level's loop structure).
6. Backward branch of `branch_type[i]` with `rs1=loop_cnt_reg[i], rs2=loop_limit_reg[i], imm_str=<target_label>`.

Reserved regs: loop_cnt_reg + loop_limit_reg.

## riscv_illegal_instr.sv

### Enum illegal_instr_type_e (distribution)
```
kIllegalOpcode            := 3
kIllegalCompressedOpcode  := 1
kIllegalFunc3             := 1
kIllegalFunc7             := 1
kReservedCompressedInstr  := 1
kHintInstr                := 3
kIllegalSystemInstr       := 3
```
(If RV32C not in supported_isa: compressed=0, no kHintInstr.)

### Strategies
- **kIllegalOpcode**: opcode ∉ legal_opcode ∧ opcode[1:0]==11.
- **kIllegalCompressedOpcode**: c_op ∈ {00, 01, 10} with c_msb chosen not in legal c00/c10 lists.
- **kIllegalFunc3**: maps per-opcode illegal func3 (JALR:≠000, BRANCH:∈{010,011}, etc.).
- **kIllegalFunc7**: func7 ∉ {0, 0100000, 1}; shifts reserved patterns.
- **kReservedCompressedInstr** (enum reserved_c_instr_e): specific encodings like all-zero instr, c.addi16sp reserved, c.lui variants, c.jr with rs1=0, etc.
- **kHintInstr**: valid HINT encodings (C_ADDI rd=0 imm=0, C_LI rd=0, C_MV rd=0 rs2!=0, etc.).
- **kIllegalSystemInstr**: opcode=1110011; func3=000 with rs1!=0 or rd!=0 and instr_bin[31:20] ∉ {valid SYSTEM codes}; else CSR with csr ∉ {implemented ∪ custom_csr}.

### Output
`get_bin_str()` returns hex: 4 chars compressed (`.2byte 0x...`), 8 chars full (`.4byte 0x...`). Comment = exception name (+ reserved variant).

## riscv_pseudo_instr.sv

Supports LI and LA (enum `riscv_pseudo_instr_name_t`). `convert2asm()` = `<name> rd, <imm_str>` lower-cased, mnemonic padded to MAX_INSTR_STR_LEN.

Expansion left to assembler (no manual LUI+ADDI unless forced).

## Stream-name table (referenced from testlist +directed_instr_N)
`riscv_int_numeric_corner_stream, riscv_jump_instr, riscv_jal_instr, riscv_push_stack_instr, riscv_pop_stack_instr, riscv_single_load_store_instr_stream, riscv_load_store_stress_instr_stream, riscv_load_store_shared_mem_stream, riscv_load_store_rand_instr_stream, riscv_hazard_instr_stream, riscv_load_store_hazard_instr_stream, riscv_multi_page_load_store_instr_stream, riscv_mem_region_stress_test, riscv_load_store_rand_addr_instr_stream, riscv_lr_sc_instr_stream, riscv_amo_instr_stream, riscv_loop_instr, riscv_illegal_instr, riscv_vector_load_store_instr_stream, riscv_vector_amo_instr_stream`.

## Integration
`directed_instr_stream_ratio[name] = count_per_1000_instrs`; `generate_directed_instr_stream` computes `insert_cnt = original_instr_cnt * ratio / 1000` and clamps to `min_insert_cnt`; creates N instances via UVM factory, shuffles; `post_process_instr` inserts each at random non-atomic positions.
