import hashlib,json,unittest
from pathlib import Path
import jsonschema
root=Path(__file__).resolve().parents[1]
class Contract(unittest.TestCase):
 def test_original_schema(self):
  raw=(root/'src/sprint08-cinema-projection.json').read_bytes()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),'5a94b6c9f2196b31ba9c151188b31900d4fbd50c2c5ecda6e95efcdde639c329')
  schema=json.loads((root/'scripts/cinema-match-projection-v0.1.schema.json').read_bytes())
  jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(json.loads(raw))
if __name__=='__main__':unittest.main()
