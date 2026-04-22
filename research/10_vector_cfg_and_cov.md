# Research Note 10 — vector_cfg.sv and cov.py

## riscv_vector_cfg.sv

### Key fields
- `vtype` (struct): `ill, fractional_lmul, reserved[XLEN-2:7], vediv, vsew, vlmul`.
- `vl ∈ [1, VLEN/vsew]` (vector length).
- `vstart ∈ [0, vl]`.
- `vxrm ∈ {RoundToNearestUp, RoundToNearestEven, RoundDown, RoundToOdd}` (fixed-point rounding).
- `vxsat` (saturation flag).
- `legal_eew[$]` — computed set of valid EEWs for current vtype.
- Gates (rand bits): `only_vec_instr`, `vec_fp`, `vec_narrowing_widening`, `vec_quad_widening`, `allow_illegal_vec_instr`, `vec_reg_hazards`, `enable_zvlsseg(1)`, `enable_fault_only_first_load`.
- `reserved_vregs[$]`.

### Constraints
- `legal_c`: solve vtype before vl before vstart; `vstart ∈ [0, vl]`; `vl ∈ [1, VLEN/vsew]`.
- `bringup_c`: `vstart=0; vl=VLEN/vsew; vediv=1`.
- `vec_quad_widening_c`: `!vec_narrowing_widening → !vec_quad_widening`; `ELEN<64 → !(vec_fp && vec_quad_widening)`.
- `vlmul_c`: `vlmul ∈ {1,2,4,8}; vlmul ≤ MAX_LMUL`; narrowing → `vlmul<8 || fractional_lmul=1`; quad-widening → `vlmul<4 || fractional_lmul=1`.
- `vsew_c`: `vsew ∈ {8,16,32,64,128}; vsew ≤ ELEN`; vec_fp → `vsew=32`; narrowing → `vsew<ELEN`; quad-widening → `vsew<ELEN/2`.
- `vseg_c`: `enable_zvlsseg → vlmul<8`.
- `vdeiv_c`: `vediv ∈ {1,2,4,8}; vediv ≤ vsew/SELEN`.

### post_randomize — compute legal_eew
```
for emul in {1/8, 1/4, 1/2, 1, 2, 4, 8}:
  if !fractional_lmul: temp_eew = vsew * emul / vlmul
  else:                temp_eew = vsew * emul * vlmul
  if 8 ≤ temp_eew ≤ 1024: legal_eew.push(int(temp_eew))
```

### vsetvli boot emission
At init (riscv_asm_program_gen:555):
```
li x<gpr1>, <vl>
vsetvli x<gpr0>, x<gpr1>, e<SEW>, m<LMUL>, d<VEDIV>
```

Between streams: runtime vsetvli inserted for vtype transitions.

### Instruction gating
- `only_vec_instr` — restrict stream to vector ops.
- `vec_fp` — allow FP vector ops; forces vsew=32 (placeholder for Zvfh later).
- `vec_narrowing_widening` — enable VW*/VN* families.
- `vec_quad_widening` — enable VWW* (requires 4x headroom).
- `allow_illegal_vec_instr`.
- `vec_reg_hazards` — constrain to ~5 regs.
- `enable_zvlsseg` — enable segmented load/store.
- `enable_fault_only_first_load` — enable VLEFF/VLSEGEFF.

### Validation: EMUL rule
```
EMUL = EEW / SEW * LMUL
if EMUL ∉ {1/8, 1/4, 1/2, 1, 2, 4, 8}: illegal-instruction exception
```
Segmented operations only issued for EEW ∈ legal_eew.

## cov.py

### Purpose
Aggregate ISS functional coverage into simulator's covergroup database.

### Steps (per --steps)
1. `csv` — convert ISS log (spike/ovpsim/sail/whisper) to CSV trace.
2. `cov` — compile coverage model (build_cov), then replay CSVs through simulator (sim_cov).

### CLI (argparse)
`-o/--output, --dir (logs dir), -bz/--batch_size, -i/--instr_cnt, -to/--timeout(1000), -s/--steps(all), --core, --isa, --iss(spike|ovpsim|sail), -tl/--testlist, --lsf_cmd, --target, -si/--simulator, --simulator_yaml, -ct/--custom_target, -cs/--core_setting_dir, --stop_on_first_error, --dont_truncate_after_first_ecall, --noclean, --vector_options, --coverage_options, --exp, -d/--debug, --enable_visualization, --compliance_mode`.

### Log parser regexes
**Spike**:
- CORE_RE: `core\s+\d+:\s+0x(?P<addr>[a-f0-9]+?)\s+\(0x(?P<bin>.*?)\)\s+(?P<instr>.*?)$`
- RD_RE: `(core\s+\d+:\s+)?(?P<pri>\d)\s+0x(?P<addr>[a-f0-9]+?)\s+\((?P<bin>.*?)\)(?:\s+(?P<csr_pre>[a-zA-Z_][a-zA-Z0-9_]*)\s+0x(?P<csr_pre_val>[a-f0-9]+))?\s+(?P<reg>[xf]\s*\d+)\s+0x(?P<val>[a-f0-9]+)(\s+(?P<csr>\S+)\s+0x(?P<csr_val>[a-f0-9]+))?`

**OVPsim**:
- INSTR_RE: `riscvOVPsim.*, 0x(?P<addr>.*?)(?P<section>\(.*\): ?)(?P<mode>[A-Za-z]*?)\s+(?P<bin>[a-f0-9]*?)\s+(?P<instr_str>.*?)$`
- RD_RE: ` (?P<r>[a-z]*[0-9]{0,2}?) (?P<pre>[a-f0-9]+?) -> (?P<val>[a-f0-9]+?)$`

**Sail**:
- START_RE: `\[4\] \[M\]: 0x.*00001010`
- INSTR_RE: `\[[0-9].*\] \[(?P<pri>.)\]: 0x(?P<addr>[A-F0-9]+?) \(0x(?P<bin>[A-F0-9]+?)\) (?P<instr>.+?$)`
- RD_RE: `x(?P<reg>[0-9]+?) <- 0x(?P<val>[A-F0-9]*)`

### Trace entry
`pc, instr, gpr list (reg:val), csr list (csr:val), binary, mode, instr_str`.

### Coverage categories (from riscv_instr_cover_group.sv ~8k lines)
- Per-opcode covergroup.
- Per-format: rs1, rs2, rd, signs (positive/negative/zero).
- Register reachability: 32 GPR + 32 FPR per operand slot.
- CSR access: by name, by privilege.
- Privilege transitions: U↔M, M↔S, S↔U.
- Exceptions / traps.
- FP rounding modes (RNE/RTZ/RDN/RUP/RMM).
- Vector: vtype combinations, vl, instruction family, EEW, mask patterns, reductions, permutations.
- Hazards: NO/RAW/WAR/WAW.

### Coverage output
Simulator-specific (VCS `-cm_dir`, Questa `cov.ucdb`, Xcelium iCov). Post-processed to CSV/YAML/HTML via simulator's native reporting tool.

## Python port implications

- `VectorConfig` as a dataclass; validate constraints in `__post_init__`; compute `legal_eew` eagerly.
- `vsetvli` emitted as a raw asm line; a small helper tracks current (sew, lmul, ediv) to know when to reissue.
- Coverage: for Phase 1, we can drop the covergroup model entirely and rely on downstream ISS coverage. For Phase 2, mirror categories as a pure-Python counter using the same trace CSV format.
