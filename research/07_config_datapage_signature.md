# Research Note 07 — instr_gen_config, data_page_gen, signature_pkg

## Config (riscv_instr_gen_config.sv) — groups of knobs

### Program structure
- `main_program_instr_cnt` (rand, ∈ [10, instr_cnt]).
- `sub_program_instr_cnt[]` (rand, sized to num_of_sub_program).
- `debug_program_instr_cnt`, `debug_sub_program_instr_cnt[]` (∈ [100,300]).
- `num_of_tests` (int, default 1), `num_of_sub_program` (5), `instr_cnt` (200).
- `no_branch_jump, no_load_store, no_fence, no_data_page, no_directed_instr, no_csr_instr, no_ebreak(1), no_ecall(1), no_dret(1), no_wfi(1)`.
- `enable_unaligned_load_store, bare_program_mode`.

### Privilege modes
- `init_privileged_mode` (rand; distributed dist over `supported_privileged_mode`, weights 6/4 for 2-mode, 4/3/3 for 3-mode; `+boot_mode=m/s/u` overrides).
- `support_supervisor_mode` (set in pre_randomize).
- `virtual_addr_translation_on` (if init_mode != M && SATP_MODE != BARE; solve order init_mode first).
- `enable_page_table_exception` (int).
- MSTATUS/MIE/SSTATUS/SIE/USTATUS/UIE (rand XLEN-bit).
- `mstatus_mprv`, `mstatus_mxr`, `mstatus_sum`, `mstatus_tvm` (0 if SATP==BARE).
- `mstatus_fs` (01 if FP else 00), `mstatus_vs` (01 if vector else 00).
- `set_mstatus_mprv`, `set_mstatus_tw`, `mstatus_tw`.

### Interrupts and traps
- `enable_interrupt, enable_nested_interrupt, enable_timer_irq`.
- `enable_illegal_csr_instruction, enable_access_invalid_csr_level`.
- `no_delegation(1), force_m_delegation, force_s_delegation`.
- `m_mode_exception_delegation[cause]`, `s_mode_*`, `m/s_mode_interrupt_delegation[cause]` — arrays.
  - Constraints: INSTRUCTION_PAGE_FAULT never delegated (dead-loop risk); only allowed causes delegated when !no_delegation && support_supervisor_mode; specific set `{IAM, BREAKPOINT, ECALL_U, IPF, LPF, SPF}` and `{S_SOFTWARE, S_TIMER, S_EXTERNAL}` interrupts.
- `mtvec_mode` ∈ `supported_interrupt_mode`; `tvec_alignment` soft == 2 (DIRECT) or `$clog2(XLEN*4/8)` (VECTORED); plusarg `+tvec_alignment=N` can fix it.

### FP
- `enable_floating_point, fcsr_rm`.

### Vector
- `enable_vector_extension, vector_instr_only, vector_cfg` (obj), `vreg_init_method`.

### Bitmanip
- `enable_b_extension, enable_zba/zbb/zbc/zbs_extension` (auto-disabled if group not in supported_isa).
- `enable_bitmanip_groups[]` (default {ZBB, ZBS, ZBP, ZBE, ZBF, ZBC, ZBR, ZBM, ZBT, ZB_TMP}).

### Reserved registers (rand, constrained)
- `gpr[4]`, `scratch_reg`, `pmp_reg[2]`, `sp`, `tp`, `ra`.
- Constraint `reserve_scratch_reg_c`: `scratch_reg ∉ {ZERO, sp, tp, ra, GP}`.
- `ra` dist `{RA:=3, T1:=2, [SP:T0]:=1, [T2:T6]:=4}`.
- `sp` if `fix_sp` == SP; else unconstrained but ≠ tp, ≠ {GP,RA,ZERO}.
- `reserved_regs = {tp, sp, scratch_reg}` set in post_randomize.

### CSR
- `gen_all_csrs_by_default`, `gen_csr_ro_write`, `add_csr_write[]`, `remove_csr_write[]`.
- `randomize_csr`, `invalid_priv_mode_csrs[]` (computed: CSRs whose name starts with D always invalid + M/S/U per init_mode).
- `check_misa_init_val`, `check_xstatus(1)`.

### PMP
- `pmp_cfg` object (created in `new()`; rand_mode = `pmp_cfg.pmp_randomize`).

### Paging
- `enable_sfence` (constrained complex: if allow_sfence_exception must be 1 and either init_mode != S or mstatus_tvm; else 0 if S-mode without TVM or no_fence).
- `allow_sfence_exception`.

### Debug
- `gen_debug_section, enable_ebreak_in_debug_rom, set_dcsr_ebreak, num_debug_sub_program, enable_debug_single_step, single_step_iterations ∈ [10,50]`.

### Memory regions
- `mem_region[] = [region_0 (3000B, xwr=111), region_1 (3000B, xwr=111)]`.
- `amo_region[] = [amo_0 (128B, xwr=111)]`.
- `s_mem_region[] = [s_region_0 (32B), s_region_1 (32B)]`.
- `stack_len = 2000`, `kernel_stack_len = 128`.
- `min_stack_len_per_program` (default 10*(XLEN/8); post_randomize lowers to 2*(XLEN/8)).
- `max_stack_len_per_program = 16*(XLEN/8)`.
- `use_push_data_section` (toggle .pushsection/.popsection).
- `data_page_pattern` ∈ {RAND_DATA, ALL_ZERO, INCR_VAL}.

