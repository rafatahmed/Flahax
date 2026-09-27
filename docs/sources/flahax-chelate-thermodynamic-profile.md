# FlahaX 25 C chelate extension

This extension is appended to the unmodified USGS PHREEQC 3.8.6
`minteq.v4.dat` database only when reference fixtures are generated. It uses
the PHREEQC convention `log_k = log10(a_product / a_reactants)` at 25 C.
It is restricted to the Davies runtime domain, I <= 0.1 mol/kgw.

`Dtp-5` represents DTPA (C14H23N3O10, 393.35 g/mol). The Fe, Ca, Mg, Mn, Zn,
and Cu formation constants and five protonation constants are the
25 C Martell and Smith stability-constant profile recorded in
`catalogue_chemistry.py`. `Edd-4` represents selected o,o-EDDHA
(C18H20N2O6, 360.36 g/mol); Fe/Ca/Mg and four protonation constants are the 25 C
o,o-EDDHA profile of Yunta et al. (2003), also recorded in that source table.

`Dtp` and `Edd` are isolated custom PHREEQC components with master aqueous
species `Dtp-5` and `Edd-4`. They do not alter or override native carbon or
chelate entries.
