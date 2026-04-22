# Research Note 06 — run.py, simulator.yaml, iss.yaml, seed & flow

## CLI (distilled)

Test selection:
- `--target` (default `rv32imc`).
- `-tl/--testlist` (default `target/<T>/testlist.yaml`).
- `-tn/--test` (default `all`).
- `-i/--iterations` (0 = use testlist value; >0 overrides all).

Simulator / compile:
- `-si/--simulator` ∈ {vcs, ius, questa, dsim, qrun, riviera, xlm, pyflow}.
- `--cmp_opts`, `--sim_opts`, `--co` (compile only), `--so` (sim only), `--cov`.

ISS:
- `--iss` ∈ {spike, ovpsim, sail, whisper, renode} (or comma-separated for cmp).
- `--iss_yaml`, `--iss_opts`, `--iss_timeout` (default 10s), `--priv` (m/s/u/su).

Seeds (mutually exclusive group):
- `--start_seed` (increments).
- `--seed` (fixed; forces iterations=1).
- `--seed_yaml` (rerun from seed.yaml).

ISA:
- `--isa`, `-m/--mabi`, `-cs/--core_setting_dir`, `-ct/--custom_target`, `-ext/--user_extension_dir`.

Output / flow:
- `-o/--output` (default `out_<date>`), `--noclean` (default TRUE — UX bug, means "do not clean"), `-d/--debug`, `-v/--verbose`, `--log_suffix`.
- `-s/--steps` ∈ {gen, gcc_compile, iss_sim, iss_cmp, all}.
- `--gen_timeout` (default 360s; pyflow auto-bumped to 1200s).
- `--stop_on_first_error`, `--lsf_cmd`, `-bz/--batch_size`.

Directed:
- `--asm_test`, `--c_test`, `--gcc_opts`.

## Flow (end to end)

```
main()
  setup RISCV_DV_ROOT env
  parse_args()                       # load_config: resolve target → isa/mabi/core_setting_dir/testlist
  create_output()                    # mkdir -p; rm -rf old if noclean==False (rare)
  [style check if requested]
  if --asm_test or --c_test: run directly and return
  process_regression_list(testlist, test, iterations, matched_list, cwd)
    read_yaml recursively; expand 'import' with <riscv_dv_root>
    iterations override; entry['iterations']>0 kept
  split matched_list into {gen_test, asm_directed, c_directed} — mutually exclusive
  if steps ~ "gen":
    gen(matched_list, args, output_dir, cwd)
      get_generator_cmd(simulator, simulator.yaml, cov, exp)
      do_compile()                    # one or more compile commands from YAML
      do_simulate()                   # per test per batch
        SeedGen.get(test_id, batch_idx)
        build cmd with +UVM_TESTNAME/+num_of_tests/+start_idx/+asm_file_name/+ntb_random_seed (VCS)
        or pyflow equivalent: --num_of_tests/--start_idx/--asm_file_name/--log_file_name/--target/--gen_test/--seed
        if lsf_cmd: queue; else run_cmd
      save seed.yaml (test_id_batch → seed)
  if steps ~ "gcc_compile":
    riscv-gcc -static -mcmodel=medany -fvisibility=hidden -nostdlib -nostartfiles
              -I<cwd>/user_extension -T<cwd>/scripts/link.ld
              -march=<isa> -mabi=<mabi> -o <test>.o <test>.S
    riscv-objcopy -O binary <test>.o <test>.bin
  if steps ~ "iss_sim":
    parse_iss_yaml(iss, iss.yaml, isa, priv, setting_dir)
    per ISS: run for each test; write log to <out>/<iss>_sim/<test>_<iter>.log
  if steps ~ "iss_cmp":
    compare_iss_log(iss_list, log_list, report)  # must be exactly 2 ISSes
      process_<iss>_sim_log → CSV
      compare_trace_csv → report PASS/FAIL lines
    save_regr_report
```

## Seed logic

```
SeedGen.get(test_id, iteration)
  if rerun_seed (from --seed_yaml): return rerun_seed["<test_id>_<iter>"]
  if fixed_seed (--seed): assert iter==0; return fixed_seed
  if start_seed (--start_seed): return start_seed + iter
  else: return random.getrandbits(31)
```

Seeds saved to `{output_dir}/seed.yaml` as `{ test_id: seed_value }`.

## Testlist YAML schema

```yaml
- import: <riscv_dv_root>/yaml/base_testlist.yaml
- test: <name>
  description: "…"
  iterations: N
  gen_test: riscv_instr_base_test | riscv_rand_instr_test | …
  gen_opts: |
    +instr_cnt=5000 +no_fence=1 +boot_mode=m …
  rtl_test: core_base_test                (documentation only)
  no_iss: 1                                (skip ISS sim)
  no_gcc: 1                                (skip GCC)
  no_post_compare: 1                       (doc only)
  asm_test: /path/to/test.S | dir          (mutually excl. with gen_test, c_test)
  c_test: /path/to/test.c | dir
  gcc_opts: "-mno-strict-align"
  iss_opts: "..."
  compare_opts: "+compare_final_value_only=1"
```

