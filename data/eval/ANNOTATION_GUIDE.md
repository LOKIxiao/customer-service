# 检索评测人工复核说明

`retrieval_qa.json` 当前是待人工复核的挑战集草稿。不要仅因为脚本能够运行，就把标签描述为“人工标注完成”。

## 复核步骤

1. 只阅读 `query`，先判断知识库是否能够回答。
2. 在知识库中寻找能够直接支持完整答案的最小 Chunk 集合。
3. 核对 `answerable`、`expected_sources` 和 `expected_chunk_ids`。
4. 多证据问题必须确认每个标注 Chunk 都不可缺少；可被单个 Chunk 完整回答时应降为单证据。
5. 无答案问题要确认不是措辞没对上，而是知识库确实没有该事实。
6. 完成复核后，才把该条 `annotation_status` 从 `draft_pending_human_review` 改为 `human_verified`。

建议由一人初标、另一人复核有争议的样本，并记录修改原因。至少检查所有多证据样本、无答案样本，以及检索失败样本，避免错误标签人为压低 Recall。

## 指标口径

- 单证据：正确 Chunk 出现在 Top K 即命中。
- 多证据：`match_mode=all`，全部正确 Chunk 都出现在 Top K 才命中。
- 无答案：不进入 Recall/MRR 分母，只计算 Retriever 是否返回空结果的拒答准确率。
- 来源级指标用于诊断检索到哪篇文档；面试和项目结论应优先报告证据级指标。

运行 `scripts/build_retrieval_eval.py` 会重新生成挑战集，并将状态重置为待人工复核，因此不要在人工复核完成后直接覆盖文件。
