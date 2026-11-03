import json
import subprocess
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]

class MatchV1ContractTests(unittest.TestCase):
    def test_all_real_matches_validate_schema(self):
        script="""import {readFileSync} from 'node:fs'; import {createMatchContract} from './runtime/match-contract-v1.mjs'; const p=JSON.parse(readFileSync('./generated/sprint08-cinema-projection-v0.1.json','utf8')); process.stdout.write(JSON.stringify(p.matches.map(m=>createMatchContract(p,m.match_id))));"""
        output=subprocess.check_output(['node','--input-type=module','-e',script],cwd=ROOT)
        records=json.loads(output);self.assertEqual(len(records),8)
        schema=json.loads((ROOT/'contracts/match-contract-v1.schema.json').read_text(encoding='utf-8'))
        validator=Draft202012Validator(schema,format_checker=FormatChecker())
        for record in records: validator.validate(record)
        bad=records[0].copy();bad['media_sha256']='f'*64
        self.assertFalse(validator.is_valid(bad))

if __name__=='__main__':unittest.main()
