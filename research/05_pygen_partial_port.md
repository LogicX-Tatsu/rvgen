# Research Note 05 — pygen/ existing Python port

Location: `pygen/pygen_src/` (~15k LOC) + `pygen/experimental/` (older proof-of-concept using python-constraint; deprecated).

## Constraint library
PyVSC (`pyvsc`) via `@vsc.randobj`, `@vsc.constraint`, `vsc.if_then`, `vsc.rangelist`, `vsc.dist`, `vsc.solve_order`, `vsc.unique`, `vsc.foreach`. Per-instruction randomization (`vsc.randomize_with(instr)`) to stay tractable. No external SAT solver.

## One-to-one mapping with SV

| SV file | Python file | Status |
|---------|-------------|--------|
| riscv_instr.sv | isa/riscv_instr.py (533L) | ported |
| rv32i/m/a/c/f/d/fc/dc/b_instr.sv | isa/rv32*.py | ported |
| rv64i/m/a/c/f/d/b_instr.sv | isa/rv64*.py | ported |
| riscv_compressed/floating_point/amo/b_instr.sv | isa/*.py | ported |
| riscv_instr_gen_config.sv | riscv_instr_gen_config.py (684L) | ported with argparse |
| riscv_directed/load_store/amo/loop/illegal instr libs | same filenames .py | ported |
| riscv_asm_program_gen.sv | riscv_asm_program_gen.py (1197L) | ported |
| riscv_instr_sequence.sv | riscv_instr_sequence.py (312L) | ported |
| riscv_instr_stream.sv | riscv_instr_stream.py (270L) | ported |
| riscv_callstack_gen.sv | riscv_callstack_gen.py (148L) | ported |
| riscv_data_page_gen.sv | riscv_data_page_gen.py (92L) | ported |
| riscv_privileged_common_seq.sv | riscv_privileged_common_seq.py (207L) | partial (stubs) |
| riscv_vector_cfg.sv, rv32v, rv64v | — | **not ported** |
| riscv_zba/zbb/zbc_instr.sv | — | **not ported** |
| riscv_debug_rom_gen.sv | stub (asm_program_gen.py:1046 `pass`) | **not ported** |
| riscv_page_table*.sv, pmp_cfg.sv | partial | **incomplete** |
| riscv_instr_cover_group.sv | riscv_instr_cover_group.py (8121L) | ported |

## Supported extensions (pygen)

Full: I, M, A, F, D, C (RV32+RV64), base B (partial).
Missing: V, Zba, Zbb, Zbc, Zbs, custom, Zfh, Zk*, Zc*.

## Privileged mode status (pygen)

- **M-mode**: functional.
- **S-mode**: skeleton only.
- **U-mode**: stubs; not functional.
- Paging: SATP modes defined but PTE generation incomplete.
- PMP: config framework, generation partial.
- Debug rom: stub (returns `dret`).

## Entry point

`run.py --simulator pyflow --test <name> --target <t>` dispatches to `pygen_src/test/riscv_instr_base_test.py` which uses `multiprocessing.Pool(cfg.num_of_tests)` and calls `riscv_asm_program_gen.gen_program()` + `gen_test_file(test_name)`. Output at `out/asm_test/*.S`.

## Key patterns

- Factory: `riscv_defines.DEFINE_INSTR(name, fmt, cat, group, imm_tp)` dynamically creates a subclass via `type(...)`.
- Registry: `riscv_instr.create_instr_list(cfg)` filters registered classes against `cfg.supported_isa` and config flags.
- Target import: `rcs = import_module("pygen_src.target."+argv.target+".riscv_core_setting")`.
- Config singleton `cfg` is created at module load; args via `argparse` in `riscv_instr_gen_config.__init__`.

## Performance ceiling

README notes ~12 min for 10k-instr generation. Constraint solver is the bottleneck. Our Python reimplementation (no PyVSC, pure rejection sampling) should be seconds.

## Gaps to replicate beyond pygen

- Vector extension (entire RVV).
- Zb* bitmanip clean split.
- Debug mode support.
- Full S/U-mode, paging, PMP generation.
- Custom extension plugin.

## Decision

Pygen is a good class-partitioning reference but **should not be a dependency**. Rewrite in pure Python without PyVSC; design for extensibility (Phase 2) by keeping the SV/pygen naming so testlist strings (`riscv_loop_instr`, `riscv_amo_instr_stream`, …) resolve unchanged.
