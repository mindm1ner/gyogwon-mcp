# 교권119 회귀 테스트 하네스 — 12개 도구를 정상·엣지·악의·빈입력·초장문으로 두들겨
# 크래시 / 빈손(빈 응답) / 과대 응답을 잡는다.  실행: python test_all.py
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import mcp_server as M

LONG = "가" * 5000          # 초장문
MAXLEN = 9000               # 이 이상이면 응답 과대 경고

# (도구, 인자, 라벨)
CASES = [
    ("emotional_support", {"feeling": ""}, "빈입력"),
    ("emotional_support", {"feeling": "다 그만두고 싶어요"}, "위기"),
    ("emotional_support", {"feeling": "안녕하세요 오늘 뭐하지"}, "무관(오작동 확인)"),
    ("check_guidance_legality", {"intended_action": ""}, "빈입력"),
    ("check_guidance_legality", {"intended_action": "학생을 때리려고요"}, "악의:체벌"),
    ("check_guidance_legality", {"intended_action": "지각생 방과후 남기기"}, "비하드코딩"),
    ("safe_parent_message", {}, "무입력"),
    ("safe_parent_message", {"situation": "체육 중 다쳤는데 손해배상 청구하고 욕함"}, "복합"),
    ("safe_parent_message", {"situation": LONG}, "초장문"),
    ("guide_response_flow", {}, "무입력"),
    ("guide_response_flow", {"infringement_type": "폭행"}, "범죄유형"),
    ("draft_statement", {}, "무입력"),
    ("draft_statement", {"who": "학부모", "when": "3교시", "what": "욕설"}, "부분입력"),
    ("defend_child_abuse", {"situation": "신고하겠다고 협박받음"}, "정상"),
    ("search_teacher_law", {"law_name": "교원지위법", "article_no": "19"}, "정상(라이브)"),
    ("search_teacher_law", {"law_name": "없는법xyz", "article_no": "1"}, "실패내성"),
    ("verify_citation", {"law_name": "아동복지법", "article_no": "17"}, "진짜조항"),
    ("verify_citation", {"law_name": "교원지위법", "article_no": "999"}, "가짜조항"),
    ("route_support", {"situation_type": "폭행"}, "정상"),
    ("route_support", {"situation_type": "외계인침공"}, "잘못된유형"),
    ("guide_complaint_response", {}, "무입력"),
    ("guide_student_guidance", {"situation": "수업 중 자는 학생"}, "정상RAG"),
    ("guide_student_guidance", {"situation": LONG}, "초장문"),
    ("review_statement", {"document": ""}, "빈입력"),
    ("review_statement", {"document": "학생이 수업 중 욕을 했다. 증거는 녹음이 있다."}, "정상"),
    ("generate_document", {"doc_type": ""}, "메뉴"),
    ("generate_document", {"doc_type": "소명서", "teacher": "김교사", "what": "자는 학생 깨움"}, "소명서"),
    ("generate_document", {"doc_type": "신고서", "who": "학부모", "offender_type": "보호자"}, "신고서"),
    ("generate_document", {"doc_type": "민원답변", "who": "학부모"}, "민원답변"),
    ("generate_document", {"doc_type": "알수없는유형"}, "미매칭→메뉴"),
]


def main():
    npass = nfail = 0
    for name, args, label in CASES:
        tag = f"{name}[{label}]"
        try:
            r = getattr(M, name)(**args)
            if not isinstance(r, str):
                print(f"❌ {tag}: 문자열 아님({type(r).__name__})"); nfail += 1; continue
            if not r.strip():
                print(f"❌ {tag}: 빈 응답"); nfail += 1; continue
            warn = f"  ⚠️길이 {len(r)}" if len(r) > MAXLEN else ""
            print(f"✅ {tag}: {len(r)}자{warn}")
            npass += 1
        except Exception as e:
            print(f"❌ {tag}: 예외 {type(e).__name__}: {e}")
            nfail += 1
    print("\n" + "=" * 40)
    print(f"결과: {npass} PASS / {nfail} FAIL  (총 {npass + nfail})")
    print("=" * 40)
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
