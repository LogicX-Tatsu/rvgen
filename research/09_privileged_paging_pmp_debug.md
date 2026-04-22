# Research Note 09 — privileged common seq, paging, PMP, debug ROM

## riscv_privileged_common_seq.sv

### Entry: enter_privileged_mode(mode, out instrs)
- Emits label `init_<mode_name>:`.
- setup_mmode_reg / setup_smode_reg / setup_umode_reg — populate register objects with bit-field sets.
- If SATP_MODE != BARE: setup_satp.
- `gen_csr_instr(regs[], instrs)` emits `li xgpr0, 0x<val>; csrw 0x<addr>, xgpr0 # <CSR_NAME>` for each reg.
- Trailing `mret` for transition.

### setup_mmode_reg fields
```
mstatus.MPRV = cfg.mstatus_mprv
mstatus.MXR = cfg.mstatus_mxr
mstatus.SUM = cfg.mstatus_sum
mstatus.TVM = cfg.mstatus_tvm
mstatus.TW = cfg.set_mstatus_tw
mstatus.FS = cfg.mstatus_fs
mstatus.VS = cfg.mstatus_vs
mstatus.SXL = 0b10 (RV64); UXL = 0b10 (RV64); XS=SD=UIE=0
mstatus.MPP = mode   ← drives MRET target
mstatus.SPP = 0
mstatus.MPIE = enable_interrupt & mstatus_mie (only when mode==MACHINE)
mstatus.MIE = 0      ← cleared; reenabled via MPIE on mret
mstatus.SPIE = enable_interrupt
mstatus.SIE = enable_interrupt
mstatus.UPIE = enable_interrupt

mie.UEIE/SEIE/MEIE = enable_interrupt
mie.USIE/SSIE/MSIE = enable_interrupt
mie.MTIE/STIE/UTIE = enable_interrupt & enable_timer_irq
```

### setup_satp
```
if SATP_MODE == BARE: skip
la xgpr0, page_table_0
srli xgpr0, xgpr0, 12              # extract PPN
and xgpr0, xgpr0, xgpr1            # mask PPN bits
[or in MODE/ASID fields]
csrs 0x<SATP>, xgpr0
```

## riscv_privil_reg.sv — CSR field table

Per-CSR setup via `add_field(name, bit_width, access_type)` with `access_type ∈ {WARL, WLRL, WPRI}`.

### MISA
- `WARL0`(26): extension A–Z bits. `WLRL`(XLEN-28): reserved. `MXL`(2).

### MSTATUS
- UIE(1,WARL), SIE(1,WARL), WPRI0(1), MIE(1,WARL), UPIE(1), SPIE(1), WPRI1(1), MPIE(1), SPP(1,WLRL), VS(2,WARL), MPP(2,WLRL), FS(2,WARL), XS(2,WARL), MPRV(1,WARL), SUM(1,WARL), MXR(1,WARL), TVM(1,WARL), TW(1,WARL), TSR(1,WARL); RV64: UXL(2), SXL(2), SD(1).

### MTVEC
- MODE(2,WARL), BASE(XLEN-2,WARL).

### MEDELEG bits (16 defined)
0 IAM, 1 IAF, 2 ILLEGAL, 3 BREAK, 4 LAM, 5 LAF, 6 SAM, 7 SAF, 8 ECALL_U, 9 ECALL_S, 11 ECALL_M, 12 IPF, 13 LPF, 15 SPF.

### MIDELEG bits
0 USIP, 1 SSIP, 3 MSIP, 4 UTIP, 5 STIP, 7 MTIP, 8 UEIP, 9 SEIP, 11 MEIP.

### SATP
- RV32: PPN(22), ASID(9), MODE(1).
- RV64: PPN(44), ASID(16), MODE(4).

### PMPCFG
- RV32: PMP0CFG..PMP3CFG (8 bits each); cfg byte = `[L:6:A(2):X:W:R]` (L bit7; X/W/R bits 6,5,4; A bits 3:2).
- RV64: PMP0CFG..PMP7CFG (8 bits each).

### PMPADDR
- RV32: 32 bits (bits [33:2] of address).
- RV64: 54 bits of address (bits [55:2]) + 10 WARL bits.

## Page tables (riscv_page_table*.sv)

### PTE field widths per mode
```
SV32: PPN0 10, PPN1 12, PPN2 1 (rsvd), PPN3 1, rsvd 1, VADDR 31
SV39: PPN0 9, PPN1 9, PPN2 26, PPN3 1, rsvd 10, VADDR 38
SV48: PPN0 9, PPN1 9, PPN2 9, PPN3 9, rsvd 10, VADDR 48
```

### PTE bit layout
- [0] v, [3:1] xwr, [4] u, [5] g, [6] a, [7] d, [9:8] rsw, then PPN fields at [10+].
- Pack order (SV32): `{ppn1, ppn0, rsw, d, a, g, u, xwr, v}`.
- Pack order (SV39): `{rsvd, ppn2, ppn1, ppn0, rsw, d, a, g, u, xwr, v}`.
- Pack order (SV48): `{rsvd, ppn3, ppn2, ppn1, ppn0, rsw, d, a, g, u, xwr, v}`.

### Constraints
- `access_dirty_bit_c`: soft a=1, soft d=1.
- `reserved_bits_c`: soft rsw=0, soft rsvd=0.
- `sw_legal_c`: xwr==NEXT_LEVEL → u=a=d=0.

### riscv_page_table topology
```
PteSize = XLEN/8; PteCnt = 4096/PteSize = 512 (RV64) or 1024 (RV32)
PageLevel = SV32:2, SV39:3, SV48:4
LinkPtePerTable = 2; SuperLeafPtePerTable = 2
num_of_page_table[i] = LinkPtePerTable ^ (PageLevel - i - 1)
  SV39: [1, 2, 4] — 7 tables; SV48: [1, 2, 4, 8] — 15 tables
```

