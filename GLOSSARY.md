# FlahaX

FlahaX plans one batch of hydroponic nutrient solution: one crop formula and one water give one recipe, plus the acid or base that sets the pH.

## Language

**Formula**:
A crop's target nutrient concentrations (mg/L).
_Avoid_: Nutrient solution, program, mix

**Recipe**:
The product weights chosen to meet a formula from a given water.
_Avoid_: Blend, result, plan

**Catalogue**:
The packaged products and formulas.
_Avoid_: Library, database

**pH reagent**:
A catalogue product used only to move pH.
_Avoid_: Acid, base, adjuster

**Label reconciliation**:
The charge a product label's ions cannot balance, reported and not refused.
_Avoid_: Label check, identity check, charge gate

**Ammonium allowance**:
The incidental NH₄-N, capped at 10 % of total N and 1.5 mmol/L, permitted when no NH₄ target is declared.
_Avoid_: Ammonium ban, zero ammonium

**Precipitation risk**:
A warning label from a phase whose constant is measured and which is known to form readily.
_Avoid_: Saturation block, precipitation gate

**EC range**:
The low–high conductivity estimate, with no midpoint.
_Avoid_: EC value, mean EC, estimated EC

**Stated model condition**:
A limit reported with the result, such as closed carbon, 25 °C or 1 L of solution taken as 1 kg of water.
_Avoid_: Declaration, assumption to confirm

**Tank A / Tank B**:
The two stock tanks: calcium and micronutrients in A, the sulfates and phosphates in B.
_Avoid_: Part A / Part B, Stock 1 / Stock 2
