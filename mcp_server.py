# 교권지기 (TeacherRights Guardian) MCP 서버
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

    Args:
        situation: The situation a teacher faces, e.g. "수업 중 자는 학생을 어떻게 지도하나".
    """
    if not situation.strip():
        return "상황을 알려주세요. 예: '수업 중 휴대폰을 계속 보는 학생을 어떻게 지도하나요?'"
    hits = _bm25(situation, topk=4)
    if not hits:
        return ("관련 문서 조각을 찾지 못했어요. 상황·학생 행동·이미 시도한 지도를 더 구체적으로 적어 주세요.") + DISCLAIMER
    out = [f"📚 **'{situation}' — 관련 근거(교육부·교육청 매뉴얼·생활지도 고시)**", ""]
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

_FOLLOWUP = ("\n📝 **필수 후속기록**: ①지도 일시·내용·거친 단계를 그날 바로 기록 "
             "②학교장 보고 ③학부모 통보. (블로그·매뉴얼: 통보·보고 누락이 절차 위반·기소 사유가 됩니다.)")


@mcp.tool(annotations={"title": "지도단계 적법성 체커", "readOnlyHint": True})
def check_guidance_legality(intended_action: str = "", steps_taken: str = "") -> str:
    """Check whether a teacher's intended guidance measure follows the lawful
    escalation ladder of Korea's student-guidance notice (조언→상담→주의→훈육→훈계),
    warn about prosecution risk from skipping steps, and list the mandatory
    follow-up records. Real-time defense before acting.

    Args:
        intended_action: What the teacher intends to do, e.g. "반성문 쓰게 하려고요", "휴대폰 걷기".
        steps_taken: Steps already taken (조언/상담/주의/훈육), optional.
    """
    if not intended_action.strip():
        return ("하려는 조치를 알려주세요. 예: '반성문 쓰게 하려고요' / '휴대폰 걷으려고요'.\n"
                "생활지도 사다리: " + " → ".join(_LADDER)) + DISCLAIMER
    a = intended_action
    rule = next((r for r in _ACTION_RULES if any(k in a for k in r[0])), None)
    out = [f"🧭 **'{intended_action}' — 적법성 체크**", ""]
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
        out.append("\n**요건·주의**")
        out += [f"- {x}" for x in reqs]
    else:
        out.append("이 조치는 사전 정의 사례엔 없지만, 아래 사다리와 **관련 문서 근거**로 판단하세요.")
        out.append("생활지도 사다리: " + " → ".join(_LADDER))
        out.append("- 낮은 단계(조언·주의)부터 시도하고, 안 되면 한 단계씩 올리세요.")
        out.append("- 모든 조치는 인권 존중 + 법령·학칙 범위 + 최소한도. 신체적 고통은 금지.")

    # 어떤 조치든 관련 고시·교육청 매뉴얼 근거를 함께 검색해 붙인다(하드코딩 안 된 사례도 커버)
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
_PARENT_THREAT = ["아동학대", "신고", "고소", "고발", "교육청", "국민신문고", "언론", "변호사", "소송", "가만 안"]
_PARENT_INTENT = ["의도", "일부러", "고의", "작정", "왜 그랬"]
_PARENT_APOLOGY = ["사과", "사죄", "잘못 인정"]
_DRAFT_EMOTION = ["힘들", "지치", "감당", "버겁", "괴롭", "스트레스", "죽겠"]
_DRAFT_FAULT = ["죄송", "제 잘못", "제 실수", "송구", "사과드"]
_DRAFT_ESCAPE = ["감당이 안", "포기", "못 하겠", "어쩔 수 없", "감당이 안 돼"]
_DRAFT_PROMISE = ["해드릴게요", "약속", "보장", "책임지"]


@mcp.tool(annotations={"title": "학부모 대화 안전 필터", "readOnlyHint": True})
def safe_parent_message(parent_message: str = "", teacher_draft: str = "") -> str:
    """Analyze a parent's message and/or a teacher's draft reply, then return a
    safer, de-escalating response strategy: detect the parent's real need and any
    threat to document, strip self-incriminating / out-of-scope phrasing from the
    teacher's draft, and reframe toward child-safety. Real-time defense for talk.

    Args:
        parent_message: What the parent said/wrote (the message being responded to). Optional.
        teacher_draft: The teacher's draft reply to make safe. Optional.
    """
    if not (parent_message.strip() or teacher_draft.strip()):
        return ("학부모가 보낸 말과(또는) 보내려는 답장 초안을 붙여넣어 주세요.") + DISCLAIMER
    out = []

    if parent_message.strip():
        out.append("**1. 상대(학부모) 말 분석**")
        pm = parent_message
        if any(k in pm for k in _PARENT_THREAT):
            out.append("- 🚨 **위협/신고 언급 감지** → 이 메시지를 **증거로 보존**(원본 캡처·저장)하세요. "
                       "정당한 지도에 대한 반복적 위협은 교육활동 침해(부당 간섭)가 될 수 있어요(→ `guide_response_flow`, `defend_child_abuse`).")
        if any(k in pm for k in _PARENT_INTENT):
            out.append("- ⚠️ **의도 추궁** → '고의였냐'는 교사가 판단·인정할 문제가 아니에요. "
                       "\"의도는 제가 판단할 수 있는 영역이 아니에요\"로 되돌리세요.")
        if any(k in pm for k in _PARENT_APOLOGY):
            out.append("- ⚠️ **사과 요구** → 사실이 확인되지 않은 잘못을 인정하지 마세요. 유감 표현과 사실 인정은 구분.")
        out.append("- 💡 **진짜 원하는 것**: 대개 처벌이 아니라 '내 아이가 학교에서 평안한 것'이에요. "
                   "거기에 맞춰 답하면 대화가 풀려요.")
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

    out.append("**3. 안전한 답장 원칙**")
    out.append("- ✅ **아동 안전·성장 프레임**: 교사 감정이 아니라 \"○○이가 안전하고 편안하게 지내려면\"으로.")
    out.append("- ✅ **직무 경계**: 의도 판단·진실 규명·형사 문제는 되돌리기. 교사는 '교육'만.")
    out.append("- ✅ **사실만, 짧게, 기록 남게**(문자/메신저로).")
    out.append("- 📩 안전 오프닝 예: \"어머니, ○○이가 학교에서 안전하고 편안하게 지내는 게 저도 가장 중요해요. "
               "그래서 함께 봐야 할 부분을 말씀드려요…\"")
    return "\n".join(out) + DISCLAIMER


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
