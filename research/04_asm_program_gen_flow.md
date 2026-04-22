# Research Note 04 — riscv_asm_program_gen.sv + instr_stream + sequence + callstack

## Phases of `gen_program()` (in order)

```
instr_stream.delete()
gen_program_header()                                   # Phase 1
for hart in 0..num_of_harts-1:
  setup_misa()                                         # Phase 2
  create_page_table(hart)
  pre_enter_privileged_mode(hart)
  gen_init_section(hart)                               # Phase 3
  if support_pmp && !bare_program_mode:                # Phase 4 (early trap)
    gen_trap_handlers(hart)
    gen_ecall_handler(hart)
    gen_instr_fault_handler(hart)
    gen_load_fault_handler(hart)
    gen_store_fault_handler(hart)
    if hart==0: gen_test_done()
  gen_sub_program(hart, sub_program[hart], ...)        # Phase 5
  main_program[hart] = riscv_instr_sequence::create    # Phase 6
  generate_directed_instr_stream(...)
  main_program[hart].gen_instr(is_main=1, no_branch=cfg.no_branch_jump)
  gen_callstack(main_program[hart], sub_program[hart], sub_names, num_of_sub_program)
  main_program[hart].post_process_instr()
  main_program[hart].generate_instr_stream()
  instr_stream += main_program[hart].instr_string_list
  if hart==0 && !support_pmp: gen_test_done()          # Phase 7
  insert_sub_program(sub_program[hart], instr_stream)  # Phase 8
  gen_program_end(hart)                                # Phase 9
  if support_debug_mode: gen_debug_rom(hart)           # Phase 10
for hart:                                              # Phase 11
  gen_data_page_begin(hart)
  gen_data_page(hart)
  gen_stack_section(hart)
  if !bare_program_mode: gen_kernel_sections(hart)
  gen_page_table_section(hart)
```

## Section order emitted

```
.include "user_define.h"
.globl _start
.section .text
[.option norvc;]            if disable_compressed_instr
.include "user_init.s"
_start:                     [dispatch by MHARTID]
h<N>_start:                 [misa → page tables → privileged setup]
init:                       [FP init → GPR init → SP init → vector init → signature INITIALIZED → dummy CSR writes]
[if PMP: trap_handlers, test_done]
sub_1:, sub_2:, …
main:                       [directed streams interleaved + random stream]
[if !PMP: test_done]
[inserted sub-programs]
h<N>_instr_end: nop
.section .data
.align 6; .global tohost; tohost: .dword 0;
.align 6; .global fromhost; fromhost: .dword 0;
[data pages: .section .h<N>region_<i>, "aw",@progbits]
.section .h<N>user_stack,"aw",@progbits
.align <12 if SATP_MODE != BARE else 2>
h<N>user_stack_start:
.rept <stack_len-1> .8byte 0x0 (.4byte if XLEN=32) .endr
h<N>user_stack_end:
.8byte 0x0
[if !bare: kernel_instr_start/end, kernel_data_start, kernel_stack_start/end]
.section .h<N>page_table,"aw",@progbits   [if paging]
```

## Boot CSR sequence (`pre_enter_privileged_mode`)

1. `la x<tp>, h<hart>kernel_stack_end` — kernel SP.
2. If !no_delegation && init_mode != MACHINE: `li xgpr0, <edeleg>; csrw MEDELEG, xgpr0; li xgpr0, <ideleg>; csrw MIDELEG, xgpr0`.
3. `la xgpr0, h<hart><mode>_handler; ori xgpr0, xgpr0, <mtvec_mode_bit>; csrw MTVEC, xgpr0` (also STVEC, UTVEC).
4. PMP CSRs (pmpcfgN / pmpaddrN).
5. Page table processing — set SATP root.
6. `la xgpr0, h<hart>init; csrw MEPC, xgpr0`.
7. Custom CSR init.
8. Enter privileged mode: set MPP in MSTATUS + MIE bits, write MSTATUS, then `mret`.

