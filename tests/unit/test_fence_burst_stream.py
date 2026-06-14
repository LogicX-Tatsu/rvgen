"""Tests for the riscv_fence_burst_instr_stream directed stream.

The stream fills a gap left by the SV TODO at ``riscv_instr.sv:286``
("fence combinations"): the default FENCE instruction in rvgen emits
the bare ``fence`` mnemonic (encoded as the most-restrictive
``fence rw, rw`` ordering). Real fence-unit verification needs
stimulus that exercises the full spec matrix of (predecessor-set,
successor-set) over {i, o, r, w}.

These tests pin:
  1. The stream is registered and discoverable via the trio.
  2. It declares BANNED_BY=("no_fence",) so it interacts correctly
     with the user knob.
  3. Emitted asm contains ``fence <pred>, <succ>`` with diverse masks
     across the run — not just the bare ``fence`` form.
  4. The pred/succ mask atoms only come from {i, o, r, w}.
  5. End-to-end: invoking the stream via +directed_instr_N populates
     the .S with the expected fence variants.
"""

from __future__ import annotations

import random as _rnd
import re

from rvgen.asm_program_gen import AsmProgramGen
from rvgen.config import make_config
from rvgen.isa.filtering import create_instr_list
from rvgen.streams import get_stream
from rvgen.streams.fence_burst import (
    FenceBurstInstrStream,
    _NONEMPTY_MASKS,
)
from rvgen.targets import get_target


def test_fence_burst_stream_registered():
    cls = get_stream("riscv_fence_burst_instr_stream")
    assert cls is FenceBurstInstrStream


def test_fence_burst_declares_no_fence_banned_by():
    """no_fence must drop the stream — FENCE is the entire payload."""
    assert FenceBurstInstrStream.BANNED_BY == ("no_fence",)


def test_mask_namespace_is_iorw_only():
    """Every mask in the candidate pool is a non-empty subset of
    {i, o, r, w}, in canonical i/o/r/w order."""
    valid = re.compile(r"^[iorw]+$")
    for mask in _NONEMPTY_MASKS:
        assert valid.match(mask), f"invalid mask atom: {mask}"
        # Each atom appears at most once and in canonical order.
        for prev, curr in zip(mask, mask[1:]):
            assert "iorw".index(prev) < "iorw".index(curr), (
                f"mask {mask!r} not in canonical i/o/r/w order"
            )
    # 2^4 - 1 = 15 non-empty subsets.
    assert len(_NONEMPTY_MASKS) == 15
    # No duplicates.
    assert len(set(_NONEMPTY_MASKS)) == 15


def test_e2e_burst_emits_diverse_pred_succ_pairs():
    """Generate a run with the stream injected and confirm the .S
    contains multiple distinct ``fence <pred>, <succ>`` lines."""
    target = get_target("rv32imc")
    cfg = make_config(
        target,
        gen_opts=(
            "+no_fence=0 "
            "+directed_instr_1=riscv_fence_burst_instr_stream,2"
        ),
    )
    cfg.seed = 42
    avail = create_instr_list(cfg)
    gen = AsmProgramGen(cfg=cfg, avail=avail, rng=_rnd.Random(42))
    lines = gen.gen_program()

    # Capture every ``fence <pred>, <succ>`` line from the stream.
    pat = re.compile(r"\bfence\s+([iorw]+)\s*,\s*([iorw]+)\b")
    pairs = []
    for L in lines:
        m = pat.search(L)
        if m:
            pairs.append((m.group(1), m.group(2)))

    # 2 stream blocks × 8..20 fences each → at least 16, often 30+.
    assert len(pairs) >= 10, f"expected ≥10 fences, got {len(pairs)}"
    # Diversity: at least 5 distinct (pred, succ) combos in a single run.
    assert len(set(pairs)) >= 5, (
        f"expected ≥5 distinct (pred, succ) combos, got {set(pairs)!r}"
    )


def test_e2e_no_fence_drops_the_stream():
    target = get_target("rv32imc")
    cfg = make_config(
        target,
        gen_opts=(
            "+no_fence=1 "
            "+directed_instr_1=riscv_fence_burst_instr_stream,3"
        ),
    )
    cfg.seed = 42
    avail = create_instr_list(cfg)
    gen = AsmProgramGen(cfg=cfg, avail=avail, rng=_rnd.Random(42))
    lines = gen.gen_program()

    # No stream block markers — and no pred/succ fence variants.
    assert not any("start riscv_fence_burst_instr_stream" in L.lower()
                   for L in lines)
    assert not any(re.search(r"\bfence\s+[iorw]+\s*,\s*[iorw]+", L)
                   for L in lines)
