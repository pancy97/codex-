# 输入字段与算法精确定义

keywords.csv一行为ASIN-关键词来源记录。asin必须属于上一阶段初选；site/category_id/period/source/metric与product上下文完全一致。keyword是原词，search_volume为非负数或空白，不能带千位逗号或K/M缩写。每个词需要relevance（high/medium/low/pending）、term_type（generic/brand/asin/pending）、review_status（approved/pending）、reviewer和evidence。
相关性参考：high为产品直接购买意图且关键属性不冲突；medium为适用场景/相邻需求但不够明确；low为已确认需求不符；pending为信息不足。generic是通用品类词，品牌和ASIN单列审核，不自动转成否定；若被明确批准为高相关且有有效搜索量，按统一公式参与基准。

competitor_review.csv每个初选ASIN一行：decision为keep/exclude/pending，附reviewer和reason。所有ASIN都必须有复核记录；只有keep参与最终统计。不要把“反查没返回”直接当没有流量。

基准按标准化后的唯一词计算：只纳入approved/high且search_volume非空的词；缺失不计，真实0计入。相同词跨ASIN出现仅计一次。如果多个非空搜索量冲突（包括0对非0）则报错；单条缺失但同口径其他来源ASIN提供该词有效数值时可复用该值。同一词分类冲突也报错。
比较时使用精确分子分母：volume*count >= sum归高，不受显示小数舍入影响。覆盖率分母是复核keep的实际ASIN数量。家族未知用ASIN临时替代并警告。

双词提取基于标准化文本的原词顺序，不跨停用词。符号转空格，连字符词需人工复核原文；已知商品型号/单位必须结合产品审核，不会仅据词形自动判断可投。
roots_1_word.csv和roots_2_word.csv在同相关性内按家族/ASIN/关键词覆盖排序；保护词仅来自配置的显式名单。候选库仍需审核，不设自动投放阈值。没有词根也能输出分层结果和提示表，不制造词根。
