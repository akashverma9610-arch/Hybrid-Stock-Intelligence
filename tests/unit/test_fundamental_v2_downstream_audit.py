import json
from pathlib import Path

from app.fundamentals.diagnostic_comparability import content_fingerprint
from scripts.audit_fundamental_v2_downstream import audit


def test_receipt_is_replayed_not_asserted_and_inventory_covers_live_boundaries():
    # Historical source bytes stay immutable; current live behavior is replayed
    # by audit and the subsequent Brain-lineage safety tests.
    checkpoint='01593df3d89c57d982f67b25bf8819281474d9ff'
    value=audit(preserved_source_revision=checkpoint)
    assert value==audit(preserved_source_revision=checkpoint)
    assert value==json.loads(Path('docs/architecture/FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_RECEIPT.json').read_text())
    assert value['fingerprint']==content_fingerprint({k:v for k,v in value.items() if k!='fingerprint'})
    assert value['explicit_values_equal'] and value['thesis_equality'] and value['weights_unchanged']
    assert value['preserved_app_files']==543 and not value['v2_active']
    assert [r['rule_id'] for r in value['shadow_rejections']]==[16,17,19,25,26,29]
    assert all(r['score'] is None for r in value['shadow_rejections'])
    inventory=json.loads(Path('docs/architecture/FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_INVENTORY.json').read_text())
    paths={row[0] for row in inventory['sites']}
    assert {'app/scoring/engine.py','app/diagnostics/synthesis.py','app/portfolio/holding_intelligence.py',
            'app/portfolio/canonical_six_gates_activation.py','app/gates/engine.py','app/crowd/engine.py'} <= paths
    assert all(Path(path).is_file() for path in paths)
