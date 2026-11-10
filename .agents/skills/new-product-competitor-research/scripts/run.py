from common import *

FIELDS = ['asin','parent_asin','site','category_id','title','price','currency','sales',
          'sales_period','sales_scope','sales_source','sales_is_estimate','relevance',
          'review_status','reviewer','evidence','critical_conflict','discovery_type','seed_refs']

def main():
    ap=argparse.ArgumentParser(description='审核种子线索，按高相关和统一销量筛选Top20')
    ap.add_argument('--product', required=True)
    ap.add_argument('--seeds', required=True)
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--out', required=True)
    a=ap.parse_args(); p=load_json(a.product); context(p)
    rules=load_json(Path(__file__).resolve().parents[1]/'rules/rules.json')
    require(rules.get('target_asin_count')==20 and rules.get('family_policy')=='one_representative', '当前版本仅支持已确认的20个样本目标和单家族代表规则')
    require(bool(p.get('facts')) and bool(p.get('exclusions')), '请提供带证据的产品事实和排除边界；无排除项可明确写无')
    for f in p['facts']:
        require(all(f.get(k) for k in ['attribute','value','source']), '每个产品事实必须有attribute/value/source')
    for k in ['sales_period','sales_scope','sales_source','currency']:
        require(bool(p.get(k)), '缺少统一销量口径: '+k)
    require(p['sales_scope'] in ['child','parent'], 'sales_scope必须为child或parent')
    seeds=read_table(a.seeds,['seed_id','seed_type','value','relevance','review_status','evidence','reviewer'])
    approved={}; seed_ids=set()
    for r in seeds:
        require(r['seed_id'] and r['seed_id'] not in seed_ids, '种子ID为空或重复')
        seed_ids.add(r['seed_id'])
        require(r['relevance'] in ['high','medium','low','pending'], '未知种子relevance')
        require(r['review_status'] in ['approved','pending'], '未知种子review_status')
        require(r['seed_type'] in ['keyword','asin'], 'seed_type必须为keyword或asin')
        if r['review_status']=='approved' and r['relevance']=='high':
            require(bool(r['evidence']) and bool(r['reviewer']), '已批准种子需要理由和审核人')
            approved[r['seed_id']]=r
    require(approved, '没有已确认的高相关种子词/ASIN；先解析产品并审核种子线索')
    rows=read_table(a.candidates,FIELDS); eligible=[]; reviews=[]; seen=set(); warnings=[]
    for r in rows:
        require(r['relevance'] in ['high','medium','low','pending'], '未知候选relevance')
        require(r['review_status'] in ['approved','pending'], '未知候选review_status')
        r['asin']=asin(r['asin']); require(r['asin'] not in seen,'候选ASIN重复，请先合并来源: '+r['asin']); seen.add(r['asin'])
        if r['parent_asin']: r['parent_asin']=asin(r['parent_asin'])
        reasons=[]
        if r['site']!=p['site'] or r['category_id']!=p['category_id']: reasons.append('站点或品类不一致')
        if r['relevance']!='high' or r['review_status']!='approved': reasons.append('尚未批准为高相关')
        if not r['evidence'] or not r['reviewer']: reasons.append('缺少产品匹配依据或审核人')
        require(r['critical_conflict'] in ['yes','no','unknown'], 'critical_conflict必须为yes/no/unknown')
        if r['critical_conflict']!='no': reasons.append('存在关键属性冲突或未确认')
        refs=[v.strip() for v in r['seed_refs'].split('|') if v.strip()]
        if not refs or any(v not in approved for v in refs): reasons.append('缺少有效的已批准种子来源')
        require(r['discovery_type'] in ['keyword_result','seed_asin'], '未知discovery_type')
        if r['discovery_type']=='keyword_result' and not any(approved.get(v,{}).get('seed_type')=='keyword' for v in refs): reasons.append('关键词结果缺少种子词来源')
        if r['discovery_type']=='seed_asin' and not any(approved.get(v,{}).get('seed_type')=='asin' and approved[v]['value'].upper()==r['asin'] for v in refs): reasons.append('ASIN入口与种子ASIN不匹配')
        if any(r[k]!=str(p[k]) for k in ['sales_period','sales_scope','sales_source']): reasons.append('销量口径不一致')
        require(r['sales_is_estimate'] in ['yes','no','unknown'], 'sales_is_estimate必须为yes/no/unknown')
        n=number(r['sales'],'sales',optional=True)
        if n is None: reasons.append('缺少销量，不能参与销量排序')
        elif n != n.to_integral_value(): reasons.append('销量必须为整数件数')
        if r['sales_scope']=='parent' and not r['parent_asin']: reasons.append('父体销量缺少父ASIN')
        r['selection_reason']='；'.join(reasons)
        if reasons: reviews.append(r)
        else:
            r['_sales']=n; eligible.append(r)
    # 父体总销量不允许在同家族不同子体上出现矛盾。
    parent_sales={}
    for r in eligible:
        if p['sales_scope']=='parent':
            key=r['parent_asin']; require(key not in parent_sales or parent_sales[key]==r['_sales'], '同父体销量冲突: '+key); parent_sales[key]=r['_sales']
    eligible.sort(key=lambda r:(-r['_sales'],r['asin']))
    selected=[]; reserve=[]; families=set()
    for r in eligible:
        family=r['parent_asin'] or r['asin']
        if not r['parent_asin']: warnings.append(r['asin']+'父体未知，不能确认已完成家族去重')
        if family in families:
            r['selection_reason']='同父体替补'; reserve.append(r); continue
        families.add(family)
        if len(selected)<20:
            r['selection_reason']='高相关审核通过，按销量排序入选'; selected.append(r)
        else: r['selection_reason']='高相关但排序在Top20之后'; reserve.append(r)
    require(selected,'没有符合条件的候选ASIN；请处理审核/口径问题')
    if len(selected)<20: warnings.append('有效样本仅'+str(len(selected))+'个，未用中低相关竞品补足')
    out=output(a.out)
    for r in rows: r.pop('_sales',None)
    fields=FIELDS+['selection_reason']
    write_csv(out/'selected_asins.csv',fields,selected)
    write_csv(out/'reserve_asins.csv',fields,reserve)
    write_csv(out/'review_queue.csv',fields,reviews)
    write_csv(out/'seed_library.csv',list(seeds[0]),seeds)
    data={'schema':'new-product-research/1', 'product':p, 'selected_asins':selected,
          'selection_status':'provisional_pending_reverse_keyword_review', 'warnings':warnings}
    write_json(out/'research_context.json',data)
    write_json(out/'audit.json',audit([a.product,a.seeds,a.candidates]))
    print(json.dumps({'selected':len(selected),'reserve':len(reserve),'review':len(reviews),'warnings':warnings},ensure_ascii=False))

if __name__=='__main__': entry(main)
