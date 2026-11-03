"""Validate existing public packages without retrieving schemas over the network."""
import json
import pathlib
import jsonschema
from referencing import Registry

root = pathlib.Path(__file__).resolve().parent.parent
web = root / 'products/ptti-web/public/data'
contracts = root / 'products/ptti-integration/contracts'
pairs = {
    'fan-inspiration-v0.1.json': 'fan-inspiration-v0.1.schema.json',
    'match-reports-v0.1.json': 'match-report-evidence-v0.1.schema.json',
    'goal17-official-match-video-additions.json': 'goal17-1-match-video-additions-v0.1.schema.json',
    'goal17-athlete-photo-additions.json': 'goal17-1-athlete-media-v0.1.schema.json',
    'match-library-strict-public.json': 'match-library-index-v0.1.schema.json',
    'web-strict-public.json': 'match-media-v0.2.schema.json',
    'pro-demo-match-intelligence.json': 'match-intelligence-v0.1.schema.json',
    'goal14-fan-content-strict-public.json': 'fan-content-intelligence-v0.1.schema.json',
}
results = []
for name, schema_name in pairs.items():
    schema = json.loads((contracts / schema_name).read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema, registry=Registry())
    validator.validate(json.loads((web / name).read_text(encoding='utf-8')))
    results.append({'public_file': name, 'schema': schema_name, 'status': 'PASS'})
(root / '.qa').mkdir(exist_ok=True)
(root / '.qa/main-schema-result.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
print('PASS: 8 public packages validate against unchanged MAIN schemas; no remote schema retrieval.')
