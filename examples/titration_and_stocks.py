"""Fictional measured-curve records and two-tank compatibility demonstration."""
from flahax import (VolumeLitres, InjectionRatio, StockTank, TemperatureCelsius,
                    plan_ph, final_solution_recipe, plan_stocks)
from .common import catalogue, record, rejection, show


def run():
    water = record('water', ions={'Ca':20}, temperatureC=25, pH=7.4, alkalinityMgLAsCaCO3=120)
    reagent = record('nitric', name='Synthetic nitric acid', kind='acid',
                      elements={'N_NO3':13.8}, densityKgPerL=1.4,
                      normalityMeqPerL=1.4*1e6*.138/14.0067)
    curve = record('curve', waterAnalysisId='water', reagentId='nitric', points=[
        {'demandMeqPerL':0, 'pH':7.4}, {'demandMeqPerL':1.2, 'pH':6.0}])
    def titrate(ph):
        return plan_ph(water, curve, reagent, ph, VolumeLitres(100), VolumeLitres(1),
                       {'N_NO3':100}, {'N_NO3':110})
    products = catalogue()
    selected = [products[n] for n in ('Calcium Nitrate (ag grade)', 'Potassium Monobasic Phosphate')]
    recipe = final_solution_recipe({'feasible':True, 'salts':[
        {'id':p['id'], 'name':p['name'], 'gramsPerLitre':dose}
        for p, dose in zip(selected, (.5, .25))]}, VolumeLitres(100))
    rules = [record('separate', productIds=[p['id'] for p in selected], constraint='separate',
                    reason='Synthetic separation rule for API demonstration',
                    temperatureMinC=20, temperatureMaxC=30)]
    limits = [record(p['id']+'-limit', productId=p['id'], maxGramsPerLitre=100,
                      temperatureMinC=20, temperatureMaxC=30) for p in selected]
    def stocks(tanks):
        return plan_stocks(recipe, InjectionRatio(100), tanks, rules, limits, TemperatureCelsius(25))
    return dict(assumptions=['Curve points, stock limits and separation rules are fictional, not measurements.',
                            'Stock recipe is prescribed to illustrate assignment, not optimized for pepper.',
                            'The supplied curve applies to its matching water/reagent, not a proven final fertilizer pH.',
                            'Measure after mixing; actual stocks require sourced compatibility/solubility records.'],
        water=water, reagent=reagent, curve=curve, titration=titrate(6.5),
        expected_outside_curve=rejection(lambda: titrate(5.5)),
        stock_recipe=recipe, compatibility_rules=rules, solubility_limits=limits,
        stocks=stocks([StockTank('A',VolumeLitres(2)), StockTank('B',VolumeLitres(2))]),
        expected_insufficient_tanks=rejection(lambda: stocks([StockTank('A',VolumeLitres(2))])))


if __name__ == '__main__':
    show(run())
