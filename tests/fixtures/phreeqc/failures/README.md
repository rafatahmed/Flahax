# Preserved target-pH reduction and failure evidence

Run `python tools/debug_nitric_phreeqc.py` with the installed PHREEQC 3.8.6-17100. It uses `tools.phreeqc_evidence.merge`: temporary copy of `minteq.v4.dat`, remove its terminal END, append `database/flahax-chelates-25c.dat` and `database/flahax-phases-25c.dat`, then a new END. The base is never modified. Each stage JSON records executable, base and merged SHA-256, command, exit status and artifact hashes. Full PHREEQC convergence/error text is in `.out` and `.screen`, not truncated into a summary.

| Stage | Observation | Scientific interpretation |
|---|---|---|
| 01_macro_original | Failure without any chelate | `pH 7.4 charge` adjusts the initial pH down to about 2.501; HNO3 cannot raise it to 6 |
| 02_add_fe_dtpa_original | Same failure with Fe-DTPA | DTPA is not the source of the failure |
| 03_macro_sodium_balance | Converges | Balance Na at fixed initial pH instead of changing pH |
| 04_add_fe_dtpa_sodium_balance | Converges | Same correction works with the Fe-only ligand profile |
| 05_actual_products_sodium_balance | Converges, but different acid requirement | Native batch nitrogen redox oxidizes ammonium; this is not the runtime fixed-valence problem |

The corrected golden case is `../products/mixed_target_ph_nitric/`: both fixed-valence nitrate titration and an independent `Fix_H+` batch using USGS-style Amm decoupling converge and agree within the declared tolerance. No chelate family was added or dropped to force convergence.

`phase_calcium_phosphate_initial_charge/` retains a rejected insufficient-background-electrolyte attempt. The final phase case uses an explicitly larger NaCl inventory so Na charge balance is feasible. `phase_mixed_product_phases_initial_charge/` retains the converged-but-warning input with carbonate phases and zero inorganic carbon. The corrected generator selects phases only when their required conserved components are present, exactly as the runtime does; it does not drop any eligible phase.

`../preserved-evidence.json` protects every archived input/output and the original six converged chelate captures with SHA-256. These diagnostics are not counted as passing golden fixtures.
