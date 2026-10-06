"""사진 시험 (2026-10-06): 바뀐 글 제작 경로(kunine.ai_photo, 회사 간판·고화질)로 삼성전자 서초·기흥을 그려 대표가 GPT 대화창 결과와 비교.
결과: reports/사진시험/*.png  (약 700원)
"""
from pathlib import Path

from . import kunine

OUT = Path("reports/사진시험")
SHOTS = {
    "서초사옥": "Wide aerial photograph of the Samsung Electronics Seocho office tower in Gangnam, Seoul, tall blue glass "
            "skyscraper with the SAMSUNG logo near the top, sunny day, busy avenue with trees, city skyline and Han river behind.",
    "기흥캠퍼스": "Aerial view of the Samsung Electronics Giheung semiconductor campus in Yongin, large grey fab building with "
             "the blue SAMSUNG logo on its wall, landscaped grounds with a pond, mountains in the distance, clear summer sky.",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, desc in SHOTS.items():
        ok = kunine.ai_photo(desc, OUT / f"{name}.png", "1536x1024", "Samsung Electronics")
        print(name, "성공" if ok else "실패")


if __name__ == "__main__":
    main()
