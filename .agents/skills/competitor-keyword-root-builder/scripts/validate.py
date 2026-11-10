from pathlib import Path
import ast, json, re, sys
base=Path(__file__).resolve().parents[1]
needed=['SKILL.md','scripts/run.py','scripts/common.py','rules/rules.json','references/workflow.md','references/input-format.md','references/sources.md','agents/openai.yaml']
errors=[]
for rel in needed:
    if not (base/rel).is_file(): errors.append('missing: '+rel)
for p in (base/'scripts').glob('*.py'):
    try: ast.parse(p.read_text(encoding='utf-8'))
    except SyntaxError as e: errors.append(str(e))
try:
    t=(base/'SKILL.md').read_text()
    if not t.startswith('---\n') or not re.search(r'^name: [a-z0-9-]+$',t,re.M): errors.append('invalid SKILL metadata')
    json.loads((base/'rules/rules.json').read_text())
except Exception as e: errors.append(str(e))
if errors:
    print('\n'.join(errors));sys.exit(1)
print('结构、语法及JSON检查通过；业务行为测试请运行总包tests/test_pipeline.py。')
