# chipforge-inst-gen

A pure-Python re-implementation of **riscv-dv**, the UVM/SystemVerilog random instruction generator from Google, with the aim of exact parity (Phase 1) and then extension beyond riscv-dv (Phase 2). No Verilator, VCS, Questa, UVM, or PyVSC — just Python.

---

## 0 — Status and where to pick up

**Current phase:** Phase 1 steps 1–7 substantially complete + Phase 2 crypto landing. **233 unit tests passing.** End-to-end CLI pipeline (gen → gcc_compile → iss_sim) passes **51/51** combinations on Spike across rv32imc/rv32imafdc/rv32imcb/rv64imc/rv64imcb, plus **21/21 trace-level matches on the chipforge-mcu RTL sim** (`rv32imc_zkn` target — RV32IMC + ratified Zkn umbrella: Zbkb/Zbkc/Zbkx/Zkne/Zknd/Zknh). Instruction registry = **301 ops**, stream registry = **11 streams**, **22 targets**. Reproducible via `scripts/mcu_validate.sh`.

### Prior §0 known issues — all resolved (2026-04-22)
1. **Spike-hang in CLI pipeline** — FIXED. Root cause: `mtvec_handler:` label landed on a 2-byte boundary (compressed code) but MTVEC masks the low 2 bits as MODE, so spike jumped into the middle of the preceding instruction → infinite illegal-instruction trap. Fix in `asm_program_gen.py::_gen_trap_handler_section` — emit `.align <tvec_alignment>` before each handler, per SV's `gen_trap_handler_section`.
2. **JalInstr backward jumps** — FIXED. Root cause: old code used `jal[i].imm_str = label[order[i]]`, producing a random permutation with possibly multiple cycles; spike could enter a cycle that didn't include the end and never terminate. Rewrote `streams/directed.py::JalInstr.build` to match SV's Hamiltonian chain `jump_start → order[0] → … → order[N-1] → end-sentinel`, with an ADDI end-sentinel.
3. **Compressed-FP + B extension** — LANDED. New `isa/rv32fc.py`, `isa/rv32dc.py`, `isa/bitmanip.py` (Zba/Zbb/Zbc/Zbs + draft RV32B). Fix to filter `_FP_GROUPS` (now includes RV32FC/RV32DC so `+enable_floating_point=0` gates them). Targets `rv32imcb`/`rv64imcb` now list ratified Zb* groups (not draft RV32B) so GCC 15.1 can assemble. CLI ISA map: `rv32imcb` → `rv32imc_zba_zbb_zbc_zbs_zicsr_zifencei`.
4. **FP unsupported_instr regression** — GUARDED. `tests/unit/test_filtering.py::test_target_unsupported_instr_honored_for_fp` asserts that marking specific FP ops in `target.unsupported_instr` removes them from the pool.

### Bonus fixes from the same session
- **RV64 store-misaligned in trap prologue.** `addi tp, tp, -4` + `sd sp, 0(tp)` on RV64 puts `sp` at a 4-byte-aligned (not 8-byte-aligned) address. SV's `yaml/iss.yaml` passes `--misaligned` to spike; we now match in `iss.py::run_iss`.
- **Loop-stream counter clobber.** RVC CB_FORMAT (C.ANDI/C.SRLI/C.SRAI) writes back through rs1, not rd. `LoopInstr`'s `reserved_rd=[cnt_reg]` only blocked rd → counter got clobbered as rs1. Now passes a restricted `avail_regs` tuple and `filtering.randomize_gpr_operands` intersects the compressed-3-bit pool with `avail_regs` (previously the avail set was silently replaced).

