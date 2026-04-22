# Research Note 02 — riscv_instr_pkg.sv enums and types

Source: `src/riscv_instr_pkg.sv` (~1600 lines).

## Fixed-width bitfield enums

### `satp_mode_t` [3:0]
`BARE=0, SV32=1, SV39=8, SV48=9, SV57=10, SV64=11`.

### `f_rounding_mode_t` [2:0]
`RNE=0, RTZ=1, RDN=2, RUP=3, RMM=4`.

### `mtvec_mode_t` [1:0]
`DIRECT=0, VECTORED=1`.

### `imm_t` [2:0]
`IMM, UIMM, NZUIMM, NZIMM` (signed, unsigned, nonzero unsigned, nonzero signed).

### `privileged_mode_t` [1:0]
`USER_MODE=0, SUPERVISOR_MODE=1, RESERVED_MODE=2, MACHINE_MODE=3`.

### `privileged_level_t` [1:0]
`U_LEVEL=0, S_LEVEL=1, M_LEVEL=3`.

### `reg_field_access_t` [1:0]
`WPRI, WLRL, WARL`.

### `pte_permission_t` [2:0]
`NEXT_LEVEL_PAGE=000, READ_ONLY_PAGE=001, READ_WRITE_PAGE=011, EXECUTE_ONLY_PAGE=100, READ_EXECUTE_PAGE=101, R_W_EXECUTE_PAGE=111`.

### `interrupt_cause_t` [3:0]
`U_SOFTWARE_INTR=0, S_SOFTWARE_INTR=1, M_SOFTWARE_INTR=3, U_TIMER_INTR=4, S_TIMER_INTR=5, M_TIMER_INTR=7, U_EXTERNAL_INTR=8, S_EXTERNAL_INTR=9, M_EXTERNAL_INTR=B`.

### `exception_cause_t` [3:0]
`INSTRUCTION_ADDRESS_MISALIGNED=0, INSTRUCTION_ACCESS_FAULT=1, ILLEGAL_INSTRUCTION=2, BREAKPOINT=3, LOAD_ADDRESS_MISALIGNED=4, LOAD_ACCESS_FAULT=5, STORE_AMO_ADDRESS_MISALIGNED=6, STORE_AMO_ACCESS_FAULT=7, ECALL_UMODE=8, ECALL_SMODE=9, ECALL_MMODE=B, INSTRUCTION_PAGE_FAULT=C, LOAD_PAGE_FAULT=D, STORE_AMO_PAGE_FAULT=F`.

### `hazard_e` [1:0]
`NO_HAZARD, RAW_HAZARD, WAR_HAZARD, WAW_HAZARD`.

### `pmp_addr_mode_t` [1:0]
`OFF=00, TOR=01, NA4=10, NAPOT=11`.

### `vxrm_t` [1:0]
`RoundToNearestUp, RoundToNearestEven, RoundDown, RoundToOdd`.

### `vreg_init_method_t`
`SAME_VALUES_ALL_ELEMS, RANDOM_VALUES_VMV, RANDOM_VALUES_LOAD`.

### `data_pattern_t` [1:0]
`RAND_DATA=0, ALL_ZERO, INCR_VAL`.

## Register enums

### `riscv_reg_t` [4:0] — GPRs, x0..x31
`ZERO, RA, SP, GP, TP, T0, T1, T2, S0, S1, A0, A1, A2, A3, A4, A5, A6, A7, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, T3, T4, T5, T6`.

### `riscv_fpr_t` [4:0] — FPRs, f0..f31
`FT0..FT7, FS0, FS1, FA0..FA7, FS2..FS11, FT8..FT11`.

### `riscv_vreg_t` [4:0] — V0..V31.

## Instruction grouping

### `riscv_instr_group_t`
Order: `RV32I, RV64I, RV32M, RV64M, RV32A, RV64A, RV32F, RV32FC, RV64F, RV32D, RV32DC, RV64D, RV32C, RV64C, RV128I, RV128C, RVV, RV32B, RV32ZBA, RV32ZBB, RV32ZBC, RV32ZBS, RV64B, RV64ZBA, RV64ZBB, RV64ZBC, RV64ZBS, RV32X, RV64X`.

### `riscv_instr_category_t` [5:0]
Order: `LOAD, STORE, SHIFT, ARITHMETIC, LOGICAL, COMPARE, BRANCH, JUMP, SYNCH, SYSTEM, COUNTER, CSR, CHANGELEVEL, TRAP, INTERRUPT, (vector include), AMO`.

