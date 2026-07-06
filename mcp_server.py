# 교권지기 (TeacherRights Guardian) MCP 서버
# 카카오 AGENTIC PLAYER 10 출품작 — 교육활동 침해를 당한 교사가 "지금 뭘·어떻게" 해야 하는지
# 법 조문·교육청 매뉴얼 근거와 함께 안내하는 교권 대응 코파일럿.
# 전송: Streamable HTTP · 무상태. 로컬 실행:  python mcp_server.py  → http://localhost:8000/mcp
# 의존: pip install "mcp[cli]"  (법령 조회는 파이썬 표준 urllib 사용, 추가 의존 없음)
import os
import json
import urllib.parse
import urllib.request
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "gyogwonjigi-teacher-rights",
    stateless_http=True,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)

# 법제처 국가법령정보 OPEN API 인증키(OC). 배포 시 환경변수로 덮어쓸 수 있음.
LAW_OC = os.environ.get("LAW_OC", "mindminer")
LAW_BASE = "https://www.law.go.kr/DRF"

# 공통 면책 고지 — 법적 오정보 방지(심사 '안정성' 축의 핵심)
DISCLAIMER = ("\n\n---\n⚠️ 본 안내는 정보 제공용이며 법률 자문이 아니에요. 개별 사안은 "
             "교권보호센터(☎1395)·시도교육청 법률지원단·변호사 상담을 함께 받으세요.")


# ─────────────────────────────────────────────────────────────
# 도구 1) 침해 대응 6단계 플로우
# ─────────────────────────────────────────────────────────────
_FLOW = [
    ("① 즉시 대응 (현장, 분 단위)",
     "침해행위 중단 요청 → 주변에 도움 요청 → 현장 이탈. 관리자(교감·교장)에 즉시 신고. "
     "폭행·성범죄·협박 등 범죄행위면 **즉시 112 신고**. 필요시 특별휴가·조퇴·병가."),
    ("② 분리조치 의사 확인 (침해 인지 즉시)",
     "학교가 피해교원에게 **분리조치를 원하는지 의사 확인**(교원 의사가 선행). 가해학생을 별도 공간으로 분리. "
     "분리 중 학생 학습권 보장(교육자료·원격수업). [근거: 교원지위법 제20조 — 즉시 분리]"),
    ("③ 증거 수집·사안 기록 (골든타임, 당일)",
     "**육하원칙(누가·언제·어디서·무엇을·어떻게·왜)** 메모(사건 직후 증거가치 최고). "
     "문자·카톡·SNS·게시판 캡처, 사진·동영상, 음성녹음. 목격자(학생·동료) 진술서. 폭행 시 진단서."),
    ("④ 신고서·의견서 제출",
     "**학교→교육지원청 24시간 내 보고, 5일 내 사안조사 보고서**. 교원은 사안신고서+의견서 작성"
     "(관련자 조치·보호조치 의견 진술). 병행 채널: 소속학교 / 교육지원청 / **1395** / 시도교육청 홈페이지."),
    ("⑤ 지역교권보호위원회 심의 (접수 후 21일 내)",
     "**교육지원청** 지역교권보호위원회가 심의(2024.3.28부터 학교→교육지원청 이관). "
     "교원 출석 진술 또는 서면 의견 제출. 가해 학생·보호자 조치·분쟁조정 심의."),
    ("⑥ 결과 통지·사후 지원 (심의 후 14일 내)",
     "학생 조치(교원지위법 제25조 7종)·보호자 조치(제26조) 처분. 심리치료·법률지원·피해회복 연계."),
]