### Later in the same session
5. **Disable-flag audit.** Verified end-to-end that `+no_csr_instr`, `+no_fence`, `+no_ebreak`, `+no_ecall`, `+no_wfi`, `+no_branch_jump`, `+disable_compressed_instr`, `+no_data_page` all suppress the targeted instructions from the random pool. Default EBREAK/ECALL/WFI/DRET are "off" (i.e. `no_*=True`), so `+no_ebreak=0` is needed to get them in the random stream.
6. **bare_program_mode now skips boot CSRs.** `asm_program_gen.py::_gen_hart_section` previously emitted `setup_misa` + `pre_enter_privileged_mode` unconditionally; SV's reference guards both with `if (!cfg.bare_program_mode)`. Fixed, so setting `+bare_program_mode=1` on an rv32ui-style core now produces output with zero CSR ops.
7. **rv32ui + rv32imc_zkn + crypto targets added.** `TargetCfg` entries for `rv32ui` (bare, no CSR), `rv32imc_zkn` (chipforge-mcu ISA: RV32IMC + Zkn umbrella — SHA-512 split-pair marked unsupported since MCU is SHA-256 only; NO Zbb since MCU doesn't actually implement Zbb's min/max/rev8/sext/etc), `rv32imc_zkn_zks` (full ratified K-family incl. SM3/SM4), `rv64imc_zkn`. `--gen_opts` CLI flag added for per-run plus-arg overrides. Invalid non-standard names (e.g. `rv32imck`) are rejected by argparse choices.
8. **Ratified crypto extensions landed.** New `isa/crypto.py` with Zbkb-only ops (`brev8`/`zip`/`unzip`), AES (`aes32esi`/`esmi`/`dsi`/`dsmi` for RV32; `aes64es`/`esm`/`ds`/`dsm`/`ks1i`/`ks2`/`im` for RV64), SHA-256 sigma/sum helpers, SHA-512 (RV32 split H/L pair + RV64 single-instruction), SM3, SM4. `filtering.py` gates RV32-only / RV64-only mnemonics by xlen.
9. **CSR-write whitelist (SV parity).** `stream.py::RandInstrStream.gen_instr` now restricts CSRRW/CSRRWI/CSRRS/CSRRC(I) target CSRs to `{MSCRATCH}` (matches SV's `include_write_reg` default). Writing random values to MISA/MSTATUS/MTVEC etc. was silently bricking the test mid-stream (e.g. clearing MISA.C → all compressed instructions become illegal → infinite handler loop).
10. **LoadStoreRandInstrStream base-reg protection.** The base register that holds the region address used to be eligible as a load `rd` — any such load would overwrite the base with garbage, sending every subsequent access into random memory. Fix: pin base_reg into a `base_locked` set so it's never picked as rd.
11. **chipforge-mcu trace-level match (21/21).** Per-instruction trace compare of Spike (golden) vs MCU Verilator sim, via the MCU's `spike_log_to_trace_csv.py` + `core_log_to_trace_csv.py` + `instr_trace_compare.py`. 7 test types × 3 seeds = 21 runs, every one `[PASSED]: N matched`, zero mismatches. Script at `scripts/mcu_validate.sh` (checked in).

### Canonical regression sweep

```bash
for t in rv32imc:riscv_arithmetic_basic_test rv32imc:riscv_rand_instr_test \
         rv32imc:riscv_jump_stress_test rv32imc:riscv_loop_test \
         rv32imc:riscv_amo_test rv32imc:riscv_rand_jump_test \
         rv32imc:riscv_no_fence_test rv32imc:riscv_mmu_stress_test \
         rv32imc:riscv_unaligned_load_store_test \
         rv32imafdc:riscv_floating_point_arithmetic_test \
         rv32imcb:riscv_b_ext_test rv32imcb:riscv_zbb_zbt_test \
         rv64imc:riscv_arithmetic_basic_test rv64imc:riscv_rand_instr_test \
         rv64imc:riscv_loop_test rv64imc:riscv_jump_stress_test \
         rv64imcb:riscv_b_ext_test; do
  target=${t%%:*}; test=${t##*:}
  for s in 100 200 300; do
    rm -rf /tmp/reg_${target}_${test}_${s}
    /home/qamar/anaconda3/bin/python -m chipforge_inst_gen \
      --target $target --test $test \
      --steps gen,gcc_compile,iss_sim --iss spike \
      --output /tmp/reg_${target}_${test}_${s} --start_seed $s -i 1 2>&1 \
      | grep -qE "tests passed ISS sim" \
      && echo "PASS $target/$test/$s" || echo "FAIL $target/$test/$s"
  done
done
```

Expected: 51/51 PASS. A FAIL is the first bread-crumb — inspect `/tmp/reg_.../asm_test/*.S` and `/tmp/reg_.../spike_sim/*.log`.

### Prompt to resume a fresh session

> Continue building the `chipforge-inst-gen` project under `/home/qamar/chipforge/chipforge-inst-gen/`. Read `CLAUDE.md` §0 first — prior known issues through 11 are all resolved, 51/51 Spike + 21/21 chipforge-mcu passing. Open workstreams: (a) step 7 proper — distinct load/store stream classes (NARROW/HIGH/MEDIUM/SPARSE locality, multi-page, alignment-aware variant); (b) step 8 — full privileged mode (paging / PMP / S-U mode / debug ROM); (c) step 12 — golden-diff harness against the 2026-04-21 riscv-dv reference output; (d) widen CSR-write whitelist beyond `{MSCRATCH}` with per-test opt-in (SV's `+include_write_reg`); (e) vector extension fleshout. Keep running `/home/qamar/anaconda3/bin/python -m pytest tests/` after every change. Update CLAUDE.md §0 when a major milestone lands.

### What's finished

- Deep read of the riscv-dv codebase at `~/Desktop/verif_env_tatsu/riscv-dv/`.
- Eleven focused research reports distilled into `research/01_*.md` … `research/*.md` in this directory — consult those before touching any file listed in this CLAUDE.md.
- **Step 1 — enums + CSRs + helpers** (`chipforge_inst_gen/isa/{enums,csrs,utils}.py`): every riscv-dv enum in declaration order (`RiscvInstrName` = 496 entries, matches SV), per-CSR field table from `riscv_privil_reg.sv`, `format_string/format_data/hart_prefix/get_label/indent_line`, `push/pop_gpr_to/from_kernel_stack`, `sign_extend/mask_imm`.
- **Step 2 — base Instr + factory + RV32I** (`chipforge_inst_gen/isa/{base,factory,csr_ops,rv32i}.py`): `Instr` class with `set_rand_mode/set_imm_len/extend_imm/randomize_imm/post_randomize/convert2asm/convert2bin`, `CsrInstr` subclass for CSRRW/CSRRS/CSRRC/CSRRWI/CSRRSI/CSRRCI, `define_instr`/`define_csr_instr` macros, `get_instr(name)` factory, 54 RV32I instrs registered. convert2bin is spec-correct per RV32I encoding (deviates from SV's convert2bin which is only used for illegal-instr emission anyway).
- **Step 3 — Config + targets + testlist loader + CLI + seeding** (`config.py`, `targets/__init__.py`, `testlist.py`, `seeding.py`, `cli.py`, `__main__.py`): 18 per-target `TargetCfg` entries, `Config` dataclass with every Phase-1 knob (plusarg-compatible), YAML testlist loader with `<riscv_dv_root>` substitution + recursive import, `SeedGen` (fixed/start/rerun/random), `python -m chipforge_inst_gen --target ... --test ... --steps gen` entry point.
- **Step 4 — InstrStream + InstrSequence + branch resolution** (`isa/filtering.py`, `stream.py`, `sequence.py`): `create_instr_list(cfg)` filters the registry per target + config flags, `get_rand_instr(rng, avail, ...)` does the SV-compatible filtered pick, `InstrStream`/`RandInstrStream` handle insert/mix/gen_instr with reserved-reg respect, `InstrSequence.post_process_instr` allocates numeric labels and resolves forward branch targets (`imm_str = "<N>f"` with byte-offset computed from per-instr sizes), `generate_instr_stream()` emits `.S` lines with the 18-char label column.
- **Step 5 — asm_program_gen + data_page + signature + privileged/boot + privileged/trap** (`asm_program_gen.py`, `sections/{data_page,signature}.py`, `privileged/{boot,trap}.py`): full M-mode DIRECT boot (setup_misa + pre_enter_privileged_mode with MTVEC/MEPC/MSTATUS/MIE/mret), init section with GPR distribution `{0:=1, 0x80000000:=1, [0x1:0xF]:=1, [0x10:0xEFFFFFFF]:=1, [0xF0000000:0xFFFFFFFF]:=1}`, main sequence, test_done/ecall handler/write_tohost chain, tohost/fromhost, user/kernel stacks, CORE_STATUS/TEST_RESULT/WRITE_GPR/WRITE_CSR signature emitters. **Output runs to completion on spike.**
- **Step 6a/6b — AMO + RVC** (`isa/amo.py`, `isa/compressed.py`, `isa/rv32{a,c}.py`, `isa/rv64{a,c}.py`): AmoInstr with aq/rl + func5/func3/AMO opcode, CompressedInstr with CI/CB/CJ/CR/CA/CL/CS/CSS/CIW formats, imm-alignment shifts, NZIMM/NZUIMM constraints, 3-bit compressed GPR enforcement, no-HINT filters. Convert2asm produces GCC-assembleable output; convert2bin for RVC is deferred (only used for illegal emission).
- **Test suite: 222 passing** (`/home/qamar/anaconda3/bin/python -m pytest tests/`).
- **End-to-end smoke verified:**
  - `python -m chipforge_inst_gen --target rv32imc --test riscv_arithmetic_basic_test --steps gen --output /tmp/x --start_seed 100 -i 1` generates a 5250-line `.S`.
  - Assembles with `riscv64-unknown-elf-gcc -march=rv32imc_zicsr_zifencei -mabi=ilp32`.
  - Runs to completion on spike (`spike --isa=rv32imc_zicsr_zifencei --priv=m test.elf` exits 0 via HTIF tohost store).

- **Step 6 FP — RV32F/RV64F/RV32D/RV64D** (`isa/floating_point.py`, `isa/rv32{f,d}.py`, `isa/rv64{f,d}.py`): FloatingPointInstr with fs1/fs2/fs3/fd, rm, has_fs* flags, per-format set_rand_mode, convert2asm for all formats (R/R4/I/S + compressed FP). `randomize_fpr_operands` invoked from stream. FP arithmetic test generates 10k lines with ~4800 FP instrs, assembles with `rv32imafdc_zicsr_zifencei`, runs to completion on spike.
- **Step 7 (partial) — directed streams** (`streams/{__init__,base,directed,loop,amo_streams}.py`): `DirectedInstrStream` base class with atomic-tagging + Start/End comments, `STREAM_REGISTRY` by SV class name, `IntNumericCornerStream` (corner-value init + 15-30 arith ops), `JalInstr` (shuffled JAL chain), `LoopInstr` (countdown loop with BNE backward branch), `LoadStoreRandInstrStream` (LA + sequence of LW/SW; aliased for `riscv_hazard_instr_stream` / `riscv_load_store_hazard_instr_stream` / `riscv_multi_page_load_store_instr_stream` / `riscv_mem_region_stress_test` / `riscv_load_store_stress_instr_stream` / `riscv_load_store_shared_mem_stream` / `riscv_load_store_rand_addr_instr_stream`), `LrScInstrStream` + `AmoInstrStream`. AsmProgramGen wires `cfg.directed_instr[idx] = (name, count)` → `get_stream(name)` → stream.generate() → wrapper `InstrStream` → `main_sequence.directed_instr`. AMO region (`amo_0`) now emitted in data section so LR/SC/AMO streams resolve.
- **Test suite: 228 passing.**
- **End-to-end smoke verified on spike:**
  - `riscv_arithmetic_basic_test` (rv32imc) — 5389 lines, includes IntNumericCornerStream 4× + RV32IMC random body.
  - `riscv_rand_instr_test` (rv32imc) — 2890 lines, multiple loop + hazard + multi-page + jal streams.
  - `riscv_amo_test` (rv32ia) — 5572 lines, AmoInstrStream + LrScInstrStream.
  - `riscv_floating_point_arithmetic_test` (rv32imafdc) — 10k+ lines with 4878 FP instrs.
- Instruction registry: **197 ops** (RV32I + RV32M + RV32A + RV32C + RV32F + RV32D + RV64I + RV64M + RV64A + RV64C + RV64F + RV64D). Stream registry: **11 streams** (corner, JAL, loop, LR/SC, AMO, + 7 load/store aliases).

**Next step when resuming work:** (1) B extension (`riscv_b_instr` + RV32B/RV64B + Zba/Zbb/Zbc/Zbs) to complete step 6. (2) Flesh out step 7 with properly distinct load/store stream classes (NARROW/HIGH/MEDIUM/SPARSE locality, alignment-aware instr selection, multi-page variant). (3) Step 8 — full privileged mode (paging, PMP, S/U mode, debug ROM). (4) Step 9 — vector extension. (5) Step 11 — GCC+ISS pipeline wrapping. (6) Step 12 — golden-diff harness against 2026-04-21.

---

## 1 — Goal

### Phase 1 — Exact parity with riscv-dv
- Match every test in `target/<T>/testlist.yaml` and `yaml/base_testlist.yaml`.
- Output `.S` files that are structurally identical (same section order, label format, register-init pattern, trap-handler shape, signature-handshake format) to riscv-dv's output. Byte-identical is not required (seeds/PRNGs differ); **structurally identical + ISS-equivalent** is.
- Same CLI surface and YAML schema as `run.py` so existing testlists keep working.
- Same integrations: spike / ovpsim / sail / whisper for ISS and RISC-V GCC for compile; we only replace the SV/UVM generator.

### Phase 2 — Beyond riscv-dv
- Add ISA/extensions riscv-dv's pygen never ported (full RVV, Zba/Zbb/Zbc/Zbs cleanly, Zfh, Zvfh, Zc*, Zk*, Smaia/Ssaia, Svnapot, Svpbmt, etc.).
- Make configuration declarative and composable (YAML-driven knob presets rather than +plusargs).
- Expose the generator as a library (`from chipforge_inst_gen import Generator`) as well as a CLI.
- Faster generation (riscv-dv pygen takes ~12 min for 10K-instr tests; goal: seconds).
- Optional: determinism-preserving seed + structured debug dumps to diff two generator versions.

### Non-goals
- No constraint-solver dependency (PyVSC, Z3, python-constraint). All "constraints" are per-instruction rejection-sampling with `random`/`numpy.random`; it's fast enough and debuggable.
- No RTL simulator integration. We stop at `.S` / `.bin` / ISS log.
- No GUI.

---

## 2 — Reference tree (riscv-dv source of truth)

Everything we're mirroring lives at `~/Desktop/verif_env_tatsu/riscv-dv/`. Key paths:

| Path | What it is | Our mirror (Phase 1) |
|------|------------|----------------------|
| `run.py` | Python harness: CLI → testlist → gen → gcc → ISS → compare | `chipforge_inst_gen/cli.py` |
| `src/riscv_instr_pkg.sv` | All enums, CSR table, helper fns | `chipforge_inst_gen/isa/enums.py`, `csrs.py`, `utils.py` |
| `src/riscv_defines.svh` | DEFINE_INSTR macros | factory helpers in `isa/factory.py` |
| `src/isa/riscv_instr.sv` | Base instruction class + registry | `isa/base.py` |
| `src/isa/rv32i_instr.sv` … `rv64x_instr.sv` | Per-extension instruction declarations | `isa/rv32i.py` … `isa/rv64x.py` |
| `src/isa/riscv_compressed_instr.sv` | RVC base | `isa/compressed.py` |
| `src/isa/riscv_floating_point_instr.sv` | F/D base | `isa/floating_point.py` |
| `src/isa/riscv_vector_instr.sv` | V base | `isa/vector.py` |
| `src/isa/riscv_amo_instr.sv` | A base | `isa/amo.py` |
| `src/isa/riscv_b_instr.sv`, `riscv_zba/zbb/zbc/zbs_instr.sv` | B + Zb* | `isa/bitmanip.py` |
| `src/isa/riscv_csr_instr.sv` | CSR ops | `isa/csr_ops.py` |
| `src/riscv_instr_gen_config.sv` | ~100 config knobs | `config.py` |
| `src/riscv_vector_cfg.sv` | Vector config (vtype, vl, vxrm, legal_eew, flags) | `vector_config.py` |
| `src/riscv_pmp_cfg.sv` | PMP region config | `pmp_config.py` |
| `src/riscv_privil_reg.sv` | Per-CSR WARL/WLRL/WPRI field table | `privileged/csr_fields.py` |
| `src/riscv_privileged_common_seq.sv` | Boot CSR sequence, MRET into target mode | `privileged/boot.py` |
| `src/riscv_page_table.sv`, `..._entry.sv`, `..._list.sv`, `..._exception_cfg.sv` | Page table construction & fault injection | `privileged/paging.py` |
| `src/riscv_debug_rom_gen.sv` | Debug ROM (DCSR, DPC, DSCRATCH, single-step) | `privileged/debug_rom.py` |
| `src/riscv_data_page_gen.sv` | Data section (RAND/INCR/ZERO) | `sections/data_page.py` |
| `src/riscv_signature_pkg.sv` | CORE_STATUS / TEST_RESULT / WRITE_GPR / WRITE_CSR protocol | `sections/signature.py` |
| `src/riscv_instr_stream.sv` | Instr list primitive + `insert_instr_stream()` | `stream.py` |
| `src/riscv_instr_sequence.sv` | Main/sub-program sequence (stack enter/exit, label, branch-target resolution) | `sequence.py` |
| `src/riscv_directed_instr_lib.sv` | jump, push/pop stack, corner-value stream | `streams/directed.py` |
| `src/riscv_load_store_instr_lib.sv` | LS base + stress/hazard/multi-page/rand-addr/vector variants | `streams/load_store.py` |
| `src/riscv_amo_instr_lib.sv` | LR/SC stream, AMO stream, vector AMO | `streams/amo.py` |
| `src/riscv_loop_instr.sv` | Nested-loop stream | `streams/loop.py` |
| `src/riscv_illegal_instr.sv` | Binary illegal-encoding generator | `streams/illegal.py` |
| `src/riscv_pseudo_instr.sv` | LI, LA pseudos | `isa/pseudo.py` |
| `src/riscv_callstack_gen.sv` | Sub-program call-tree + non-recursive linking | `callstack.py` |
| `src/riscv_asm_program_gen.sv` | Top-level `.S` composer | `asm_program_gen.py` |
| `target/<T>/riscv_core_setting.sv` | per-target XLEN/supported_isa/CSRs/support_flags | `targets/<T>.py` (plus YAML) |
| `target/<T>/testlist.yaml` | per-target tests | reused as-is |
| `yaml/base_testlist.yaml` | 14 base tests | reused as-is |
| `yaml/iss.yaml`, `yaml/simulator.yaml`, `yaml/csr_template.yaml` | ISS + sim + CSR config | reused as-is |
| `pygen/pygen_src/` | Existing ~15K-LOC Python port (uses PyVSC). **Study but don't depend on it.** Good reference for class partitioning; its constraints and vector/B/debug/paging are incomplete. |
| `2026-04-21/riscv_floating_point_arithmetic_test/asm_test/*.S` | 100 golden reference `.S` files to diff against |

---

## 3 — Architectural invariants (must not drift)

These come out of the golden `.S` files and the riscv-dv SV source — they are the definition of "exact parity":

1. **Section order in `.S`:**
   ```
   .include "user_define.h"
   .globl _start
   .section .text
   [.option norvc;]            ; if disable_compressed_instr
   .include "user_init.s"
   _start:    [MHARTID dispatch]
   h0_start:  [setup_misa → page tables → pre_enter_privileged_mode]
   init:      [FP init → GPR init → SP init → vector init → signature INITIALIZED → dummy CSR writes]
   (if PMP) [trap_handlers, test_done]
   sub_1:, sub_2:, …
   main:     [directed streams interleaved into random stream]
   (if !PMP) test_done:
   (insert sub-programs)
   h<N>_instr_end: nop
   .section .data
   .align 6; .global tohost; tohost: .dword 0;
   .align 6; .global fromhost; fromhost: .dword 0;
   [data pages: .section .h<N>_region_<i>, "aw",@progbits]
   .section .h<N>_user_stack,"aw",@progbits  [stack_len .4byte/.8byte 0x0]
   (if !bare) kernel_instr_* , kernel_data_*, kernel_stack_*
   .section .h<N>_page_table,"aw",@progbits  [if paging]
   ```

2. **Label column** = 18 characters (`LABEL_STR_LEN = 18`). Every instruction line emits `"<label + ':' padded to 18 chars><mnemonic>"` where an unlabeled line uses 18 spaces. Do not change.

3. **Mnemonic column width** = 13 chars (`MAX_INSTR_STR_LEN`). Instructions are padded to 13 chars before operands.

4. **Boot CSR sequence** (for target `init_privileged_mode`):
   - Write MSTATUS with MPP=target_mode, MPIE/SPIE/UPIE per `enable_interrupt`, MIE=0, MPRV/MXR/SUM/TVM/TW/FS/VS per knobs.
   - Write MIE (if target implements it) with M/S/U-software/timer/external enables.
   - `gen_csr_instr()` loads each value via `li xgpr0, 0x<val>; csrw 0x<addr>, xgpr0 # <NAME>`.
   - If SATP_MODE != BARE: load root page table label, shift right 12 to get PPN, write SATP with MODE | PPN via `csrs`.
   - `mret` to transition.

5. **Trap handler** (DIRECT mode): push GPRs to kernel stack. Exact push sequence (`riscv_instr_pkg.push_gpr_to_kernel_stack`):
   - If scratch CSR implemented: `addi tp, tp, -4; sw sp, 0(tp); add sp, tp, zero` (save user SP onto kernel stack, then move KSP to gpr.SP).
   - If MSTATUS && SATP_MODE != BARE && MPRV: read MSTATUS, isolate MPP, if MPP != M-mode sign-extend sp using `slli/srli` by `XLEN - MAX_USED_VADDR_BITS` (= 30); else `1: nop`.
   - Allocate: `addi sp, sp, -32*(XLEN/8)`.
   - Push x1..x31 (skip x0): `sw/sd xi, i*(XLEN/8)(sp)`.
   - `add tp, sp, zero` (restore KSP to tp for nested-interrupt safety).
   Then read xCAUSE, `srli` XLEN-1 to get interrupt-vs-exception bit, dispatch; each handler ends with `pop_gpr_from_kernel_stack` + `mret/sret/uret`. `ebreak_handler` and `illegal_instr_handler` bump `xEPC` by 4 before `pop`. **VECTORED mode**: 16-entry jump table at `<mode>_handler`, entry 0 = exception handler, entries 1..15 = interrupt vectors.

6. **Signature protocol** (writes 32-bit word to `cfg.signature_addr`):
   - CORE_STATUS=00: `[bits 12:8]=status,[7:0]=00`.
   - TEST_RESULT=01: `[bit 8]=result,[7:0]=01`.
   - WRITE_GPR=02: write 02, then 32 words x0..x31.
   - WRITE_CSR=03: `[bits 19:8]=csr_addr,[7:0]=03`, then `csrr` and store.

7. **Reserved registers** from config: `cfg.reserved_regs = {tp, sp, scratch_reg}` (set in `post_randomize()`). `gpr[0..3]`, `pmp_reg[0..1]`, `ra` also reserved per their constraints. GP is implicitly reserved (holds 1 at test_done).

8. **Stack section format**:
   ```
   .section .h<N>user_stack,"aw",@progbits;
   .align <12 if SATP_MODE != BARE else 2>
   h<N>user_stack_start:
   .rept <stack_len - 1>
   .8byte 0x0   (or .4byte 0x0 if XLEN=32)
   .endr
   h<N>user_stack_end:
   .8byte 0x0
   ```

9. **FP register init**: `li x<temp>, <rand32>; fmv.w.x f<n>, x<temp>` for each f0..f31; then `fsrmi <rm>`. No FLW/FLD/.rodata FP constants.

10. **GPR init distribution** (riscv_asm_program_gen:672):
    `reg_val dist { 0:=1, 0x80000000:=1, [0x1:0xF]:=1, [0x10:0xEFFFFFFF]:=1, [0xF0000000:0xFFFFFFFF]:=1 }`.

11. **Branch-target resolution** (riscv_instr_sequence: `post_process_instr`): numeric labels `0:`, `1:`, … assigned in order; each random BRANCH picks step ∈ [1, cfg.max_branch_step] forward (default 20), target clamped to `label_idx-1`; byte offset computed from per-instruction sizes (2 for compressed, 4 otherwise); unused labels erased.

12. **insert_instr_stream(new, idx=-1, replace=False)**: pick random idx in current stream; if the picked instr has `atomic=True` retry up to 10 times; if still atomic scan for first non-atomic. Directed stream atoms carry comments `Start <name>` / `End <name>` on first/last instr.

13. **Call-stack generation** (riscv_callstack_gen): program 0 = main at level 0; levels ascend monotonically by at most 1; pool of sub-program IDs at each level is shuffled and distributed to callers of the previous level; no recursion (`unique sub_program_id`, `!= program_id`). Max depth 20, max sub-programs 20, max calls per func 5.

---

## 4 — Enum and CSR reference (condensed — full detail in `research/02_instr_pkg_enums.md`)

### Instruction groups
`RV32I, RV64I, RV32M, RV64M, RV32A, RV64A, RV32F, RV32FC, RV64F, RV32D, RV32DC, RV64D, RV32C, RV64C, RV128I, RV128C, RVV, RV32B, RV32ZBA, RV32ZBB, RV32ZBC, RV32ZBS, RV64B, RV64ZBA, RV64ZBB, RV64ZBC, RV64ZBS, RV32X, RV64X`.

### Categories
`LOAD, STORE, SHIFT, ARITHMETIC, LOGICAL, COMPARE, BRANCH, JUMP, SYNCH, SYSTEM, COUNTER, CSR, CHANGELEVEL, TRAP, INTERRUPT, AMO` (vector categories inserted via include macro).

### Formats
`J, U, I, B, R, S, R4, CI, CB, CJ, CR, CA, CL, CS, CSS, CIW, VSET, VA, VS2, VL, VS, VLX, VSX, VLS, VSS, VAMO`.

### Privilege / misc
- `privileged_mode_t`: `USER=0, SUPERVISOR=1, RESERVED=2, MACHINE=3`.
- `f_rounding_mode_t`: `RNE=0, RTZ=1, RDN=2, RUP=3, RMM=4`.
- `satp_mode_t`: `BARE=0, SV32=1, SV39=8, SV48=9, SV57=10, SV64=11`.
- `mtvec_mode_t`: `DIRECT=0, VECTORED=1`.
- `pmp_addr_mode_t`: `OFF=00, TOR=01, NA4=10, NAPOT=11`.
- `pte_permission_t`: `NEXT_LEVEL=000, R=001, RW=011, X=100, RX=101, RWX=111`.
- `exception_cause_t` 0..F: IAM, IAF, ILLEGAL, BREAKPOINT, LAM, LAF, SAM, SAF, ECALL_U, ECALL_S, –, ECALL_M, IPF, LPF, –, SPF.
- `interrupt_cause_t`: U/S/M-software (0,1,3), U/S/M-timer (4,5,7), U/S/M-external (8,9,B).

### CSRs (by block)
- User: 0x000 USTATUS, 0x004 UIE, 0x005 UTVEC, 0x040 USCRATCH, 0x041 UEPC, 0x042 UCAUSE, 0x043 UTVAL, 0x044 UIP; 0x001–0x003 FFLAGS/FRM/FCSR; 0xC00–0xC9F counters.
- Supervisor: 0x100 SSTATUS, 0x102/3 SEDELEG/SIDELEG, 0x104 SIE, 0x105 STVEC, 0x106 SCOUNTEREN, 0x10A SENVCFG, 0x140 SSCRATCH, 0x141 SEPC, 0x142 SCAUSE, 0x143 STVAL, 0x144 SIP, 0x180 SATP.
- Machine info: 0xF11 MVENDORID, 0xF12 MARCHID, 0xF13 MIMPID, 0xF14 MHARTID, 0xF15 MCONFIGPTR.
- Machine trap setup: 0x300 MSTATUS, 0x301 MISA, 0x302 MEDELEG, 0x303 MIDELEG, 0x304 MIE, 0x305 MTVEC, 0x306 MCOUNTEREN, 0x310 MSTATUSH.
- Machine trap handling: 0x340 MSCRATCH, 0x341 MEPC, 0x342 MCAUSE, 0x343 MTVAL, 0x344 MIP.
- Machine config: 0x30A MENVCFG, 0x31A MENVCFGH, 0x747 MSECCFG, 0x757 MSECCFGH.
- PMP cfg: 0x3A0..0x3AF; PMP addr: 0x3B0..0x3EF and 0x4C0..0x4DF.
- Debug: 0x7B0 DCSR, 0x7B1 DPC, 0x7B2 DSCRATCH0, 0x7B3 DSCRATCH1; trigger 0x7A0..0x7A5.
- Vector: 0x008 VSTART, 0x009 VXSAT, 0x00A VXRM, 0xC20 VL, 0xC21 VTYPE, 0xC22 VLENB.

### Parameters / constants
- `XLEN ∈ {32, 64, 128}` from target's `riscv_core_setting.sv`.
- `MAX_INSTR_STR_LEN = 13`; `LABEL_STR_LEN = 18`; `MAX_CALLSTACK_DEPTH = 20`; `MAX_SUB_PROGRAM_CNT = 20`; `MAX_CALL_PER_FUNC = 5`.
- `compressed_gpr = {S0, S1, A0..A5}` (x8..x15).
- Default writeable CSR set `= {MSCRATCH}`.
- `MPRV_MASK = 1<<17`; `SUM_MASK = 1<<18`; `MPP_MASK = 3<<11`.

---

## 5 — Targets and tests (condensed — full detail in `research/01_targets_and_testlists.md`)

### Targets mapping to (XLEN, supported_isa, privilege, SATP, HARTS)
- `rv32i`: 32, {RV32I}, M, BARE, 1.
- `rv32ia/iac/ic/if/im/imac/imafdc/imc/imcb/imc_sv32`: 32, various, M (or M+U for sv32), BARE (SV32 for sv32).
- `rv64imc/imcb`: 64, various, M, BARE.
- `rv64gc`, `rv64imafdc`: 64, full G, U+S+M, SV39.
- `rv64gcv`: 64, G + RVV (VLEN=512, ELEN=32, MAX_LMUL=8), M only, BARE.
- `ml`, `multi_harts`: special variants.

### Base testlist (14 tests)
- `riscv_arithmetic_basic_test`, `riscv_rand_instr_test`, `riscv_jump_stress_test`, `riscv_loop_test`, `riscv_rand_jump_test`, `riscv_mmu_stress_test`, `riscv_no_fence_test`, `riscv_illegal_instr_test`, `riscv_ebreak_test`, `riscv_ebreak_debug_mode_test`, `riscv_full_interrupt_test`, `riscv_csr_test`, `riscv_unaligned_load_store_test`, `riscv_amo_test`.

### FP tests (rv32ia import chain)
- `riscv_floating_point_arithmetic_test` (iters=1, instr_cnt=10000, +enable_floating_point=1, +no_fence=1, +no_data_page=1, +no_branch_jump=1, +boot_mode=m).
- `riscv_floating_point_rand_test` (+directed streams 0..4, +no_fence=0).
- `riscv_floating_point_mmu_stress_test` (+directed streams 0..3, instr_cnt=5000).

### Vector tests (rv64gcv)
- `riscv_vector_arithmetic_test`, `riscv_vector_arithmetic_stress_test` (+vector_instr_only=1), `riscv_vector_load_store_test`, `riscv_vector_amo_test`.

### Privileged / CSR / PMP / B
- `riscv_privileged_mode_rand_test`, `riscv_invalid_csr_test`, `riscv_page_table_exception_test` (iters=0 by default), `riscv_sfence_exception_test`, `riscv_u_mode_rand_test` (+boot_mode=u), `riscv_pmp_test`, `riscv_b_ext_test`, `riscv_zbb_zbt_test`.

---

## 6 — Planned Python package layout

```
chipforge_inst_gen/
  __init__.py
  cli.py                  # argparse, replaces run.py top-level
  config.py               # maps to riscv_instr_gen_config.sv
  targets/
    __init__.py           # loads target by name
    rv32i.py … rv64gcv.py # XLEN, supported_isa, CSR list, support_* flags
  isa/
    enums.py              # InstrName, InstrGroup, InstrCategory, InstrFormat, Reg, Fpr, Vreg, Csr, ...
    csrs.py               # per-CSR WARL/WLRL/WPRI field table
    utils.py              # format_string, format_data, hart_prefix, imm extend/mask
    base.py               # Instr base class: has_rs1/2/3/rd/imm flags, convert2asm, set_rand_mode, set_imm_len, extend_imm, get_opcode/func3/func7
    factory.py            # DEFINE_INSTR equivalents; registry { name: class }
    pseudo.py             # LI, LA
    illegal.py            # binary illegal-encoding generator
    compressed.py         # CI/CB/CJ/CR/CA/CL/CS/CSS/CIW base + no_hint_illegal constraint
    floating_point.py     # FP operand fields + set_rand_mode + convert2asm + hazard check
    vector.py             # vs1/vs2/vs3/vd + va_variant + vm + widening/narrowing constraints
    amo.py                # aq/rl + AMO convert2asm
    bitmanip.py           # B + Zba + Zbb + Zbc + Zbs
    csr_ops.py            # CSR write_csr constraint + address filtering
    rv32i.py rv64i.py …   # per-extension instruction declarations
  stream.py               # InstrStream (list primitive), insert_instr_stream, mix_instr_stream
  sequence.py             # InstrSequence (main/sub program), post_process_instr (label, branch target), generate_instr_stream (string output), stack enter/exit
  callstack.py            # CallStackGen
  streams/
    directed.py           # jump, jal chain, push/pop stack, int_numeric_corner
    load_store.py         # base + stress/hazard/multi-page/rand-addr + vector LS
    amo.py                # LR/SC, AMO stream, vector AMO
    loop.py               # nested loops
    illegal.py            # delegate to isa/illegal.py
  privileged/
    boot.py               # setup_mmode_reg, setup_smode_reg, setup_umode_reg, gen_csr_instr, setup_satp
    csr_fields.py         # per-CSR field table
    paging.py             # PageTable, PageTableEntry, PageTableList, exception injection, page_fault_handling_routine
    pmp.py                # PmpCfg + pmpcfg packing + pmpaddr NAPOT encoding
    debug_rom.py          # DCSR/DPC/DSCRATCH, single-step, ebreak header/footer
  sections/
    data_page.py          # .section .hN_region_N, align 2 pattern, RAND/INCR/ZERO
    signature.py          # CORE_STATUS/TEST_RESULT/WRITE_GPR/WRITE_CSR emit templates
  asm_program_gen.py      # top-level AsmProgramGen composer (orchestrates everything above)
  iss/
    spike.py, ovpsim.py, sail.py, whisper.py   # log → CSV parsers (port from scripts/)
    compare.py            # trace CSV diff
  gcc.py                  # riscv-gcc + objcopy invocation
  testlist.py             # YAML loader with <riscv_dv_root> import
  seeding.py              # SeedGen: --seed / --start_seed / --seed_yaml semantics
tests/
  unit/
    test_enums.py
    test_format_string.py
    test_instr_asm.py     # per-instruction assembly smoke tests
    test_branch_resolution.py
    ...
  golden/
    test_fp_arith_against_golden.py  # diff our .S against 2026-04-21 riscv-dv output
research/
  01_…_targets_and_testlists.md
  02_instr_pkg_enums.md
  03_isa_class_hierarchy.md
  (more research notes to add — see §11)
```

---

## 7 — Phase 1 execution plan (order matters)

Each step ends with a concrete `done when` criterion.

1. **Enums, CSR table, registers.**
   - Port `riscv_instr_pkg.sv` enums to `isa/enums.py`.
   - Port per-CSR field table from `riscv_privil_reg.sv` to `isa/csrs.py`.
   - Port helper functions (`format_string`, `format_data`, `hart_prefix`, `get_label`, `push/pop_gpr_to/from_kernel_stack` as asm-string generators).
   - Done when: `from chipforge_inst_gen.isa import enums, csrs` imports cleanly and tests confirm all enum members match SV order.

2. **Base instruction class + factory + RV32I.**
   - `Instr` base with `rd, rs1, rs2, imm, csr` + `has_*` flags.
   - `set_rand_mode()`, `set_imm_len()`, `extend_imm()`, `imm_c` equivalent, `convert2asm()`, `get_opcode/func3/func7()`, `convert2bin()`.
   - Factory helper equivalent to `DEFINE_INSTR` — generates subclasses from (name, fmt, category, group, imm_type).
   - Register every RV32I instruction; verify `.convert2asm()` matches expected strings for canonical encodings.
   - Done when: all 47 RV32I instructions produce correct `.S` lines and correct 32-bit encodings (checked against `llvm-mc`/`spike` disassembly).

3. **Config + targets + testlist loader.**
   - `Config` dataclass mirroring `riscv_instr_gen_config.sv`. Every knob a named field with default; constraint validation in `__post_init__` runs the post-randomize equivalents.
   - Per-target module with XLEN, supported_isa, privilege list, CSR list, support_* flags.
   - YAML testlist loader with `<riscv_dv_root>` substitution and recursive import.
   - CLI with the argument set from `run.py` §1 of `research/run.py` notes.
   - Done when: `python -m chipforge_inst_gen --target rv32imc --test riscv_arithmetic_basic_test --iterations 2 --steps gen` runs and emits two `.S` files (content can be crude for now).

4. **InstrStream + Sequence + branch resolution.**
   - Port `riscv_instr_stream.sv` (queue, `insert_instr_stream`, `mix_instr_stream`, atomic tagging).
   - Port `riscv_instr_sequence.sv`:
     - `gen_instr()` with per-instruction random selection honoring reserved regs and category filters.
     - `post_process_instr()` for label allocation and branch target resolution (numeric labels `0:..N:`, step ∈ [1, max_branch_step], byte-offset computation from per-instr size).
     - `generate_instr_stream()` → list of `.S` lines with 18-char label column + 13-char mnemonic column.
     - Stack-enter / stack-exit for non-main sequences.
   - Done when: generating a 500-instruction main program produces syntactically valid `.S` and assembles with `riscv-gcc` without errors.

5. **Data page + signature + top-level asm_program_gen skeleton.**
   - `.section .data` with tohost/fromhost.
   - `.hN_region_<i>` data pages with RAND/INCR/ZERO patterns.
   - User-stack and kernel-stack sections with correct align and repeat counts.
   - Signature emitter (`CORE_STATUS INITIALIZED`, `WRITE_GPR`, `WRITE_CSR`, `TEST_RESULT`).
   - `AsmProgramGen.gen_program()` phase ordering per §3-1.
   - Minimal `gen_program_header` / `setup_misa` / `pre_enter_privileged_mode` / `gen_init_section` / `gen_test_done` / `gen_trap_handlers` (DIRECT-mode only, for M-mode targets).
   - Done when: `riscv_arithmetic_basic_test` output assembles, links against riscv-dv's `scripts/link.ld`, and passes through spike up to `ecall` on `test_done`.

6. **Extensions: M, C, A, F, D, B.**
   - Add per-extension instruction declarations.
   - Add `riscv_compressed_instr` (CI/CB/CJ/CR/CA/CL/CS/CSS/CIW) with 3-bit register constraints, NZIMM/NZUIMM rules, no-HINT-illegal filter, immediate alignment shifts.
   - Add FP base (fs1/fs2/fs3/fd, rm, hazard checker) + RV32F/RV64F/RV32D/RV64D.
   - Add AMO base (aq/rl, `.w`/`.d` suffix, aq/rl mnemonic append) + RV32A/RV64A.
   - Add B + Zba + Zbb + Zbc + Zbs.
   - Hook `+disable_compressed_instr`, `+enable_floating_point`, `+enable_b_extension`, `+enable_zb*_extension` knobs.
   - Done when: `riscv_amo_test`, `riscv_ebreak_test`, `riscv_floating_point_arithmetic_test`, `riscv_b_ext_test` all assemble and run on spike.

7. **Directed streams.**
   - `riscv_directed_instr_stream` base (atomic tagging + start/end comments).
   - `riscv_int_numeric_corner_stream` (Zero/AllOne/NegativeMax LIs then 15–30 arithmetic).
   - `riscv_jal_instr` (shuffled back-to-back jump chain).
   - `riscv_jump_instr` (LA + ADDI + optional branch + JAL/JALR).
   - `riscv_push/pop_stack_instr`.
   - `riscv_load_store_base_instr_stream` + NARROW/HIGH/MEDIUM/SPARSE locality + alignment-aware instruction selection + subclass variants (single, stress, rand, hazard, load_store_hazard, multi_page, mem_region_stress, rand_addr, shared_mem).
   - `riscv_lr_sc_instr_stream` and `riscv_amo_instr_stream`.
   - `riscv_loop_instr` (nested, 1–2 deep, 1–25 body instructions, various branch types).
   - Done when: every `+directed_instr_*` name from base_testlist + rv32ia testlist resolves and every base test's generated `.S` structurally matches riscv-dv output.

8. **Privileged: boot, trap, paging, PMP, debug.**
   - Boot CSR sequence per §3-4; MRET mode transition.
   - Trap handlers: DIRECT **and** VECTORED; exception dispatch table; each handler's push/pop pair; mepc+=4 for ebreak/illegal.
   - Paging for SV32/SV39/SV48: PTE layout, page_table_list topology (1 + Link^N leaves), `process_page_table` linker, `gen_page_fault_handling_routine` for on-the-fly PTE fix.
   - PMP: pmpcfg packing (RV32: 4/CSR, RV64: 8/CSR), pmpaddr NAPOT encoding `addr >> 2 | ((1<<g) -1)`, TOR monotonicity.
   - Debug rom: DCSR ebreak bits, DPC increment if cause==ebreak, DSCRATCH0 single-step counter.
   - Exception injection via `riscv_page_table_exception_cfg`.
   - Done when: `riscv_mmu_stress_test`, `riscv_invalid_csr_test`, `riscv_privileged_mode_rand_test`, `riscv_u_mode_rand_test`, `riscv_pmp_test`, `riscv_ebreak_debug_mode_test` all run on spike and on rv64gc core model.

9. **Vector (for rv64gcv).**
   - `VectorConfig` (vtype, vl, vstart, vxrm, vxsat, legal_eew, gates: vec_fp, narrowing/widening/quad, zvlsseg, fault_only_first, reg hazards).
   - `vsetvli` boot init (li vl; vsetvli x0, x1, e<SEW>, m<LMUL>, d<EDIV>).
   - Vector instruction base (vs1..vd, va_variant, vm, widening/narrowing/convert detection, overlap constraints, mask_enable/disable constraint).
   - Vector load/store stream (UNIT_STRIDED/STRIDED/INDEXED), vector AMO stream.
   - Done when: `riscv_vector_arithmetic_test`, `riscv_vector_load_store_test`, `riscv_vector_amo_test` assemble and pass through spike with `--isa=rv64gcv` without illegal-instruction traps.

10. **Multi-hart.**
    - `NUM_HARTS > 1`: `hart_prefix("h<n>_")` applied to labels; main-entry dispatcher reads MHARTID and branches.
    - Shared-memory load/store stream.
    - Done when: `multi_harts` testlist produces correct `.S` with per-hart sections.

11. **ISS wrapping + comparison + GCC.**
    - Port `scripts/*_log_to_trace_csv.py` parsers.
    - Port `scripts/instr_trace_compare.py` CSV diff.
    - GCC + objcopy invocation matching `gcc_compile` in `run.py`.
    - End-to-end pipeline replicates `run.py`'s `steps = gen | gcc_compile | iss_sim | iss_cmp | all`.
    - Done when: the full pipeline (`--target rv32imc --test riscv_arithmetic_basic_test --iss spike,ovpsim --iterations 2`) runs to completion and emits `iss_regr.log` with PASS lines.

12. **Golden-file diff harness.**
    - `tests/golden/` compares our output to riscv-dv's 100 `.S` files in `2026-04-21/riscv_floating_point_arithmetic_test/asm_test/`. Match on structure (section order, label presence, instruction mix distributions, bootstrap shape), not byte-for-byte.
    - Done when: all 100 golden FP test files structurally match.

---

## 8 — Phase 2 ideas (ordered roughly by value)

1. **Full RVV 1.0** (riscv-dv pygen has none). Add Zve*, Zvl*, whole-register moves, segmented 1..8-field variants, reductions, permutations.
2. **Zfh / Zvfh / Zfinx / Zdinx / Zhinx.** FP half-precision, NaN-box tests, in-X-register FP variants.
3. **Zk* crypto** (Zknd, Zkne, Zknh, Zbkb, Zbkc, Zbkx, Zksh, Zksed).
4. **Zicond (conditional move), Zimop (may-be-operations), Zicfilp/Zicfiss (CFI), Svnapot, Svpbmt, Smaia/Ssaia.** All newer ratified extensions.
5. **Declarative YAML configs.** Replace the `+plusarg` soup with nested YAML configs; keep +plusarg parser for backwards-compat.
6. **Library API.** `Generator(target="rv32imc", test="riscv_arithmetic_basic_test", iterations=2).generate()` returning a list of `.S` strings and `(asm, bin)` pairs.
7. **Faster generation.** Target `<5s` for 10k-instr test (vs ~12 min for pygen). The non-constraint-solver architecture already buys this.
8. **Extension marketplace.** Allow user extensions by dropping a single `isa/myext.py` with a declarative registration (`@register_extension("MYEXT", ...)`).
9. **Structured coverage model.** Replace `riscv_instr_cover_group.sv` (~8k lines) with a declarative coverpoint list; dump coverage to YAML.
10. **Multiple seeds per test + differential rerun.** Emit a manifest enabling exact rerun across versions.

---

## 9 — Conventions

- **Python 3.11+** (pattern matching, `StrEnum`).
- Dependencies kept minimal: only `PyYAML`. Optional: `numpy` for weighted sampling, `pytest` for tests. **No constraint solver.**
- Types: `dataclasses` + `typing`. Keep mutable dataclasses simple; randomization methods return new instances or mutate in place following riscv-dv's style.
- No UVM: no "factory create by string name"; use a plain registry `dict[str, Type[Instr]]`. Respect riscv-dv's class naming (`riscv_<instr>_instr`) because testlist `+directed_instr_N=<name>` references it.
- Stream output is **list of `str` lines**, not a single string, so unit tests can assert on a specific line.
- Randomness goes through a single `random.Random(seed)` per generator; the seed seeding rules mirror `SeedGen` in `run.py`.
- File layout and import shape should let you do `from chipforge_inst_gen.isa import Instr, InstrName`.
- Every enum matches riscv-dv's declaration order exactly.
- `.S` output uses **spaces only** (no tabs), matching the golden files.

---

## 10 — Testing strategy

- **Unit tests** per module: enums, helpers, per-instruction `convert2asm()`, branch-target math, stack layout, CSR field packing, PMP NAPOT encoding, PTE layout.
- **Golden diff** against `2026-04-21/` (100 FP tests) — see `tests/golden/`.
- **Assembler round-trip**: for every generated `.S`, invoke `riscv-unknown-elf-gcc` and fail if it does not assemble/link.
- **Spike smoke test**: every generated `.o` runs on spike and reaches `test_done` without unexpected trap.
- **Cross-ISS comparison**: spike ↔ ovpsim (when both tools are installed).

---

## 11 — Research notes (under `research/`)

These are distilled summaries of the riscv-dv source that were produced before writing any code. Always re-read before editing the corresponding module.

- `01_targets_and_testlists.md` — target matrix, CSR implementations, testlist tree, yaml asset map.
- `02_instr_pkg_enums.md` — full enum catalog, CSR addresses, parameters, helper functions.
- `03_isa_class_hierarchy.md` — instruction class tree, formats, encoding, per-class constraints.
- `04_asm_program_gen_flow.md` *(todo, see agent report cached in context)* — phase order in `gen_program()`, boot CSR sequence, trap handler shapes, signature emit, stack/data/page sections.
- `04_asm_program_gen_flow.md` — phase order in `gen_program()`, boot CSR sequence, trap handler shapes, signature emit, stack/data/page sections, callstack generator, post_process_instr.
- `05_pygen_partial_port.md` — partial Python port in `pygen/pygen_src/`: class-by-class SV→Py mapping, gaps (no V, no Zb*, partial S/U/debug/PMP/paging; PyVSC dependency; ~12-min runtime for 10k-instr).
- `06_run_py_and_iss.md` — full CLI surface, YAML testlist schema, simulator.yaml / iss.yaml templating, seed logic, batching, gcc/objcopy steps, iss_cmp pipeline, parser regexes.
- `07_config_datapage_signature.md` — every config knob grouped by topic, all constraint blocks, data_page section format, signature protocol with exact emitted asm.
- `08_directed_instr_libs.md` — every directed-stream class (jump, jal, push/pop, int corner, load/store variants, AMO/LR-SC, loop, illegal, vector LS/AMO) with parameters and integration points.
- `09_privileged_paging_pmp_debug.md` — boot CSR sequence per mode, per-CSR field table, SATP setup, PTE layouts per satp_mode, page-fault routine, PMP packing + NAPOT encoding, debug ROM structure.
- `10_vector_cfg_and_cov.md` — VectorCfg fields/constraints, vsetvli/vsetivli emit, legal_eew formula, cov.py orchestration + log-parser regexes.
- `11_golden_fp_sfiles.md` — exact formatting of golden `.S` files (18-space label column, 13-col mnemonic, `li+fmv.w.x` FP init loop, fsrmi line, test_done trailer, kernel/user stack layout, per-seed variance vs invariants).

All 11 notes are complete. **Do not delete items from this list** — the notes are required reading before modifying that part of the code.

---

## 12 — Open questions / risks

- **Randomization parity.** riscv-dv uses SV constrained randoms; we use per-instruction rejection sampling. This will not produce byte-identical streams for the same seed. Strategy: ISS-equivalent + structurally-equivalent rather than byte-equivalent. Document this explicitly in the golden diff harness.
- **ABI names vs `xN`/`fN`.** Golden `.S` uses ABI names (`a0`, `t0`, `fa0`). Our `convert2asm()` must emit ABI names for integer regs and `fN` names for FP regs, following `riscv_reg_t.name()`.
- **Custom / user extensions.** riscv-dv supports `isa/custom/` and `user_extension/`. Phase 1 should stub these out; Phase 2 makes them first-class via a plugin system.
- **Debug ROM placement.** riscv-dv aligns to 4KB. Some RTL cores have specific reset-debug addresses; keep this as a config knob.
- **Vector `cfg.vector_cfg.vtype.vlmul` is an exponent** (1/2/4/8), but `fractional_lmul` flips it to a fractional multiplier — the set of legal EEWs is a derived set not a trivial range. Preserve the SV post-randomize formula.
- **`riscv_csr_test`** is generated by a separate Python script (`scripts/gen_csr_test.py`) not the main generator. Port it as a separate command.
