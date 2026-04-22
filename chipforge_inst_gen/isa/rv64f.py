"""RV64F registrations — port of ``src/isa/rv64f_instr.sv``."""

from __future__ import annotations

from chipforge_inst_gen.isa.enums import (
    RiscvInstrCategory as C,
    RiscvInstrFormat as F,
    RiscvInstrGroup as G,
    RiscvInstrName as N,
)
from chipforge_inst_gen.isa.factory import define_instr
from chipforge_inst_gen.isa.floating_point import FloatingPointInstr


for _n in (N.FCVT_L_S, N.FCVT_LU_S, N.FCVT_S_L, N.FCVT_S_LU):
    define_instr(_n, F.I_FORMAT, C.ARITHMETIC, G.RV64F, base=FloatingPointInstr)
