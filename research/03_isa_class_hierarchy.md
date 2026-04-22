# Research Note 03 — src/isa/ instruction class hierarchy

Source: `src/isa/*.sv` (`riscv_instr.sv` base + per-extension subclasses).

## Class tree

```
riscv_instr (base, uvm_object)
├── riscv_compressed_instr (RV32C/RV64C/RV128C)
├── riscv_floating_point_instr (RV32F/RV64F/RV32D/RV64D)
│   └── riscv_vector_instr (RVV)
├── riscv_amo_instr (RV32A/RV64A)
├── riscv_b_instr (RV32B/RV64B — draft bitmanip)
├── riscv_csr_instr (CSR ops)
├── riscv_zba_instr / riscv_zbb_instr / riscv_zbc_instr / riscv_zbs_instr
└── riscv_custom_instr (user extensions)
```

Base integer (RV32I/RV64I) instructions use `riscv_instr` directly via `DEFINE_INSTR`.

## riscv_instr base class

### Static registry (elaboration-time)
- `instr_registry[riscv_instr_name_t]` — bool per known opcode.
- `instr_template[name]` — cached singleton instance.
- `instr_names[$]` — filtered flat list post-`create_instr_list(cfg)`.
- `instr_group[group_t][$]` and `instr_category[category_t][$]` — filtered groupings.
- Static `register(name)` called at class definition via INSTR_BODY macro.

### `create_instr_list(cfg)`
Enumerates the registry, calls UVM factory to instantiate each class by name, applies filters:
- ISA extension ∈ `cfg.supported_isa`.
- Not in `unsupported_instr[]`.
- Respects `cfg.disable_compressed_instr`, `cfg.enable_floating_point`, `cfg.enable_vector_extension`.
- Respects `cfg.reserved_regs` (e.g. skip C_ADDI16SP if SP reserved).
- Ensures EBREAK/ECALL/WFI/DRET/FENCE/SFENCE.VMA only appear when enabled.
- Fills `instr_names`, `instr_group`, `instr_category`, and `instr_template`.

### Factories
- `get_instr(name)` — shallow copy of template singleton.
- `get_rand_instr(include/exclude_instr/category/group)` — random filtered pick.
- `get_load_store_instr(...)` — specialized for memory ops; honors `unsupported_instr`.

### Operand fields
```
rand riscv_reg_t rd, rs1, rs2;
rand bit[11:0] csr;
rand bit[31:0] imm;
bit has_rd, has_rs1, has_rs2, has_imm = 1;  // toggled per format
bit is_branch_target, has_label=1, is_compressed, is_illegal_instr, is_floating_point;
int idx = -1;
string comment;
bit [31:0] imm_mask = ~0;
string imm_str;
```

### set_rand_mode() — per format
- R: `has_imm=0`.
- I: `has_rs2=0`.
- S, B: `has_rd=0`.
- U, J: `has_rs1=has_rs2=0`.

### set_imm_len()
- U, J → 20 bits.
- I, S, B → 12 bits if signed, 5 bits if UIMM (shift amount).
- `imm_mask = ~0 << imm_len`.

### imm_c constraint
- SLLIW/SRLIW/SRAIW → `imm[11:5]==0` (5-bit shamt).
- SLLI/SRLI/SRAI → RV32 shamt 5 bits, RV64 shamt 6 bits.

### post_randomize()
1. `extend_imm()` — sign-extend to 32b using `imm_mask` for signed, not for U/UIMM/NZUIMM.
2. `update_imm_str()` — build canonical decimal/hex string.

### Encoding — `get_opcode()` bits[6:0]
`LUI=0110111, AUIPC=0010111, JAL=1101111, JALR=1100111, BRANCH=1100011, LOAD=0000011, STORE=0100011, OP-IMM=0010011, OP=0110011, FENCE=0001111, SYSTEM=1110011, (RV64)OP-IMM-32=0011011, OP-32=0111011, FP-LOAD=0000111, FP-STORE=0100111, FMADD_S=1000011, FMSUB_S=1000111, FNMSUB_S=1001011, FNMADD_S=1001111, OP-FP=1010011, AMO=0101111, OP-V=1010111`.

### Binary layout per format
- J: `{imm[20], imm[10:1], imm[11], imm[19:12], rd, opcode}`.
- U: `{imm[31:12], rd, opcode}`.
- I: `{imm[11:0], rs1, func3, rd, opcode}`.
- S: `{imm[11:5], rs2, rs1, func3, imm[4:0], opcode}`.
- B: `{imm[12], imm[10:5], rs2, rs1, func3, imm[4:1], imm[11], opcode}`.
- R: `{func7, rs2, rs1, func3, rd, opcode}`.
- R4 (FP FMA): `{rs3, fmt[1:0], rs2, rs1, func3/rm, rd, opcode}`.

