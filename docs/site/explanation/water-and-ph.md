# Why FlahaX needs your water's pH

**Why calculate pH at all.** The acid you add depends on how strongly the
water and the fertilizers resist a pH change. Bicarbonate in well water is the
main buffer: the more of it, the more acid. FlahaX calculates the pH the mix
will have and the acid that brings it to your target, instead of a rule of
thumb, so it needs the water's composition and its measured pH.

**How the lab report's charge balance is used.** In a complete water analysis the positive charges (calcium,
magnesium, sodium, potassium) equal the negative ones (bicarbonate, chloride,
sulfate, nitrate). A lab report may contain a charge imbalance. FlahaX retains
the analysed ions and carries the imbalance as residual charge in its chemistry
calculation. The nutrient fit uses the reported water contributions. Titrated
alkalinity can supply carbon through the supported inorganic proton reference,
and an omitted chloride value remains unmeasured.

The interactive water interview flags a charge difference above 5% for review
and offers to correct a value, continue with the analysis, or start again.
Check units and missing measurements when reviewing that warning. The model
also reports its input and domain qualifications. RO water is an explicit
ion-free example.

[Total alkalinity and carbon inference](../models/total-alkalinity.md) explains
noncarbonate buffers, the supported proton reference and input limitations.