### `riscv_instr_format_t` [5:0]
Order: `J_FORMAT, U_FORMAT, I_FORMAT, B_FORMAT, R_FORMAT, S_FORMAT, R4_FORMAT, CI_FORMAT, CB_FORMAT, CJ_FORMAT, CR_FORMAT, CA_FORMAT, CL_FORMAT, CS_FORMAT, CSS_FORMAT, CIW_FORMAT, VSET_FORMAT, VA_FORMAT, VS2_FORMAT, VL_FORMAT, VS_FORMAT, VLX_FORMAT, VSX_FORMAT, VLS_FORMAT, VSS_FORMAT, VAMO_FORMAT`.

### `va_variant_t` [3:0]
`VV, VI, VX, VF, WV, WI, WX, VVM, VIM, VXM, VFM, VS, VM`.

### `misa_ext_t`
`MISA_EXT_A..MISA_EXT_Z` (26, letters A-Z).

## Instruction name enum (riscv_instr_name_t) — representative families

- **RV32I (47)**: LUI, AUIPC, JAL, JALR, BEQ, BNE, BLT, BGE, BLTU, BGEU, LB, LH, LW, LBU, LHU, SB, SH, SW, ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI, ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND, NOP, FENCE, FENCE_I, ECALL, EBREAK, CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI.
- **RV32M (8)**: MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU.
- **RV64M (5)**: MULW, DIVW, DIVUW, REMW, REMUW.
- **RV32A (11)**: LR_W, SC_W, AMOSWAP_W, AMOADD_W, AMOAND_W, AMOOR_W, AMOXOR_W, AMOMIN_W, AMOMAX_W, AMOMINU_W, AMOMAXU_W.
- **RV64A (11)**: same as RV32A suffix _D.
- **RV32F (22)**: FLW, FSW, FMADD_S, FMSUB_S, FNMSUB_S, FNMADD_S, FADD_S, FSUB_S, FMUL_S, FDIV_S, FSQRT_S, FSGNJ_S, FSGNJN_S, FSGNJX_S, FMIN_S, FMAX_S, FCVT_W_S, FCVT_WU_S, FMV_X_W, FEQ_S, FLT_S, FLE_S, FCLASS_S, FCVT_S_W, FCVT_S_WU, FMV_W_X.
- **RV64F (4)**: FCVT_L_S, FCVT_LU_S, FCVT_S_L, FCVT_S_LU.
- **RV32D (~27)**: Same shape as RV32F with suffix _D; FLD, FSD, FMADD_D..FMV_D_X.
- **RV64D (6)**: FCVT_L_D, FCVT_LU_D, FMV_X_D, FCVT_D_L, FCVT_D_LU, FMV_D_X.
- **RV64I (11)**: LWU, LD, SD, ADDIW, SLLIW, SRLIW, SRAIW, ADDW, SUBW, SLLW, SRLW, SRAW.
- **RV32C (28)**: C_LW, C_SW, C_LWSP, C_SWSP, C_ADDI4SPN, C_ADDI, C_LI, C_ADDI16SP, C_LUI, C_SRLI, C_SRAI, C_ANDI, C_SUB, C_XOR, C_OR, C_AND, C_BEQZ, C_BNEZ, C_SLLI, C_MV, C_EBREAK, C_ADD, C_NOP, C_J, C_JAL, C_JR, C_JALR.
- **RV64C (8)**: C_ADDIW, C_SUBW, C_ADDW, C_LD, C_SD, C_LDSP, C_SDSP.
- **RV32FC/RV32DC (8)**: C_FLW, C_FSW, C_FLWSP, C_FSWSP, C_FLD, C_FSD, C_FLDSP, C_FSDSP.
- **Zba (3)**: SH1ADD, SH2ADD, SH3ADD (+ADD_UW, SH1ADD_UW, SH2ADD_UW, SH3ADD_UW, SLLI_UW on RV64).
- **Zbb (17+)**: ANDN, CLZ, CPOP, CTZ, MAX, MAXU, MIN, MINU, ORC_B, ORN, REV8, ROL, ROR, RORI, SEXT_B, SEXT_H, XNOR, ZEXT_H (plus W-variants on RV64).
- **Zbc (3)**: CLMUL, CLMULH, CLMULR.
- **Zbs (8)**: BCLR, BCLRI, BEXT, BEXTI, BINV, BINVI, BSET, BSETI.
- **RV32B draft (many)**: GORC/GORCI, CMIX, CMOV, PACK/PACKU/PACKH, XPERM_*, SLO, SRO, SLOI, SROI, GREV/GREVI, FSL, FSR, FSRI, CRC32_*, SHFL, UNSHFL, SHFLI, UNSHFLI, BCOMPRESS, BDECOMPRESS, BFP, ADD_UW, SHxADD_UW, SLLI_UW.
- **Vector (~150)**: VSETVL, VSETVLI, VADD/VSUB/VRSUB, VWADD*/VWSUB*, VADC/VMADC/VSBC/VMSBC, VAND/VOR/VXOR, VSLL/VSRL/VSRA, VNSRL/VNSRA, VMS*, VMIN*/VMAX*, VMUL*/VDIV*/VREM*, VWMUL*, VMACC/VNMSAC/VMADD/VNMSUB/VWMACC*, VMERGE/VMV, VSADD/VSSUB (saturating), VAADD/VASUB (averaging), VSSRL/VSSRA, VNCLIP*, VFADD..VFSQRT (FP ops), VFCVT_*, VF*CVT_*_W (narrowing), VRED*, VFRED*, Vmask ops (VMAND_MM..VID_V), permutation (VSLIDE*, VRGATHER, VCOMPRESS, VMV1R..VMV8R), Load/Store (VLE_V, VSE_V, strided, indexed, segmented, fault-first), Vector AMO.
- **Privileged/system (8)**: DRET, MRET, URET, SRET, WFI, SFENCE_VMA.
- **Pseudo (2)**: LI, LA (enum `riscv_pseudo_instr_name_t`).

