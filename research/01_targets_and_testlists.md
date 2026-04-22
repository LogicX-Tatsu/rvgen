# Research Note 01 — Targets and Testlists

Source: `/home/qamar/Desktop/verif_env_tatsu/riscv-dv/target/` and `yaml/`.
Captured: 2026-04-22.

## Target matrix (XLEN / ISA / privilege / MMU / harts)

| Target | XLEN | Supported ISA | Priv | SATP | HARTS | Notes |
|--------|------|---------------|------|------|-------|-------|
| rv32i | 32 | RV32I | M | BARE | 1 | Base 32-bit |
| rv32ia | 32 | RV32I,RV32A | M | BARE | 1 | Atomic |
| rv32iac | 32 | RV32I,RV32C,RV32A | M | BARE | 1 | Compressed+Atomic |
| rv32ic | 32 | RV32I,RV32C | M | BARE | 1 | Compressed; unaligned LDR/STR |
| rv32if | 32 | RV32I,RV32F | M | BARE | 1 | Partial FP |
| rv32im | 32 | RV32I,RV32M | M | BARE | 1 | MUL/MULH/MULHSU/MULHU unsupported |
| rv32imac | 32 | RV32I,RV32M,RV32A,RV32C | M | BARE | 1 | Full 32-bit MAC |
| rv32imafdc | 32 | RV32I,RV32M,RV32C,RV32F,RV32FC,RV32D,RV32DC,RV32A | M | BARE | 1 | Full FP+compressed FP |
| rv32imc | 32 | RV32I,RV32M,RV32C | M | BARE | 1 | **base testlist anchor** |
| rv32imcb | 32 | RV32I,RV32M,RV32C,RV32B | M | BARE | 1 | Bitmanip |
| rv32imc_sv32 | 32 | RV32I,RV32M,RV32C | M,U | SV32 | 1 | Virtual memory |
| rv64gc | 64 | RV32IM+RV64IM+RV32C+RV64C+RV32A+RV64A+RV32F+RV64F+RV32D+RV64D+RV32X | U,S,M | SV39 | 1 | Full G extension |
| rv64gcv | 64 | (rv64gc minus RV32X)+RVV | M | BARE | 1 | VLEN=512, ELEN=32, MAX_LMUL=8 |
| rv64imafdc | 64 | Same as rv64gc (different name) | U,S,M | SV39 | 1 | |
| rv64imc | 64 | RV32IM+RV64IM+RV32C+RV64C | M | BARE | 1 | 64-bit IMC |
| rv64imcb | 64 | RV32IM+RV32C+RV32B+RV64IM+RV64C+RV64B | M | BARE | 1 | 64-bit Bitmanip |
| ml | 32 | RV32I,RV32M,RV32C,RV32A | M | BARE | 1 | ML focused |
| multi_harts | 32 | RV32I,RV32M,RV32C,RV32A | M | BARE | 2 | Multi-hart sync |

## CSR implementation

M-only targets (rv32i/ic/im/imc/imcb, rv64imc/imcb, ml, multi_harts):
`MVENDORID, MARCHID, MIMPID, MHARTID, MSTATUS, MISA, MIE, MTVEC, MCOUNTEREN, MSCRATCH, MEPC, MCAUSE, MTVAL, MIP`. No custom CSRs.

Privileged targets (rv32ia/iac/if, rv64gc, rv64imafdc): above **plus** user-mode (USTATUS…UIP), supervisor-mode (SSTATUS…SIP, SATP), FP (FCSR on rv64gc/imafdc).

## Interrupts and exceptions

- All targets: DIRECT and VECTORED (max_interrupt_vector_num=16).
- M-only: M_SOFTWARE_INTR, M_TIMER_INTR, M_EXTERNAL_INTR.
- Privileged targets: adds U/S software/timer/external (9 total).

Base exceptions (all): INSTRUCTION_ACCESS_FAULT, ILLEGAL_INSTRUCTION, BREAKPOINT, LOAD_ADDRESS_MISALIGNED, LOAD_ACCESS_FAULT, ECALL_MMODE.
Privileged add: INSTRUCTION_ADDRESS_MISALIGNED, STORE_AMO_ADDRESS_MISALIGNED, STORE_AMO_ACCESS_FAULT, ECALL_UMODE, ECALL_SMODE, INSTRUCTION_PAGE_FAULT, LOAD_PAGE_FAULT, STORE_AMO_PAGE_FAULT.

