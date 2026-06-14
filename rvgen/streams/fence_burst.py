"""Fence-burst directed stream — systematic FENCE ordering exploration.

Port forward of the SV TODO at ``riscv_instr.sv:286`` ("SV TODO: fence
combinations"). The default ``FENCE`` instruction in rvgen emits the
bare ``fence`` mnemonic, which encodes as ``fence rw, rw`` — i.e. the
most-restrictive ordering. Real-world cores need stimulus that
exercises every (predecessor-set, successor-set) combination so the
fence unit's ordering logic is verified across the full RVI spec
matrix (i / o / r / w on both sides).

This stream emits a burst of FENCE instructions with diverse
``<pred>, <succ>`` masks. Each fence is encoded as a hand-written
pseudo so we don't have to extend the FENCE Instr class itself.

Example output:

    fence rw, rw      # full barrier
    fence r,  w
    fence iorw, iorw  # I/O included
    fence w,  r
    ...

Register as ``riscv_fence_burst_instr_stream``. Honors
``cfg.no_fence`` via ``BANNED_BY``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from rvgen.isa.base import Instr
from rvgen.isa.enums import RiscvInstrName
from rvgen.streams import register_stream
from rvgen.streams.base import DirectedInstrStream
from rvgen.streams.directed import _LiPseudo


# Spec-defined mask atoms (RVI spec, Table 2.1).
# - i / o = device I/O reads / writes
# - r / w = memory reads / writes
_MASK_ATOMS = ("i", "o", "r", "w")


def _all_nonempty_masks() -> tuple[str, ...]:
    """Return every non-empty subset of {i, o, r, w} as a packed string.

    16 subsets total → 15 non-empty. The empty mask is technically legal
    (``fence , ,`` would order nothing) but most assemblers reject it,
    so we skip it.
    """
    out = []
    for bits in range(1, 1 << len(_MASK_ATOMS)):
        s = "".join(a for i, a in enumerate(_MASK_ATOMS) if bits & (1 << i))
        out.append(s)
    return tuple(out)


_NONEMPTY_MASKS = _all_nonempty_masks()


class _FencePseudo(_LiPseudo):
    """Hand-written ``fence <pred>, <succ>`` line.

    Carries the spec atoms as Python attrs so a future runtime sampler
    can attribute coverage back to which masks were active.
    """

    def __init__(self, pred: str, succ: str):
        super().__init__()
        self.instr_name = RiscvInstrName.FENCE
        self._fence_pred = pred
        self._fence_succ = succ

    def get_instr_name(self) -> str:
        return "fence"

    def convert2asm(self) -> str:
        body = f"fence{' ':>{8}}{self._fence_pred}, {self._fence_succ}"
        if self.comment:
            body = f"{body} #{self.comment}"
        return body


@dataclass
class FenceBurstInstrStream(DirectedInstrStream):
    """Emit a burst of FENCE instructions sweeping spec-defined orderings.

    ``num_fences`` controls the burst size. Each fence picks an
    independent (pred, succ) pair from the 15 non-empty subsets of
    {i, o, r, w}, so over a burst of 16+ fences the full spec matrix is
    sampled with high probability.
    """

    # FENCE is the entire payload — honor the user's no_fence knob.
    BANNED_BY: ClassVar[tuple[str, ...]] = ("no_fence",)

    num_fences: int = 0

    def build(self) -> None:
        if self.num_fences == 0:
            self.num_fences = self.rng.randint(8, 20)
        for _ in range(self.num_fences):
            pred = self.rng.choice(_NONEMPTY_MASKS)
            succ = self.rng.choice(_NONEMPTY_MASKS)
            self.instr_list.append(_FencePseudo(pred, succ))


register_stream("riscv_fence_burst_instr_stream", FenceBurstInstrStream)