### convert2asm()
- LABEL column = `LABEL_STR_LEN` (18 spaces).
- Mnemonic column width = `MAX_INSTR_STR_LEN` (13, padded).
- Load: `<instr> rd, imm(rs1)`.
- Store: `<instr> rs2, imm(rs1)`.
- Branch: `<instr> rs1, rs2, imm`.
- Appends `# <comment>` if present.
- Output lower-cased.

## riscv_compressed_instr

### Extra fields / flags
- `is_compressed = 1`.
- `imm_align` — alignment shift count (1/2/3 bytes).

### Key constraints
- `rvc_csr_c`: CIW/CL/CS/CB/CA formats restrict rd/rs1/rs2 to x8..x15 (S0..A5); C_ADDI16SP → rd==SP; C_JR/C_JALR → rs2==ZERO, rs1!=ZERO.
- `imm_val_c`: NZIMM/NZUIMM lower 6 bits ≠ 0; C_LUI imm[31:5]==0; C_SRAI/C_SRLI/C_SLLI imm[31:5]==0; C_ADDI4SPN imm[1:0]==0.
- `no_hint_illegal_instr_c`: rd!=ZERO for C_ADDI/C_ADDIW/C_LI/C_LUI/C_SLLI/C_LWSP; C_JR rs1!=ZERO; C_ADD/C_MV rs2!=ZERO; C_LUI rd!=SP.

### set_imm_len override
- CI/CSS → 6, CL/CS → 5, CJ → 11, CB(ANDI)→6, CB(other)→7.
- Memory: C_SD/LD/LDSP/SDSP → align=3; C_SW/LW/LWSP/SWSP/ADDI4SPN → align=2; else 1.

### extend_imm override
- `imm <<= imm_align` after super.extend_imm (except C_LUI which already has shifted interpretation).

### get_c_opcode [1:0]
- 00: C_ADDI4SPN/C_LW/C_LD/C_LQ/C_SW/C_SD/C_SQ.
- 01: C_NOP..C_BNEZ.
- 10: C_SLLI..C_SDSP.

## riscv_floating_point_instr

### Extra fields
- `rand riscv_fpr_t fs1, fs2, fs3, fd; rand f_rounding_mode_t rm; rand bit use_rounding_mode_from_instr; bit has_fs1=fs2=fd=1, has_fs3=0`.

### set_rand_mode()
- Zeros all int-operand flags, enables FP flags per format.
- I_FORMAT + category==LOAD → has_imm=has_rs1=1 (for FLW/FLD address).
- FMV_X_*/FCVT_W_*/FCVT_L_* (FP→int): has_rd=1, has_fd=0.
- FMV_W_*/FCVT_S_*/FCVT_D_* (int→FP): has_rs1=1, has_fs1=0.
- R4_FORMAT → has_fs3=1.

### convert2asm
- LOAD: `<i> fd, imm(rs1)`; STORE: `<i> fs2, imm(rs1)`.
- FP→int ops: `<i> rd, fs1`; int→FP: `<i> fd, rs1`.
- R_FORMAT COMPARE: `<i> rd, fs1, fs2`; FCLASS: `<i> rd, fs1`.
- R_FORMAT ARITHMETIC binary: `<i> fd, fs1, fs2`.
- R4_FORMAT FMA: `<i> fd, fs1, fs2, fs3`.
- Appends `, <rm>` if ARITHMETIC and `use_rounding_mode_from_instr`; skip for FMIN/FMAX/FMV/FCLASS/FSGNJ variants.

### rvfc_csr_c
- CL/CS/CI/CSS formats (compressed FP): rs1∈[S0:A5]; fs2∈[FS0:FS1]; fd∈[FA0:FA5] (3-bit enc).

### check_hazard_condition(pre_instr)
- RAW if any of fs1/fs2/fs3 == pre.fd.
- WAW if fd == pre.fd.
- WAR if fd ∈ {pre.fs1, pre.fs2, pre.fs3}.

## riscv_vector_instr : riscv_floating_point_instr

### Extra fields
- `rand riscv_vreg_t vs1, vs2, vs3, vd; rand va_variant_t va_variant; rand bit vm, wd; rand bit[10:0] eew; rand bit[3:0] emul;` with has_vs1/2/3/d/vm flags.
- `is_widening_instr, is_narrowing_instr, is_convert_instr`.
- `allowed_va_variants[$]` per instruction.