## Testlist import chain

- rv32ia, rv32iac, rv32if, rv32imafdc, rv32imcb, rv32imc_sv32 → import `rv32imc/testlist.yaml`
- rv64gc, rv64gcv, rv64imafdc → import `rv64imc/testlist.yaml`
- multi_harts → imports base_testlist.yaml + hart-specific tests
- ml → standalone: `riscv_rand_test` only

## Base testlist (14 tests, anchored at rv32imc)

| Test | Key gen_opts | iters |
|------|--------------|-------|
| riscv_arithmetic_basic_test | +instr_cnt=5000 +directed_instr_0=riscv_int_numeric_corner_stream +no_csr_instr=1 +no_fence=1 +no_data_page=1 +no_branch_jump=1 +boot_mode=m | 2 |
| riscv_rand_instr_test | +instr_cnt=2000 +num_of_sub_program=5 directed 1–6 load/store/loop/hazard/jal +no_csr_instr=1 +no_fence=1 | 2 |
| riscv_jump_stress_test | +instr_cnt=5000 +num_of_sub_program=5 +directed_instr_1=riscv_jal_instr,20 +no_csr_instr=1 +no_load_store=1 +no_fence=1 | 2 |
| riscv_loop_test | +instr_cnt=2000 +num_of_sub_program=5 +directed_instr_1=riscv_loop_instr,20 +no_csr_instr=1 +no_fence=1 | 2 |
| riscv_rand_jump_test | +instr_cnt=5000 +num_of_sub_program=10 +directed_instr_0=riscv_load_store_rand_instr_stream,8 +no_csr_instr=1 +no_fence=1 | 2 |
| riscv_mmu_stress_test | +instr_cnt=2000 +num_of_sub_program=5 directed 0,1,3 +no_csr_instr=1 +no_fence=1 | 2 |
| riscv_no_fence_test | +no_fence=1 (gen_test=riscv_rand_instr_test) | 2 |
| riscv_illegal_instr_test | +illegal_instr_ratio=5 (gen_test=riscv_rand_instr_test) | 2 |
| riscv_ebreak_test | +instr_cnt=2000 +no_ebreak=0 (gen_test=riscv_rand_instr_test) | 2 |
| riscv_ebreak_debug_mode_test | +instr_cnt=2000 +no_ebreak=0, sim_opts +enable_debug_seq=1, compare_opts +compare_final_value_only=1 | 2 |
| riscv_full_interrupt_test | +enable_interrupt=1 +enable_timer_irq=1 +no_fence=1, sim_opts +enable_irq_seq=1, compare_opts +compare_final_value_only=1 | 2 |
| riscv_csr_test | gen_test=riscv_csr_test, no_iss=10, no_post_compare=1, rtl_test=core_csr_test | 1 |
| riscv_unaligned_load_store_test | +instr_cnt=2000 +num_of_sub_program=5 directed 0–3 +enable_unaligned_load_store=1 gcc_opts=-mno-strict-align | 1 |
| riscv_amo_test | +no_csr_instr=1 +instr_cnt=5000 +num_of_sub_program=2 +directed_instr_0=riscv_lr_sc_instr_stream,3 +directed_instr_1=riscv_amo_instr_stream,3 +boot_mode=m +no_fence=1 | 2 |

## Target-specific extra tests (selected highlights)

