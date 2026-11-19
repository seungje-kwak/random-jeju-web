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
| M2 | 익명 세션, 토큰 검증 | |
| M3 | 랜덤 지점 + 주변 코스 | |
| M4 | 사진 업로드, 사진 지도, 피드 | |
| M5 | 방문 인증 | |
| M6 | 한국어 완성 | |
| M7 | Ktor 서버 종료 | |

## 마이그레이션

- `0000_randomjeju_baseline.sql`: RandomJeju 프로젝트에 이미 있는 구조(2026-11-19 덤프). 다시 실행하지 않는다.
- `0001_mypace.sql`: 해커톤 테이블. 2026-11-19 적용.
- `0002_merge.sql`: 통합용 열과 `visits` 테이블 (PRD FR-30). 2026-11-19 적용. 시간 열 변환(FR-32)과 정책 정리(FR-34)는 Ktor를 끄는 M7에 한다.

장소 데이터는 `backend/scripts/seed_supabase.py`로 넣는다 (다시 실행해도 된다).

## 로컬 실행

지금 코드는 해커톤 커밋 `30e236c`와 같다. 실행 방법은 해커톤과 같다.

```bash
# backend (http://localhost:8000)
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
# backend/.env.example을 backend/.env로 복사하고 SUPABASE_URL, SUPABASE_SERVICE_KEY를 채운다
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# frontend (http://localhost:3000)
cd frontend
npm install
npm run dev
```

`.env`, `.env.local`은 커밋하지 않는다.
