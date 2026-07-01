# Interview Preparation Guide

Use these STAR+R stories for behavioural rounds. Practice each aloud — keep to 60-90 seconds.

---

## Story 1: Technical Problem-Solving (HPF Passband Droop)

**S:** M.Tech thesis on OTRA biquad filter — LPF and BPF matched simulation, but HPF showed unexplained passband droop of 4 dB.

**T:** Find root cause and fix it before thesis submission.

**A:** Built automated bias sweep across 4 VB1 operating points using ngspice + Python. Plotted gain vs bias voltage and noticed the droop only appeared at specific bias voltages. Traced it to the CMFB bias recovery circuit in the transistor-level OTRA — the bias mirror couldn't recover fast enough at high VB1.

**R:** Resolved to <1dB across all 3 responses. Published methodology in thesis (67 pages, DTU 2026).

**R:** Learned that transistor-level effects (finite output resistance, bias recovery) cause systematic deviations that ideal OTRA models miss. Systematic parameter sweeps catch what single-point simulation doesn't.

---

## Story 2: Building Tooling (AnalogCheck RAG)

**S:** While debugging netlists for thesis, realized that port-label swaps between Y1/Y5 admittance nodes simulate fine but produce wrong transfer functions — no standard tool catches this.

**T:** Build a reusable debugger that catches silent semantic SPICE errors.

**A:** Built token-split netlist parser in Python (no regex — too fragile for X devices). Added 5 deterministic checks (floating node, missing ground, M vs MEG, etc.). Then built a RAG pipeline indexing 20 common IC error patterns + PSpice reference into ChromaDB, so the LLM gets grounded context instead of guessing.

**R:** 35 chunks indexed, ~35ms retrieval. Integrated into CLI with --rag flag.

**R:** The combination of deterministic checks + RAG-enhanced LLM is a good pattern — the deterministic layer catches 70% of errors instantly, the LLM handles the ambiguous 30%.

---

## Story 3: Working Under Constraints (Thesis Timeline)

**S:** Had 3 months to complete verification of a single-OTRA filter at 3 abstraction levels.

**T:** Finish all 3 levels (behavioral, transistor, layout-extracted) within the deadline.

**A:** Prioritized: behavioral first (quick wins, validate topology), then transistor (found the droop), then layout-extracted (automatic with ngspice automation). Wrote a Python+Pytest testbench that could run all 3 comparisons in one command — let me iterate fast.

**R:** All 3 levels completed, thesis submitted on time (67 pages, clean compile).

**R:** Automation was the force multiplier — without the testbench, I'd have run each simulation manually and missed the deadline.

---

## Common technical questions

| Question | How to answer |
|----------|--------------|
| What is an OTRA? | Operational transresistance amplifier: V_out = R_m * (I_p - I_n). Inputs are currents (virtually grounded output). Unlike op-amp (V_in → V_out), OTRA maps current difference to voltage. |
| Why OTRA over op-amp? | No slew rate limitation, inherently wide bandwidth, no capacitive time constants at inputs. Better for high-frequency filters. |
| What is CFOA? AD844? | Current Feedback Op-Amp. AD844 is the commercial IC. Two AD844s make one OTRA. |
| What is RAG? | Retrieval-Augmented Generation. Vector DB (ChromaDB) stores domain docs. On query, retrieve relevant chunks → feed to LLM as context. Grounds the answer in real docs, not model knowledge. |
| How do you verify an op-amp? | DC op point (biasing), AC (gain/GBW/PM), transient (slew/settling), CMRR, PSRR, load stability, PVT corners, Monte Carlo. |
| Cadence flow? | Schematic → ADE L (simulation) → Layout XL → DRC → LVS → PEX → post-layout simulation. |