- **rv32i**: `riscv_misaligned_instr_test` (+enable_misaligned_instr=1), disables `riscv_csr_test`.
- **rv32ic**: `riscv_non_compressed_instr_test` (+disable_compressed_instr=1), `riscv_hint_instr_test` (+hint_instr_ratio=5), `riscv_pmp_test` (+pmp_randomize=0 +pmp_num_regions=1 +pmp_granularity=1 +pmp_region_0=L:0,A:TOR,X:1,W:1,R:1,ADDR:FFFFFFFF).
- **rv32ia (also rv32iac/if/imafdc via import chain)**: `riscv_machine_mode_rand_test`, `riscv_privileged_mode_rand_test`, `riscv_invalid_csr_test`, `riscv_page_table_exception_test` (disabled, iters=0), `riscv_sfence_exception_test`, boosted `riscv_amo_test`, **FP tests**: `riscv_floating_point_arithmetic_test`, `riscv_floating_point_rand_test`, `riscv_floating_point_mmu_stress_test`.
- **rv32imcb / rv64imcb**: `riscv_b_ext_test` (+enable_b_extension=1), `riscv_zbb_zbt_test` (+enable_bitmanip_groups=zbb,zbt).
- **rv32imc_sv32**: `riscv_u_mode_rand_test` (+boot_mode=u).
- **rv64gcv**: `riscv_vector_arithmetic_test`, `riscv_vector_arithmetic_stress_test`, `riscv_vector_load_store_test` (directed riscv_vector_load_store_instr_stream,10), `riscv_vector_amo_test` (directed riscv_vector_amo_instr_stream,10).
- **ml**: `riscv_rand_test` with riscv_ml_test (instr_cnt=100000, illegal_instr_ratio=5, hint_instr_ratio=5, 7 stream_name_N knobs, +dist_control_mode=1).
- **multi_harts**: `riscv_load_store_shared_mem_test` (directed riscv_load_store_shared_mem_stream), `riscv_amo_test` with 2 harts, `riscv_single_hart_test` (+num_of_harts=1).

## YAML assets

- **base_testlist.yaml** (7052B): the 14 core tests above.
- **cov_testlist.yaml** (531B): `riscv_instr_cov_test` and experimental twin.
- **csr_template.yaml** (3562B): CSR field template with misa + mwarlexample WARL examples.
- **iss.yaml**: spike (`--log-commits --isa=<variant> --priv=<priv> --misaligned`), ovpsim (OVPsimPlus.exe), sail (`riscv_ocaml_sim_RV<xlen>`), whisper (`WHISPER_ISS` + whisper.json + iccmrw), renode (python wrapper).
- **simulator.yaml**: vcs, ius, questa, dsim, qrun, riviera, xlm, pyflow. Each has compile + simulate command templates.
- **whisper.json**: ICCM region at 0x0 size 0x80000000.

## Extension support matrix

| Target | M | A | C | F | D | B | V |
|--------|---|---|---|---|---|---|---|
| rv32i | - | - | - | - | - | - | - |
| rv32ia | - | Y | - | - | - | - | - |
| rv32iac | - | Y | Y | - | - | - | - |
| rv32ic | - | - | Y | - | - | - | - |
| rv32if | - | - | - | Y* | - | - | - |
| rv32im | Y | - | - | - | - | - | - |
| rv32imac | Y | Y | Y | - | - | - | - |
| rv32imafdc | Y | Y | Y | Y | Y | - | - |
| rv32imc | Y | - | Y | - | - | - | - |
| rv32imcb | Y | - | Y | - | - | Y | - |
| rv32imc_sv32 | Y | - | Y | - | - | - | - |
| rv64gc | Y | Y | Y | Y | Y | - | - |
| rv64gcv | Y | Y | Y | Y | Y | - | Y |
| rv64imafdc | Y | Y | Y | Y | Y | - | - |
| rv64imc | Y | - | Y | - | - | - | - |
| rv64imcb | Y | - | Y | - | - | Y | - |
| ml | Y | Y | Y | - | - | - | - |
| multi_harts | Y | Y | Y | - | - | - | - |

## Common core-setting parameters

- NUM_GPR = 32, NUM_FLOAT_GPR = 32, NUM_VEC_GPR = 32.
- VLEN = 512, ELEN = 32, SELEN = 8, MAX_LMUL = 8 (rv64gcv).
- support_pmp = 0, support_epmp = 0, support_debug_mode = 0 default.
- support_umode_trap = 0 default, support_sfence = 0 except rv64gc/imafdc = 1.
- support_unaligned_load_store = 1 default; 0 for rv32ia, rv32iac, rv32if, rv32imafdc.

## File paths cheat-sheet

- Per-target settings: `target/<name>/riscv_core_setting.sv`.
- Per-target testlist: `target/<name>/testlist.yaml`.
- Shared YAML: `yaml/{base_testlist, cov_testlist, csr_template, iss, simulator, whisper}`.
