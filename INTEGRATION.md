# Connecting FlahaX to FlahaFAST

This repository is the Python package. FlahaFAST does not contain a copy. The application calls FlahaX only when `FLAHAX_RECOMMENDATIONS=true`. With the variable unset, Water → Crop → Salts → Recipe → Results is unchanged.

The server runs `python -m flahax` with `PYTHONPATH` set to the package `src` directory.

1. `FLAHAX_SRC`, when it is set.
2. A sibling checkout, `../Flahax/src`, when this app is started from `FlahaFast/server`.
3. The older in-app folder `flahax/src`, if a copy is still on disk.

On the production host the installed tree is `/var/www/flahafast.flaha.org/flahax/src`. Set `FLAHAX_SRC` to that path in `server/.env`. Updating the package is a copy from this repository. It is not part of the FlahaFAST deploy archive.

## What must already be true

FlahaX needs the crop targets after the user confirms Crop, and the water ions after the user confirms Water. Both exist only when the user reaches Salts. The salts pre-checked today come from the formula record. That is not a FlahaX result.

Recipe weighs whatever salts were confirmed. If an accepted FlahaX mix is thrown away there and solved again, the recommendation is lost. The grams travel with the salts only when the user accepted them.

A saved run is never rewritten.

## Start without a gap

One switch, default off: `FLAHAX_RECOMMENDATIONS`.

While it is off, every screen is the current flow. No new request, no new button, no change to Open results.

While it is on:

1. Salts asks for a recommendation only after water and the formula are both saved. The call is allowed to fail. A non-zero exit, including total `N`, an unknown ion, or a negative ppm, is shown as that error. The formula’s own salt ticks stay as they are.
2. The recommendation is a panel, not a new stage. **Use this combination** is available only when `feasible` is true. It replaces the selection and stores the grams on the draft. A restricted salt is added only when a requested ion finished short and that salt can supply it. An overshoot does not bring in chloride or borax. Warnings name salts that remain in the result. When the fit stays outside 1%, the panel names the ions that missed. **Keep my salts** leaves the selection untouched and stores nothing from FlahaX.
3. Recipe, if and only if the draft says the user accepted, uses those grams as the salt amounts and does not solve them again. A/B and pH stay optional and unchanged. If the user did not accept, Recipe solves as it does now.
4. Open results saves the balance that Recipe actually produced. The snapshot may record `flahaxAccepted: true` or `false`. It does not replace the result with a new solve at save time.
5. History analysis, for a saved run with `flahaxAccepted` not true, may show the recommendation beside the saved balance. If that call fails, the history page omits the panel. The saved numbers stay.

## What not to do in the first connection

Do not block Salts while the recommendation loads. Do not change Crop, Water, or the formula row in the database. Do not auto-accept. Do not run FlahaX inside Open results. Do not deploy the Python package inside the Node process until the salt panel has been tried with the switch on and with the switch off.

The join is `python -m flahax`. Stdin is `{targets, water, salts}`. `salts` are the fertilizer rows saved in FlahaFAST, including any the user added. The JSON file inside this package is an example for the tests and is not read by that command. Version 0.2.0 still rejects total `N`, and grams may be accepted only when `feasible` is true. A non-zero exit is an error message, not an empty success.
