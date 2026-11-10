import argparse, csv, json, re, sys, hashlib, unicodedata
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

VERSION = '1.0.0'

def require(ok, message):
    if not ok: raise ValueError(message)

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def read_table(path, required):
    p = Path(path)
    if p.suffix.lower() == '.xlsx':
        try: from openpyxl import load_workbook
        except ImportError: raise ValueError('读取xlsx需要openpyxl；也可以另存为UTF-8 CSV，无需安装依赖')
        wb = load_workbook(p, read_only=True, data_only=True)
        try:
            it = iter(wb.active.values); header = next(it, ())
            header = [str(x).strip() if x is not None else '' for x in header]
            rows = [dict(zip(header, row)) for row in it if any(x is not None for x in row)]
        finally: wb.close()
    else:
        with p.open(encoding='utf-8-sig', newline='') as f:
            r = csv.DictReader(f); header = r.fieldnames or []; rows = list(r)
    require(len(header) == len(set(header)), '存在重复列名')
    require(set(required) <= set(header), '缺少列: ' + ', '.join(sorted(set(required)-set(header))))
    return [{k: '' if v is None else str(v).strip() for k, v in row.items() if k} for row in rows]

def number(v, label, optional=False):
    if v == '' and optional: return None
    try: n = Decimal(str(v))
    except InvalidOperation: raise ValueError(label + '必须是数字，不接受逗号、百分号、K/M缩写')
    require(n.is_finite() and n >= 0, label + '必须是有限非负数字')
    return n

def normalized(s):
    s = unicodedata.normalize('NFKC', s).casefold()
    s = re.sub(r'[^\w\s]', ' ', s)
    return ' '.join(s.split())

def asin(s):
    s = s.upper()
    require(bool(re.fullmatch('[A-Z0-9]{10}', s)), 'ASIN格式不正确: ' + s)
    return s

def context(p):
    for k in ['product_id','site','category_id','keyword_period','keyword_source','keyword_metric','keyword_language']:
        require(isinstance(p.get(k), str) and bool(p[k].strip()), '产品上下文缺少: ' + k)
    require(p['keyword_language'] == 'en', 'v1仅支持英文词根提取；其他语言需另配分词器')

def output(path):
    p = Path(path)
    require(not p.exists(), '输出目录已存在；请使用新目录，避免覆盖历史版本: '+str(p))
    p.mkdir(parents=True)
    return p

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def write_csv(path, fields, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader()
        for row in rows:
            # 仅在给人阅读的CSV中防止Excel将外部文本当公式执行；JSON保留真实原文。
            w.writerow({k: "'"+str(v) if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for k,v in row.items()})

def audit(paths):
    return {'version':VERSION, 'created_utc':datetime.now(timezone.utc).isoformat(),
            'inputs':[{'file':Path(p).name, 'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in paths]}

def entry(fn):
    try: fn()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        print('ERROR: '+str(e), file=sys.stderr); sys.exit(2)
