from common import *
from collections import defaultdict

FIELDS=['asin','site','category_id','period','source','metric','keyword','search_volume',
        'relevance','term_type','review_status','reviewer','evidence']

def main():
    ap=argparse.ArgumentParser(description='按同品类高相关去重关键词算术平均分层，并构建英文词根候选')
    ap.add_argument('--research',required=True)
    ap.add_argument('--keywords',required=True)
    ap.add_argument('--competitor-review',required=True)
    ap.add_argument('--rules',default=str(Path(__file__).resolve().parents[1]/'rules/rules.json'))
    ap.add_argument('--out',required=True)
    a=ap.parse_args(); research=load_json(a.research); p=research['product']; context(p)
    require(research.get('schema')=='new-product-research/1','不支持的研究上下文版本')
    selected={r['asin']:r for r in research['selected_asins']}
    require(selected,'没有入选ASIN')
    reviews=read_table(a.competitor_review,['asin','decision','reviewer','reason'])
    keep=set(); seen=set()
    for r in reviews:
        aid=asin(r['asin']); require(aid in selected and aid not in seen,'复核ASIN不在样本内或重复: '+aid); seen.add(aid)
        require(r['decision'] in ['keep','exclude','pending'],'复核decision必须为keep/exclude/pending')
        require(bool(r['reviewer']) and bool(r['reason']), '竞品复核需要审核人和理由')
        if r['decision']=='keep': keep.add(aid)
    require(seen==set(selected),'必须对所有初选ASIN进行反查复核')
    require(keep,'没有复核保留的竞品')
    rows=read_table(a.keywords,FIELDS); groups={}; source_rows=[]; skipped=[]
    for r in rows:
        aid=asin(r['asin']); require(aid in selected,'关键词来源不属于初选样本: '+aid)
        for rk,pk in [('site','site'),('category_id','category_id'),('period','keyword_period'),('source','keyword_source'),('metric','keyword_metric')]:
            require(r[rk]==p[pk], '关键词口径不一致: '+rk+' / '+aid)
        require(r['relevance'] in ['high','medium','low','pending'],'未知relevance')
        require(r['term_type'] in ['generic','brand','asin','pending'],'未知term_type')
        require(r['review_status'] in ['approved','pending'],'未知review_status')
        if r['review_status']=='approved': require(bool(r['reviewer']) and bool(r['evidence']),'已审核关键词缺少审核人或依据')
        k=normalized(r['keyword']); require(bool(k),'关键词不能为空')
        volume=number(r['search_volume'],'search_volume',optional=True)
        r['keyword_normalized']=k
        if aid not in keep: skipped.append(r); continue
        source_rows.append(r)
        signature=(r['relevance'],r['term_type'],r['review_status'])
        if k not in groups: groups[k]={'signature':signature,'volume':volume,'asins':set(),'originals':set(),'evidence':set()}
        g=groups[k]
        require(g['signature']==signature,'同一去重关键词的审核分类冲突: '+k)
        if volume is not None:
            require(g['volume'] is None or g['volume']==volume,'同一周期、同一去重词搜索量冲突，需先核实: '+k)
            g['volume']=volume
        g['asins'].add(aid);g['originals'].add(r['keyword']);g['evidence'].add(r['evidence'])
    # 严格按用户确认的高相关去重关键词口径；不额外按类型或覆盖数加权/排除。
    baseline_values=[g['volume'] for g in groups.values() if g['signature'][0]=='high' and g['signature'][2]=='approved' and g['volume'] is not None]
    require(baseline_values,'缺少同品类、已审核高相关关键词的有效搜索量，无法计算基准')
    total=sum(baseline_values,Decimal(0)); count=len(baseline_values)
    baseline=total/Decimal(count)
    rules=load_json(a.rules)
    require(rules.get('baseline_method')=='arithmetic_mean_high_relevance_unique_keywords','基准规则与已确认口径不一致')
    stop=set(rules['stopwords']); mapping=rules.get('token_map',{})
    for x,y in mapping.items(): require(re.fullmatch('[a-z0-9]+',x) and re.fullmatch('[a-z0-9]+',y),'token_map仅允许已确认的单词对单词映射')
    protected={normalized(x) for x in rules.get('protect_roots',[])}
    keywords=[]; root_groups={}; root_evidence=[]; pending=[]
    for k,g in sorted(groups.items()):
        rel,typ,status=g['signature'];v=g['volume'];families={selected[x]['parent_asin'] or x for x in g['asins']}
        band='unknown' if v is None else ('high' if v*count>=total else 'low')
        row={'keyword':k,'originals':' | '.join(sorted(g['originals'])),'relevance':rel,'term_type':typ,
             'review_status':status,'search_volume':'' if v is None else str(v),'search_band':band,
             'asin_coverage':len(g['asins']),'family_coverage':len(families),'source_asins':'|'.join(sorted(g['asins'])),
             'evidence':' | '.join(sorted(g['evidence']))}
        keywords.append(row)
        if not (status=='approved' and typ=='generic' and rel in ['high','medium']): continue
        if re.search(r'[^\x00-\x7f]',k): pending.append({'keyword':k,'reason':'非英文字符，需人工分词'});continue
        # 先在原始顺序构建相邻窗口，再过滤停用词，避免跨停用词拼接。
        tokens=k.split(); tokens=[mapping.get(t,t) for t in tokens]
        valid=lambda t: bool(re.fullmatch('[a-z0-9]+',t)) and t not in stop and not t.isdigit() and len(t)>1
        roots={(t,1) for t in tokens if valid(t)}
        roots.update((' '.join(tokens[i:i+2]),2) for i in range(len(tokens)-1) if all(valid(t) for t in tokens[i:i+2]))
        for root,n in roots:
            key=(root,rel)
            if key not in root_groups: root_groups[key]={'n':n,'keywords':set(),'asins':set(),'families':set(),'variants':set()}
            rg=root_groups[key];rg['keywords'].add(k);rg['asins'].update(g['asins']);rg['families'].update(families);rg['variants'].update(g['originals'])
            for aid in sorted(g['asins']): root_evidence.append({'root':root,'word_count':n,'relevance':rel,'keyword':k,'asin':aid,'parent_asin':selected[aid]['parent_asin']})
    root_rows=[]
    for (root,rel),g in root_groups.items():
        root_rows.append({'root':root,'word_count':g['n'],'relevance':rel,'keyword_coverage':len(g['keywords']),
             'asin_coverage':len(g['asins']),'family_coverage':len(g['families']),
             'asin_coverage_rate':len(g['asins'])/len(keep),'protected':'yes' if root in protected else 'no',
             'status':'candidate_requires_review','examples':' | '.join(sorted(g['keywords'])[:5])})
    root_rows.sort(key=lambda r:(0 if r['relevance']=='high' else 1,-r['family_coverage'],-r['asin_coverage'],-r['keyword_coverage'],r['root']))
    warnings=[]
    if len(keep)<20: warnings.append('最终有效竞品'+str(len(keep))+'个；覆盖率分母使用实际数量')
    unknown=[x for x in keep if not selected[x]['parent_asin']]
    if unknown: warnings.append('部分父体未知，family_coverage使用ASIN临时代替，不能视为完成家族去重')
    out=output(a.out)
    kfields=['keyword','originals','relevance','term_type','review_status','search_volume','search_band','asin_coverage','family_coverage','source_asins','evidence']
    write_csv(out/'keyword_library.csv',kfields,keywords)
    for rel in ['high','medium','low']:
        for band in ['high','low']:
            write_csv(out/f'keywords_{rel}_relevance_{band}_volume.csv',kfields,[r for r in keywords if r['relevance']==rel and r['search_band']==band and r['review_status']=='approved' and r['term_type']=='generic'])
    write_csv(out/'keyword_review_and_special.csv',kfields,[r for r in keywords if r['review_status']!='approved' or r['term_type']!='generic' or r['search_band']=='unknown' or r['relevance']=='pending'])
    rfields=['root','word_count','relevance','keyword_coverage','asin_coverage','family_coverage','asin_coverage_rate','protected','status','examples']
    for n in [1,2]: write_csv(out/f'roots_{n}_word.csv',rfields,[r for r in root_rows if r['word_count']==n])
    write_csv(out/'root_evidence.csv',['root','word_count','relevance','keyword','asin','parent_asin'],root_evidence)
    write_csv(out/'tokenization_review.csv',['keyword','reason'],pending)
    write_csv(out/'excluded_competitor_keywords.csv',FIELDS,skipped)
    data={'schema':'new-product-keywords/1','product':p,'formula':'sum(high_relevance_unique_keyword_volumes) / count(high_relevance_unique_keywords_with_volume)',
          'baseline':str(baseline),'baseline_numerator':str(total),'baseline_denominator':count,
          'baseline_scope':'approved high-relevance keywords, one category/site/source/metric/period',
          'effective_asins':sorted(keep),'warnings':warnings,'keywords':keywords,'roots':root_rows,'source_rows':source_rows,
          'status':'research_candidates_not_bulk_or_bid_recommendations'}
    write_json(out/'keyword_context.json',data)
    write_json(out/'audit.json',audit([a.research,a.keywords,a.competitor_review,a.rules]))
    print(json.dumps({'baseline':str(baseline),'baseline_count':count,'keywords':len(keywords),'roots':len(root_rows),'warnings':warnings},ensure_ascii=False))

if __name__=='__main__': entry(main)