@mcp.tool(annotations={"title": "교권 침해 대응 절차 안내", "readOnlyHint": True})
def guide_response_flow(current_stage: str = "", infringement_type: str = "") -> str:
    """Guide a teacher through the 6-step response process after an
    educational-activity infringement in Korea — what to do now, in order,
    with deadlines. Emphasizes the current stage if given.

    Args:
        current_stage: Where the teacher is now, e.g. "방금 당함", "증거 수집 중", "신고함". Optional.
        infringement_type: Type of infringement, e.g. "폭언", "폭행", "악성민원". Optional.
    """
    out = ["📋 **교육활동 침해 대응 6단계** — 지금 위치에서 할 일을 순서대로 짚어드릴게요.", ""]
    for title, body in _FLOW:
        out.append(f"**{title}**")
        out.append(body)
        out.append("")
    out.append("💡 진술서·경위서가 막히면 `draft_statement`, 아동학대 신고 협박을 받았다면 "
               "`defend_child_abuse`, 지원기관 연결은 `route_support`를 불러 주세요.")
    if infringement_type and ("폭행" in infringement_type or "성" in infringement_type or "협박" in infringement_type):
        out.insert(1, "🚨 **범죄행위(폭행·성범죄·협박)로 보여요 — 먼저 112에 신고하세요.**\n")
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 2) 진술서·경위서 초안 생성
# ─────────────────────────────────────────────────────────────
@mcp.tool(annotations={"title": "진술서·경위서 초안 생성", "readOnlyHint": True})
def draft_statement(
    who: str = "",
    when: str = "",
    where: str = "",
    what: str = "",
    context_before: str = "",
    context_after: str = "",
    infringement_type: str = "",
) -> str:
    """Draft a Korean teacher's incident statement (진술서/경위서) for an
    educational-activity infringement, structured to be recognized as a valid
    infringement (six-W factual narration with before/after context).

    Args:
        who: Who caused it (학생/보호자 등).
        when: When it happened (일시).
        where: Where it happened (장소).
        what: What was said/done (구체 언행).
        context_before: Situation just before the incident.
        context_after: What happened right after / impact.
        infringement_type: Type, e.g. 모욕·협박·수업방해·악성민원.
    """
    def f(v, ph):
        return v.strip() if v.strip() else f"《{ph} — 채워 주세요》"
    body = (
        "교육활동 침해 사안 경위서 (초안)\n"
        "========================================\n\n"
        f"1. 일시: {f(when, '언제')}\n"
        f"2. 장소: {f(where, '어디서')}\n"
        f"3. 관련자: {f(who, '누가')}\n"
        f"4. 침해 유형: {f(infringement_type, '유형(모욕·협박·수업방해 등)')}\n\n"
        "5. 사건 경위\n"
        f"  (1) 사건 직전 상황: {f(context_before, '정당한 교육활동이 무엇이었는지 — 예: 수업 중 휴대폰 사용을 제지함')}\n"
        f"  (2) 침해 언행: {f(what, '실제 말·행동을 그대로 인용 — 예: 큰소리로 ○○○ 라고 말하며 …')}\n"
        f"  (3) 사건 직후·영향: {f(context_after, '이후 상황과 교육활동에 준 지장 — 예: 수업 진행 불가, 다른 학생 동요')}\n\n"
        "6. 증거 자료: (녹음·캡처·목격자 진술 등 첨부 목록)\n\n"
        "위 내용은 사실과 다름이 없습니다.\n"
        "작성일: 20  .  .  .    작성자(교원):            (서명)"
    )
    tips = (
        "\n\n📝 **인정률 높이는 팁**\n"
        "- \"욕설을 들었다\"로 끝내지 말고 **전후 경위·상황 맥락**까지 객관적으로 서술하세요(침해 인정의 결정적 자료).\n"
        "- 침해 언행은 **들은 그대로 따옴표로 인용**하세요.\n"
        "- 정당한 교육활동(무엇을 지도하던 중이었는지)을 (1)에 분명히 적으세요 — 정당성의 근거가 됩니다."
    )
    return "```\n" + body + "\n```" + tips + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 3) 아동학대 신고 대응 (정당한 생활지도 방어)
