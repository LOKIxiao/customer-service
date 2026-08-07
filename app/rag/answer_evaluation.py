import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.agents.compliance_agent import ComplianceAgent
from app.agents.response_agent import ResponseAgent
from app.llm.factory import create_llm_client
from app.rag.factory import create_retriever


DEFAULT_DATASET = Path("data/eval/answer_qa.json")
DEFAULT_REPORT = Path("data/eval/answer_evaluation_report.json")
REFUSAL_MARKERS = ("没有相关信息", "未找到", "无法确认", "暂时没有", "无法回答", "联系人工客服")


def load_dataset(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def score_answer(case: dict[str, Any], answer: str) -> dict[str, Any]:
    """用人工标注的必要事实组和禁止事实做可复现的确定性评分。"""
    normalized = answer.casefold().replace(" ", "")
    answerable = bool(case["answerable"])

    if not answerable:
        refused = any(marker.casefold().replace(" ", "") in normalized for marker in REFUSAL_MARKERS)
        return {
            "completeness": 1.0 if refused else 0.0,
            "forbidden_hits": [],
            "refused": refused,
            "rule_passed": refused,
        }

    required_groups = case.get("required_facts", [])
    matched_groups = []
    for alternatives in required_groups:
        matched_groups.append(
            any(str(value).casefold().replace(" ", "") in normalized for value in alternatives)
        )

    forbidden_hits = [
        value
        for value in case.get("forbidden_facts", [])
        if str(value).casefold().replace(" ", "") in normalized
    ]
    completeness = sum(matched_groups) / len(matched_groups) if matched_groups else 1.0

    return {
        "completeness": completeness,
        "matched_required_facts": sum(matched_groups),
        "total_required_facts": len(matched_groups),
        "forbidden_hits": forbidden_hits,
        "refused": False,
        "rule_passed": completeness == 1.0 and not forbidden_hits,
    }


class LLMAnswerJudge:
    """可选的语义裁判；默认不启用，避免评测脚本自动产生外部调用费用。"""

    def __init__(self) -> None:
        load_dotenv()
        api_key = os.getenv("EVAL_JUDGE_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("EVAL_JUDGE_API_KEY or LLM_API_KEY is required for --llm-judge")

        self.client = ChatOpenAI(
            api_key=api_key,
            base_url=os.getenv("EVAL_JUDGE_BASE_URL") or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("EVAL_JUDGE_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0,
        )

    def judge(self, case: dict[str, Any], answer: str, contexts: list[str]) -> dict[str, Any]:
        prompt = f"""
你是严格的客服 RAG 回答评测员。只返回 JSON，不要输出解释性前后缀。

根据问题、知识库证据和人工标准答案，评估实际回答。
评分范围均为 0 到 1：
- correctness：事实是否正确
- faithfulness：实际回答中的事实是否都能被证据支持
- completeness：是否覆盖标准答案中的必要信息
- refusal_correct：无答案问题是否正确拒答；有答案问题填 true
- passed：correctness>=0.8、faithfulness=1、completeness>=0.8 且 refusal_correct=true

问题：{case['query']}
是否可回答：{case['answerable']}
标准答案：{case['reference_answer']}
知识库证据：{json.dumps(contexts, ensure_ascii=False)}
实际回答：{answer}

返回格式：
{{"correctness": 0.0, "faithfulness": 0.0, "completeness": 0.0, "refusal_correct": false, "passed": false, "reason": "简短原因"}}
""".strip()
        raw = self.client.invoke(prompt).content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        return json.loads(raw)


def evaluate_cases(
    cases: list[dict[str, Any]],
    split: str = "test",
    use_llm_judge: bool = False,
) -> dict[str, Any]:
    selected = [case for case in cases if split == "all" or case.get("split") == split]
    retriever = create_retriever()
    response_agent = ResponseAgent(create_llm_client())
    compliance_agent = ComplianceAgent()
    judge = LLMAnswerJudge() if use_llm_judge else None
    results = []

    for case in selected:
        chunks = retriever.retrieve(case["query"], top_k=3)
        contexts = [chunk.content for chunk in chunks]
        sources = [chunk.source for chunk in chunks]
        raw_reply = (
            "根据知识库内容：\n"
            + "\n\n".join(
                f"来源：{chunk.source}\n内容：{chunk.content}" for chunk in chunks
            )
            if chunks
            else "我暂时没有在知识库中找到相关信息，请你换个问法试试。"
        )
        generated = response_agent.generate(
            user_message=case["query"],
            intent="knowledge_base_query",
            raw_reply=raw_reply,
        )
        final_answer = compliance_agent.review(generated).response
        rule_result = score_answer(case, final_answer)
        expected_sources = case.get("expected_sources", [])
        source_hit = not expected_sources or all(source in sources for source in expected_sources)
        result = {
            "id": case["id"],
            "query": case["query"],
            "answerable": case["answerable"],
            "retrieved_sources": sources,
            "source_hit@3": source_hit,
            "answer": final_answer,
            "rule": rule_result,
        }
        if judge:
            result["llm_judge"] = judge.judge(case, final_answer, contexts)
        results.append(result)

    answerable_results = [result for result in results if result["answerable"]]
    unanswerable_results = [result for result in results if not result["answerable"]]
    rule_passes = sum(result["rule"]["rule_passed"] for result in results)
    source_hits = sum(result["source_hit@3"] for result in answerable_results)
    refusal_hits = sum(result["rule"]["refused"] for result in unanswerable_results)
    summary = {
        "split": split,
        "total": len(results),
        "answerable": len(answerable_results),
        "unanswerable": len(unanswerable_results),
        "source_hit@3": source_hits / len(answerable_results) if answerable_results else 0.0,
        "rule_answer_accuracy": rule_passes / len(results) if results else 0.0,
        "refusal_accuracy": refusal_hits / len(unanswerable_results) if unanswerable_results else 0.0,
        "llm_judge_enabled": use_llm_judge,
    }
    if judge:
        summary["llm_judge_pass_rate"] = (
            sum(result["llm_judge"]["passed"] for result in results) / len(results)
            if results
            else 0.0
        )

    return {"summary": summary, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate final RAG answers")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--split", choices=("dev", "test", "all"), default="test")
    parser.add_argument("--llm-judge", action="store_true")
    args = parser.parse_args()

    report = evaluate_cases(load_dataset(args.dataset), split=args.split, use_llm_judge=args.llm_judge)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report: {args.output}")


if __name__ == "__main__":
    main()
