# FlahaX 25 C chelate extension

This extension is appended to the unmodified USGS PHREEQC 3.8.6
`minteq.v4.dat` database only when reference fixtures are generated. It uses
the PHREEQC convention `log_k = log10(a_product / a_reactants)` at 25 C.
It is restricted to the Davies runtime domain, I <= 0.1 mol/kgw.

`minteq.v4.dat` ends with the PHREEQC database `END` keyword. The fixture
generator removes only that final keyword in its temporary merged copy, adds
this extension, and writes a new final `END`. Appending after `END` is invalid:
PHREEQC silently ignores the additional master species. The installed base
database is never copied into the repository or modified.

`Dtp-5` represents the Iron DTPA product (C14H23N3O10, 393.35 g/mol). Only
the 1:1 Fe(III)-DTPA reaction and five protonation constants are included.
`Edd-4` represents the Iron EDDHA product, selected o,o-EDDHA
(C18H20N2O6, 360.36 g/mol); four protonation constants and the selected Fe
stability value define the project's 25 C o,o-EDDHA profile.
Only its 1:1 Fe(III) complex is included. Ca, Mg, Mn, Zn, and Cu DTPA/EDDHA
complexes are deliberately excluded because no corresponding product is in the
FlahaX library.

`Dtp` and `Edd` are isolated custom PHREEQC components with master aqueous
species `Dtp-5` and `Edd-4`. They do not alter or override native carbon or
chelate entries.

## Provenance and interpretation

- [Yunta et al. (2003), Inorganic Chemistry 42, 5412–5421](https://doi.org/10.1021/ic034333j) reports EDDHA protonation/metal-equilibrium measurements. The selected rac-o,o protonation steps are 11.88, 10.80, 8.67, 6.28 (cumulative 11.88, 22.68, 31.35, 37.63). These are also tabulated in [López-Rayo's primary research thesis, reproducing the 2010 article table 2](https://repositorio.uam.es/bitstream/handle/10486/14129/66236_lopez%20rayo%20sandra.pdf?isAllowed=y&sequence=1).
- [Smith and Martell's critical compilation](https://doi.org/10.1016/0048-9697(87)90127-6) and [NIST SRD 46 documentation](https://www.nist.gov/system/files/documents/srd/46_8.htm) identify the DTPA stability-data family. The retained project profile uses five protonation steps 10.48, 8.60, 4.28, 2.60, 2.00 and Fe(III) log beta 28.60.
- These are **selected project-profile parameters**, not a claim of newly established infinite-dilution thermodynamic constants. Published measurements use specified supporting electrolytes; stereoisomer composition and activity/concentration conventions matter. The inherited EDDHA Fe value 35.10 is rounded. No undocumented concentration-to-activity correction has been applied. PHREEQC and runtime deliberately use exactly the same selected values and reaction convention. Numerical equivalence verifies that implementation, not experimental calibration of a commercial lot. The owner-amended [G6 computational assessment](../computational-review.md) does not require laboratory work for the planning-package release; independent chemical/bench validation is not claimed.

## Genuinely absent phase definitions

`flahax-phases-25c.dat` supplies only the following missing phase entries; native trace phases are not redefined:

| Phase | Source at 25 C | Dissolution log K |
|---|---|---:|
| Struvite | [Ronteltap, Maurer and Gujer (2007), standard solubility product](https://doi.org/10.1016/j.watres.2006.11.046) | -13.26 |
| Kieserite | Installed USGS PHREEQC 3.8.6 `pitzer.dat`, Kieserite reaction | -0.123 |
| Sylvite | Installed USGS PHREEQC 3.8.6 `phreeqc.dat`, Sylvite reaction | 0.9 |

The Kieserite equilibrium constant is transferred, **not** the Pitzer activity parameters or a high-salinity validity claim. All three retain explicit water stoichiometry and unit solid activity. `Ure = Ure` is a neutral inventory identity, not a fitted reaction. Exact source names/lines and equations are in the generated coverage matrix.
