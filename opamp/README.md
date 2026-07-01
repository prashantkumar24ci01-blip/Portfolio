# Two-Stage CMOS Operational Amplifier

**Technologies:** 180nm CMOS (theoretical design + layout plan)
**Timeline:** 2026

## What it does

Miller-compensated two-stage CMOS op-amp design exercise covering the full design flow: topology selection → transistor sizing → DC/AC/transient verification plan → layout strategy.

## Topology

- Differential input pair (NMOS)
- Current-mirror active load (PMOS)
- Common-source second gain stage
- Current-mirror bias branch
- Miller compensation capacitor

## Verification plan

| Analysis | What it verifies |
|----------|-----------------|
| DC operating point | Bias currents, VDS saturation margins |
| AC (gain/phase) | DC gain, GBW, phase margin |
| Transient (step) | Slew rate, settling time |
| Output swing | Rail-to-rail capability |
| CMRR | Common-mode rejection |
| PSRR | Supply noise rejection |
| Load stability | Capacitive load tolerance |
| Power | Static + dynamic consumption |

## Layout practices mapped

- Symmetric differential pair (common-centroid)
- Current mirror matching (interdigitation)
- Dummy devices for edge effects
- Guard rings for substrate isolation
- Short high-impedance routing (minimize parasitic C)

## Resume bullet

> *"Designed Miller-compensated two-stage CMOS op-amp with differential pair, current-mirror load, and common-source gain stage. Defined DC/AC/transient verification plan covering gain, GBW, phase margin, slew rate, CMRR, PSRR, and load stability."*
