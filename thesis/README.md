# Single-OTRA Multifunctional Biquad Filter — M.Tech Thesis

**Technologies:** Cadence Virtuoso, ngspice, 180nm CMOS, Python, Pytest
**Timeline:** 2025-2026
**Location:** `Z:\sushant\sim\thesis\`

## What it does

Verifies a single-OTRA biquad filter at three abstraction levels (behavioral → transistor → layout-extracted). Demonstrates LPF, BPF, and HPF responses from the same topology using Mann 2021 passive-admittance mapping.

## Key finding

Identified **HPF passband droop root cause** via systematic VB1 bias sweep across 4 operating points — a CMOS bias-recovery issue that ideal models don't capture. Resolved to <1dB. Validated all 3 responses against published targets.

## Architecture

```
Behavioral OTRA (E/F sources)
  → fast functional verification of LPF/BPF/HPF
  → match published targets (f0, gain, Q)

Transistor OTRA (180nm CMOS, BSIM4)
  → VB1 bias sweep → found passband droop
  → CMFB stability analysis
  → bias recovery window characterization

Layout-extracted (post-PEX)
  → parasitic-aware verification
  → validate against pre-layout results
```

## Key files

| File | Purpose |
|------|---------|
| `thesis_main.tex` | Full thesis LaTeX source (67 pages) |
| `thesis_main.pdf` | Compiled PDF |
| `spice/netlists/` | LPF, BPF, HPF CMOS netlists (.cir) |
| `spice/results/` | ngspice .txt output files |
| `Figures/fig_combined.png` | Combined gain plot (LPF+BPF+HPF up to 100MHz) |

## STAR+R Interview Story

**Situation:** M.Tech thesis on OTRA biquad filter verification at DTU. Published reference design showed ideal transfer functions with published performance specs.

**Task:** Validate all 3 responses (LPF, BPF, HPF) at behavioral, transistor, and layout-extracted levels. Identify any discrepancies.

**Action:** Built automated ngspice+Pytest testbench. Performed systematic VB1 bias sweep across 4 operating points. Isolated HPF passband droop to bias recovery circuit in the CMFB loop.

**Result:** Resolved droop to <1dB. All 3 responses validated within 8% of published targets. Developed reusable verification methodology.

**Reflection:** Learned that transistor-level effects (bias recovery, finite output resistance) cause systematic deviations that ideal models miss — and that systematic parameter sweeps are the most reliable way to find them.

## Resume bullet

> *"Verified single-OTRA biquad filter at behavioral, transistor, and layout-extracted levels in 180nm CMOS; built automated ngspice+Pytest testbench; identified HPF passband droop root cause via systematic VB1 sweep, resolved to <1dB."*