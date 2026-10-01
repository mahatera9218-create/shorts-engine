"""블로그 본문용 '선수 데이터 표' (대표 결정 2026-10-01): AI 브리핑이 인용할 만한 실제 데이터.

사람들은 '원태인 연봉'을 검색하지 '원태인 연봉 벤츠'를 검색하지 않는다 → 표는 비교 물건이 아니라
선수의 소속·올해 연봉·연봉 근거·올 시즌 기록(뉴스에서 뽑아 확인한 값, 기준일 포함)·1경기당 연봉(계산)으로.
결과: posts/<글>/table.json {title, header, rows} — 도우미가 '[표 1: …]' 자리에 네이버 표로 보여 준다.
"""
from __future__ import annotations

import re

from .receipt import won

SKIP = {"salary"}
GENERIC = {"contract_total": "계약 총액", "games": "출전 경기", "home_runs": "홈런", "hits": "안타", "wins": "승",
           "innings": "이닝", "goals": "골", "assists": "도움", "points": "득점"}


def _with_detail(value: str, label: str, common: str) -> str:
    """두 선수 조건이 다를 때 값 옆에 각자 조건: 계약은 기간을 병기 ('80억원 · 4년 FA 계약, 최대'),
    그 밖은 다른 말만 괄호로 ('135경기 (타자)')."""
    if "계약" in common:
        period = re.search(r"\d+(?:\+\d+)?년", label)
        detail = " ".join(x for x in [period.group(0) if period else "", "FA" if "FA" in label else "", "계약"] if x)
        detail += ", 최대" if "최대" in label else ""
        main, _, rest = value.partition(" (약 ")
        return f"{main} · {detail}" + (f" (약 {rest}" if rest else "")
    detail = label
    for w in common.split():
        detail = detail.replace(w, " ")
    detail = re.sub(r"\s+", " ", detail).strip(" ·,")
    for w in ("의", "와", "과"):
        detail = re.sub(rf"{w}$", "", detail).strip()
    return f"{value} ({detail})" if detail else value


def _base(label: str) -> str:
    return re.split(r"\s*\(", label, 1)[0].strip()


def _when(label: str) -> str:
    m = re.search(r"\(([^)]*)\)", label)
    return m.group(1) if m else ""


def _value(f: dict, fx: float | None) -> str:
    v, u = f["value"], f.get("unit", "")
    if u == "KRW":
        return won(v)
    if u in ("USD", "EUR", "GBP"):
        word = {"USD": "달러", "EUR": "유로", "GBP": "파운드"}[u]
        eok, man = divmod(int(v), 10 ** 8)
        man //= 10 ** 4
        amt = (f"{eok:,}억" + (f" {man:,}만" if man else "")) if eok else (f"{man:,}만" if man else f"{v:,.0f}")
        return f"{amt} {word}" + (f" (약 {won(v * fx)})" if fx and u == "USD" else "")
    num = f"{v:,}" if float(v).is_integer() else f"{v}"
    return num + ("" if u in ("점", "") else u)


def _stats(facts: dict, prefix: str = "") -> list[tuple[str, str, str]]:
    """(항목, 값, 기준) — 같은 항목은 가장 최근 날짜 하나만."""
    best: dict[str, tuple[str, dict]] = {}
    for k, f in facts.items():
        key = k.split(".", 1)[1] if prefix and k.startswith(prefix) else (None if prefix else k)
        if key is None or key in SKIP or key.startswith("fx_"):
            continue
        name = _base(f["label"])
        if prefix:
            name = name.split(" ", 1)[1] if " " in name else name  # "박찬호 경기" → "경기"
        if name not in best or str(f.get("date", "")) > str(best[name][1].get("date", "")):
            best[name] = (k, f)
    return [(n, f, _when(f["label"]) or str(f.get("date", ""))) for n, (_, f) in best.items()]


def build(d: dict, n: dict, facts: dict) -> dict | None:
    th = d.get("theme", "receipt")
    season = d.get("season", "")
    if th == "rank":
        rows = [[f"{r['rank']}위", r["name"], r.get("team") or "-", won(r["krw"]), won(r["krw"] / d["games"])] for r in d["rows"]]
        return {"title": d["title"], "header": ["순위", "선수", "팀", f"{season} 연봉", "1경기당"], "rows": rows}
    if th in ("same", "cross"):
        a, b = d["a"], d["b"]
        an, bn = a.get("short_name") or a["player"], b.get("short_name") or b["player"]
        rows = [["소속", a.get("team", "-"), b.get("team", "-")],
                [f"{season} 연봉", won(n["a"]["salary_krw"]), won(n["b"]["salary_krw"])]]
        keys = [k.split(".", 1)[1] for k in facts if k.startswith("a.")]
        for key in [k for k in keys if f"b.{k}" in facts and k not in SKIP and not k.startswith("fx_")]:
            fa, fb = facts[f"a.{key}"], facts[f"b.{key}"]
            label = _base(fa["label"])
            for nm in (a["player"], an):
                label = label.removeprefix(nm).strip()
            label = label.removeprefix("올 시즌").strip() or key
            other = _base(fb["label"])
            for nm in (b["player"], bn):
                other = other.removeprefix(nm).strip()
            other = other.removeprefix("올 시즌").strip()
            va, vb = _value(fa, a.get("fx_krw_per_usd")), _value(fb, b.get("fx_krw_per_usd"))
            if other != label:  # 두 선수 기사 표현이 다르면 공통 이름 + 각자 조건(기간 등)을 값 옆에 (대표 요청 2026-10-01)
                common = GENERIC.get(key, label)
                va, vb = _with_detail(va, label, common), _with_detail(vb, other, common)
                label = common
            rows.append([label, va, vb])
        if n.get("unit_label") and n.get("va"):
            rows.append([f"{n['unit_label']}당 연봉 (계산)", won(n["va"]), won(n["vb"])])
        return {"title": f"{an} vs {bn} {season} 연봉·기록", "header": ["항목", an, bn], "rows": rows}
    name = d.get("short_name") or d.get("player", "")
    fx = d.get("fx_krw_per_usd")
    rows = [["소속", d.get("team") or "-"]]
    sal = facts.get("salary")
    rows.append([f"{season} 연봉", _value(sal, fx) if sal else won(n.get("salary_krw", 0))])
    if d.get("salary_basis"):
        rows.append(["연봉 근거", d["salary_basis"]])
    dates = set()
    for label, f, _ in _stats(facts):
        rows.append([label, _value(f, fx)])
        if f.get("date"):
            dates.add(str(f["date"]))
    per = n.get("per", {})
    if per.get("games"):
        rows.append(["1경기당 연봉 (계산)", won(per["games"])])
    if n.get("min_wage_yearly_krw") and n.get("salary_krw"):
        rows.append(["최저임금 몇 년치 (계산)", f"{n['salary_krw'] / n['min_wage_yearly_krw']:.1f}년"])
    if dates:
        rows.append(["기준", f"{max(dates)}까지 보도된 기록 (기록마다 날짜가 조금 다를 수 있음)"])
    return {"title": f"{name} {season} 연봉·시즌 기록", "header": ["항목", "내용"], "rows": rows}
