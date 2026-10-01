"""User-supplied pepper targets; do not invent a complete water analysis."""
from flahax import VolumeLitres, plan_fertilizer_workflow, solve_weights
from .common import catalogue, show
from .pepper_stock_review import review

TARGETS = dict(N_NO3=128, N_NH4=0, P=58, K=211, Ca=104, Mg=40, S=54,
               Fe=5, Mn=2, Zn=.3, B=.7, Cu=.1, Mo=.1, Na=0)
NAMES = ['Boric Acid', 'Calcium Nitrate (ag grade)', 'Iron II Sulfate (Hepahydrate)',
         'Mg Nitrate', 'Mn EDTA', 'Potassium Nitrate', 'Copper Sulfate (pentahydrate)',
         'Potassium Sulfate', 'Zinc Sulfate (Monohydrate)', 'Sodium Molybdate (Dihydrate)',
         'Potassium Monobasic Phosphate', 'Phosphoric Acid (75%)']


def run():
    products = catalogue()
    salts = [products[name] for name in NAMES]
    water = {ion: 20 if ion == 'Ca' else 0 for ion in TARGETS}
    workflow = plan_fertilizer_workflow(salts, TARGETS, water, 6.5,
                                       final_volume=VolumeLitres(1000))
    assert workflow.nutrient_gap['Ca'] == 84
    assert workflow.stages['chemistry'].status == 'needs_input'
    return dict(
        assumptions=['1000 L illustrative final batch; targets and water in mg/L.',
                     'No invented chloride, alkalinity, acid density or measured titration curve.',
                     'Catalogue Phosphoric Acid (75%) P assay needs commercial-grade confirmation.',
                     'NH4/Na additions require separate review, not automatic zero-target failure.'],
        targets_mg_per_l=TARGETS, water_mg_per_l=water, workflow=workflow,
        stock_allocation_review=review(workflow.recommendation, 1000),
        alternative_raw_least_squares=solve_weights(salts, TARGETS, water))


if __name__ == '__main__':
    show(run())
