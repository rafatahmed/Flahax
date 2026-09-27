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
(C18H20N2O6, 360.36 g/mol); Fe/Ca/Mg and four protonation constants are the 25 C
o,o-EDDHA profile of Yunta et al. (2003), also recorded in that source table.
Only its 1:1 Fe(III) complex is included. Ca, Mg, Mn, Zn, and Cu DTPA/EDDHA
complexes are deliberately excluded because no corresponding product is in the
FlahaX library.

`Dtp` and `Edd` are isolated custom PHREEQC components with master aqueous
species `Dtp-5` and `Edd-4`. They do not alter or override native carbon or
chelate entries.
