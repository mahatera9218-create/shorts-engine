"""블로그 이름 후보 겹침 점검 (2026-10-04): 네이버 공식 블로그 검색 API로 같은·비슷한 이름의 블로그가 있는지 본다.

- 이름을 따옴표로 검색해 결과 문서 수와, 블로그 이름(bloggername)에 후보가 들어간 블로그를 센다.
- API는 상위 100개까지만 주므로 '없음'은 '검색 상위에서 못 찾음'이라는 뜻이다. 최종 확인은 네이버 블로그 앱에서.
결과: reports/브랜드/블로그이름-점검-<날짜>.md
"""
from __future__ import annotations

import time
from datetime import date

from .common import ROOT, load_yaml, missing_secrets, request_json
from .naver_hub import ApiHub, clean


def norm(s: str) -> str:
    return "".join(s.split()).lower()


def main() -> None:
    out = ROOT / "reports" / "브랜드" / f"블로그이름-점검-{date.today()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 블로그 이름 후보 겹침 점검 ({date.today()})", "",
             "네이버 블로그 검색(공식 API) 상위 100개에서 같은 이름이 들어간 블로그를 찾았어요. "
             "'없음'은 검색 상위에서 못 찾았다는 뜻이라 최종 확인은 앱에서 한 번 더 해요.", ""]
    if missing_secrets("naver_hub"):
        lines.append("- 네이버 키가 없어 점검하지 못함")
    else:
        hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"])
        lines += ["| 후보 | 검색 문서 수 | 이름이 겹치는 블로그 |", "|---|---|---|"]
        for c in load_yaml("blog_names.yaml")["candidates"]:
            name = c["name"]
            try:
                data = request_json("GET", hub.base + hub.paths["blog_search"], headers=hub._headers(),
                                    params={"query": f'"{name}"', "display": 100, "sort": "sim"})
                same = sorted({clean(it.get("bloggername")) for it in data.get("items", [])
                               if norm(name) in norm(clean(it.get("bloggername")) or "")})
                lines.append(f"| {name} | {data.get('total', 0):,} | {', '.join(same) if same else '없음'} |")
            except Exception as e:  # 실패도 그대로 남긴다
                lines.append(f"| {name} | 실패 | {type(e).__name__} |")
            time.sleep(0.15)
        lines += ["", "## 후보별 뜻", ""] + [f"- **{c['name']}**: {c['why']}" for c in load_yaml("blog_names.yaml")["candidates"]]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
