# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Import, approve and replay a Sonneveld batch from the mix
interview.
"""

from copy import deepcopy
import json

from . import VolumeLitres, plan_fertilizer_workflow
from .batch_cli import read_json
from .canonical_result import seal_summary
from .delivery_contracts import DeliveryError
from .evaluated_remedies import available_product_search
from .grower_report import summarize_batch
from .sonneveld import design_targets

REQUIRED = {
    'title',
    'sonneveld',
    'final_volume_litres',
    'target_ph',
    'water',
    'equilibrium',
    'salts',
    'alternative_products',
    'maximum_concentrations',
    'ph_adjustment',
    'volumetric_stocks',
}


def check_batch_session(session):
    """Validate the embedded, self-contained batch inputs."""
    profile = session['sonneveld_batch']
    if (
        not isinstance(profile, dict)
        or set(profile) != REQUIRED
        or not isinstance(profile['title'], str)
        or not profile['title'].strip()
        or not isinstance(profile['alternative_products'], list)
        or not isinstance(profile['sonneveld'], dict)
        or 'root_zone_feedback' not in profile['sonneveld']
        or set(session) - {'sonneveld_batch', 'selected_candidate', 'saved_state'}
    ):
        raise DeliveryError('invalid_session', 'Invalid Sonneveld batch profile')
    if 'saved_state' in session and not isinstance(session.get('selected_candidate'), str):
        raise DeliveryError('invalid_session', 'Saved Sonneveld batch needs a reviewed candidate')


def approve_batch(prompts, resource):
    """Review the imported sample and confirm the exact design before
    formulation.
    """
    profile = read_json(resource, 'Sonneveld batch profile')
    session = {'sonneveld_batch': profile}
    check_batch_session(session)
    design = profile['sonneveld']
    sample = design['root_zone_feedback']
    if isinstance(sample, dict):
        sample.pop('approval', None)  # an imported profile always needs interactive review
    preview = design_targets(design)
    feedback = preview['root_zone_feedback']
    lines = [
        f'{key}: measured {value:g}, guide {feedback["guide_mmol_l"][key]:g} mmol/L'
        for key, value in feedback['measured_mmol_l'].items()
        if key in feedback['guide_mmol_l']
    ]
    lines += [f'{key}: no guide' for key in feedback['without_guide']]
    lines += [f'{key}: no measurement' for key in feedback['without_measurement']]
    lines += [
        f'{key}: feed adjustment {value:+g} mmol/L'
        for key, value in design['adjustments_mmol_l'].items()
    ]
    lines += [
        f'{key}: finished target {value:.8g} mmol/L'
        for key, value in preview['columns_mmol_l']['D'].items()
    ]
    for offset in range(0, len(lines), 6):
        for line in lines[offset : offset + 6]:
            prompts.say(line)
        if prompts.choose(
            f'Review root-zone sample {feedback["sample_id"]} ({feedback["sampled_on"]})',
            ('Continue review', 'Stop'),
        ):
            raise KeyboardInterrupt
    sample['approval'] = {
        'approved_by': prompts.text('Approve this feed preview as grower'),
        'reason': prompts.text('Reason for approving the feed adjustments'),
        'design_sha256': feedback['design_sha256'],
    }
    return prompts.text('Save these answers as', profile['title']), session


def calculate_batch(session):
    """Run the common recipe search and verify the selected rounded
    preparation.
    """
    profile = deepcopy(session['sonneveld_batch'])
    title, target_input = profile.pop('title'), profile.pop('sonneveld')
    alternatives = profile.pop('alternative_products')
    litres = profile.pop('final_volume_litres')
    design = design_targets(target_input, require_approval=True)
    workflow = plan_fertilizer_workflow(
        **profile,
        targets=design['targets_mg_l'],
        final_volume=VolumeLitres(litres),
        remedy_options=(available_product_search(alternatives),) if alternatives else (),
        max_remedy_evaluations=4,
    )
    search = workflow.remedies
    candidate_id = search.get('best_verified_candidate_id')
    if candidate_id is not None:
        record = next(option for option in search['options'] if option['id'] == candidate_id)
        inputs = json.loads(record['snapshot'])['inputs']
        inputs['final_volume'] = VolumeLitres(inputs['final_volume']['value'])
        workflow = plan_fertilizer_workflow(**inputs)
        products = inputs['salts']
    else:
        products = profile['salts']
    stage = workflow.stages['volumetric_stocks']
    if stage.status != 'calculated':
        raise DeliveryError('invalid_value', stage.message or 'No verified rounded preparation')
    candidate = candidate_id or 'original'
    identity = workflow.canonical_result.result_id
    if session.get('selected_candidate', identity) != identity:
        raise DeliveryError('stale_session', 'Rounded candidate changed; import and review again')
    summary = summarize_batch(
        workflow,
        products,
        title=title,
        water_label=profile['equilibrium']['water_analysis_id'],
    )
    summary['sonneveld_target_design'] = design
    summary['remedies'] = search
    summary['selected_preparation_candidate'] = candidate
    return seal_summary(summary)


def save_reviewed_batch(prompts, store, name, session, summary):
    """Let the grower adopt the verified preparation and save its
    calculation identity.
    """
    candidate = summary['selected_preparation_candidate']
    label = (
        'Use verified original recipe' if candidate == 'original' else 'Use verified alternative'
    )
    rounded = summary['volumetric_stocks']
    prompts.say(f'Modeled pH {rounded["ph"]:.5f}; all declared preparation checks passed.')
    prompts.say('See the rounded product weights and stock volumes on the results screen.')
    if not prompts.choose('Choose the preparation to use', ('Stop', label)):
        raise KeyboardInterrupt
    store.save(
        'sessions',
        name,
        session | {'selected_candidate': summary['calculation_identity']['result_id']},
    )