Test globbing is **exact string match** (no regex, no glob). `--test all` matches everything.

## Pre-defined targets (19)

`rv32imc, rv32i, rv32im, rv32ic, rv32ia, rv32iac, rv32imac, rv32imafdc, rv32if, rv32imcb, rv32imac_zkne_zknd_...`, `rv32imc_sv32, multi_harts, rv64imc, rv64imcb, rv64gc, rv64gcv, rv64imafdc, ml`.

Mapping: 32-bit → `ilp32`, 64-bit → `lp64`. ISA extended with `_zicsr_zifencei` suffix.

## simulator.yaml template example (VCS)

```yaml
- tool: vcs
  compile:
    cmd:
      - "vcs -file <cwd>/vcs.compile.option.f +incdir+<setting> +incdir+<user_extension>
         +vcs+lic+wait -f <cwd>/files.f -full64 -l <out>/compile.log
         -Mdir=<out>/vcs_simv.csrc -o <out>/vcs_simv <cmp_opts> <cov_opts>"
    cov_opts: "-cm_dir <out>/test.vdb"
  sim:
    cmd: "<out>/vcs_simv +vcs+lic+wait <sim_opts> +ntb_random_seed=<seed> <cov_opts>"
    cov_opts: "-cm_dir <out>/test.vdb -cm_log /dev/null -cm_name test_<seed>_<test_id>"
```

Placeholders: `<cwd>, <out>, <setting>, <user_extension>, <cmp_opts>, <sim_opts>, <seed>, <test_id>, <cov_opts>`. Env vars substituted via `env_var:` list.

## iss.yaml templates

```yaml
- iss: spike
  path_var: SPIKE_PATH
  cmd: "<path_var>/spike --log-commits --isa=<variant> --priv=<priv> --misaligned -l <elf>"

- iss: ovpsim
  path_var: OVPSIM_PATH
  cmd: "<path_var>/riscvOVPsimPlus.exe --controlfile <cfg_path>/riscvOVPsim.ic
        --objfilenoentry <elf> --override riscvOVPsim/cpu/simulateexceptions=T
        --trace --tracechange --traceshowicount --tracemode --traceregs
        --finishafter 1000000"

- iss: sail
  path_var: SAIL_RISCV
  cmd: "<path_var>/riscv_ocaml_sim_RV<xlen> <elf>"

- iss: whisper
  path_var: WHISPER_ISS
  cmd: "<path_var> <elf> --log --xlen <xlen> --isa <variant><priv>
        --configfile <config_path>/whisper.json --iccmrw"

- iss: renode
  path_var: RENODE_PATH
  cmd: "python3 <scripts_path>/renode_wrapper.py --renode '<path_var>'
        --elf <elf> --isa <variant> --priv=<priv> --mem-size 0x80000000"
```

Whisper special: expands `g` in variant to `imafd`. OVPsim needs `<cfg_path>/riscvOVPsim.ic`.

## ISS log parsers (scripts/)

- `spike_log_to_trace_csv.py`: regex for `core N: 0x<pc> (0x<bin>) <disasm>` (CORE_RE) and `(core \d:)?<pri>\s+0x<addr>\s+\(<bin>\)\s*(?:<csr_pre>\s+0x<csr_pre_val>)?\s+<reg>\s+0x<val>\s*(?:<csr>\s+0x<csr_val>)?` (RD_RE).
- `ovpsim_log_to_trace_csv.py`: INSTR_RE = `riscvOVPsim.*, 0x<addr><section>: <mode>\s+<bin>\s+<instr_str>`; RD_RE = ` <r> <pre> -> <val>`.
- `sail_log_to_trace_csv.py`: START_RE `[4] [M]: 0x...00001010`; INSTR_RE `[…] [<pri>]: 0x<addr> (0x<bin>) <instr>`; RD_RE `x<reg> <- 0x<val>`.
- `whisper_log_trace_csv.py`.
- `instr_trace_compare.py`: CSV diff yielding PASS/FAIL lines per instruction; summary `N PASSED, M FAILED`.

## Exit codes

- `RET_SUCCESS=0`, `RET_FAIL=1`, `RET_FATAL=-1`, keyboard interrupt = 130.

## Gotchas

- `--noclean` default `True` = "do not clean", inverse of intuitive.
- Log suffix applied only to generator logs; ISS comparison uses `<iss>_sim/<test>_<iter>.log` ignoring suffix.
- IUS sim has `check_return_code = False` (spurious non-zero exits).
- `riscv_csr_test` skips compile stage and is generated by `scripts/gen_csr_test.py`.
- `test_id` used as seed key is `<test_name>_<batch_index>`, not per-iteration.
- Iterations==0 silently skipped.
- `--custom_target` requires explicit `--isa` and `--mabi`.
- ISA 'c' stripped for GCC if `+disable_compressed_instr` present in gen_opts.
