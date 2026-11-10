#!/usr/bin/env python3
"""SessionStart 훅: 이 레포에 끝나지 않은 과제 문서가 있으면 세션 맥락에 알린다.

진행 기록은 에이전트가 남겨야 생기고, 남겨도 다음 세션이 읽지 않으면 소용없다.
읽는 쪽을 구조로 보장한다 — 세션이 시작될 때 과제 목록을 먼저 보여 준다.
기록을 쓰게 강제하지는 않는다(언제 남길지는 판단이 필요하다). 판단할 수 없으면 조용히 통과한다(fail-open).
"""
import json
import os
import sys
from pathlib import Path

KNACK = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
LIMIT = 5

GUIDE = ("이 레포에 끝나지 않은 과제 문서 {n}건 ({base}):\n{items}\n"
         "사용자 요청이 이 과제와 관련 있으면 코드를 고치기 전에 `knack work status <slug>` 와 과제 문서를 읽고 이어서 한다. "
         "다른 에이전트가 작업 중인 단계는 건드리지 말고 사용자에게 확인한다. "
         "승인·결정·막힘·인계는 `knack work log` 로 남긴다. 관련 없는 요청이면 무시한다.")


def main():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        data = {}
    try:
        sys.path.insert(0, os.path.join(KNACK, "lib"))
        import work

        cwd = Path((data.get("cwd") if isinstance(data, dict) else None) or os.getcwd())
        base, items = work.open_tasks(cwd)
    except Exception:
        return
    if not items:
        return
    shown = ["  - " + i for i in items[:LIMIT]]
    if len(items) > LIMIT:
        shown.append(f"  - … 외 {len(items) - LIMIT}건 (knack work list)")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": GUIDE.format(n=len(items), base=base, items="\n".join(shown))}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