`setup_misa()`:
- High bits from XLEN: RV32→2'b01, RV64→2'b10.
- Set per-extension bit per supported_isa (C=2, I=8, M=12, A=0, F=5, D=3, V=21).
- `li xgpr0, 0x<misa>; csrw MISA, xgpr0`.

## GPR init distribution

```
reg_val dist {
  0x00000000                 := 1,    # Zero
  0x80000000                 := 1,    # Sign bit
  [0x1 : 0xF]                := 1,    # Small positive
  [0x10 : 0xEFFF_FFFF]       := 1,    # Mid range
  [0xF000_0000 : 0xFFFF_FFFF] := 1    # Negative range
}
```
Skip SP and TP. Emit `li x<i>, 0x<val>`.

## FP register init

For each f0..f31:
- Single-prec: `li xgpr0, <rand32>; fmv.w.x f<i>, xgpr0`.
- Double-prec: upper/lower halves with shifts then `fmv.d.x f<i>, xgpr2`.
Then `fsrmi <fcsr_rm>`.

## Trap handler (DIRECT mode)

```
<mode>_handler:
  push_gpr_to_kernel_stack(STATUS, SCRATCH, mstatus_mprv, sp, tp, instr)
  csrr xgpr0, xCause
  srli xgpr0, xgpr0, XLEN-1
  bne  xgpr0, x0, <mode>_intr_handler

<mode>_exception_handler:
  csrr xgpr0, xCAUSE
  li xgpr1, BREAKPOINT
  beq xgpr0, xgpr1, ebreak_handler
  li xgpr1, ECALL_UMODE / ECALL_SMODE / ECALL_MMODE
  beq xgpr0, xgpr1, ecall_handler
  ... 
  li xgpr1, ILLEGAL_INSTRUCTION
  beq xgpr0, xgpr1, illegal_instr_handler
  la x<scratch>, test_done
  jalr x1, x<scratch>, 0
```

VECTORED mode: a 16-slot jump table starting at `<mode>_handler`. Slot 0 = exception handler, slots 1..15 = `<mode>_intr_vector_1..15` which each push GPRs, signal `HANDLING_IRQ`, then branch to `<mode>_intr_handler` or `test_done`.

`ebreak_handler` / `illegal_instr_handler`: `csrr xgpr0, MEPC; addi xgpr0, xgpr0, 4; csrw MEPC, xgpr0; pop_gpr_from_kernel_stack; mret`.

`ecall_handler`: `dump_perf_stats` (write all performance CSRs via WRITE_CSR signature), `gen_register_dump` (sd/sw x0..x31 to `_start`), `la x<scratch>, write_tohost; jalr x0, x<scratch>, 0`.

## Main program composition

```
main_program[hart].instr_cnt = cfg.main_program_instr_cnt
main_program[hart].label_name = "main"  (or "h<N>_main" for multi-hart)
generate_directed_instr_stream(hart, "main", instr_cnt, min_insert_cnt=1, main_program[hart].directed_instr)
DV_CHECK_RANDOMIZE_FATAL(main_program[hart])
main_program[hart].gen_instr(is_main=1, no_branch=cfg.no_branch_jump)
gen_callstack(main_program[hart], sub_program[hart], sub_program_name, cfg.num_of_sub_program)
main_program[hart].post_process_instr()
main_program[hart].generate_instr_stream()
instr_stream += main_program[hart].instr_string_list
instr_stream += [<indent>la x<scratch>, test_done, <indent>jalr x0, x<scratch>, 0]
```

## Callstack generator (riscv_callstack_gen)

- `program_cnt = num_sub_program + 1`.
- `stack_level[0]=0`; `stack_level[i] ∈ [stack_level[i-1], stack_level[i-1]+1]`, max `max_stack_level`.
- For each level: collect programs at that level + next level, create a pool whose size is `urandom_range(next.size, next.size+1)`, shuffle; distribute pool items to callers.
- Wire `sub_program_id[]` per program; `gen_callstack` then calls `insert_jump_instr(target_label, idx)` on each caller.

## Sub-program stack enter/exit (riscv_instr_sequence)

