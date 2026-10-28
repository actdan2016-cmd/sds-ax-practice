# eval.py - 평가 세트 자동 채점
import json
from langchain import rag_chain, retriever

PASS_THRESHOLD = 4   # 2일차 성공 기준: 5문항 중 4문항 이상 정답

with open("eval_set.json", encoding="utf-8") as f:
    eval_set = json.load(f)

passed = 0
for item in eval_set:
    hits = retriever.invoke(item["question"])
    sources = sorted({h.metadata["source"] for h in hits})

    if item["expected_source"] is None:
        # no_answer 유형: 체인이 '찾을 수 없다'고 거절하는지로 채점
        answer = rag_chain.invoke(item["question"])
        ok = "찾을 수 없" in answer
    else:
        # 기대 출처가 검색 결과 상위 k개 안에 있는지로 채점
        ok = item["expected_source"] in sources

    passed += ok
    mark = "통과" if ok else "실패"
    print(f"[{mark}] ({item['type']}) {item['question']}")
    print(f"       기대: {item['expected_source']} / 실제 검색: {sources}")

print(f"\n정답 {passed}/{len(eval_set)}문항")
if passed >= PASS_THRESHOLD:
    print(f"[성공 기준 통과] {PASS_THRESHOLD}문항 이상 정답입니다.")
else:
    print(f"[성공 기준 미달] {PASS_THRESHOLD}문항 이상 필요합니다. {PASS_THRESHOLD - passed}문항 더 맞혀야 합니다.")