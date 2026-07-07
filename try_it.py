# 교권119 직접 체험 — 서버 없이 로컬에서 도구를 하나씩 눌러본다.
# 실행(내 터미널에서):  cd C:\Users\chaey\gyogwon-mcp   →   python try_it.py
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import mcp_server as M

TOOLS = [
    ("emotional_support", "🚨 마음 지지 (상담)", [("feeling", "지금 마음/상황")]),
    ("check_guidance_legality", "🛡️ 지도단계 적법성 체크", [("intended_action", "하려는 조치(예: 반성문 쓰게 하려고요)")]),
    ("safe_parent_message", "🛡️ 학부모 대화 안전", [("situation", "상황(선택, 엔터로 건너뜀)"),
                                                ("parent_message", "학부모가 한 말(선택)"),
                                                ("teacher_draft", "내 답장 초안(선택)")]),
    ("guide_response_flow", "📋 침해 대응 절차 안내", [("current_stage", "현재 상황(선택)"),
                                               ("infringement_type", "침해 유형(선택)")]),
    ("draft_statement", "📋 진술서·경위서 초안", [("who", "누가"), ("when", "언제"),
                                           ("where", "어디서"), ("what", "무엇을(말·행동)"),
                                           ("infringement_type", "유형(선택)")]),
    ("defend_child_abuse", "📋 아동학대 신고 방어", [("situation", "상황(선택)")]),
    ("search_teacher_law", "📋 법령 조회(라이브)", [("law_name", "법령명(예: 교원지위법)"),
                                             ("article_no", "조 번호(예: 19, 없으면 목차)")]),
    ("verify_citation", "📋 인용 법조항 진위 검증", [("law_name", "상대가 든 법령명(예: 아동복지법)"),
                                          ("article_no", "조 번호(예: 17)"),
                                          ("claimed_content", "상대 주장 내용(선택)")]),
    ("route_support", "📋 지원기관 연결", [("situation_type", "유형(폭행/성범죄/아동학대신고/악성민원/심리소진/법률)")]),
    ("guide_complaint_response", "📋 악성민원 응대", [("situation", "상황(선택)")]),
    ("guide_student_guidance", "📋 생활지도 근거 검색", [("situation", "상황(예: 수업 중 자는 학생)")]),
    ("review_statement", "📋 진술서·경위서 검토", [("document", "검토할 진술서·경위서 내용 붙여넣기")]),
]


def main():
    print("=" * 56)
    print("  교권119 체험 — 번호를 고르고 질문을 입력하세요")
    print("  (선택 항목은 그냥 엔터로 건너뛰면 돼요)")
    print("=" * 56)
    while True:
        print()
        for i, (_, label, _a) in enumerate(TOOLS, 1):
            print(f" {i:2}. {label}")
        print("  0. 종료")
        sel = input("\n번호> ").strip()
        if sel in ("0", "q", "quit", "exit"):
            print("\n수고하셨어요! 🌱")
            break
        if not sel.isdigit() or not (1 <= int(sel) <= len(TOOLS)):
            print("→ 1~%d 사이 번호를 입력하세요." % len(TOOLS))
            continue
        name, label, args = TOOLS[int(sel) - 1]
        kwargs = {}
        for k, prompt in args:
            v = input(f"  {prompt}: ").strip()
            if v:
                kwargs[k] = v
        try:
            result = getattr(M, name)(**kwargs)
        except Exception as e:
            result = f"(오류: {e})"
        print("\n" + "─" * 56)
        print(result)
        print("─" * 56)


if __name__ == "__main__":
    main()
