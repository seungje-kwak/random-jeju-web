# Random Jeju

주사위를 굴리면 제주 어딘가가 뽑히고, 그 근처 실제 장소로 내 취향·체력·시간에 맞춘 하루 코스를 받고, 다녀온 사진을 지도와 피드에 남기는 웹앱.

기존 RandomJeju(Android + Ktor)와 해커톤 웹앱 MyPace Jeju를 합친 저장소다. 계획과 결정은 [tasks/prd-random-jeju-merge.md](tasks/prd-random-jeju-merge.md)에 있다. 코스 엔진의 기준 문서는 [prd-mypace-jeju.md](prd-mypace-jeju.md)와 `tasks/prd-*.md`다.

```
frontend/              Next.js 14 + Tailwind, 카카오맵      → Vercel  (Root Directory: frontend)
backend/               FastAPI, 코스 플래너(규칙/LLM)       → Railway (Root Directory: backend)
supabase/migrations/   DB 구조 기록. Supabase 프로젝트는 RandomJeju 프로젝트 하나를 쓴다
data/                  장소 시드 CSV, 데모 코스
```

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| M0 | 저장소 만들기, RLS 긴급 조치, DB 비밀번호 교체, Vercel·Railway 연결 | 저장소·RLS·비밀번호 완료 (2026-11-19). Vercel·Railway 연결 남음 |
| M1 | 해커톤 스키마·장소 데이터를 RandomJeju Supabase로 | 완료 (2026-11-19). 배포 환경 변수(US-005)는 Vercel·Railway 연결 뒤 |
| M2 | 익명 세션, 토큰 검증 | 완료 (2026-11-19) |
| M3 | 랜덤 지점 + 주변 코스 | 완료 (2026-11-19). `/random` 화면, 랜덤 코스, 한국어 기본, 유료 잠금 끔. 배포 환경의 응답 시간 측정은 Vercel·Railway 연결 뒤 |
| M4 | 사진 업로드, 사진 지도, 피드 | 완료 (2026-11-19). `/feed`, `/map`, `/upload`, 4개 탭, 좋아요·댓글·닉네임. 글·댓글 삭제(US-028)와 게시글 화면(US-029)은 P1 |
| M5 | 방문 인증 | 완료 (2026-11-19). 랜덤 지점 500m·장소 200m(넓은 장소 500m)·7일 안의 사진이면 "다녀옴" 인증, 코스·여행 모드·피드에 표시 |
| M6 | 한국어 완성 | 완료 (2026-11-19). 장소 1,065곳 한국어 소개(검수 66, LLM 번역 999), 추천 이유·빈 식사 시간 문구 한국어 |
| M7 | Ktor 서버 종료 | 완료 (2026-11-19). Cloud Run 공개 호출 차단(403, 되돌릴 수 있음), 시간 열 `timestamptz` 변환, Android용 정책 12개 삭제. Supabase B는 해커톤 웹앱용으로 그대로 둔다 |

## 마이그레이션

- `0000_randomjeju_baseline.sql`: RandomJeju 프로젝트에 이미 있는 구조(2026-11-19 덤프). 다시 실행하지 않는다.
- `0001_mypace.sql`: 해커톤 테이블. 2026-11-19 적용.
- `0002_merge.sql`: 통합용 열과 `visits` 테이블 (PRD FR-30). 2026-11-19 적용. 시간 열 변환(FR-32)과 정책 정리(FR-34)는 Ktor를 끄는 M7에 한다.
- `0003_random_point.sql`: 격자 칸을 육지로 자르고 `random_point()`, `mark_grids()` 함수를 만든다 (PRD FR-0, FR-1). 2026-11-19 적용.
- `0004_posts.sql`: 사진 게시글·피드·좋아요·댓글·사진 지도 DB 함수 (PRD FR-11–FR-18). 좋아요·댓글 수를 한 번 다시 센다. 2026-11-19 적용.
- `0005_visits.sql`: 방문 인증 저장(`add_visit`, 코스·장소당 한 번)과 코스별 인증 목록, 피드의 인증 배지 (PRD FR-19–FR-21). 2026-11-19 적용.
- `0006_cleanup.sql`: Ktor를 끈 뒤 정리. 타임존 없는 시간 열 4개를 `timestamptz`로(촬영 시각은 한국 시간, 나머지는 UTC로 해석), `create_photo_post`가 시간대 있는 촬영 시각을 받게, Android 앱용 RLS 정책 12개 삭제 (PRD FR-32, FR-34). 2026-11-19 적용.

장소 데이터 순서 (모두 다시 실행해도 된다):

1. 장소 영어 설명을 고쳤거나 장소를 더했으면 `backend/scripts/translate_places.py` (바뀐 장소만 LLM으로 한국어 번역 → `data/seed/places_ko.csv`)
2. `backend/scripts/build_places.py` (CSV → `backend/app/data/places.json`, 한국어 설명 포함)
3. `backend/scripts/seed_supabase.py` (Supabase에 넣기)
4. 장소 위치가 바뀌었으면 `backend/scripts/mark_grids.py` (랜덤 지점을 뽑을 칸이 장소 위치에 따라 정해진다)

랜덤 코스 품질 평가 (Supabase 없이, 규칙 플래너): `backend/.venv/Scripts/python.exe backend/scripts/eval_random.py` → `backend/eval/random-rules.json`

## 로컬 실행

```bash
# backend (http://localhost:8000)
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
# backend/.env.example을 backend/.env로 복사하고 SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET을 채운다
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# frontend (http://localhost:3000)
cd frontend
npm install
# frontend/.env.example을 frontend/.env.local로 복사하고 NEXT_PUBLIC_* 값을 채운다
npm run dev
```

`.env`, `.env.local`은 커밋하지 않는다.

게스트 로그인 확인 (백엔드가 켜져 있을 때, 익명 사용자 하나를 만든다):

```bash
cd frontend && node --env-file=.env.local scripts/check-guest-auth.mjs
```
