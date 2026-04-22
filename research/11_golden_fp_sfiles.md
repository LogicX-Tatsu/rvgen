# Research Note 11 — golden `.S` format (FP test examples, 2026-04-21)

Reference: `/home/qamar/Desktop/verif_env_tatsu/riscv-dv/2026-04-21/riscv_floating_point_arithmetic_test/asm_test/*.S` (100 files).

## Directory layout (per-test run)
```
<run_date>/<test_name>/
  asm_test/
    <test>_0.S .o .bin
    <test>_1.S .o .bin
    ... up to <test>_99
  compile.log
  seed.yaml
  sim_<test>_0.log, ...
  spike_sim/
  vcs_simv, vcs_simv.daidir/
```

## Invariant skeleton (all 100 files)

```
.include "user_define.h"
.globl _start
.section .text
.option norvc;
_start:           <dispatch>
  csrr x5, 0xf14
  li x6, 0
  beq x5, x6, 0f
  ...
0: la x<temp>, h0_start
   jalr x0, x<temp>, 0

h0_start:
  li  x<temp>, 0x40000120
  csrw 0x301, x<temp>           # MIDELEG / MISA
  [kernel_sp setup]
  [trap_vec_init: la, ori <mtvec_mode_bit>, csrw MTVEC]
  [mepc_setup: la, csrw MEPC]
  [custom_csr_setup: nop]
  [init_machine_mode: MSTATUS, MIE setup, mret]

init:             <— label col = 18 chars
                  li x<temp>, <rand32>
                  fmv.w.x f0, x<temp>
                  li x<temp>, <rand32>
                  fmv.w.x f1, x<temp>
                  ... (32 repeats for f0..f31)
                  fsrmi <0-4>
                  li x0, 0x0
                  li x1, <rand32>
                  li x2, 0x80000000
                  ...
                  la x<sp>, user_stack_end

main:             [~5000 random FP/int/CSR instructions with rounding modes]

test_done:        <— 18-char label col
                  li gp, 1
                  ecall

write_tohost:     sw gp, tohost, t5
_exit:            j write_tohost
instr_end:        nop

.section .data
.align 6; .global tohost; tohost: .dword 0;
.align 6; .global fromhost; fromhost: .dword 0;

.section .user_stack,"aw",@progbits;
.align 2
user_stack_start:
.rept 1999
.4byte 0x0
.endr
user_stack_end:
.4byte 0x0

mtvec_handler:    .option norvc;
                  j mmode_exception_handler
                  j mmode_intr_vector_1
                  j mmode_intr_vector_2
                  ...
                  j mmode_intr_vector_15

mmode_intr_vector_1..15: [push, signal HANDLING_IRQ, dispatch]
mmode_exception_handler: [dispatch MCAUSE]
mmode_intr_handler: [reads MSTATUS, MIE, MIP; clears MIP]
ebreak_handler, ecall_handler, instr_fault_handler, load_fault_handler,
store_fault_handler, pt_fault_handler, illegal_instr_handler: …

.section .kernel_stack,"aw",@progbits;
.align 2
kernel_stack_start:
.rept 127
.4byte 0x0
.endr
kernel_stack_end:
.4byte 0x0
```

## Exact formatting conventions

- Labels at column 0, followed by `:` and then padding of spaces to reach column 18 (so `main:             ` is 18 chars total).
- Empty label column = 18 spaces.
- Mnemonic starts at column 18.
- Operands typically start after a 6-space gap (column 33 if mnemonic ≤ 5 chars; grows with mnemonic length). Padded to `MAX_INSTR_STR_LEN = 13`.
- Operands separated by `, `.
- Comments introduced by ` # <text>`.
- `li rd, <imm>` used uniformly; assembler expands to lui+addi as needed. Same for `la rd, label`.
- Large immediates printed as decimal (e.g. `li x27, 2147483648`) sometimes; hex (`0xffff...`) other times — both valid.
- Section directives can be multi-statement on one line separated by `;` (`.align 6; .global tohost; tohost: .dword 0;`).
- Stack init: `.rept N` of `.4byte 0x0` then `.endr` then final `.4byte 0x0`.
- FP constants NOT in `.rodata`; loaded via `li xN, <imm>; fmv.w.x fN, xN`.

## Per-test variability

What varies per seed:
- Which register is chosen as temp (`x13`, `x16`, `x27`, `x29`, `x31`…); chosen once per test, reused.
- The 32 random FP immediates feeding fmv.w.x.
- The 31 random integer immediates feeding li x1..x31.
- `fsrmi <0|1|2|3|4>` value.
- MTVEC vectored-mode bit (ori with 1 or 0).
- Main-program instruction mix and operand choices (~4400–5000 instructions per test).
- File length: ~53 tests at ~6200 lines, ~47 at ~5527 lines (variation driven by `li` expansions for big immediates).

What stays invariant:
- Section order, label set, directive shape, stack/kernel layout, trap handler structure, 18-char label column, FP init pattern (32 × li+fmv.w.x then fsrmi), test_done trailer.

## FP operations observed in main
- fadd.s, fsub.s, fmul.s, fdiv.s, fmadd.s, fmsub.s, fnmadd.s, fnmsub.s.
- fcvt.s.w, fcvt.s.wu, fcvt.w.s, fcvt.wu.s.
- feq.s, fle.s, flt.s.
- fmv.x.w, fmv.w.x.
- fsgnj.s, fsgnjn.s, fsgnjx.s, fmin.s, fmax.s, fsqrt.s, fclass.s.
- Rounding modes suffix: `, rne | , rup | , rdn | , rmm | , rtz` (optional for some ops, skipped for FMIN/FMAX/FMV/FCLASS/FSGNJ*).

## Integer / CSR operations observed
- Full RV32I arithmetic, logical, shifts, slt, lui, auipc, addi, li, la.
- CSR ops: csrr, csrw, csrrs, csrrc, csrrsi, csrrwi, csrrci. Custom CSR 0x340 appears frequently (non-standard simulation register).

## Oddities to preserve

- Empty `custom_csr_setup:` label with a `nop` under it (hook for future use).
- Trailing whitespace in label lines (e.g. `test_done:        ` with spaces padding to col 18).
- `.option norvc;` repeated inside `mtvec_handler` even though global `.option norvc;` already set.
- Blank lines between logical sections preserved.
- MTVEC `ori` bit sometimes 0 (test_99 example) rather than 1.

## Byte-level output requirement

For Phase 1 structural parity:
1. Emit section ordering exactly as above.
2. Emit 18-char label col, 13-char mnemonic col.
3. FP init pattern `li xN, <imm>; fmv.w.x fN, xN` × 32 followed by `fsrmi <rm>`.
4. Integer init `li x0, 0x0` then `li x1..x31, <imm>` (skip reserved).
5. Include kernel and user stack sections with correct `.rept` counts and `.4byte` fills.
6. Generate mtvec_handler jump table when mtvec_mode == VECTORED.
7. Provide write_tohost + _exit + instr_end terminators.
8. Use ABI register names (`a0`, `t0`, `fa0`) not `x10`/`f10`.
