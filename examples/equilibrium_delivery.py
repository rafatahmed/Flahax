"""One synthetic water -> recipe -> equilibrium -> acid -> stocks -> pump plan."""
from datetime import datetime, timezone
from flahax import (VolumeLitres, InjectionRatio, StockTank, TemperatureCelsius,
                    plan_fertilizer_workflow, plan_pump_command, compose_delivery_plan,
                    transition_plan, delivery_report)
from .common import catalogue, record, show


def run():
    salt = catalogue()['Potassium Nitrate']
    acid_products = [record(formula, chemicalFormula=formula, massFraction=.5,
                            densityKgPerL=1.2)
                     for formula in ('HNO3', 'H3PO4')]
    # Separate reagent records: the comparative candidates use arbitrary 50%
    # products; the legacy HNO3 delivery adapter uses nitrate-N assay instead.
    nitric = record('nitric-delivery', name='Synthetic nitric acid', kind='acid',
                     chemicalFormula='HNO3', elements={'N_NO3':13.8}, densityKgPerL=1.4)
    workflow = plan_fertilizer_workflow([salt], {'K':10}, {}, 6.5,
        final_volume=VolumeLitres(100),
        maximum_concentrations={'N_NO3':10, 'P':1, 'S':1},
        equilibrium=dict(water_totals={}, water_mass_kg=100,
                         water_analysis_id='synthetic-pure-water', complete_analysis=True,
                         carbon_boundary='closed', temperature_c=25, phases=[]),
        acids=dict(products=acid_products, maximum_nutrient_error_percent=1,
                   maximum_reagent_volume_litres=.1, preferred_product_id='HNO3'),
        nitric=dict(reagent=nitric, reagent_channel_id='acid',
                    maximum_reagent_volume=VolumeLitres(.1), maximum_nutrient_error_percent=1),
        stocks=dict(injection_ratio=InjectionRatio(100), tanks=[StockTank('A', VolumeLitres(2))],
                    compatibility_rules=[], temperature=TemperatureCelsius(25),
                    solubility_limits=[record('synthetic-kno3-limit', productId=salt['id'],
                        maxGramsPerLitre=50, temperatureMinC=20, temperatureMaxC=30)]))
    ph_plan = workflow.stages['nitric'].value
    calibration = record('synthetic-pump', channelId='acid', stockDensityKgPerL=1.4,
        testTemperatureC=25, flowLitresPerMinute=.001, standardDeviationLitresPerMinute=.00001,
        validMinLitres=1e-9, validMaxLitres=.1)
    command = plan_pump_command(calibration, VolumeLitres(ph_plan.reagent_volume_litres),
        VolumeLitres(1), as_of=datetime(2026, 9, 28, tzinfo=timezone.utc))
    draft = compose_delivery_plan(workflow.stages['batch'].value, workflow.stages['stocks'].value,
                                   ph_plan, [command], {'modelVersion':'synthetic-example'})
    validated = transition_plan(draft, 'validated')
    # Deliberately do not manufacture an operator-approved state or execute I/O.
    return dict(assumptions=['Synthetic pure-water/KNO3 scenario; not pepper chemistry.',
                            '100 kg FINAL solvent inventory, including reagent carrier water; 100 L final volume.',
                            'All acid assays, density, limits and calibration are fictional teaching inputs.',
                            'Fixed as_of date demonstrates reproducibility, not current calibration validity.',
                            'Aqueous-only, 25 C, closed carbon; no automatic hardware control.'],
                workflow=workflow, calibration=calibration,
                delivery=validated, human_report=delivery_report(validated))


if __name__ == '__main__':
    show(run())