### Assembly for tables
```
.align 12
page_table_<N>:
  .dword 0x<pte_0>, 0x<pte_1>, ...     # 8 per line RV64 (.word RV32)
```

### Page table linking (process_page_table)
For each non-leaf table, walk its link PTEs and OR in child-table PPN: `la x<gpr1>, page_table_<i>; for each link-PTE j: load, add child ppn, store`.

If supervisor mode enabled: walk leaf PTEs covering kernel code, clear U bit so user cannot execute kernel.

### Exception injection (riscv_page_table_exception_cfg)
Flags (each randomized per ratio 5–10%):
- `allow_page_access_control_exception` — randomize xwr to illegal combo.
- `allow_superpage_misaligned_exception` — randomize PPN at level>0.
- `allow_leaf_link_page_exception` — set xwr=NEXT_LEVEL at level 0.
- `allow_invalid_page_exception` — clear v.
- `allow_privileged_mode_exception` — flip u.
- `allow_zero_access_bit_exception` — clear a.
- `allow_zero_dirty_bit_exception` — clear d.

### gen_page_fault_handling_routine
Walks tables from root to leaf, reads MTVAL as faulting vaddr, converts to PPN, iteratively resolves:
```
csrr x<fault_vaddr>, MTVAL
srli x<fault_vaddr>, x<fault_vaddr>, 12
slli x<fault_vaddr>, x<fault_vaddr>, VADDR_SPARE+12
la x<pte_addr>, page_table_0
fix_pte:
  srli x<tmp>, x<fault_vaddr>, XLEN-VPN_WIDTH
  slli x<tmp>, x<tmp>, 3
  ld x<pte>, 0(x<pte_addr>)
  [check link vs leaf]
  [if link, descend]
fix_leaf_pte:
  and x<pte>, x<pte>, x<mask>
  li x<tmp>, <valid_leaf_pte_bits>
  or x<pte>, x<pte>, x<tmp>
  sd x<pte>, 0(x<pte_addr>)
  sfence.vma
```

## PMP (riscv_pmp_cfg.sv)

### Fields
- `pmp_num_regions` default 1 (1..16).
- `pmp_granularity` (G). grain = 2^(G+2) bytes.
- `cfg_per_csr = 4 (RV32) or 8 (RV64)`.
- `pmp_randomize, pmp_allow_illegal_tor, enable_pmp_exception_handler=1, suppress_pmp_setup, enable_write_pmp_csr`.
- `pmp_cfg[]`: per-region struct (L, A, X, W, R, addr, offset, addr_mode).
- `mseccfg = {rlb=1, mmwp=0, mml=0}` (ePMP default).

### Constraints
- `xwr_c`: `!mml & w & !r` is illegal (W without R).
- `TOR`: if a==TOR and addr_mode>0: `pmp_cfg[i].addr > pmp_cfg[i-1].addr`.
- `NAPOT`: `pmp_cfg[i].addr & ((1<<addr_mode)-1) == ((1<<addr_mode)-1)` with preceding bit [addr_mode] == 0.

### pmpaddr packing
```
format_addr(addr):
  shifted = addr >> 2
  RV32: return shifted              # 32 bits
  RV64: return {10'b0, shifted[XLEN-11:0]}   # 54 bits
```

Granularity G field in CSR controls min match size = 2^(G+2) bytes.

## Debug ROM (riscv_debug_rom_gen.sv)

### Fields
- `debug_main[$]`, `debug_end[$]`, `str[$]`, `dret`.

### gen_program()
No debug section: `debug_main = {dret}`.

With debug section:
1. push_gpr_to_kernel_stack.
2. Signal CORE_STATUS IN_DEBUG_MODE.
3. If `set_dcsr_ebreak`: gen_dcsr_ebreak (set ebreak(m/s/u) in DCSR).
4. If `enable_debug_single_step`: gen_single_step_logic (DSCRATCH0 counter, DCSR.step bit).
5. gen_dpc_update (bump DPC by 4 if DCSR.cause == ebreak).
6. Signal WRITE_CSR DCSR.
7. If `enable_ebreak_in_debug_rom || set_dcsr_ebreak`: gen_increment_ebreak_counter.
8. Generate random debug sub-program body.
9. pop_gpr_from_kernel_stack.
10. append `dret`.

### DCSR fields
```
[31:28] XDEBUGVER=4
[15] ebreakm, [13] ebreaks, [12] ebreaku
[10] stepie, [9] stopcount, [8] stoptime
[7:6] cause (1=ebreak, 4=step, 5=haltreq)
[3] step
[2:1] prv
```

### Single-step logic (DSCRATCH0 counter, DCSR.step bit)
```
csrw DSCRATCH1, x<scratch>   ; save
csrr x<scratch>, DCSR
andi x<scratch>, x<scratch>, 4
beqz x<scratch>, 1f
  csrr x<scratch>, DSCRATCH0
  bgtz x<scratch>, 2f
    csrc DCSR, 0x4          ; clear step
    j 3f
1:
  csrs DCSR, 0x4            ; set step
  li x<scratch>, <iterations>
  csrw DSCRATCH0, x<scratch>
  j 3f
2:
  csrr x<scratch>, DSCRATCH0
  addi x<scratch>, x<scratch>, -1
  csrw DSCRATCH0, x<scratch>
3: csrr x<scratch>, DSCRATCH1   ; restore
```

### Ebreak header/footer
Header detects re-entry via DSCRATCH0 counter (prevents infinite loop); footer resets counter, writes DCSR+DPC to signature, restores scratch, `dret`.
