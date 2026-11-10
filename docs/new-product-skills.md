# 新品研究技能安装与验证

两个完整技能位于`.agents/skills/`，不依赖旧聊天文件。

- new-product-competitor-research：产品证据、种子词/ASIN审核、高相关销量Top20。
- competitor-keyword-root-builder：反查导入、相关性审核、同品类高相关去重关键词搜索量算术平均、单/双词根。

Python 3.10+可处理CSV；xlsx可选openpyxl。没有西柚连接时需要用户导出，不虚构接口。相关性由Agent提出、人工审核，脚本负责确定性数据处理。

验证命令（仓库根目录）：

```bash
python tests/test_new_product_skills.py
python .agents/skills/new-product-competitor-research/scripts/validate.py
python .agents/skills/competitor-keyword-root-builder/scripts/validate.py
```

使用包含本提交的分支启动新Codex任务，验证技能目录是否被发现；若未被自动列出，可显式要求读取对应SKILL.md按流程执行。请勿把“文件存在”当成“新对话已自动识别”。

虚构样例位于每个技能examples目录；真实资料请使用templates重新填写并审核。未接飞书、未配置密钥、不生成Bulk。本变更不修复云环境草稿接口的INVALID_ARGUMENT错误，该错误需在环境设置中另行诊断。