### Constraints
- `operand_group_c` — if vlmul>0, all vd/vs* aligned to vlmul.
- `widening_instr_c` — vd aligned to 2*vlmul, vs1/vs2 not overlapping widened vd range, if masked vd!=0; WV/WX → vs2 also aligned to 2*vlmul.
- `narrowing_instr_c` — vs2 aligned to 2*vlmul, vd not overlapping.
- `vector_mask_enable_c` — VMERGE/VFMERGE/VADC/VSBC → vm==0 (implicit v0 mask).
- `vector_mask_disable_c` — VMV/VFMV/VCOMPRESS/VFMV_F_S/VFMV_S_F/VMV_X_S/VMV_S_X → vm==1 (vm==0 is reserved).

### set_rand_mode
- Detects prefix: `VW*`/`VFW*` → widening; `VN*`/`VFN*` → narrowing; `*CVT*` → convert.
- VA_FORMAT may set has_imm=has_rs1=has_fs1=1 (for VI/VX/VF variants).

### convert2asm per format
- VA_FORMAT: `<name>.<va_variant> vd, vs2, <VV→vs1|VI→imm|VX→rs1|VF→fs1>`; VMV is special: VV→`vmv.v.v vd, vs1`, VX→`vmv.v.x vd, rs1`, VI→`vmv.v.i vd, imm`.
- VL: `<name> vd, (rs1)`; VS: `<name> vs3, (rs1)`.
- VLX: `<name> vd, (rs1), vs2`; VLS: `<name> vd, (rs1), rs2`.
- Append `, v0.t` suffix when masked (`vm==0`).

## riscv_amo_instr

- Extra: `rand bit aq, rl` with constraint `(aq && rl)==0`.
- `get_instr_name()`: for RV32A append `.w`, RV64A `.d`, then `.aq`/`.rl` suffix.
- convert2asm: LR_W/LR_D → `<i> rd, (rs1)`; else → `<i> rd, rs2, (rs1)`.

## riscv_b_instr

- Extra `rand riscv_reg_t rs3` + `has_rs3` flag.
- set_rand_mode: R_FORMAT unary ops (BMATFLIP, CRC32_*) → has_rs2=0; R4_FORMAT → has_imm=0, has_rs3=1; I_FORMAT FSRI/FSRIW → has_rs3=1.
- Encoding: R4 uses `{rs3, func2, rs2, rs1, func3, rd, opcode}`.

## riscv_csr_instr

- Extra `rand bit write_csr` + static class-level lists `exclude_reg[$], include_reg[$], include_write_reg[$]`, `allow_ro_write`.
- `csr_addr_c`: csr ∈ include_reg, csr ∉ exclude_reg.
- `write_csr_c`: allow write only if (csr[11:10]==11 && allow_ro_write) OR (include_write_reg non-empty && csr ∈ include_write_reg) OR (csr[11:10]!=11 && include_write_reg empty).
- `csr_csrrw`: CSRRW/CSRRWI → write_csr=1. 
- `csr_csrrsc`: CSRRS/CSRRC → write_csr=1 OR rs1==x0.
- Solve order: csr → write_csr → rs1,imm.

## riscv_zba_instr
- SLLI_UW → imm_len = $clog2(XLEN); others → $clog2(XLEN) - 1.

## riscv_zbb_instr
- set_rand_mode: I_FORMAT unary (CLZ, CLZW, CTZ, CTZW, CPOP, CPOPW, ORC_B, SEXT_B, SEXT_H, REV8) → has_imm=0; ZEXT_H (R_FORMAT) → has_rs2=0.

## riscv_zbc_instr — simple R_FORMAT with func7=0000101.

## riscv_zbs_instr
- BCLRI/BEXTI/BINVI/BSETI I_FORMAT → imm_len = $clog2(XLEN).

## Pseudo instructions (`riscv_pseudo_instr.sv`)
- Enum: `LI, LA`.
- Expansion deferred to assembler (we emit `li rd, imm` / `la rd, label`).

## Illegal instruction generator (`riscv_illegal_instr.sv`)
- Parameterizes: use reserved opcodes, reserved func bits, HINT encodings, privileged in U-mode, compressed illegal.
- Bucket distribution: random opcode / invalid CSR / invalid privileged / invalid func / illegal C encoding.
- Produces `.4byte 0x<hex>` or `.2byte 0x<hex>` directives when the assembler wouldn't accept the raw instruction.

## Extension register register-count / operand cheat-sheet
- Integer: 32× GPR x0..x31.
- FP: 32× FPR f0..f31.
- Vector: 32× vreg v0..v31 (v0 can act as mask).

## Reusable insight
Each class must supply:
1. field list (with `has_*` flags),
2. randomization constraints,
3. `set_rand_mode()` and `set_imm_len()` overrides,
4. `convert2asm()`,
5. encoding helpers `get_opcode()`, `get_func3()`, `get_func7()` (and `get_c_opcode()` for RVC).