## Privileged register (CSR) map

- **User mode 0x000..0x044**: USTATUS(000), UIE(004), UTVEC(005), USCRATCH(040), UEPC(041), UCAUSE(042), UTVAL(043), UIP(044).
- **FP CSRs**: FFLAGS(001), FRM(002), FCSR(003).
- **Counters (R/O user)**: CYCLE(C00), TIME(C01), INSTRET(C02), HPMCOUNTER3..31 (C03..C1F). RV32 upper halves at C80..C9F.
- **Supervisor**: SSTATUS(100), SEDELEG(102), SIDELEG(103), SIE(104), STVEC(105), SCOUNTEREN(106), SENVCFG(10A), SSCRATCH(140), SEPC(141), SCAUSE(142), STVAL(143), SIP(144), SATP(180), SCONTEXT(5A8).
- **Hypervisor**: HSTATUS(600), HEDELEG(602), HIDELEG(603), HIE(604), HCOUNTEREN(606), HGEIE(607), HENVCFG(60A/61A), HTVAL(643), HIP(644), HVIP(645), HTINST(64A), HGEIP(E12), HGATP(680), HCONTEXT(6A8), HTIMEDELTA(605/615).
- **Virtual supervisor**: VSSTATUS(200), VSIE(204), VSTVEC(205), VSSCRATCH(240), VSEPC(241), VSCAUSE(242), VSTVAL(243), VSIP(244), VSATP(280).
- **Machine info**: MVENDORID(F11), MARCHID(F12), MIMPID(F13), MHARTID(F14), MCONFIGPTR(F15).
- **Machine trap setup**: MSTATUS(300), MISA(301), MEDELEG(302), MIDELEG(303), MIE(304), MTVEC(305), MCOUNTEREN(306), MSTATUSH(310).
- **Machine trap handling**: MSCRATCH(340), MEPC(341), MCAUSE(342), MTVAL(343), MIP(344).
- **Machine config**: MENVCFG(30A), MENVCFGH(31A), MSECCFG(747), MSECCFGH(757).
- **PMP**: PMPCFG0..15 (3A0..3AF), PMPADDR0..63 (3B0..3EF, 4C0..4DF).
- **Machine counters**: MCYCLE(B00), MINSTRET(B02), MHPMCOUNTER3..31 (B03..B1F), MCOUNTINHIBIT(320), MHPMEVENT3..31 (323..33F).
- **Debug**: TSELECT(7A0), TDATA1..3 (7A1..7A3), TINFO(7A4), TCONTROL(7A5), MCONTEXT(7A8), MSCONTEXT(7AA), DCSR(7B0), DPC(7B1), DSCRATCH0/1(7B2/7B3).
- **Vector**: VSTART(008), VXSTAT(009), VXRM(00A), VL(C20), VTYPE(C21), VLENB(C22).

## Important structs

- `mem_region_t { string name; int unsigned size_in_bytes; bit[2:0] xwr; }`
- `mseccfg_reg_t { rlb, mmwp, mml }` — ePMP security.
- `pmp_cfg_reg_t { rand bit l; bit[1:0] zero; rand pmp_addr_mode_t a; rand bit x, w, r; rand bit[XLEN-1:0] addr, offset; rand int addr_mode; }`
- `vtype_t { bit ill; bit fractional_lmul; reserved; int vediv, vsew, vlmul; }`

