---
name: competitor-keyword-root-builder
description: 反查已筛选竞品流量词，按新品证据审核高中低相关，复核竞品，并以同品类高相关去重关键词搜索量算术平均划分高低搜索量，提炼英文单词根和相邻双词根；为新品词根广泛、精准Test和ASIN研究提供候选库。
---

# 竞品流量词反查、分层与词根构建

先读 references/workflow.md、references/input-format.md；输入上一技能的research_context.json。没有前序文件时先补齐产品依据和竞品审核，不能直接把陌生ASIN当已选竞品。

## 执行步骤
1. 按初选ASIN从西柚实际已授权接口或用户导出获取词。保留原始文件、站点、周期、指标定义和来源；不假设第三方词是竞品真实广告搜索词。
2. 结合上游产品事实，逐词提出high/medium/low/pending相关性，记录依据；品牌/ASIN专项标记，不能仅按是否含种子词机械判断。人工批准后才能进入正式分层和词根库。
3. 用目标关键词覆盖、流量相关性和产品差异复核全部初选竞品。输出保留/排除/待确认及原因，不设置未确认的重叠阈值。填competitor_review.csv；待确认与排除ASIN不进入最终统计。如需换ASIN，回上游重建批次，不能静默改旧结果。
4. 执行确定性脚本。基准严格等于同品类、同站点、同周期、同指标、同来源中已审核高相关关键词搜索量之和÷有效搜索量的去重词数。无额外权重，禁止按ASIN/家族覆盖加权。
5. 相同标准词只计一次；不同ASIN同一词搜索量不叠加；冲突报错。缺失不计入分子分母，真实0参与。若无有效样本则停止，不输出伪基准。
6. >=基准为high搜索量，<为low；缺失unknown。三种相关性都对比同一基准，品牌/ASIN及未审核项单列；不得把高搜索量解释为高转化。
7. 从已批准high/medium通用词中提炼英文单词和原始相邻双词，分别记录相关性。先建邻接窗口再过滤停用词，不跨停用词拼接；默认不删s归一，已确认词形在rules/token_map中维护。保留non/not/no等否定意义，纯数字单独不成投放词根，数字单位仍保留在完整关键词供审核。
8. 展示独立关键词/ASIN/家族覆盖及来源，不设最低频次，不合成词根搜索量。所有词根是待审候选，不自动等于可投放词。

## 命令
```bash
python scripts/run.py --research ../research-001/research_context.json --keywords templates/keywords.csv --competitor-review templates/competitor_review.csv --out runs/keywords-001
```
路径改为真实文件。CSV零依赖；xlsx可选openpyxl。v1英文分词；其他语言需另配规则。

## 下游
词根广泛：审核后的单/双词根；精准Test：审核后的完整关键词；ASIN抓取蹭流：复核后的ASIN还需单独审核投放适配；自动抓录：后续架构模块设置。当前不分预算、不出竞价、不出Bulk、不自动否定。
