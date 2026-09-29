# 운영자 안내 · Pexels 사진 키 (썸네일 실사 배경, 무료)

썸네일 배경에 **진짜 경기장·야구공 사진**을 넣으려면 Pexels 키 1개가 필요합니다. **무료**이고 결제 수단도 필요 없습니다.
(Pexels 사진은 상업 이용이 무료입니다. 사진 출처는 글 끝에 자동으로 붙습니다.)

## ① 가입 (계정 생성은 대표님 결정)

1. 휴대폰 브라우저로 **pexels.com/api** 접속
2. **Get Started** 또는 **Your API Key** 누르기 → 이메일이나 구글로 가입
3. 사용 목적을 묻는 칸이 나오면 아래처럼 적기
   - 무엇에 쓰나요: `Blog thumbnails for a sports salary blog`
   - 웹사이트: `https://blog.naver.com/tenbillionsound`
4. 약관 동의 → 키 생성

## ② 키 복사 → GitHub에 넣기

1. 화면에 나온 API 키를 **복사**
2. 👉 [키 넣는 화면 열기](https://github.com/mahatera9218-create/shorts-engine/settings/secrets/actions/new)
3. **Name:** `PEXELS_API_KEY` / **Secret:** 붙여넣기 → **Add secret**

## ③ 이미지 다시 그리기

1. 👉 [이미지 다시 그리기 열기](https://github.com/mahatera9218-create/shorts-engine/actions/workflows/rebuild-images.yml)
2. **Run workflow** → 칸은 비워 두고 초록 버튼
3. 1~2분 뒤 ✅ 나오면 Claude에게 알려주세요. 새 썸네일을 제가 먼저 확인합니다.