## Parameters/constants

- `SINGLE_PRECISION_FRACTION_BITS = 23`.
- `DOUBLE_PRECISION_FRACTION_BITS = 52`.
- `MAX_USED_VADDR_BITS = 30`.
- `IMM25_WIDTH = 25; IMM12_WIDTH = 12; INSTR_WIDTH = 32; DATA_WIDTH = 32`.
- `MAX_INSTR_STR_LEN = 13`.
- `LABEL_STR_LEN = 18` (used for column-aligned label padding; note the golden `.S` files show 18 leading spaces, so the effective output column = 18).
- `MAX_CALLSTACK_DEPTH = 20; MAX_SUB_PROGRAM_CNT = 20; MAX_CALL_PER_FUNC = 5`.
- Status bit masks: `MPRV_BIT_MASK = 1<<17; SUM_BIT_MASK = 1<<18; MPP_BIT_MASK = 3<<11`.
- `riscv_csr_t = bit[11:0]; program_id_t = bit[15:0]`.
- `default_include_csr_write = {MSCRATCH}`.
- `all_gpr = {ZERO, RA, SP, GP, TP, T0..T2, S0, S1, A0..A7, S2..S11, T3..T6}`.
- `compressed_gpr = {S0, S1, A0..A5}` (x8..x15).
- `all_categories = {LOAD, STORE, SHIFT, ARITHMETIC, LOGICAL, COMPARE, BRANCH, JUMP, SYNCH, SYSTEM, COUNTER, CSR, CHANGELEVEL, TRAP, INTERRUPT, AMO}`.

## Helper functions

- `format_string(str, len=10)` — right-pad to `len` spaces.
- `format_data(bytes[], group=4)` — hex string with commas grouping bytes.
- `get_instr_name(str)` → `riscv_instr_name_t` via linear enum scan.
- `push_gpr_to_kernel_stack(status, scratch, mprv, sp, tp, ref instr[$])` — saves user SP; allocates 32*(XLEN/8) bytes; pushes all 32 GPRs (except x0 but the logic writes all). Handles MPRV/physical address translation.
- `pop_gpr_from_kernel_stack(...)` — reverse.
- `get_int_arg_value / get_bool_arg_value / get_hex_arg_value(str, ref val)` — plusarg parsing helpers.
- `hart_prefix(hart=0)` — returns `""` if NUM_HARTS<=1 else `h<hart>_`.
- `get_label(label, hart)` — prepends hart prefix.
- `get_val(str, out val, hex=0)` — parse 0x… or decimal.

## Macros / includes (riscv_defines.svh)

- `DEFINE_INSTR`, `DEFINE_C_INSTR`, `DEFINE_FP_INSTR`, `DEFINE_FC_INSTR`, `DEFINE_AMO_INSTR`, `DEFINE_CSR_INSTR`, `DEFINE_VA_INSTR`, `DEFINE_B_INSTR`, `DEFINE_ZBA/ZBB/ZBC/ZBS_INSTR`, `DEFINE_CUSTOM_INSTR`.
- `INSTR_BODY(instr_n, fmt, category, group, imm_tp=IMM)` expands to a `riscv_<instr>_instr` subclass with `riscv_instr::register(instr_n)` and constructor that sets `instr_name, format, group, category, imm_type` + calls `set_imm_len()` and `set_rand_mode()`.
- `VA_INSTR_BODY(..., vav, ext)` for vector variants.
- `VECTOR_INCLUDE(inc)` — gated on `ifdef ENABLE_VECTORS`.

## Included files chain (from riscv_instr_pkg.sv in order)

`riscv_core_setting.sv` (XLEN, supported_isa, …) → vector_cfg, pmp_cfg, instr_gen_config → isa/riscv_instr.sv, amo_instr, zba/zbb/zbc/zbs, b_instr, csr_instr, floating_point_instr, vector_instr, compressed_instr → rv32a/c/dc/d/fc/f/i/b/zba/zbb/zbc/zbs/m, rv64 equivalents, rv128c, rv32v, custom → pseudo_instr, illegal_instr → reg, privil_reg, page_table_entry/exception_cfg, page_table, page_table_list, privileged_common_seq, callstack_gen, data_page_gen → instr_stream, loop_instr, directed/load_store/amo instr libs → instr_sequence, asm_program_gen, debug_rom_gen, instr_cover_group.