- `program_stack_len ∈ [cfg.min_stack_len_per_program : cfg.max_stack_len_per_program]`, XLEN/8-aligned.
- `gen_stack_enter_instr` prepends push-stack stream; `gen_stack_exit_instr` appends pop-stack stream.
- `generate_return_routine`: pick random `ra` ≠ reserved/ZERO; emit `addi ra, cfg.ra, <rand_lsb>` then `c.jalr ra` / `c.jr ra` / `jalr ra, ra, 0`.

## insert_instr_stream algorithm

```
idx = -1 means random pick:
  idx = urandom_range(0, current_instr_cnt-1)
  for _ in 10: if not atomic then break; else repick
  if still atomic: scan for first non-atomic
if replace: inherit label from instr_list[idx], replace slice; else insert at idx
```

## post_process_instr (branch target resolution)

- Walk all instr_list: assign `idx` = running counter; if has_label & not atomic, maybe mark `is_illegal_instr` per `illegal_instr_pct` (special compressed handling — only flip if next instr also compressed, else only flip full 4-byte), assign `label = "<label_idx>"`, `is_local_numeric_label=1`, bump label_idx.
- Branch targets: array `branch_idx[30]` each ∈ [1, cfg.max_branch_step].
- For each BRANCH instruction with `!branch_assigned && !is_illegal_instr`:
  - `target = instr.idx + branch_idx[branch_cnt]`, clamp to `label_idx-1`.
  - `imm_str = "<target>f"` (forward-ref).
  - Compute byte offset by summing per-instr sizes (2 or 4) from i+1 until label matches.
  - `branch_target[target] = 1`; `branch_cnt = (branch_cnt+1) % branch_idx.size`.
- Remove labels not used as branch targets.

## generate_instr_stream (final string)

```
for i in 0..instr_list.size-1:
  if i==0: prefix = format_string("<label_name>:", 18)      # "main:             "
  elif instr_list[i].has_label: prefix = format_string("<instr.label>:", 18)
  else: prefix = 18 spaces
  str = prefix + instr_list[i].convert2asm()
  instr_string_list.push_back(str)
insert_illegal_hint_instr()
```

Labels used: `_start`, `h<N>_start`, `init`, `main`, `test_done`, `h<N>user_stack_start/end`, `h<N>kernel_sp`, `h<N>kernel_instr_start/end`, `h<N>kernel_data_start`, `h<N>kernel_stack_start/end`, `h<N>mtvec_handler`, `h<N>mmode_exception_handler`, `h<N>mmode_intr_handler`, `h<N>ecall_handler`, `h<N>ebreak_handler`, `h<N>illegal_instr_handler`, `h<N>instr_fault_handler`, `h<N>load_fault_handler`, `h<N>store_fault_handler`, `h<N>pt_fault_handler`, `write_tohost`, `_exit`, `h<N>_instr_end`.

## gen_test_done

```
test_done:
                li gp, 1
                ecall                    # or "j write_tohost" if bare_program_mode
```

## Signature emitters (from riscv_signature_pkg)

CORE_STATUS:
```
li xgpr1, <signature_addr>
li xgpr0, <core_status>
slli xgpr0, xgpr0, 8
addi xgpr0, xgpr0, 0x00      # CORE_STATUS tag
sw xgpr0, 0(xgpr1)
```
TEST_RESULT: same but `0x01` tag and result value.
WRITE_GPR: write tag `0x02`, then 32 stores of x0..x31.
WRITE_CSR: `[bits 19:8]=csr_addr, [7:0]=0x03`, store, then `csrr xgpr0, <csr>; sw xgpr0, 0(xgpr1)`.

## Register usage policy

- Reserved always: tp (kernel SP), sp (user SP), scratch_reg, ZERO, RA, GP (test-done signal via `li gp, 1`).
- `cfg.reserved_regs = {tp, sp, scratch_reg}` (post_randomize).
- `cfg.gpr[0..3]` — used inline in hardcoded routines.
- `cfg.pmp_reg[0..1]` — PMP exception helpers.
- `cfg.ra` — dist `{RA:=3, T1:=2, [SP:T0]:=1, [T2:T6]:=4}`.
