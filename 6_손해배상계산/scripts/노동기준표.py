#!/usr/bin/env python3
"""engine/labor 모듈의 RULES·OPTIONS 로 `노동금액-계산기준.md` 를 다시 만든다.

    python scripts/노동기준표.py

규칙 요지·상태와 옵션 기본값은 코드가 원본이다. 문서를 손으로 고치지 말고 모듈을 고친 뒤 이 스크립트를 돌린다.
근거 판례 원문 인용은 각 모듈 머리 docstring 에 있다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.labor.calculate import MODULES  # noqa: E402

HEAD = """# 노동 금액 계산 기준

> 자동 생성본 — `python scripts/노동기준표.py`. 원본은 `engine/labor/*.py` 의 `RULES`·`OPTIONS` 와 머리 docstring 이다.

엔진은 법적 판단(통상임금성, 해고 무효, 다툼의 적절성, 사용촉진 적법성)을 하지 않는다. 사람이 사건.yaml 에 판정해 넣은 값으로
계산만 한다. 규칙 상태가 **불명확**이거나 옵션 기본값이 '없음'인 곳은 판례가 갈리거나 확인되지 않은 지점이다.
기본값이 없는 옵션은 결과가 달라질 때 엔진이 멈추고 선택을 요구한다. 불명확 규칙으로 정한 금액은 서면·검토의견에서 단정하지 않는다
(루트 공통 규칙).

## 검증 방식

- 2026. 9. 15. LBOX 판례·결정례·유권해석과 국가법령정보센터 조문으로 영역별 조사 후, 별도 검증자가 인용 원문을 대조하고 산식을 반박해 본 판정을 반영했다.
- 판결문에 숫자가 남아 있는 사례는 `tests/test_labor_*.py` 에서 판결 숫자로 재현한다. 재현하지 못한 사례와 사유는 테스트 주석과 모듈 docstring 에 있다.
- 해고기간 임금의 연 20% 지연이자(개정 근로기준법 제37조 제1항 제2호, 2025. 10. 23. 시행)는 1심 판결이 갈리고 고법·대법원 판단이 없어, 계산표에 대안 결과를 함께 낸다.
- 대법원 계산프로그램이 없는 영역이므로 법원 제출 전 담당자가 입력값과 계산표를 검산한다.

## 모듈과 순서

| 절 | 모듈 | 받는 값 | 넘기는 값 |
|---|---|---|---|
| `ordinary` | ordinary.py | — | 통상시급, 1일 통상임금 |
| `overtime` | overtime.py | 통상시급 | 월별 증가 임금, 원금 항목 |
| `leave` | leave.py | 1일 통상임금 | 원금 항목 |
| `average_wage` | average.py | 1일 통상임금, 월별 증가 임금 | 1일 평균임금 |
| `retirement` | retirement.py | 1일 평균임금 | 원금 항목 |
| `dismissal` | dismissal.py | 1일 평균임금, 1일 통상임금 | 원금 항목, 근로관계 종료 사실 |
| `interest` | interest.py | 모든 원금 항목 | 지연손해금 구간·금액·문구, 소멸시효 만료일 |
"""


def main() -> None:
    lines = [HEAD]
    for section, label, mod in MODULES:
        lines.append(f"\n## {label} (`{section}:` / {Path(mod.__file__).name})\n")
        lines.append("| 규칙 | 요지 | 상태 |\n|---|---|---|")
        for rid, (summary, status) in mod.RULES.items():
            mark = f"**{status}**" if "불명확" in status else status
            lines.append(f"| {rid} | {summary.replace('|', '/')} | {mark} |")
        lines.append("\n| 옵션 | 기본값 | 규칙 | 선택지 |\n|---|---|---|---|")
        for key, spec in mod.OPTIONS.items():
            default = "없음(선택 필수)" if spec.default in (None, "unset") else f"`{spec.default}`"
            choices = "; ".join(f"`{k}` {v}" for k, v in spec.choices.items()) if spec.choices else spec.description
            lines.append(f"| `{key}` | {default} | {spec.rule} | {choices.replace('|', '/')} |")
    out = ROOT / "노동금액-계산기준.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
