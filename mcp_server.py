# 교권119 (Teacher Rights 119) MCP 서버
# 카카오 AGENTIC PLAYER 10 출품작 — 교육활동 침해를 당한 교사가 "지금 뭘·어떻게" 해야 하는지
# 법 조문·교육청 매뉴얼 근거와 함께 안내하는 교권 대응 코파일럿.
# 전송: Streamable HTTP · 무상태. 로컬 실행:  python mcp_server.py  → http://localhost:8000/mcp
# 의존: pip install "mcp[cli]"  (법령 조회는 파이썬 표준 urllib 사용, 추가 의존 없음)
import os
import re
import math
import json
import urllib.parse
import urllib.request
from typing import Optional
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))

mcp = FastMCP(
    "gyogwon119-teacher-rights",
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
        "**4. 지금 할 일 (구체적으로)**",
        "- 📝 **기록**: 지도한 **일시·장소·정확한 언행·이미 거친 단계**를 오늘 바로 적으세요. 자신에게 문자·이메일로 보내두면 '시각'이 증거로 남아요. 관련 문자·카톡 캡처, 목격한 동료·학생 진술도 확보. (진술서 초안 → `draft_statement`)",
        "- ☎ **연락**: **교권보호 통합상담 ☎1395**(평일 09~18시 · 카카오톡 채널 '1395'는 상시)로 전화하면 **신고·심리상담·법률지원·교육감 의견 제출**을 한 번에 안내받아요. 마음이 힘들면 **교원치유·심리상담 ☎1899-9876**.",
        "- ⚖️ **법률·비용**: 소속 시도교육청 **법률지원단**(무료 법률상담·소송 지원)과 **교원배상책임보험**(민사 소송비 심급별 최대 660만원·형사 최대 1,000만원 선지원)을 쓰세요. 연결 방법은 **1395로 문의**하거나 `route_support` 참고. (지원단 번호는 지역별이라 1395가 가장 빠른 입구예요.)",
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


# 환각 방지 가드(응답 하단에 붙여 LLM에 "근거 밖 조문·수치 지어내지 말라"를 강제)
GUARD = ("\n\n⚖️ 위에 제시된 조문·시행일 등 근거만 사용하세요. 제시되지 않은 조항·숫자는 "
         "지어내지 말고 '미확인'으로 남기세요.")

# 법제처 다운 대비 핵심 조문 캐시(build_law_cache.py로 생성)
try:
    with open(os.path.join(HERE, "law_cache.json"), encoding="utf-8") as _lf:
        LAW_CACHE = json.load(_lf)
except Exception:
    LAW_CACHE = {}


def _cache_lookup(law_name):
    for k, v in LAW_CACHE.items():
        if k in law_name or law_name in k or (law_name in (v.get("name") or "")):
            return v
    return None


def _cache_answer(law_name, article_no):
    """실시간 조회 실패 시 캐시본으로 답(없으면 None)."""
    v = _cache_lookup(law_name)
    if not v:
        return None
    e = v.get("efYd", "")
    head = (f"📖 **{v.get('name', law_name)}** (시행 {e[:4]}-{e[4:6]}-{e[6:]}) — "
            "⚠️ 실시간 조회 실패로 **캐시본**을 보여드려요(최신본은 law.go.kr에서 확인).")
    arts = v.get("articles", {})
    if not article_no:
        return head + "\n\n캐시된 조문: " + ", ".join(f"제{a}조" for a in arts)
    key = article_no.replace("제", "").replace("조", "").strip()
    a = arts.get(key)
    if not a:
        return head + f"\n\n제{key}조는 캐시에 없어요. 실시간 조회를 다시 시도해 주세요."
    return head + f"\n\n**제{key}조({a.get('title','')})**\n\n" + a.get("text", "")


@mcp.tool(annotations={"title": "교권 법령 조항 조회", "readOnlyHint": True})
def search_teacher_law(law_name: str = "교원지위법", article_no: str = "") -> str:
    """Look up a current Korean statute article relevant to teachers' rights,
    live from the government legal database (법제처). Returns the exact,
    up-to-date article text as legal grounds.
    USE THIS when the user needs the precise legal wording of an article. For
    "how should I guide a student" use `guide_student_guidance`; to check whether
    a specific intended measure is lawful use `check_guidance_legality`.

    Args:
        law_name: Law name, e.g. "교원지위법", "아동학대처벌법", "초중등교육법".
        article_no: Article number to fetch, e.g. "19". If empty, returns the table of contents.
    """
    # 1) 법령명으로 검색 → 현행 법령일련번호(MST)
    s = _law_get("lawSearch.do", {"target": "law", "query": law_name, "display": "5"})
    if not s:
        c = _cache_answer(law_name, article_no)   # 법제처 다운 → 캐시 폴백
        return (c + GUARD + DISCLAIMER) if c else \
            ("법령 정보 서비스에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." + DISCLAIMER)
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
    if not units:
        c = _cache_answer(law_name, article_no)   # 본문 조회 실패 → 캐시 폴백
        if c:
            return c + GUARD + DISCLAIMER

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
    return header + f"\n\n**{label}({hit.get('조문제목','')})**\n\n" + text + GUARD + DISCLAIMER


@mcp.tool(annotations={"title": "인용 법조항 진위 검증", "readOnlyHint": True})
def verify_citation(law_name: str = "", article_no: str = "", claimed_content: str = "") -> str:
    """Reverse-verify a law article that someone (a parent, complainant, etc.) cited
    as grounds — does that article actually EXIST, and what does it really say? Checks
    the current text live from 법제처. Use when a teacher wants to confirm "is this
    cited article real / does it really say that?" — a defense against false citations.

    Args:
        law_name: The cited law name, e.g. "아동복지법".
        article_no: The cited article number, e.g. "17" or "17의3".
        claimed_content: What it is claimed to say (optional, for comparison).
    """
    if not (law_name.strip() and article_no.strip()):
        return "검증할 법령명과 조 번호를 알려주세요. 예: 법령 '아동복지법', 조 '17'." + DISCLAIMER
    real = search_teacher_law(law_name, article_no)   # 실제 조문 조회(캐시 폴백 포함)
    if "연결하지 못했어요" in real:
        return "🔎 지금은 인용을 검증할 수 없어요(법령 서비스 연결 실패). 잠시 후 다시 시도해 주세요." + DISCLAIMER
    if ("찾지 못" in real) or ("캐시에 없어요" in real):
        return (f"🔎 **인용 검증: {law_name} 제{article_no}조**\n\n"
                "❌ **현행 법령에서 확인되지 않아요.** 존재하지 않는 조항이거나 법령명·조 번호가 부정확할 수 있어요. "
                "상대가 근거로 든 조항이라면 **허위·과장 인용일 수 있으니 반드시 재확인**하세요.") + DISCLAIMER
    banner = (f"🔎 **인용 검증: {law_name} 제{article_no}조** → ✅ **실제로 존재하는 조항이에요.** "
              "아래 현행 원문과 상대의 주장을 대조하세요.\n")
    if claimed_content.strip():
        banner += (f"\n· 상대가 말한 내용: \"{claimed_content.strip()[:120]}\" → "
                   "**아래 실제 조문과 범위·표현이 같은지 확인하세요.** 다르면 인용이 부정확한 거예요.\n")
    return banner + "\n" + real


# ─────────────────────────────────────────────────────────────
# 도구 5) 상황별 지원기관 라우팅
# ─────────────────────────────────────────────────────────────
_SUPPORT = {
    "폭행": [("1395 교권침해 직통", "신고·상담·심리·법률 원스톱", "☎1395(평일 09~18·카톡 상시)"),
            ("경찰", "범죄행위 형사 대응", "☎112"),
            ("교원배상책임보험", "손해배상·소송비 심급별 최대 660만원 선지원", "시도교육청/보험사")],
    "성범죄": [("1395 교권침해 직통", "신고·상담·심리·법률 원스톱", "☎1395"),
             ("경찰", "성폭력범죄 형사 대응", "☎112"),
             ("교육활동보호센터(구 교원치유지원센터)", "심리상담·치료", "☎1899-9876")],
    "아동학대신고": [("교육지원청", "교육감 의견 제출 요청", "관할 교육지원청"),
                ("시도교육청 법률지원단", "무료 법률상담·소송지원", "시도교육청 법무/교권 부서"),
                ("교원배상책임보험", "민사 소송비 심급별 최대 660만원·형사 최대 1,000만원 선지원", "시도교육청")],
    "악성민원": [("교육지원청 통합민원팀", "악성·특이민원 기관 대응", "관할 교육지원청"),
             ("1395", "교권침해 민원 상담", "☎1395")],
    "심리소진": [("교육활동보호센터(구 교원치유지원센터)", "마음건강 심리상담·치료", "☎1899-9876"),
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


# ─────────────────────────────────────────────────────────────
# 도구 7) 생활지도 상황별 근거 검색 (RAG — 교육부·교육청 매뉴얼 + 생활지도 고시)
# ─────────────────────────────────────────────────────────────
def _tokenize(text: str):
    """한국어: 단어 + 글자 bigram, 영숫자: 단어. (경량 BM25용)"""
    toks = re.findall(r"[가-힣]+|[a-z0-9]+", text.lower())
    out = []
    for t in toks:
        if "가" <= t[0] <= "힣":
            out.append(t)
            if len(t) > 2:
                out += [t[i:i + 2] for i in range(len(t) - 1)]
        else:
            out.append(t)
    return out


def _load_corpus():
    try:
        with open(os.path.join(HERE, "corpus.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CORPUS = _load_corpus()
_DOC_TOKENS = [_tokenize(c["text"]) for c in CORPUS]
_N = len(CORPUS)
_AVGDL = (sum(len(d) for d in _DOC_TOKENS) / _N) if _N else 0.0
_DF = {}
for _d in _DOC_TOKENS:
    for _w in set(_d):
        _DF[_w] = _DF.get(_w, 0) + 1
_IDF = {w: math.log(1 + (_N - df + 0.5) / (df + 0.5)) for w, df in _DF.items()}
_TF = [{} for _ in _DOC_TOKENS]
for _i, _d in enumerate(_DOC_TOKENS):
    for _w in _d:
        _TF[_i][_w] = _TF[_i].get(_w, 0) + 1


def _bm25(query: str, topk: int = 4, k1: float = 1.5, b: float = 0.75):
    q = _tokenize(query)
    scored = []
    for i in range(_N):
        dl = len(_DOC_TOKENS[i])
        tf = _TF[i]
        s = 0.0
        for w in q:
            f = tf.get(w)
            if f:
                s += _IDF.get(w, 0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / _AVGDL))
        if s > 0:
            scored.append((s, i))
    scored.sort(reverse=True)
    return [CORPUS[i] for _, i in scored[:topk]]


@mcp.tool(annotations={"title": "생활지도 상황별 근거 검색", "readOnlyHint": True})
def guide_student_guidance(situation: str = "") -> str:
    """For a described student-guidance situation, retrieve the most relevant
    passages from Korea's Ministry of Education / provincial education office
    manuals and the official student-guidance notice, so the assistant can give
    a grounded, cited answer on how to guide the student within lawful bounds.
    USE THIS for open "how do I handle/guide X" questions. To check whether a
    SPECIFIC intended measure is lawful (order, prosecution risk) use
    `check_guidance_legality`; for exact statute text use `search_teacher_law`.

    Args:
        situation: The situation a teacher faces, e.g. "수업 중 자는 학생을 어떻게 지도하나".
    """
    if not situation.strip():
        return "상황을 알려주세요. 예: '수업 중 휴대폰을 계속 보는 학생을 어떻게 지도하나요?'"
    hits = _bm25(situation, topk=4)
    if not hits:
        return ("관련 문서 조각을 찾지 못했어요. 상황·학생 행동·이미 시도한 지도를 더 구체적으로 적어 주세요.") + DISCLAIMER
    out = [f"📚 **'{situation[:80]}' — 관련 근거(교육부·교육청 매뉴얼·생활지도 고시)**", ""]
    for h in hits:
        src = h["source"] + (f" p.{h['page']}" if h.get("page") else "")
        out.append(f"**〔{src}〕**\n{h['text']}")
        out.append("")
    out.append("↑ 위 근거로 단계적 지도(조언→주의→훈육→훈계→분리 등)와 정당한 범위를 안내하세요. "
               "정당한 생활지도는 아동학대로 보지 않아요(→ `defend_child_abuse`).")
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 8) 지도단계 적법성 체커 (실시간 방어 — 행동)
# 「교원의 학생생활지도에 관한 고시」 사다리: 조언(9)→상담(10)→주의(11)→훈육(12)→훈계(13)
# ─────────────────────────────────────────────────────────────
_LADDER = ["제9조 조언", "제10조 상담", "제11조 주의", "제12조 훈육", "제13조 훈계"]

# 사다리 단계를 '실제 행동'으로 — 방어·경고만이 아니라 "이렇게 해보세요"를 준다
_LADDER_HOWTO = {
    "제9조 조언": "조용히 다가가 눈을 맞추고 낮은 목소리로 상황을 짚어 주세요(비난·창피 주기 X).",
    "제10조 상담": "쉬는 시간에 1:1로 행동의 이유를 물어보세요(피곤·무기력·갈등·가정 문제 등). 판단보다 경청 먼저.",
    "제11조 주의": "학급 규칙을 상기시키고 결과를 예고한 뒤, 일시·내용을 간단히 기록해 두세요.",
    "제12조 훈육": "특정 과업 부여·자리 이동·(방해가 지속되면) 최소한의 분리 등 지시를 하세요(인권·최소한도).",
    "제13조 훈계": "사유와 개선 방안을 함께 제시하고, 성찰문은 수업시간 외에 부여하세요.",
}

# 명백 위법(체벌·물리적 폭력) — 사다리 판정 이전에 즉시 차단
_REDFLAG = ["때리", "때려", "체벌", "손찌검", "뺨", "꿀밤", "회초리", "매질", "발로 차",
            "밀치", "머리채", "폭행", "밀쳐", "쥐어박"]

# 자주 하려는 조치 → (사다리 index, 한 줄 판정, [요건·경고 목록])
_ACTION_RULES = [
    (("성찰문", "반성문", "반성", "성찰"), 4,
     "성찰문(성찰하는 글쓰기)은 **제13조 훈계**의 과제예요.",
     ["전제: 조언·상담·주의·훈육을 거쳤는데도 개선이 없을 때만 가능(고시 제13조①).",
      "훈계 시 **사유와 개선방안을 함께 제시**해야 해요(제13조②).",
      "수업시간이 아닌 때에, 학칙 근거로.",
      "⚠️ 앞 단계 없이 바로 성찰문을 시키면 '정서학대' 근거로 쓰일 수 있어요."]),
    (("휴대폰", "스마트기기", "핸드폰", "폰", "기기"), 2,
     "수업 중 스마트기기 사용 제한은 **제11조 주의②**로 가능해요.",
     ["주의로 사용 제한 → 불응·위험 소지 의심 시 제12조 훈육④로 필요범위 내 보관.",
      "보관 절차: 주의 → 물품 보관 → 학교장 보고 → **보호자에게 인계**(학생에게 임의 처분 X).",
      "⚠️ 교과 수업시간 녹음은 개인정보·형사 위험. 증거는 원본 보존, 불리해도 삭제 금지."]),
    (("압수", "수거", "보관", "빼앗"), 3,
     "물품 보관·제한은 **제11조 주의 → 제12조 훈육④**(위험물품, 필요범위 내).",
     ["합리적 이유(위해 우려)가 있어야 하고, 보관 후 **학교장 보고 + 보호자 인계**.",
      "학생에게 임의로 처분·폐기하면 안 돼요."]),
    (("세워", "서있", "손 들", "교실 뒤", "벌"), 3,
     "특정 과업·지시는 **제12조 훈육**이에요.",
     ["인권 존중 + 법령·학칙 범위 내, 최소한도.",
      "⚠️ 신체적 고통·건강에 해가 되는 방식은 금지(체벌 금지)."]),
    (("청소", "원상복구"), 4,
     "청소·원상복구는 **제13조 훈계**의 과제예요(훼손 시설·물품 대상).",
     ["전제: 앞 단계(조언~훈육)를 거침 + 사유·개선방안 함께 제시."]),
    (("분리", "내보", "교실 밖", "제지"), 3,
     "수업 방해 학생 분리·제지는 **제12조 훈육**(+ 법 제20조의2 긴급 제지).",
     ["긴급 제지는 위험 상황에서 최소한도로. 분리 시 학생 학습권 보장.",
      "정당한 분리에 불응해 방해하면 제16조로 교육활동 침해 조치 가능."]),
]

_FOLLOWUP = ("\n📝 **필수 후속기록 (이렇게)**: ①지도한 **일시·장소·언행·거친 단계**를 그날 바로 메모"
             "(자신에게 문자·이메일로 남기면 '시각'이 증거로 남아요) ②학교장에게 **서면 보고** ③학부모에게 **통보**. "
             "(통보·보고 누락이 절차 위반·기소 사유가 돼요.)")


@mcp.tool(annotations={"title": "지도단계 적법성 체커", "readOnlyHint": True})
def check_guidance_legality(intended_action: str = "", steps_taken: str = "") -> str:
    """Check whether a teacher's intended guidance measure follows the lawful
    escalation ladder of Korea's student-guidance notice (조언→상담→주의→훈육→훈계),
    warn about prosecution risk from skipping steps, and list the mandatory
    follow-up records. Real-time defense before acting.
    USE THIS for "can I do X / is X okay" about a SPECIFIC planned measure. For
    open how-to guidance use `guide_student_guidance`; for exact statute text use
    `search_teacher_law`.

    Args:
        intended_action: What the teacher intends to do, e.g. "반성문 쓰게 하려고요", "휴대폰 걷기".
        steps_taken: Steps already taken (조언/상담/주의/훈육), optional.
    """
    if not intended_action.strip():
        return ("하려는 조치를 알려주세요. 예: '반성문 쓰게 하려고요' / '휴대폰 걷으려고요'.\n"
                "생활지도 사다리: " + " → ".join(_LADDER)) + DISCLAIMER
    if any(k in intended_action for k in _REDFLAG):
        return (
            "❌ **안 됩니다 — 체벌·물리적 폭력은 어떤 경우에도 금지예요.**\n\n"
            "정당한 생활지도는 **신체적 고통을 주지 않는 범위**에서만 인정돼요(교원의 학생생활지도 고시). "
            "때리거나 물리적 힘을 가하면 「아동복지법」·「형법」 위반이 될 수 있고, 정당한 생활지도의 면책(초중등교육법 제20조의6)도 받지 못해요.\n\n"
            "**대신 이렇게 하세요**: 조언 → 상담 → 주의 → 훈육 → 훈계의 단계로 지도하세요. "
            "학생이 자신·타인을 해칠 급박한 위험이 있을 때만 **최소한의 '제지'**(법 제20조의2)가 허용되며, 그마저도 신체에 해를 주면 안 돼요.\n"
            "마음이 많이 힘드셔서 그러시는 거라면, 먼저 `emotional_support`로 잠깐 숨을 고르셔도 좋아요."
        ) + DISCLAIMER
    a = intended_action
    rule = next((r for r in _ACTION_RULES if any(k in a for k in r[0])), None)
    out = [f"🧭 **'{intended_action[:80]}' — 적법성 체크**", ""]
    if rule:
        _, idx, verdict, reqs = rule
        out.append(verdict)
        prior = _LADDER[:idx]
        if prior:
            out.append(f"\n**앞 단계(먼저 거쳐야 함)**: {' → '.join(prior)}")
            if steps_taken.strip():
                out.append(f"거친 단계로 적어주신 것: {steps_taken}")
            else:
                out.append("⚠️ 앞 단계를 거쳤는지 확인하세요 — 건너뛰면 정당성이 약해져요.")
        out.append("\n**✅ 지금 이렇게 하세요 (단계별 실전 행동)**")
        out += [f"- **{st}** — {_LADDER_HOWTO[st]}" for st in _LADDER[:idx + 1]]
        out.append("\n**요건·주의**")
        out += [f"- {x}" for x in reqs]
    else:
        out.append("이 조치는 사전 정의 사례엔 없지만, 아래 사다리와 **관련 문서 근거**로 판단하세요.")
        out.append("생활지도 사다리: " + " → ".join(_LADDER))
        out.append("- 낮은 단계(조언·주의)부터 시도하고, 안 되면 한 단계씩 올리세요.")
        out.append("- 모든 조치는 인권 존중 + 법령·학칙 범위 + 최소한도. 신체적 고통은 금지.")
        out.append("\n**🧩 실전: 이렇게 해보세요(단계별)**")
        out += [f"- **{st}** — {_LADDER_HOWTO[st]}" for st in _LADDER]

    # 하드코딩 규칙에 없는 조치일 때만 문서 근거를 붙인다
    # (매칭된 규칙은 큐레이션 실전 단계로 충분 + 짧은 질의의 RAG 노이즈 방지)
    if not rule:
        hits = _bm25(intended_action, topk=2)
        if hits:
            out.append("\n**📚 관련 근거(고시·교육청 매뉴얼)**")
            for h in hits:
                src = h["source"] + (f" p.{h['page']}" if h.get("page") else "")
                out.append(f"〔{src}〕 {h['text'][:220]}")
    out.append(_FOLLOWUP)
    out.append("\n✅ 이 사다리를 지킨 정당한 생활지도는 아동학대로 보지 않아요(초중등교육법 제20조의6, → `defend_child_abuse`).")
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 9) 학부모 대화 안전 필터 (실시간 방어 — 말)
# ─────────────────────────────────────────────────────────────
_PARENT_THREAT = ["아동학대", "신고", "고소", "고발", "교육청", "국민신문고", "언론", "변호사", "소송",
                  "가만 안", "손해배상", "배상", "청구", "치료비", "합의금", "책임 물", "책임지라",
                  "협박", "가만두지", "각오", "국민청원", "제보", "민사", "형사"]
_PARENT_INSULT = ["욕", "욕설", "모욕", "폭언", "막말", "소리 질", "소리를 질", "삿대질", "쌍욕", "반말로",
                  "성희롱", "성적", "몸매", "외모"]
_INJURY_WORDS = ["다쳤", "다쳐", "다치", "부상", "골절", "삐었", "안전사고", "보건실", "다칠"]
_EXPOSURE = ["몰래 촬영", "몰래 녹음", "녹음해서", "sns", "SNS", "단톡방", "맘카페", "인터넷에 올",
             "유포", "박제", "커뮤니티에 올"]
_PARENT_INTENT = ["의도", "일부러", "고의", "작정", "왜 그랬"]
_PARENT_APOLOGY = ["사과", "사죄", "잘못 인정"]
_DRAFT_EMOTION = ["힘들", "지치", "감당", "버겁", "괴롭", "스트레스", "죽겠"]
_DRAFT_FAULT = ["죄송", "제 잘못", "제 실수", "송구", "사과드"]
_DRAFT_ESCAPE = ["감당이 안", "포기", "못 하겠", "어쩔 수 없", "감당이 안 돼"]
_DRAFT_PROMISE = ["해드릴게요", "약속", "보장", "책임지"]


_COMPLAINT_WORDS = ["반복", "계속", "트집", "매일", "자꾸", "여러 번", "민원", "시도 때도"]


@mcp.tool(annotations={"title": "학부모 대화 안전 도우미", "readOnlyHint": True})
def safe_parent_message(situation: str = "", parent_message: str = "", teacher_draft: str = "") -> str:
    """Help a teacher respond safely to a parent. Accepts ANY of: a free-text
    situation description, the parent's verbatim message, and/or the teacher's
    draft reply. Detects threats/tactics and the parent's real need, strips
    self-incriminating or out-of-scope phrasing from the draft, and returns a
    de-escalating, child-safety-framed response script. Real-time defense for talk.

    Args:
        situation: Free description of what's happening, e.g. "학부모가 전화로 계속 항의해요". Optional.
        parent_message: The parent's exact words being responded to. Optional.
        teacher_draft: The teacher's draft reply to make safe. Optional.
    """
    ctx = (situation + " " + parent_message).strip()
    if not (ctx or teacher_draft.strip()):
        return ("상황을 설명해 주시거나(예: '학부모가 계속 트집을 잡아요'), 학부모가 보낸 말이나 "
                "보내려는 답장 초안을 붙여넣어 주세요. 셋 중 아무거나 돼요.") + DISCLAIMER
    out = []

    if ctx:
        out.append("**1. 상황·상대 말 분석**")
        hit = False
        if any(k in ctx for k in _PARENT_THREAT):
            hit = True
            out.append("- 🚨 **위협/신고 언급** → (문자·녹음이 있으면) 원본을 **증거로 보존**하세요. "
                       "정당한 지도에 대한 반복 위협은 교육활동 침해(부당 간섭)가 될 수 있어요(→ `guide_response_flow`, `defend_child_abuse`).")
        if any(k in ctx for k in _PARENT_INTENT):
            hit = True
            out.append("- ⚠️ **의도 추궁** → '고의였냐'는 교사가 판단·인정할 문제가 아니에요. "
                       "\"의도는 제가 판단할 영역이 아니에요\"로 되돌리기.")
        if any(k in ctx for k in _PARENT_APOLOGY):
            hit = True
            out.append("- ⚠️ **사과 요구** → 사실 확인 전 잘못 인정 금지. 유감 표현과 사실 인정은 구분.")
        if any(k in ctx for k in _PARENT_INSULT):
            hit = True
            out.append("- 🚨 **욕설·폭언·모욕 감지** → 그 자체로 교육활동 침해(모욕)가 될 수 있어요. "
                       "원본을 **증거로 보존**하고, 지속되면 교권보호위 사안이에요(→ `guide_response_flow`).")
        if any(k in ctx for k in _INJURY_WORDS):
            hit = True
            out.append("- 🩹 **학생 부상·안전사고·배상 관련** → ①과실을 **성급히 인정하지 마세요** "
                       "②교육활동 중 배상책임은 **교원배상책임보험(최대 2억)·학교안전공제회**로 처리돼요 — "
                       "개인이 떠안지 마세요(→ `route_support`).")
        if any(k in ctx for k in _COMPLAINT_WORDS):
            hit = True
            out.append("- 🔁 **반복·악성 민원 성격** → 민원은 개인이 아닌 **학교 민원대응팀**으로 정식 접수하세요"
                       "(→ `guide_complaint_response`). **익명이면 응대 의무가 없어요**(민원처리법).")
        if any(k in ctx for k in _EXPOSURE):
            out.append("- 🎥 **무단 촬영·녹음·유포** → 정보통신망법상 불법정보·교육활동 침해(제19조)가 될 수 있어요. "
                       "원본·게시물을 **증거로 보존**하고 삭제 요청·신고를 검토하세요(→ `defend_child_abuse`).")
        # 키워드가 못 잡아도 빈손이 되지 않게, 자주 있는 유형을 항상 함께 제시(해당되면 참고)
        out.append("- 🗂️ **함께 점검할 유형**(해당되면 그 원칙 적용): "
                   "위협·신고·손해배상 → 증거 보존+교원배상책임보험 · 욕설·모욕·성적언동 → 교육활동 침해 가능+증거 · "
                   "의도·잘잘못 추궁 → 판단 되돌리기 · 학생 부상·안전사고 → 과실 인정 말고 학교안전공제회 · "
                   "반복·악성 민원 → 민원대응팀·익명 응대 의무 없음 · 무단 촬영·유포 → 증거 보존·신고 검토")
        out.append("- 💡 **진짜 원하는 것**: 대개 처벌이 아니라 '내 아이가 학교에서 평안한 것'이에요. "
                   "거기에 맞춰 답하면 풀려요.")
        out.append("")

    if teacher_draft.strip():
        td = teacher_draft
        flags = []
        if any(k in td for k in _DRAFT_EMOTION):
            flags.append("**교사 감정 토로**(\"힘들다·감당 안 된다\") → 공격 대상이 돼요. 빼세요.")
        if any(k in td for k in _DRAFT_ESCAPE):
            flags.append("**직무 회피성 표현**(\"못 하겠다·포기\") → 직무유기로 읽힐 수 있어요.")
        if any(k in td for k in _DRAFT_FAULT):
            flags.append("**성급한 과실 인정**(\"제 잘못·죄송\") → 사실 확인 전 인정은 불리해요. 유감 표현으로 대체.")
        if any(k in td for k in _DRAFT_PROMISE):
            flags.append("**과한 약속**(\"해드릴게요·책임지겠다\") → 지키기 어려운 약속은 화근. 신중히.")
        out.append("**2. 내 초안 위험 표현**")
        out += [f"- 🚫 {f}" for f in flags] if flags else ["- 큰 위험 표현은 안 보여요. 아래 원칙만 확인하세요."]
        out.append("")

    # 상황 맞춤 '완성형' 답장 초안 (상황 설명만 줘도 나옴 — 바로 다듬어 쓰도록)
    out.append("**3. 안전한 답장 초안 (바로 다듬어 쓰세요)**")
    if any(k in ctx for k in _INJURY_WORDS):
        out.append("- \"어머니, ○○이가 다쳐서 많이 놀라셨죠. 저도 아이 상태가 가장 걱정입니다. 치료와 회복이 우선이니 "
                   "필요한 부분은 함께 챙기겠습니다. 다만 배상·책임 문제는 제가 개인적으로 판단·약속드릴 수 있는 부분이 "
                   "아니라서요, 학교안전공제회와 교육활동 보호 절차를 통해 정식으로 안내받으실 수 있도록 돕겠습니다.\"")
    elif any(k in ctx for k in _PARENT_THREAT + _PARENT_INSULT + _EXPOSURE):
        out.append("- \"어머니, 먼저 ○○이가 학교에서 안전하고 편안하게 지내는 게 저도 가장 중요하다는 말씀 드려요. "
                   "오늘 있었던 일은 사실 그대로 기록해 두었습니다. 다만 잘잘못이나 책임을 제가 개인적으로 "
                   "판단드릴 수 있는 부분은 아니어서, 정식 절차를 통해 함께 확인하고 논의드리면 좋겠습니다.\"")
    elif any(k in ctx for k in _COMPLAINT_WORDS):
        out.append("- \"말씀 주신 부분은 학교 민원 절차를 통해 정식으로 접수·답변드리겠습니다. "
                   "○○이 교육과 관련된 상담은 언제든 정규 경로로 도와드릴게요.\"")
    elif any(k in ctx for k in _PARENT_INTENT + _PARENT_APOLOGY):
        out.append("- \"의도나 잘잘못은 제가 판단드릴 수 있는 부분이 아니에요. 다만 ○○이에게 도움이 될 방향은 "
                   "함께 상담으로 논의드리고 싶습니다.\"")
    else:
        out.append("- \"어머니, ○○이가 안전하고 편안하게 지내는 게 저도 가장 중요해요. 그래서 함께 봐야 할 부분을 "
                   "말씀드리려 합니다. 상담이 필요하시면 정규 경로로 도와드릴게요.\"")
    out.append("\n**원칙**: 아동 안전·성장 프레임 / 과실·의도·책임은 개인이 인정·판단 말고 되돌리기 / 사실만·짧게·기록 남게.")
    # 키워드 판정을 실제 교육청 민원·대응 매뉴얼 근거로 뒷받침(RAG)
    refs = _bm25(ctx or teacher_draft, topk=2)
    if refs:
        out.append("\n**📚 근거(교육청 민원·대응 매뉴얼)**")
        for h in refs:
            src = h["source"] + (f" p.{h['page']}" if h.get("page") else "")
            out.append(f"〔{src}〕 {h['text'][:180]}")
    return "\n".join(out) + DISCLAIMER


# ─────────────────────────────────────────────────────────────
# 도구 10) 마음 지지 (정서·생명 안전 레이어 — 상담 어투)
# 위기 신호 시 절차를 멈추고 "당신 잘못이 아니다" + 실제 사람·기관 연결.
# ─────────────────────────────────────────────────────────────
_CRISIS = ["죽고 싶", "죽고싶", "사라지고 싶", "사라지고싶", "살기 싫", "살고 싶지 않",
           "나만 없으면", "그만두고 싶", "버틸 수 없", "버틸수 없", "끝내고 싶",
           "자해", "뛰어내리", "없어지고 싶", "다 놓고 싶", "죽어버리"]
_DISTRESS = ["자책", "수치", "창피", "제 잘못", "내 탓", "힘들", "무섭", "두렵", "불안",
             "외롭", "혼자", "떨려", "잠을 못", "숨이", "우울", "지쳤", "무너", "괴롭",
             "신고", "민원", "소송", "조사받", "수사", "협박", "억울", "눈물", "울었",
             "울고", "못 자", "답답", "무기력", "심장", "미치겠", "죽을 것", "버티"]

_CRISIS_LINES = (
    "☎ **자살예방 상담전화 109** (24시간·무료·익명)\n"
    "☎ **정신건강 위기상담 1577-0199**\n"
    "☎ **교육활동보호센터(구 교원치유지원센터) 1899-9876** (선생님을 위한 상담)"
)


@mcp.tool(annotations={"title": "마음 지지 (상담)", "readOnlyHint": True})
def emotional_support(feeling: str = "") -> str:
    """Give warm, counseling-style emotional support to a teacher in distress
    over an infringement / false report. IMPORTANT: call this FIRST — before any
    procedural tool — whenever the teacher expresses self-blame, shame,
    hopelessness, or crisis. It validates, says 'this is not your fault', and
    connects the teacher to real people/hotlines. It never replaces professional
    help; it routes to it.

    Args:
        feeling: How the teacher is feeling or what they are going through.
    """
    f = feeling or ""
    # 위기 신호 → 절차 멈추고 즉시 사람·기관 연결(초단문)
    if any(k in f for k in _CRISIS):
        return (
            "🕊️ 잠깐만요. 이 말씀부터 드리고 싶어요.\n\n"
            "**지금 혼자 계시지 마세요.** 곁에 있어 줄 사람에게 지금 연락해 주세요.\n\n"
            "지금 바로 이야기 나눌 수 있는 곳이에요:\n" + _CRISIS_LINES + "\n\n"
            "선생님 잘못이 아니에요. 지금의 고통은 상황이 만든 거예요, 선생님이 부족해서가 아니에요.\n"
            "이 순간을 혼자 넘기지 않으셔도 돼요. 위 번호 중 하나에 지금 전화해 주실 수 있을까요? 저도 여기 있을게요."
        )
    # 자책·소진 등 일반 고통(관련 키워드 있을 때만) → 상담 어투 지지 + 리프레이밍 + 연결
    if any(k in f for k in _DISTRESS):
        return (
            "🌱 여기까지 혼자 버텨오셨네요. 얼마나 힘드셨을까요.\n\n"
            "먼저 꼭 드리고 싶은 말이 있어요 — **이건 선생님 잘못이 아니에요.** "
            "신고·민원을 겪은 대부분의 선생님은 학대에 해당하는 일을 하지 않았어요. 오해와 상황이 만든 일이에요.\n\n"
            "자책이 밀려올 땐, 그 말을 하는 사람이 '내 인생에서 정말 중요한 사람인가'를 떠올려 보세요. 대개는 아니에요.\n\n"
            "혼자 두고 싶지 않아요. 선생님을 위한 곳이에요:\n"
            "☎ **교육활동보호센터(구 교원치유지원센터) 1899-9876** — 선생님 전용 심리상담(무료)\n"
            "· 교권침해 피해교사 모임·교원단체 상담 — 같은 일을 겪은 사람들과 함께\n"
            "· 마음이 많이 무너질 땐 ☎ **정신건강 위기상담 1577-0199**, ☎ **자살예방 109**\n\n"
            "오늘은 딱 하나만 해요 — 물 한 잔, 믿는 사람에게 문자 한 통. "
            "서류·절차는 마음이 조금 가라앉은 뒤에 저와 천천히 봐요. 지금은 선생님이 먼저예요."
        )
    return ("지금 마음이 어떠세요? 무슨 일이 있었는지 편하게 말씀해 주세요. "
            "천천히 들을게요. 혼자 감당하지 않으셔도 돼요.")


# ─────────────────────────────────────────────────────────────
# 도구 12) 진술서·경위서 검토 (생성 도구 draft_statement의 짝)
# ─────────────────────────────────────────────────────────────
# (필수 요소, 감지 키워드) — 하나라도 있으면 '있음'으로 본다
_REVIEW_ELEMENTS = [
    ("일시(언제)", ["일시", "시경", "교시", "오전", "오후", "년", "월", "일"]),
    ("장소(어디서)", ["장소", "교실", "학교", "복도", "운동장", "앞", "실에서", "실 "]),
    ("관련자(누가)", ["학생", "학부모", "보호자", "가해", "○○", "피해교원", "본인"]),
    ("침해 언행(무엇을)", ["말", "행동", "욕", "라고", "했다", "하였", "고함", "폭언"]),
    ("전후 맥락·정당한 지도", ["지도", "수업", "훈육", "주의", "제지", "훈계", "중이", "요구"]),
    ("증거 자료", ["증거", "녹음", "캡처", "사진", "동영상", "목격", "진단서", "cctv", "CCTV"]),
]


@mcp.tool(annotations={"title": "진술서·경위서 검토", "readOnlyHint": True})
def review_statement(document: str = "") -> str:
    """Review a teacher's already-written incident statement (진술서/경위서/의견서):
    flag missing required elements (six-W, context, evidence) and self-incriminating
    or out-of-scope phrasing, and suggest fixes. The review counterpart of
    `draft_statement`. Use when a teacher has a draft and asks "is anything missing?".

    Args:
        document: The statement text to review.
    """
    if not document.strip():
        return ("검토할 진술서·경위서 내용을 붙여넣어 주세요. (초안이 필요하면 `draft_statement`로 만들 수 있어요.)") + DISCLAIMER
    d = document
    has_digit = any(ch.isdigit() for ch in d)
    out = ["📝 **진술서·경위서 검토**", "", "**1. 필수 요소 점검**"]
    missing = []
    for name, kws in _REVIEW_ELEMENTS:
        present = any(k in d for k in kws) or (name.startswith("일시") and has_digit)
        out.append(f"- {'✅' if present else '⚠️'} {name}{'' if present else ' — 빠졌어요, 채우면 좋아요'}")
        if not present:
            missing.append(name)

    out.append("\n**2. 위험 표현 점검**")
    flags = []
    if any(k in d for k in _DRAFT_EMOTION):
        flags.append("교사 감정 토로(\"힘들다·감당 안 된다\") → 공격 대상. 빼기")
    if any(k in d for k in _DRAFT_FAULT):
        flags.append("성급한 과실 인정(\"제 잘못·죄송\") → 사실 확인 전 인정은 불리. 유감 표현으로")
    if any(k in d for k in _DRAFT_ESCAPE):
        flags.append("직무 회피성(\"못 하겠다·포기\") → 직무유기로 읽힘")
    if any(k in d for k in _DRAFT_PROMISE):
        flags.append("과한 약속(\"해드릴게요·책임지겠다\") → 화근")
    out += [f"- 🚫 {f}" for f in flags] if flags else ["- 큰 위험 표현은 안 보여요."]

    out.append("\n**3. 보완 제안**")
    if missing:
        out.append(f"- 빠진 요소({', '.join(missing)})를 채우세요. 특히 **침해 언행은 들은 그대로 인용**, "
                   "**정당한 교육활동(무엇을 지도하던 중이었는지)**을 분명히.")
    else:
        out.append("- 필수 요소는 갖췄어요. 침해 언행이 **구체적 인용**인지, 전후 맥락이 **객관적 서술**인지 다시 보세요.")
    out.append("- 감정·과실 인정·직무이탈 표현은 빼고, **사실·시간 순서·증거 목록** 중심으로.")
    out.append("- 초안부터 다시 잡으려면 `draft_statement`를 쓰세요.")
    return "\n".join(out) + DISCLAIMER


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