### Kernel programs
- `kernel_program_instr_cnt = 400`.

### Misc
- `signature_addr (default 0xdeadbeef)`, `require_signature_addr`.
- `boot_mode_opts`, `asm_test_suffix`.
- `disable_compressed_instr` (auto if RV32/64C not supported).
- `illegal_instr_ratio`, `hint_instr_ratio`.
- `num_of_harts = NUM_HARTS`, `enable_misaligned_instr`, `enable_dummy_csr_write`.
- `max_branch_step = 20`, `max_directed_instr_stream_seq = 20`.
- `dist_control_mode` + `category_dist[cat]` for `+dist_<cat>=N` support.

## Important helper methods

- `setup_instr_distribution()` reads `+dist_<cat>=` per category if `dist_control_mode==1`; defaults to 10.
- `init_delegation()` zeroes all delegation arrays.
- `check_setting()`:
  - If any RV64 in supported_isa, require XLEN==64.
  - If RV128, require XLEN==128.
  - Else require XLEN==32 AND SATP_MODE ∈ {BARE, SV32}.
- `get_invalid_priv_lvl_csr()` builds list based on init_mode.
- `pre_randomize()` sets `support_supervisor_mode` flag.
- `post_randomize()` sets `reserved_regs`, `min_stack_len_per_program`, calls `check_setting`.

## data_page_gen (riscv_data_page_gen.sv)

- `gen_data(idx, pattern, num_bytes, out bytes[])`:
  - RAND_DATA: per-byte random.
  - INCR_VAL: `(idx + i) % 256`.
  - ALL_ZERO: default zero.
- `gen_data_page(hart, pattern, is_kernel=0, amo=0)`:
  - Select region: amo → `cfg.amo_region`; kernel → `cfg.s_mem_region`; else `cfg.mem_region`.
  - For each region emit:
    ```
    .section .h<N><name>,"aw",@progbits;      [.pushsection if use_push_data_section]
    h<N><name>:
    .word 0x<32-byte chunk formatted via format_data>
    ...
    ```
  - AMO region has NO hart prefix. 
  - 32-byte rows, last row padded.

## signature_pkg (riscv_signature_pkg.sv)

### signature_type_t (bit[7:0])
- `CORE_STATUS=0x00` — core status info (bits [12:8]=core_status_t, [7:0]=CORE_STATUS).
- `TEST_RESULT=0x01` — pass/fail (bit[8]=test_result_t, [7:0]=TEST_RESULT).
- `WRITE_GPR=0x02` — then 32 follow-up writes of x0..x31.
- `WRITE_CSR=0x03` — [bits 19:8]=csr_addr, [7:0]=WRITE_CSR; then csrr+sw.

### core_status_t (bit[4:0])
`INITIALIZED=0x00, IN_DEBUG_MODE=0x01, IN_MACHINE_MODE=0x02, IN_HYPERVISOR_MODE=0x03, IN_SUPERVISOR_MODE=0x04, IN_USER_MODE=0x05, HANDLING_IRQ=0x06, FINISHED_IRQ=0x07, HANDLING_EXCEPTION=0x08, INSTR_FAULT_EXCEPTION=0x09, ILLEGAL_INSTR_EXCEPTION=0x0A, LOAD_FAULT_EXCEPTION=0x0B, STORE_FAULT_EXCEPTION=0x0C, EBREAK_EXCEPTION=0x0D`.

### test_result_t
`TEST_PASS=0, TEST_FAIL=1`.

### Assembly templates

CORE_STATUS:
```
li x<gpr1>, 0x<signature_addr>
li x<gpr0>, 0x<core_status>
slli x<gpr0>, x<gpr0>, 8
addi x<gpr0>, x<gpr0>, 0x0          # CORE_STATUS tag = 0x00
sw x<gpr0>, 0(x<gpr1>)
```

TEST_RESULT: similar but tag 0x01 and value is `test_result`.

WRITE_GPR:
```
li x<gpr1>, 0x<signature_addr>
li x<gpr0>, 0x02                    # tag
sw x<gpr0>, 0(x<gpr1>)
sw x0,  0(x<gpr1>)
sw x1,  0(x<gpr1>)
...
sw x31, 0(x<gpr1>)
```

WRITE_CSR (if csr ∈ implemented_csr):
```
li x<gpr1>, 0x<signature_addr>
li x<gpr0>, 0x<csr_addr>
slli x<gpr0>, x<gpr0>, 8
addi x<gpr0>, x<gpr0>, 0x3          # WRITE_CSR tag = 0x03
sw x<gpr0>, 0(x<gpr1>)
csrr x<gpr0>, 0x<csr_addr>
sw x<gpr0>, 0(x<gpr1>)
```

`core_is_initialized()` (only if require_signature_addr and signature_addr != 0xdeadbeef) emits a CORE_STATUS INITIALIZED handshake in the init section.

`dump_perf_stats()` iterates implemented_csr and emits WRITE_CSR for each in `[MCYCLE..MHPMCOUNTER31H]`.

`gen_register_dump(ref instr[$])`:
```
la x<gpr0>, _start
sd x0,  0(x<gpr0>)       # (sw if XLEN=32)
sd x1,  8(x<gpr0>)
...
sd x31, 248(x<gpr0>)
```

`gen_program_end(hart)` (hart 0 only):
```
write_tohost: sw gp, tohost, t5
_exit:        j write_tohost
```