# ─────────────────────────────────────────────────────────────
@mcp.tool(annotations={"title": "아동학대 신고 대응 가이드", "readOnlyHint": True})
def defend_child_abuse(situation: str = "") -> str:
    """Guide a Korean teacher who is threatened with or reported for child abuse
    over legitimate student guidance. Provides the legal defense logic and the
    Superintendent's-opinion procedure. IMPORTANT: never states immunity as
    absolute — it holds only within the bounds of statute/notice/school rules.

    Args:
        situation: The guidance situation and what was reported. Optional.
    """
    out = [
        "🛡️ **\"아동학대로 신고하겠다\"는 협박·신고에 대한 대응**",
        "",
        "**1. 법적 방어 논리 — 정당한 생활지도는 아동학대가 아닙니다**",
        "- 「초·중등교육법」 **제20조의6(「아동복지법」의 적용 배제, 2025.9.16 개정)**: 교원의 정당한 학생생활지도(제20조의2제1항)·긴급 제지(제20조의2제3항) 등은 **「아동복지법」 제17조 제3호(신체학대)·제5호(정서학대)·제6호(방임) 금지행위로 보지 않습니다.**",
        "- 단, 이 면책은 **법령·고시·학칙이 정한 범위 내의 지도**일 때만 성립해요. 「교원의 학생생활지도에 관한 고시」가 정한 방식(조언·상담·주의·훈육·훈계·분리·물리적 제지 등)을 지켰는지가 정당성의 기준입니다.",
        "  *(정확한 현행 조문은 `search_teacher_law('초중등교육법','20의6')`로 확인)*",
        "",
        "**2. 교육감 의견 제출 제도 (혼자 두지 않는 장치)**",
        "- 「교원지위법」 제17조 + 「아동학대처벌법」 제11조의2·제17조의3: 정당한 교육활동이 아동학대로 신고돼 조사·수사가 진행되면 **교육감이 수사기관에 의견을 신속히 제출(의무)**해요.",
        "- 교육지원청이 사실관계를 조사하고 '정당한 생활지도 여부'를 판단해 경찰·검찰에 의견서를 냅니다.",
        "",
        "**3. 든든한 근거 통계**",
        "- 2023.9~2024.6 교육감 의견서 제출 553건 중 **약 70%가 '정당한 교육활동'** 입장.",
        "- 정당하다고 본 사안: **불기소 57.3% + 수사개시 전 종결 28.2% ≈ 85%가 교사에게 유리하게 종결.**",
        "",
        "**4. 지금 할 일**",
        "- 지도 상황을 **육하원칙으로 기록**(→ `draft_statement`)하고, 고시·학칙 근거를 함께 남기세요.",
        "- 소속 교육지원청·교권보호센터(☎1395)에 알리고 **교육감 의견 제출**을 요청하세요.",
        "- 교원배상책임보험(소송비 심급별 최대 660만원 선지원)·법률지원단 연결(→ `route_support`).",
    ]
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 4) 교권 법령 조항 실시간 조회 (법제처 OPEN API)
# ─────────────────────────────────────────────────────────────
def _law_get(path: str, params: dict) -> Optional[dict]:
    params = {"OC": LAW_OC, "type": "JSON", **params}
    url = f"{LAW_BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _flatten_article(a: dict) -> str:
    """조문 하나의 본문(조문내용 먼저, 이어서 항·호)을 순서대로 텍스트로 모은다."""
    parts = []
    top = a.get("조문내용")
    if isinstance(top, str):
        parts.append(top)
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.endswith("내용") and isinstance(v, str):
                    parts.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(a.get("항"))            # 조문내용 다음에 항·호를 붙인다
    seen, out = set(), []
    for p in parts:
        p = p.strip()
        if p and p not in seen:  # 중복 제거(순서 보존)
            seen.add(p)
            out.append(p)
    return "\n".join(out)


@mcp.tool(annotations={"title": "교권 법령 조항 조회", "readOnlyHint": True})
def search_teacher_law(law_name: str = "교원지위법", article_no: str = "") -> str:
    """Look up a current Korean statute article relevant to teachers' rights,
    live from the government legal database (법제처). Returns the exact,
    up-to-date article text as legal grounds.

    Args:
        law_name: Law name, e.g. "교원지위법", "아동학대처벌법", "초중등교육법".
        article_no: Article number to fetch, e.g. "19". If empty, returns the table of contents.
    """
    # 1) 법령명으로 검색 → 현행 법령일련번호(MST)
    s = _law_get("lawSearch.do", {"target": "law", "query": law_name, "display": "5"})
    if not s:
        return "법령 정보 서비스에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." + DISCLAIMER
    laws = s.get("LawSearch", {}).get("law", [])
    if isinstance(laws, dict):
        laws = [laws]
    cur = next((l for l in laws if l.get("현행연혁코드") == "현행"), laws[0] if laws else None)
    if not cur:
        return f"'{law_name}'에 해당하는 법령을 찾지 못했어요. 정확한 법령명을 알려주세요." + DISCLAIMER
    mst = cur.get("법령일련번호")
    name = cur.get("법령명한글", law_name)
    eff = cur.get("시행일자", "")

    # 2) 본문 조회
    b = _law_get("lawService.do", {"target": "law", "MST": mst})
    jo = (b or {}).get("법령", {}).get("조문", {})
    units = jo.get("조문단위", []) if isinstance(jo, dict) else []
    if isinstance(units, dict):
        units = [units]

    header = f"📖 **{name}** (시행 {eff[:4]}-{eff[4:6]}-{eff[6:]}, 현행) — 법제처"
    if not article_no:
        # 목차 반환
        titles = [f"- 제{u.get('조문번호')}조 {u.get('조문제목','')}" for u in units if u.get('조문제목')]
        return (header + "\n\n조회할 조를 알려주세요(예: 제19조). 주요 조문:\n"
                + "\n".join(titles[:40])) + DISCLAIMER

    want = article_no.replace("제", "").replace("조", "").strip()   # "19" 또는 "20의2"
    base, _, branch = want.partition("의")                          # 가지번호(의2) 분리
    base, branch = base.strip(), branch.strip()

    def _match(u):
        if str(u.get("조문번호", "")) != base:
            return False
        gaji = str(u.get("조문가지번호", "") or "").strip()
        return gaji == branch                                       # 가지 없으면 둘 다 ""

    hit = next((u for u in units if _match(u)), None)
    label = f"제{base}조의{branch}" if branch else f"제{base}조"
    if not hit:
        return header + f"\n\n{label}를 찾지 못했어요. article_no 없이 부르면 조문 목차를 볼 수 있어요." + DISCLAIMER
    text = _flatten_article(hit)
    return header + f"\n\n**{label}({hit.get('조문제목','')})**\n\n" + text + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 5) 상황별 지원기관 라우팅
