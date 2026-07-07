# 핵심 조문 캐시 빌더 (빌드 시 1회) — 법제처 API 다운 시 폴백용 law_cache.json 생성.
# 실행: python build_law_cache.py   (mcp_server의 조회·추출 로직 재사용)
import json
import os
import mcp_server as M

# 캐시할 핵심 조문: 표시명 → (검색어, [조문(가지)번호])
TARGETS = {
    "교원지위법": ("교원의 지위 향상 및 교육활동 보호", ["17", "19", "20", "25", "26"]),
    "초중등교육법": ("초ㆍ중등교육법", ["20의2", "20의6"]),
    "아동학대처벌법": ("아동학대범죄의 처벌 등에 관한 특례법", ["11의2", "17의3"]),
}


def fetch(query, arts):
    s = M._law_get("lawSearch.do", {"target": "law", "query": query, "display": "5"})
    laws = (s or {}).get("LawSearch", {}).get("law", [])
    if isinstance(laws, dict):
        laws = [laws]
    cur = next((l for l in laws if l.get("현행연혁코드") == "현행"), laws[0] if laws else None)
    if not cur:
        return None
    b = M._law_get("lawService.do", {"target": "law", "MST": cur.get("법령일련번호")})
    jo = (b or {}).get("법령", {}).get("조문", {})
    units = jo.get("조문단위", []) if isinstance(jo, dict) else []
    if isinstance(units, dict):
        units = [units]
    articles = {}
    for a in arts:
        base, _, branch = a.partition("의")
        base, branch = base.strip(), branch.strip()
        hit = next((u for u in units
                    if str(u.get("조문번호", "")) == base
                    and str(u.get("조문가지번호", "") or "").strip() == branch), None)
        if hit:
            articles[a] = {"title": hit.get("조문제목", ""), "text": M._flatten_article(hit)}
    return {"name": cur.get("법령명한글", query), "efYd": cur.get("시행일자", ""), "articles": articles}


def main():
    cache = {}
    for law, (q, arts) in TARGETS.items():
        r = fetch(q, arts)
        if r:
            cache[law] = r
            print(f"{law} ({r['name']}, 시행 {r['efYd']}): {list(r['articles'].keys())}")
        else:
            print(f"{law}: 실패")
    out = os.path.join(M.HERE, "law_cache.json")
    json.dump(cache, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
