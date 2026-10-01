"""Explicit fixed-pH mixed catalogue chemistry and a precipitation example."""
from flahax import (convert_catalogue_product_dose, solve_catalogue_product_doses,
                    calculate_equilibrium_ph)
from .common import catalogue, rejection, show


def run():
    products = catalogue()
    doses = {'Calcium Nitrate (ag grade)': .15,
             'Magnesium Sulfate (Heptahydrate)': .10,
             'Potassium Monobasic Phosphate': .05, 'Potassium Nitrate': .10,
             'Iron DTPA': .004, 'Iron EDDHA': .003, 'CH - micro': .005, 'Urea': .005}
    # Fixed pH is an imposed boundary, not a predicted pH of this recipe.
    mixed = solve_catalogue_product_doses(doses, 6.,
        water_totals={'Na+': .002, 'Cl-': .002}, allow_precipitation=False)
    # A dilute calcium/phosphate mixture with an imposed pH boundary.
    precipitation = solve_catalogue_product_doses(
        {'Calcium Nitrate (ag grade)': .4, 'Potassium Monobasic Phosphate': .1},
        7.4, allow_precipitation=True)
    return dict(assumptions=['Synthetic fixed-pH demonstrations, not the pepper mixture.',
                            'Product doses are g/kg-water, NOT g/L.',
                            'Aqueous-only SI diagnoses risk; positive SI is not an allocated solid.',
                            'Precipitation allocation uses a separate dilute calcium/phosphate case.'],
                catalogue_conversions_at_001_g_per_kg_water={
                    name: convert_catalogue_product_dose(product, .01)
                    for name, product in products.items()},
                product_doses_g_per_kg_water=doses, mixed=mixed.aqueous,
                precipitation=precipitation.aqueous,
                expected_davies_rejection=rejection(lambda: calculate_equilibrium_ph(
                    {'Na+': .2, 'Cl-': .2}, complete_analysis=True,
                    carbon_boundary='closed', phases=[])))


if __name__ == '__main__':
    show(run())
