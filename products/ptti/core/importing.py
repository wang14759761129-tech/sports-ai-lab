"""Schema detection never mixes before-score and after-score conventions."""
import csv
import io
from core.engine import ingest
from core.adapters.protocol_v0_3 import convert,ADAPTER_VERSION

def import_csv(raw):
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),strict=True)
        headers=reader.fieldnames or []; original=list(reader)
    except (UnicodeError,csv.Error):
        rows,report=ingest(raw);return rows,report,dict(source_schema='unrecognized',original_points=[])
    historical=bool({'game_number','point_winner','server_score_before'} & set(headers))
    modern=bool({'game','winner','score_a','score_b'} & set(headers))
    provenance=dict(source_schema='protocol_v0_3' if historical else '1.0.0-new',source_repository='sports-ai-lab' if historical else None,source_revision='1b30e8ea0f8a90a745fb6c30105599f0334fdf7c' if historical else None,adapter_version=ADAPTER_VERSION if historical else None,original_points=original,conversion_warnings=[])
    if (historical and modern) or len(headers)!=len(set(headers)) or any(None in r or any(v is None for v in r.values()) for r in original):
        return [],dict(valid=False,row_count=len(original),issues=[dict(level='error',row=1,field='csv',message='CSV 混合两种协议、表头重复或行列数量错误；请使用单一完整格式。')]),provenance
    rows,report=convert(original) if historical else ingest(raw)
    if historical: provenance['conversion_warnings']=[i for i in report['issues'] if i['level']=='warning']
    return rows,report,provenance