# ─────────────────────────────────────────────────────────────
_SUPPORT = {
    "폭행": [("1395 교권침해 직통", "신고·상담·심리·법률 원스톱", "☎1395 / 카톡 채널 '1395'"),
            ("경찰", "범죄행위 형사 대응", "☎112"),
            ("교원배상책임보험", "손해배상·소송비 심급별 최대 660만원 선지원", "시도교육청/보험사")],
    "성범죄": [("1395 교권침해 직통", "신고·상담·심리·법률 원스톱", "☎1395"),
             ("경찰", "성폭력범죄 형사 대응", "☎112"),
             ("교원치유지원센터", "심리상담·치료", "☎1899-9876")],
    "아동학대신고": [("교육지원청", "교육감 의견 제출 요청", "관할 교육지원청"),
                ("시도교육청 법률지원단", "무료 법률상담·소송지원", "시도교육청 법무/교권 부서"),
                ("교원배상책임보험", "소송비 심급별 최대 660만원 선지원", "시도교육청")],
    "악성민원": [("교육지원청 통합민원팀", "악성·특이민원 기관 대응", "관할 교육지원청"),
             ("1395", "교권침해 민원 상담", "☎1395")],
    "심리소진": [("교원치유지원센터", "마음건강 심리상담·치료", "☎1899-9876"),
             ("교원안심공제", "상담·심리치료 지원", "시도 교육활동보호센터 경유")],
    "법률": [("시도교육청 법률지원단", "무료 법률상담·소송지원", "시도교육청"),
           ("한국교총 교권상담", "교권상담·변호인단", "kfta.or.kr"),
           ("전교조 교권상담마당", "교권·성폭력 상담", "eduhope.net")],
}


@mcp.tool(annotations={"title": "상황별 지원기관 연결", "readOnlyHint": True})
def route_support(situation_type: str = "") -> str:
    """Route a Korean teacher to the right support organizations for their
    situation (assault, sexual offense, false child-abuse report, malicious
    complaint, burnout, legal help).

    Args:
        situation_type: One of 폭행·성범죄·아동학대신고·악성민원·심리소진·법률, or free text.
    """
    key = None
    for k in _SUPPORT:
        if k in situation_type or situation_type in k:
            key = k
            break
    if not key:
        return ("상황 유형을 알려주세요: **폭행 · 성범죄 · 아동학대신고 · 악성민원 · 심리소진 · 법률**.\n"
                "가장 급할 땐 어디서든 **☎1395**(교권침해 원스톱)로 시작하세요.") + DISCLAIMER
    rows = _SUPPORT[key]
    out = [f"🤝 **'{key}' 상황 — 연결할 지원기관**", ""]
    for name, what, contact in rows:
        out.append(f"- **{name}** — {what} · {contact}")
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 6) 악성민원 응대 가이드
# ─────────────────────────────────────────────────────────────
@mcp.tool(annotations={"title": "악성민원 응대 가이드", "readOnlyHint": True})
def guide_complaint_response(situation: str = "") -> str:
    """Guide a Korean teacher on handling malicious complaints under the 2024
    school complaint-response system (call recording, ending abusive calls,
    escalating to the complaint team).

    Args:
        situation: The complaint situation. Optional.
    """
    out = [
        "📞 **악성민원 응대 — 2024 학교 민원 응대 체계 기준**",
        "",
        "**핵심 원칙: 민원은 '개인 교사'가 아니라 '기관(팀)'이 받습니다.**",
        "",
        "- **창구 일원화**: 학교 대표전화 접수 → **민원대응팀**(학교장 책임)이 분류·배분·답변. 개인 휴대폰 응대 의무 없음.",
        "- **통화 녹음**: 예방·대응 목적 **상시 녹음 가능**(통화연결음으로 고지). 증거로 보존하세요.",
        "- **먼저 끊어도 됩니다**: 욕설·협박·성희롱 시 **교직원이 먼저 통화를 종료**할 수 있어요(법령 근거).",
        "- **상급 이관**: 학교가 처리 곤란한 민원은 **교육지원청 통합민원팀**(교육장 직속)으로 이관하세요.",
        "- **교육활동 침해성 민원**은 일반 민원과 구분해 **교권보호위원회에서 처리**합니다(→ `guide_response_flow`).",
        "",
        "**응대 스크립트 예시**",
        "\"민원은 학교 민원대응팀을 통해 정식으로 접수·답변드립니다. 욕설·협박이 계속되면 통화를 종료하겠습니다. "
        "교육활동을 침해하는 내용은 관련 절차에 따라 처리됩니다.\"",
    ]
    return "\n".join(out) + DISCLAIMER


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
