# 교권119 RAG 색인 빌더 (빌드 시 1회 실행 — 배포 런타임엔 불필요)
# 교육부·시도교육청 생활지도/교권 문서 + 학생생활지도 고시 → 텍스트 추출 → 조각(chunk) → corpus.json
# 실행:  pip install pymupdf  &&  python build_corpus.py
# (fitz/pymupdf·requests는 빌드 전용 의존. 런타임 서버는 corpus.json만 읽음)
import os, re, json, io, urllib.request, urllib.parse

OC = os.environ.get("LAW_OC", "mindminer")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 출처 목록 — 최신(2025·2026) 우선. PDF는 (표시명, url), 고시는 법제처 행정규칙 API로 수집.
PDF_SOURCES = [
    # 교육부 공식 국가 표준 매뉴얼(최고 권위)
    ("교육부 교육활동 보호 매뉴얼(2026 일부개정)",
     "https://www.moe.go.kr/boardCnts/fileDown.do?m=0305&s=moe&fileSeq=45f76c653581704fce50f2d1b387f01a"),
    ("전남교육청 교육활동보호 매뉴얼(2026)",
     "https://www.jne.go.kr/upload/thsupport/na/bbs_339/ntt_5170000/doc_57389173-2d62-4eb9-a118-4547e343a6ab1772a7724b93123.pdf"),
    ("경기교육청 2026 교육활동 보호 종합대책",
     "https://www.goe.go.kr/resource/goe/na/bbs_2675/2026/03/e75532f7-cc69-48b8-abb7-ea9143081ff9.pdf"),
    ("서울교육청 교육활동 보호 시행계획(2026)",
     "https://buseo.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2143615&q_fileId=3d60e492-fa75-4315-997f-3bda2fe4c356"),
    # 실전 생활지도 자료(문제행동별 개입·상담기법·사례) — 추출 검증됨(KR 0.93~0.97)
    ("문제행동별 개인상담 개입 지도서(17개 교육청 Wee센터, 2026)",
     "https://www.ice.go.kr/upload/ice/na/bbs_2094/2026/05/e658af8a6a1e40cfa3537b2f2f41ea0f.pdf"),
    ("학생상담·생활지도 매뉴얼(교사용, NYPI)",
     "https://www.nypi.re.kr/repository/bitstream/2022.oak/3424/1/41.pdf"),
    ("경남교육청 교육활동 보호 매뉴얼(2025)",
     "https://www.gne.go.kr/component/file/ND_fileDownload.do?q_fileSn=181533599&q_fileId=d331ec43-ea10-42b8-b191-f552e3735c19"),
    ("학교 민원 응대 안내자료(교육부·경기, 2024)",
     "https://www.goe.go.kr/resource/old/BBSMSTR_000000000107/BBS_202410080511161001.pdf"),
]
ADMRUL_QUERIES = ["교원의 학생생활지도에 관한 고시"]

CHUNK_MAX = 500   # 조각 최대 글자수


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def chunks_from_text(text, source, page):
    """페이지 텍스트를 문장 경계에서 ~CHUNK_MAX 글자로 묶어 조각화."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    # 폰트 깨짐 등 추출 실패 페이지 스킵(쓰레기 방지): 한글 비율이 너무 낮으면 버린다
    if len(re.findall(r"[가-힣]", text)) < len(text) * 0.15:
        return []
    sents = re.split(r"(?<=[.。!?])\s+|\n", text)
    out, buf = [], ""
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if len(buf) + len(s) + 1 > CHUNK_MAX and buf:
            out.append({"source": source, "page": page, "text": buf.strip()})
            buf = s
        else:
            buf = (buf + " " + s).strip()
    if buf:
        out.append({"source": source, "page": page, "text": buf.strip()})
    return out


def from_pdf(name, url):
    import fitz
    print(f"[PDF] {name} …", end=" ", flush=True)
    data = _fetch(url)
    doc = fitz.open(stream=data, filetype="pdf")
    items = []
    for i in range(doc.page_count):
        items += chunks_from_text(doc[i].get_text(), name, i + 1)
    print(f"{doc.page_count}p → {len(items)} chunks")
    return items


def _walk_text(x, acc):
    if isinstance(x, dict):
        for k, v in x.items():
            if k.endswith("내용") and isinstance(v, str):
                acc.append(v)
            else:
                _walk_text(v, acc)
    elif isinstance(x, list):
        for i in x:
            _walk_text(i, acc)
    elif isinstance(x, str) and len(x) > 40:
        acc.append(x)


def from_admrul(query):
    print(f"[고시] {query} …", end=" ", flush=True)
    su = ("https://www.law.go.kr/DRF/lawSearch.do?"
          + urllib.parse.urlencode({"OC": OC, "target": "admrul", "type": "JSON", "query": query}))
    s = json.loads(_fetch(su).decode("utf-8"))
    r = s.get("AdmRulSearch", {}).get("admrul", [])
    r = [r] if isinstance(r, dict) else r
    hit = next((x for x in r if query in (x.get("행정규칙명") or "")), r[0] if r else None)
    if not hit:
        print("없음"); return []
    rid = hit.get("행정규칙일련번호")
    name = hit.get("행정규칙명", query)
    bu = ("https://www.law.go.kr/DRF/lawService.do?"
          + urllib.parse.urlencode({"OC": OC, "target": "admrul", "type": "JSON", "ID": rid}))
    b = json.loads(_fetch(bu).decode("utf-8"))
    acc = []
    _walk_text(b, acc)
    text = "\n".join(dict.fromkeys(acc))   # 중복 제거·순서 보존
    items = chunks_from_text(text, name, 0)
    print(f"{len(items)} chunks")
    return items


def main():
    corpus = []
    for name, url in PDF_SOURCES:
        try:
            corpus += from_pdf(name, url)
        except Exception as e:
            print(f"  실패({name}): {e}")
    for q in ADMRUL_QUERIES:
        try:
            corpus += from_admrul(q)
        except Exception as e:
            print(f"  실패({q}): {e}")
    for i, c in enumerate(corpus):
        c["id"] = i
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus.json")
    json.dump(corpus, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    srcs = {}
    for c in corpus:
        srcs[c["source"]] = srcs.get(c["source"], 0) + 1
    print(f"\n총 {len(corpus)} chunks → {out}")
    for s, n in srcs.items():
        print(f"  · {s}: {n}")


if __name__ == "__main__":
    main()
