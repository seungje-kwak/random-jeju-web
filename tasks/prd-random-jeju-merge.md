# PRD: Random Jeju 웹 통합 (랜덤 지점 + 맞춤 코스)

| 항목 | 내용 |
|---|---|
| 문서 버전 | v0.2 (2026-11-19: 미정 사항 11개를 결정하고 Supabase A 조회 결과를 반영. 결정 기록은 10장) · v0.1 (2026-11-19, 초안) |
| 대상 코드 | 해커톤 웹앱 `hackathon/frontend`, `hackathon/backend` (커밋 `30e236c` 기준) / 기존 앱 `D:\androidStudio\RandomJeju`, `D:\intellij\random-jeju-api` |
| 코스 엔진 기준 문서 | `prd-mypace-jeju.md` 8·9·10장, `tasks/prd-recommendation-p0.md`, `tasks/prd-recommendation-p1.md`, `tasks/prd-travel-range.md`. 이 문서가 바꾸지 않는 코스 규칙은 모두 그 문서들을 따른다 |
| 결정된 방향 | ① 랜덤 = 랜덤 지점을 뽑고 그 주변 실제 장소로 하루 코스 ② 국내+외국인, 한국어 기본 ③ RandomJeju에서 사진 업로드·사진 지도, 게시판(피드·좋아요·댓글), 랜덤 지점 방문 인증을 가져옴 ④ Supabase는 RandomJeju 프로젝트로 통합. 그 밖의 결정은 10장 |

---

## 1. 개요

### 1.1 두 앱의 지금 상태

| | RandomJeju (기존) | MyPace Jeju (해커톤) |
|---|---|---|
| 형태 | Android 앱(Jetpack Compose) + Ktor(Kotlin) API. API는 Cloud Run에 배포(이전에는 Render) | Next.js 14 웹(Vercel) + FastAPI(Railway) |
| DB | Supabase 프로젝트 **A**: PostGIS, Auth, Storage(`photos`, `thumbnails`) | Supabase 프로젝트 **B**: 장소 1,065곳, 코스 |
| 랜덤 | `grids`에서 `blacklist = false`인 칸 하나를 무작위로 고르고, 칸 안의 임의 좌표와 읍면동 이름을 준다 (`RandomLocationService.kt:10-70`). 입력이 없고 장소 정보도 없다. 결과 카드의 "상세 정보" 버튼은 TODO다 | 없음. 같은 조건으로 다른 동네의 코스를 받는 "Shuffle my day"만 있다 |
| 추천 | 없음 | 실제 장소로 하루 코스를 짠다. 취향·체력·식단·시작/끝 시각·영업시간·식사 시간을 반영하고, LLM이나 규칙으로 고른다. 여행 중 다시 짜기 4종(비·휴무·배고픔·피곤)이 있다 |
| 소셜 | 사진 업로드(EXIF 위치), 사진 지도(마커와 읍면동 클러스터), 게시판(카테고리, 좋아요, 댓글) | 없음 |
| 사용자 | Supabase 이메일 로그인. 서버는 `?userId=`를 검증하지 않고 믿는다 | 없음. 코스를 UUID로만 구분한다 |
| 화면 언어 | 한국어 | 영어 기본. ko/ja/zh 메시지가 있지만 장소 설명은 27곳만 번역됐다 |
| 데이터 양 (2026-11-19 조회) | 사용자 2명(모두 이메일), 게시글 27, 사진 32, 댓글 8, 좋아요 25, 뽑힌 지점 274, 격자 7,969칸, 읍면동 43 | 장소 1,065곳, 지역 14개 |

### 1.2 풀려는 문제

- RandomJeju의 랜덤은 좌표 하나만 준다. 사용자는 "여기서 뭘 하지?"에서 멈추고, 그 지점에 가야 할 이유가 없다.
- MyPace의 코스는 정확하지만 "어디로 갈지"를 사용자가 정해야 한다. 우연히 발견하는 재미와, 다녀온 기록을 남기고 나눌 곳이 없다.

### 1.3 합친 서비스

| 항목 | 내용 |
|---|---|
| 이름 | Random Jeju (랜덤제주). MyPace라는 이름은 쓰지 않는다 (Q-01) |
| 한 줄 소개 | 주사위를 굴리면 제주 어딘가가 뽑히고, 그 근처 실제 장소로 내 취향·체력·시간에 맞춘 하루 코스를 받고, 다녀온 사진을 지도와 피드에 남기는 웹앱 |
| 핵심 흐름 | 🎲 굴리기 → 랜덤 지점 공개 → 이 근처로 하루 코스 → 여행 모드(다시 짜기) → 사진 올리기 → 방문 인증 → 사진 지도와 피드 |
| 사용자 | 제주를 여행하는 국내 여행자와 외국인 여행자 |
| 화면 언어 | 한국어 기본. en/ja/zh는 언어 선택으로 바꾼다 |

---

## 2. 목표

| # | 목표 | 달성 기준 |
|---|---|---|
| G1 | 핵심 흐름이 배포 환경에서 끝까지 동작한다 | 배포된 Vercel 주소에서 굴리기 → 코스 → 여행 모드 → 사진 업로드 → 방문 인증 → 피드와 사진 지도에 보이기까지 한 번에 된다 |
| G2 | 랜덤 코스가 해커톤 코스와 같은 품질 규칙을 지킨다 | 평가 스크립트(US-015)에서 이동 30분 상한 위반 0건, 식사 보장 위반 0건, 영업시간 위반 0건 |
| G3 | RandomJeju의 실제로 동작하던 기능을 웹에서 모두 쓸 수 있다. 알려진 버그는 옮기지 않는다 | 사진 업로드, 사진 지도, 피드, 좋아요, 댓글이 웹에서 동작한다. 썸네일 90° 회전, 로그아웃 상태 크래시, userId 위조가 재현되지 않는다 |
| G4 | 한국어가 기본이다 | 첫 방문(브라우저 언어 ko) 화면, 장소 설명, 코스 추천 이유가 한국어로 나온다 |
| G5 | 서비스가 한 스택으로 모인다 | 모든 요청이 Vercel → Railway(FastAPI) → Supabase A로 간다. Ktor 서버와 Supabase B를 끌 수 있다 |

---

## 3. 사용자 흐름과 화면 구조

### 3.1 핵심 흐름

```
[🎲 랜덤 탭]
   │ 🎲 굴리기 (로그인·온보딩 없이 바로)
   ▼
지도 카메라가 랜덤 지점으로 이동 + 주사위 마커
카드: "애월읍 어딘가" · 33.4631, 126.3312
      가장 가까운 동네: 한담 해안 (1.2km) · 근처 장소 3곳 미리보기(사진)
   │ [이 근처로 하루 코스 짜기]        [🎲 다시 굴리기]
   ▼
취향 프로필이 저장돼 있나?
   ├ 없다 → 온보딩 랜덤 모드 (지역 고르기 단계를 뺀 5단계) → 프로필 저장
   └ 있다 → 바로
   ▼
/course/{id}  (해커톤 결과 페이지 + 상단 "🎲 랜덤 지점" 배너)
   │ [여행 시작] → /course/{id}/trip (다시 짜기 4종, 해커톤 그대로)
   │ [📷 사진 올리기] (각 장소 카드와 여행 모드에서)
   ▼
업로드 → 위치가 맞으면 "다녀옴" 인증 → 피드·사진 지도에 표시
```

### 3.2 화면 구조

| 경로 | 화면 | 출처 |
|---|---|---|
| `/` | 랜딩. "🎲 랜덤으로 떠나기"(→ `/random`)와 "직접 지역 골라 코스 짜기"(→ `/onboarding`) | 해커톤 랜딩을 고침 |
| `/random` | 랜덤 탭. 전체 화면 카카오맵 + 아래 카드 | 새로 만듦 (Android `RandomView.kt`의 웹판) |
| `/onboarding` | 온보딩. `?mode=random`이면 지역 단계를 빼고, 끝나면 랜덤 코스를 만든다 | 해커톤 |
| `/course/{id}`, `/course/{id}/trip`, `/course/{id}/purchase` | 코스 결과, 여행 모드, 구매 목업 | 해커톤 |
| `/map` | 사진 지도. 읍면동 클러스터와 사진 마커 | 새로 만듦 (Android `MainActivity`의 지도) |
| `/feed` | 피드. 카테고리 필터, 좋아요, 댓글 | 새로 만듦 (Android `BoardView.kt`) |
| `/upload` | 사진 올리기 | 새로 만듦 (Android `PhotoUploadView.kt`, `UploadPostScreen.kt`) |
| `/posts/{id}` | 게시글 하나. 사진 지도 마커와 공유 링크가 여기로 온다 | 새로 만듦 (P1) |

- 모바일: 아래 탭 4개 `🎲 랜덤 | 🗺 지도 | 📰 피드 | ➕ 올리기`. 기본 탭은 랜덤이다. 코스, 여행 모드, 온보딩 화면에서는 탭을 숨기고 뒤로 가기를 둔다.
- 데스크톱: 같은 4개를 위쪽 내비게이션으로 둔다.
- Android의 검색 탭은 가져오지 않는다. 검색창이 연결되지 않은 채 하드코딩된 목록만 있었고, 카테고리 버튼은 피드의 카테고리 필터가 대신한다.

---

## 4. 사용자 스토리

단계(M0–M7)는 8.1의 구현 순서다. 우선순위는 P0(이번 통합에 꼭 필요), P1(P0가 배포된 뒤)이다.

### 4.1 기반: DB·인증·배포

#### US-001: Supabase A에 해커톤 스키마와 데이터 넣기 (P0, M1)
**설명:** 개발자로서, 해커톤 테이블과 장소 데이터를 Supabase A에 넣어서 한 DB로 서비스하고 싶다.

**완료 기준:**
- [x] `backend/sql/schema.sql`을 Supabase A의 SQL 편집기에서 실행해 8개 테이블(`areas`, `places`, `place_accessibility`, `food_options`, `phrase_cards`, `courses`, `course_items`, `place_reports`)이 생긴다. RandomJeju 테이블(`grids`, `locations`, `admin_areas`, `photos`, `posts`, `post_likes`, `comments`, `users`)과 이름이 겹치지 않음을 실행 전에 확인한다 (2026-11-19, `supabase/migrations/0001_mypace.sql`로 적용. 적용할 때 8개 테이블은 이미 빈 채로 있었고 열은 스키마와 같았다)
- [x] `backend/.env`의 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`를 A로 바꾸고 `scripts/seed_supabase.py`가 성공한다
- [x] `places` 1,065행, `areas` 14행이 들어간다 (accessibility 1,065, food_options 351, phrase_cards 49)
- [x] 백엔드 `pytest`가 모두 통과한다 (213 통과, 3 건너뜀). V9 UI가 되돌려 놓은 `frontend/config/map.ts`의 `bounds`를 제주 전체로 고쳐 `test_seed_bounds_cover_all_of_jeju`도 통과한다. 이 값은 지도 컴포넌트가 쓰지 않으므로(`lib/landmarks.ts`의 `ISLAND_MAP_BOUNDS`를 쓴다) 화면은 바뀌지 않는다
- [x] 로컬에서 코스 만들기(4개 지역) → 코스 보기 → 비 재구성 → Shuffle → 여행 모드가 A를 상대로 동작한다
- 뺀 것: `scripts/reset_emma.py`(해커톤 발표용 Emma 데모)는 Random Jeju에 옮기지 않는다. 해커톤 저장소에서도 10:00–18:00 안에 정류장 9(이호테우해변)가 들어가지 않아 실패한다 (`f062493` 이후 시간 계산). `eval_planner.py`는 Supabase를 읽지 않으므로 DB 이전 확인에 쓰지 않는다

#### US-002: RandomJeju 스키마를 저장소에 기록하고 보강하기 (P0, M1)
**설명:** 개발자로서, Supabase A에 손으로 만들어진 RandomJeju 테이블을 마이그레이션 파일로 남기고, 통합에 필요한 열과 제약을 더하고 싶다.

**완료 기준:**
- [x] `pg_dump --schema-only`로 A의 `public` 스키마를 받아 `supabase/migrations/0000_randomjeju_baseline.sql`로 저장한다 (데이터 없이). 2026-11-19 조회로 확인한 구조(8.5)와 같아야 한다
- [x] `0001_mypace.sql`은 해커톤 `schema.sql`과 같은 내용이다
- [x] `0002_merge.sql`이 FR-30의 변경을 담고, 두 번 실행해도 오류가 없다 (`if not exists`). 2026-11-19 적용. **FR-32(시간 열 변환)는 M7로 미룬다**: Ktor가 아직 이 열들에 타임존 없는 값을 쓰고 있어서, 지금 바꾸면 Android 업로드의 촬영 시각이 9시간 어긋난다. FR-34의 정책 정리도 M7이다. (둘 다 2026-11-19 M7에서 `0006_cleanup.sql`로 적용)
- [x] `post_likes`는 이미 `(post_id, user_id)`가 기본 키라 고유 제약을 더하지 않는다. 같은 정의의 중복 제약 `post_likes_unique_post_user`는 지운다. `admin_areas.geom`의 중복 인덱스 `idx_admin_geom`도 지운다
- [x] 모든 테이블에 RLS가 켜져 있다 (FR-34). 새 `visits` 테이블 포함. 적용 뒤 Ktor 응답(사진 28, 클러스터 12)이 그대로다

#### US-003: 익명 세션과 닉네임 (P0, M2)
**설명:** 사용자로서, 가입하지 않고도 사진을 올리고 좋아요와 댓글을 남기고 싶다.

**완료 기준:**
- [x] Supabase A에서 Anonymous Sign-Ins를 켠다 (2026-11-19)
- [x] 신원이 필요한 첫 동작(굴리기, 올리기, 좋아요, 댓글) 직전에 프론트가 `supabase.auth.signInAnonymously()`로 세션을 만든다. 화면에는 아무것도 뜨지 않는다. 세션이 이미 있으면 다시 만들지 않는다 (`frontend/lib/auth.ts`의 `accessToken()`. 동시에 불려도 세션은 하나. 실제 호출 지점은 M3·M4)
- [x] 첫 게시글이나 첫 댓글을 쓸 때 닉네임 입력 창(2–12자)이 뜬다. 저장하면 `POST /me`로 `users` 행이 생긴다. 다음부터는 뜨지 않는다 (M4에서 올리기·댓글에 연결, 브라우저 확인)
- [x] 닉네임을 정하기 전의 표시 이름은 `여행자` + 사용자 ID 앞 4자리다 (`displayName`, 4개 언어)
- [x] 로그인하지 않아도 피드, 사진 지도, 코스는 볼 수 있다 (Android의 "로그아웃이면 게시판이 비어 있음"을 고친다). 읽기는 게스트 세션을 만들지 않고, 세션이 이미 있을 때만 토큰을 보낸다
- [x] Typecheck/lint passes
- [x] Verify in browser (M4, 닉네임 창)
- 확인 (2026-11-19): `frontend/scripts/check-guest-auth.mjs`가 실제 프로젝트에서 supabase-js로 익명 로그인 → `/me` → 닉네임 저장까지 9개 항목을 통과했다

#### US-004: FastAPI에서 Supabase 토큰 검증 (P0, M2)
**설명:** 개발자로서, 요청한 사용자를 서버가 토큰으로 확인해서 다른 사람으로 위장한 쓰기를 막고 싶다.

**완료 기준:**
- [x] `backend/app/auth.py`에 의존성 `current_user`(토큰이 없거나 틀리면 401 `UNAUTHORIZED`)와 `optional_user`(없으면 `None`, 틀리면 401)를 만든다
- [x] `Authorization: Bearer <access_token>`을 Supabase JWKS(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`)로 검증한다. 프로젝트가 아직 HS256 공유 비밀을 쓰면 `SUPABASE_JWT_SECRET`으로 검증한다. `aud = authenticated`, 만료 시각을 확인하고 `sub`를 사용자 ID로 쓴다. 발급자(`iss`)와 `role = authenticated`도 확인해 anon·service 키를 거부한다. 2026-11-19 현재 이 프로젝트는 HS256(JWKS 비어 있음)이다. HS256 토큰이 왔는데 비밀이 없으면 503 `AUTH_NOT_CONFIGURED`
- [x] 어느 엔드포인트도 사용자 ID를 쿼리나 본문으로 받지 않는다
- [x] 테스트: 올바른 토큰, 만료된 토큰, 서명이 틀린 토큰, 토큰 없음 4가지 (`tests/test_auth.py`, 그 밖에 anon 키, 다른 서명 키, 서명 없는 토큰, 쿼리의 사용자 ID 등 29개)

#### US-005: 배포 설정 (P0, M1–M2)
**설명:** 개발자로서, 새 스택이 Vercel·Railway·Supabase A로 자동 배포되게 하고 싶다.

**완료 기준:**
- [x] 두 서비스를 GitHub `main`에 연결해 push마다 자동 배포한다 (2026-11-19). Vercel 프로젝트 `random-jeju-web`(Root Directory `frontend`) → https://random-jeju-web.vercel.app. Railway 프로젝트 `elegant-perception`(Root Directory `backend`, `Procfile`). 커밋 `ee931cf`가 두 곳 모두 성공했다. 그 앞 `2831084`는 Railway 첫 빌드가 실패하고 재시도에서 성공했다 (원인은 Railway 로그로 아직 보지 않았다)
- [x] Railway 환경 변수: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`(A), `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`(`https://random-jeju-web.vercel.app`), 기존 LLM 변수. 공개 주소 https://random-jeju-web-production.up.railway.app. 2026-11-19 확인: Vercel 주소의 CORS 사전 요청이 허용되고, 게스트 토큰으로 `GET /me`가 200이며, LLM은 Gemini로 켜져 있다
- [x] Vercel 환경 변수: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_KAKAO_MAP_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. 첫 배포본(`ee931cf`)에는 `NEXT_PUBLIC_API_URL`이 빠져 화면이 `http://localhost:8000`을 불렀다. 값을 넣고 다시 빌드한 `b18674e` 배포본에는 넷 다 들어갔다 (2026-11-19). `NEXT_PUBLIC_*`는 빌드 때 코드에 박히므로 값을 바꾸면 다시 빌드해야 한다
- [x] CORS가 `Authorization` 헤더와 `DELETE` 메서드를 허용한다 (`backend/app/main.py`: `allow_headers=["*"]`, `allow_methods`에 `DELETE`)
- [ ] 카카오 개발자 콘솔의 JavaScript 키에 로컬 주소와 Vercel 주소를 사이트 도메인으로 등록한다. 2026-11-19: 로컬은 등록돼 있고, Vercel 주소는 카카오가 `domain mismatched! caller=https://random-jeju-web.vercel.app`으로 거부한다. 배포 빌드의 키는 로컬과 같은 키다. 이 키는 해커톤 프론트의 키(해커톤 카카오 앱)이고, 그 앱에는 `http://localhost:3000`과 해커톤 주소 `https://frontend-iota-seven-41.vercel.app`만 등록돼 있다. Vercel 주소를 다른 카카오 앱(Random Jeju용)에 등록하면 이 키에는 적용되지 않는다. 해결 방법은 README "배포"
- [x] `GET /`의 응답으로 배포된 백엔드가 Supabase A를 보고 있음을 확인한다. 2026-11-19: `store: supabase`, 피드와 사진 지도가 RandomJeju(A)의 게시글·사진(28장)을 돌려준다

### 4.2 랜덤 + 추천

#### US-010: 랜덤 지점 뽑기 (P0, M3)
**설명:** 사용자로서, 주사위를 굴려 제주의 한 지점을 받고 그 근처에 뭐가 있는지 바로 보고 싶다.

**완료 기준:**
- [x] `scripts/mark_grids.py`가 FR-0대로 `grids.blacklist`를 채우고, 남은 칸 수와 읍면동별 수를 출력한다. 장소 데이터(`places`)를 다시 넣을 때마다 다시 실행한다 (`grids.land_cell`·`land_share`·`land_lat/lng`는 `supabase/migrations/0003_random_point.sql`이 한 번 계산한다). 2026-11-19: 7,969칸 중 6,614칸 사용, 1,355칸 제외(바다 408, 장소에서 멂 883, 준비 안 된 지역 64)
- [x] DB 함수 `random_point()`가 FR-1대로 지점을 하나 고른다 (실행 약 3.5ms, `anon`·`authenticated`는 호출 불가)
- [x] `POST /random-points`(FR-3)가 지점을 `locations`에 저장하고 `location_id`, 좌표, 읍면동 이름, 근처 요약을 돌려준다
- [x] 근처 요약에 가장 가까운 동네까지의 거리와 근처 장소 최대 3곳(사진이 있는 곳 먼저)이 있다. Android의 TODO였던 "상세 정보"를 이것으로 대신한다
- [ ] 응답 시간 p95 500ms 이하 (규칙: LLM을 부르지 않는다). LLM은 부르지 않는다. p95는 배포 환경(Railway) 로그로 잰다
- [x] 테스트: 1,000번 뽑아 모든 지점이 육지 위(`admin_areas` 안)이고, `blacklist = true`인 칸이나 우도·추자도에 떨어진 지점이 없다 (2026-11-19 DB에서 1,000번: 위반 0, 읍면동 36곳)

#### US-011: 랜덤 지점에서 코스 만들기 (플래너) (P0, M3)
**설명:** 개발자로서, 해커톤 플래너가 "지역 + 무작위 동네" 대신 "랜덤 지점에서 가장 가까운 동네"로 코스를 짜게 하고 싶다.

**완료 기준:**
- [x] `planner.random_course(places, profile_in, start_time, end_time, point, selectable)`를 더한다. FR-4–FR-8을 따른다
- [x] `TripCtx`에 `near: Optional[dict]`를 더하고, `near`가 있으면 `pick_anchor`가 동네를 무작위로 고르지 않고 그 장소를 앵커로 쓴다 (`_hub_id`, `_seen_hubs`도 그 장소로 채운다). `near`가 없으면 지금과 똑같이 동작한다
- [x] 기존 테스트가 모두 통과한다. `new_course`와 `prepare`는 고치지 않았으므로 기존 평가 결과는 그대로다. (해커톤의 무료 3곳 미리보기 테스트 3개는 US-017로 잠금이 꺼져서 `paywall_on` 픽스처로 잠금을 켜고 돌린다)
- [x] 테스트: FR-0이 막는 지점(바다, 우도, 추자도, 한라산 중턱)을 함수에 직접 넣어도 코스가 나오거나 FR-8의 오류가 난다 (예외로 멈추지 않는다)
- [x] 테스트: 같은 지점·같은 입력·같은 seed면 같은 코스가 나온다 (`tests/test_random.py`, 13개)

#### US-012: 랜덤 코스 API (P0, M3)
**설명:** 프론트 개발자로서, 뽑은 지점으로 코스를 만드는 엔드포인트가 필요하다.

**완료 기준:**
- [x] `POST /random-courses`(FR-9)가 201과 `Course`를 돌려준다. `Course`에 `kind`와 `random_origin`이 있다 (FR-10)
- [x] `GET /courses/{id}`도 `kind`, `random_origin`, `visits`를 돌려준다. 해커톤 코스는 `kind = "pick"`, `random_origin = null`이다
- [x] 다른 사용자의 `location_id`를 주면 404 `LOCATION_NOT_FOUND`다
- [x] `courses.owner_id`에 요청한 사용자 ID가 저장된다 (`POST /courses`도 토큰이 있으면 저장한다)
- [x] 테스트: 정상, 없는 `location_id`, 남의 `location_id`, 잘못된 시간 창(422 `INVALID_TIME_WINDOW`) (`tests/test_random_api.py`, 12개)

#### US-013: 랜덤 탭 화면 (P0, M3)
**설명:** 사용자로서, 지도 위에서 주사위를 굴리고 뽑힌 곳을 눈으로 확인하고 싶다.

**완료 기준:**
- [x] `/random`은 카카오맵(제주 전체)과 아래 카드로 이루어진다. 휴대폰에서는 지도가 화면 위쪽 46%, 1024px 이상에서는 지도와 카드가 나란히 놓인다. 카카오 SDK를 못 불러오면 섬 그림 위에 주사위를 놓는다
- [x] 🎲 버튼을 누르면 버튼이 비활성화되고 주사위가 돈다(최소 0.7초). 응답이 오면 지도 카메라가 지점으로 0.6초 동안 이동하고 주사위 마커가 하나 찍힌다. 이전 마커는 지운다. `prefers-reduced-motion`이면 움직임 없이 옮긴다
- [x] 카드에 읍면동 이름, 좌표, 가장 가까운 동네와 거리, 근처 장소 3곳(사진, 이름, 거리)이 보인다. 한국어가 아니면 읍면동 대신 지역의 영어 이름을 쓴다 (읍면동 이름은 한국어만 있다)
- [x] 카드 버튼: "이 근처로 하루 코스 짜기", "🎲 다시 굴리기"
- [x] 실패하면 카드에 "지금은 뽑을 수 없어요. 다시 시도해 주세요."가 보이고 버튼이 다시 눌린다 (게스트 로그인이 실패하면 그 문구를 보여준다)
- [x] 마지막으로 뽑은 지점은 `sessionStorage`에 남아서, 다른 탭에 갔다 와도 카드가 그대로다 (Android에서는 탭을 바꾸면 사라졌다)
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19, 375px와 800px, 한국어·영어)

#### US-014: 코스 페이지의 랜덤 배너와 다시 굴리기 (P0, M3)
**설명:** 사용자로서, 이 코스가 어느 랜덤 지점에서 나왔는지 보고, 마음에 안 들면 바로 다시 굴리고 싶다.

**완료 기준:**
- [x] `kind = "random"`인 코스는 배너를 보여준다: "🎲 랜덤 지점: 애월읍", "{동네} 근처 · 랜덤 지점에서 {km}". `snap_km`이 `SNAP_NOTICE_KM`보다 크면 "랜덤 지점 바로 근처엔 갈 곳이 적어서 {km} 떨어진 {동네} 근처로 옮겼어요"를 덧붙인다. **`SNAP_NOTICE_KM`은 5km**로 정했다: 2km로 두면 평가에서 78%의 코스에 이 문구가 붙는다
- [x] 코스 지도에 랜덤 지점을 주사위 마커로 함께 그린다. 코스 마커와 구분된다. 카카오맵은 주사위와 정류장이 한 화면에 들어오게 맞춘다
- [x] 랜덤 코스에서는 "Shuffle my day" 대신 "🎲 다른 곳 굴리기"를 보여준다. 누르면 같은 프로필과 시간으로 새 지점을 뽑고 새 코스로 이동한다. `router.replace` 대신 `router.push`를 쓴다: Shuffle과 같이 뒤로 가기로 이전 코스에 돌아갈 수 있다. 이전 코스는 DB에 남는다
- [x] 해커톤 방식 코스(`kind = "pick"`)의 화면은 바뀌지 않는다 (Shuffle 그대로)
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19: 조천읍 지점 → 닭머르해안길 2.6km, 다시 굴리기 → 한경면 지점 → 한림읍 코스)

#### US-015: 랜덤 코스 평가 스크립트 (P0, M3)
**설명:** 개발자로서, 랜덤 코스가 품질 규칙을 지키는지와 얼마나 다양한지 숫자로 보고 싶다.

**완료 기준:**
- [x] `scripts/eval_random.py --n N`이 사용 가능한 칸(`app/data/grids.json`, `mark_grids.py`가 씀)에서 N개(기본 300)를 고르고, 프로필 20개와 시간 창 5개를 돌려 쓰며 `random_course`를 부른다. Supabase를 쓰지 않는다. (`eval_planner.py`에 옵션으로 넣지 않고 따로 만들었다. 식사·동선 지표는 `eval_planner.metrics`를 그대로 쓴다)
- [x] 출력: 성공률, 이동 30분 초과 수, 식사 보장 위반 수, 영업시간 위반 수, `snap_km`의 중앙값·p90·최댓값, 서로 다른 동네 수, 지역별 분포
- [x] 결과를 `backend/eval/random-rules.json`에 저장한다
- [x] 2026-11-19 결과(300곳): 성공 100%, 이동·영업시간·여행 시간 위반 0, 식사 누락 0, 점심 100%·저녁 91%, `snap_km` 중앙값 3.7km·p90 6.7km·최대 14.4km, 동네 126곳, 한 동네 최대 3%. 처음 규칙(식사 가능한 동네를 어디서든 우선)은 중앙값 9.9km·p90 33.6km였다 (FR-6)

#### US-016: 온보딩 랜덤 모드와 프로필 저장 (P0, M3)
**설명:** 사용자로서, 취향은 한 번만 입력하고, 그 뒤로는 굴릴 때마다 바로 코스를 받고 싶다.

**완료 기준:**
- [x] `/onboarding?mode=random&location_id=…`은 지역 고르기 단계를 뺀 5단계다. 마지막 단계에서 `POST /random-courses`를 부르고 `/course/{id}`로 간다. 지점을 못 찾으면(404) "주사위로 돌아가기"를 보여준다
- [x] 온보딩이 끝나면 `user_profile`, `start_time`, `end_time`을 `localStorage`의 `rj.profile`에 저장한다 (읽기·쓰기는 try/catch). 해커톤 방식 온보딩도 저장한다
- [x] 저장된 프로필이 있으면 랜덤 카드의 "이 근처로 하루 코스 짜기"가 온보딩 없이 바로 코스를 만든다
- [x] 랜덤 카드에 "취향 다시 고르기" 링크가 있다. 누르면 저장된 답이 채워진 채로 열린다
- [x] 해커톤 방식 온보딩(`/onboarding`, 지역 단계 포함)은 그대로 동작한다
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19: 5단계 진행 → 코스, 저장된 프로필로 바로 코스)

#### US-017: 프리미엄 잠금 끄기 (P0, M3)
**설명:** 사용자로서, 결제 없이 모든 코스를 끝까지 보고 싶다. 돈을 받지 않는 "구매" 버튼은 오해를 산다.

**완료 기준:**
- [x] 백엔드 설정 `PAYWALL_ENABLED`(기본 `false`)를 더한다. `false`이면 `build_course`가 모든 코스를 `premium`처럼 만든다 (모든 장소, 문장 카드 포함)
- [x] 프론트 설정 `NEXT_PUBLIC_PAYWALL_ENABLED`(기본 `false`)가 `false`이면 등급 표시를 숨긴다. 잠금 카드와 "Unlock" 링크는 `locked_count`가 0이라 나오지 않는다. `/course/{id}/purchase`로 직접 오면 코스 화면으로 보낸다
- [x] 코드는 지우지 않는다. 두 설정을 `true`로 바꾸면 해커톤 때 동작이 돌아온다
- [x] 테스트: 두 값 각각에서 코스 응답의 장소 수
- [x] Typecheck/lint passes
- [x] Verify in browser (4곳 모두 보이고 등급 표시 없음)

### 4.3 사진·지도·피드 (RandomJeju 이관)

#### US-020: 사진 게시글 올리기 API (P0, M4)
**설명:** 사용자로서, 사진 한 장과 글, 카테고리를 올리고 싶다.

**완료 기준:**
- [x] `POST /posts`(multipart, FR-11)가 사진을 처리하고(FR-12) Storage에 올린 뒤 `photos`와 `posts`를 한 트랜잭션으로 만든다 (DB 함수 `create_photo_post`, `supabase/migrations/0004_posts.sql`)
- [x] 저장된 원본과 썸네일 모두 EXIF가 없다 (GPS, 기기 정보가 공개 URL로 새지 않는다)
- [x] 방향 정보가 다른 테스트 사진 8장(EXIF Orientation 1–8)의 썸네일이 모두 바로 선다. Ktor `ImageUtils.kt:38`의 "항상 90° 회전"을 옮기지 않는다
- [x] DB 저장이 실패하면 이미 올린 Storage 파일을 지운다 (502 `UPLOAD_FAILED`)
- [x] 15MB 초과는 413 `FILE_TOO_LARGE`, 이미지가 아니면 415 `UNSUPPORTED_IMAGE`, 카테고리가 틀리면 422 `INVALID_CATEGORY`다 (Ktor는 모두 500이었다). 4,000만 화소 초과도 413 (Pillow는 그 두 배부터만 막아서 직접 확인한다)
- [x] 사용자당 하루 30장 제한. 넘으면 429 `UPLOAD_LIMIT`
- [x] 테스트: 정상, 각 오류, Orientation 8종 (`tests/test_posts.py`, 41개)

#### US-021: 올리기 화면 (P0, M4)
**설명:** 사용자로서, 사진을 고르면 위치가 자동으로 잡히고, 없으면 쉽게 정하고 싶다.

**완료 기준:**
- [x] 사진을 고르면 브라우저에서 `exifr`로 GPS와 촬영 시각을 읽어 미리보기와 작은 지도에 보여준다
- [x] GPS가 없으면 "현재 위치 사용"(`navigator.geolocation`, 정확도 100m 이하만)과 "지도에서 고르기"를 고를 수 있다. 어떤 방법으로 정했는지 `location_source`로 보낸다
- [x] 카테고리는 필수다. 글은 500자까지 선택이다
- [x] 올리기 전에 "이 사진은 지도에 대략적인 위치(약 100m)와 함께 공개돼요"를 보여준다 (FR-13a)
- [x] 코스 화면의 "📷 사진 올리기"로 들어오면 `course_id`가 함께 간다
- [x] 성공하면 그 게시글이 맨 위에 있는 피드로 간다 ("사진을 올렸어요"). 방문 인증 토스트는 M5
- [x] 로그아웃 상태여도 오류가 나지 않는다 (US-003의 익명 세션을 먼저 만든다. Android `PhotoUploadView.kt:69`의 `!!` 크래시를 옮기지 않는다). 첫 게시글이면 닉네임 창이 먼저 뜬다
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19: 위치 없는 사진 → 카테고리 없이 올리기 막힘 → 닉네임 1글자 거부 → 저장 → 피드 맨 위에 표시. 테스트 게시글 1개와 댓글 1개가 실제 DB에 남아 있다)

#### US-022: 사진 지도 API (P0, M4)
**설명:** 프론트 개발자로서, 지도에 보이는 범위의 사진 마커와 읍면동 클러스터를 받아야 한다.

**완료 기준:**
- [x] `GET /photos/map`과 `GET /photos/clusters`(FR-14, FR-15)를 만든다. 클러스터에는 그 사진들이 있는 범위 `extent`도 준다 (지도에서 클러스터를 누르면 거기로 맞춘다)
- [x] 두 쿼리가 `photos.geom`의 GiST 인덱스를 쓴다 (`geom && ST_MakeEnvelope`). Ktor는 `gps_lat BETWEEN`으로 걸러 인덱스를 쓰지 않았다
- [x] 클러스터는 `admin_area_id`로 묶는다. Ktor처럼 읍면동 이름의 마지막 단어로 묶지 않는다
- [x] 테스트: 범위 확인(422 `INVALID_BBOX`), 좌표 반올림. (실제 DB: 사진 26장, 클러스터 11개)

#### US-023: 사진 지도 화면 (P0, M4)
**설명:** 사용자로서, 제주 지도에서 다른 사람들이 찍은 사진을 둘러보고 싶다.

**완료 기준:**
- [x] `/map`은 전체 화면 카카오맵이다. 지도 레벨이 `clusterMinLevel`(7) 이상이면 읍면동 클러스터(최신 썸네일 + 개수 + 이름), 미만이면 사진 마커(말풍선 썸네일)를 그린다
- [x] 지도가 멈추면(`idle`) 300ms 뒤 보이는 범위로 다시 불러온다. 바뀐 마커만 더하고 지운다
- [x] 클러스터를 누르면 그 클러스터 사진들이 있는 범위로 맞추고, 그 화면에서는 사진을 하나씩 보여준다 (Android에서는 TODO였다). 처음에는 평균 지점으로 확대했는데, 애월읍 사진 5장이 8×12km에 퍼져 있어 하나도 안 보였다
- [x] 사진 마커를 누르면 아래 시트에 게시글 카드(사진, 닉네임, 시간, 글, 좋아요, 댓글)가 보인다. 가짜 데이터는 쓰지 않는다
- [x] "내 위치" 버튼이 있다. 위치 권한을 거절해도 지도는 동작한다
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19, 375px)

#### US-024: 피드 API (P0, M4)
**설명:** 프론트 개발자로서, 최신 게시글을 카테고리별로 나눠 받아야 한다.

**완료 기준:**
- [x] `GET /posts`(FR-16)가 커서 방식으로 20개씩 준다. 커서는 URL에 안전한 base64 문자열이다 (시각의 "+"가 쿼리에서 공백으로 바뀌어 2쪽이 깨지는 문제가 테스트에서 나왔다)
- [x] 토큰 없이도 동작한다. 토큰이 있으면 `is_liked`가 채워지고, 없으면 `false`다
- [x] 시간은 ISO 8601(타임존 포함)로 준다. "N분 전" 같은 상대 시간은 프론트가 언어에 맞춰 만든다
- [x] 작성자나 사진 행이 없는 게시글도 빠지지 않는다 (left join, 작성자 없음 = "알 수 없음")

#### US-025: 피드 화면 (P0, M4)
**설명:** 사용자로서, 다른 여행자의 제주 사진을 카테고리별로 보고 싶다.

**완료 기준:**
- [x] `/feed`에 카테고리 칩(전체 + `post_category` 값)이 있고, 고른 값이 URL `?category=`에 남는다
- [x] 카드: 닉네임, 상대 시간, 사진, 글, 카테고리, 좋아요 수, 댓글 수. 방문 인증 배지는 M5
- [x] 아래로 스크롤하면 다음 20개를 불러온다. 더 없으면 "마지막 게시글이에요" (2026-11-19: 20 → 28개)
- [x] 비어 있으면 "아직 사진이 없어요. 첫 사진을 올려 보세요" + 올리기 버튼
- [x] Android의 동작하지 않던 공유·북마크·⋮ 버튼은 만들지 않는다
- [x] Typecheck/lint passes
- [x] Verify in browser

#### US-026: 좋아요 (P0, M4)
**설명:** 사용자로서, 마음에 드는 사진에 좋아요를 누르고 취소하고 싶다.

**완료 기준:**
- [x] `POST /posts/{id}/like`(FR-17)가 DB 함수 하나로 토글한다 (`post_likes`의 기본 키가 중복을 막는다). `posts.like_count`도 함께 고친다. 이 열은 예전 서버가 고치지 않아 모두 0이었으므로 마이그레이션에서 한 번 다시 셌다 (좋아요 25, 댓글 8)
- [x] 화면은 누르는 즉시 바뀌고(낙관적 업데이트), 실패하면 원래대로 돌아가며 안내를 띄운다. 앱이 멈추지 않는다
- [x] Typecheck/lint passes
- [x] Verify in browser (좋아요 → 1 → 취소 → 0)

#### US-027: 댓글 (P0, M4)
**설명:** 사용자로서, 사진에 댓글을 읽고 남기고 싶다.

**완료 기준:**
- [x] `GET /posts/{id}/comments`, `POST /posts/{id}/comments`(FR-18). 댓글 수도 함께 고친다
- [x] 빈 댓글이나 500자 초과는 422 `INVALID_COMMENT`다 (Ktor는 500이었다). 화면에서는 빈 댓글이면 등록 버튼이 꺼진다
- [x] 피드 카드의 댓글 아이콘이 아래 시트를 열고, 목록(오래된 순)과 입력창을 보여준다. 첫 댓글이면 닉네임 창이 먼저 뜬다
- [x] 등록하면 목록 끝에 바로 붙고, 카드의 댓글 수가 1 늘어난다
- [x] Typecheck/lint passes
- [x] Verify in browser (확인 중 동시 요청에서 "Server disconnected"가 나서 고쳤다: 8.3)

#### US-028: 내 게시글·댓글 지우기 (P1)
**설명:** 사용자로서, 내가 올린 사진과 댓글을 지우고 싶다.

**완료 기준:**
- [ ] `DELETE /posts/{id}`, `DELETE /comments/{id}`. 작성자가 아니면 403 `FORBIDDEN`이다
- [ ] 게시글을 지우면 Storage 파일, 좋아요, 댓글, 방문 인증도 지운다
- [ ] 내 글에만 ⋮ 메뉴 → "삭제"와 확인 창이 보인다
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

#### US-029: 게시글 화면 (P1)
**설명:** 사용자로서, 사진 지도나 공유 링크에서 게시글 하나를 열어 보고 싶다.

**완료 기준:**
- [ ] `GET /posts/{id}`와 `/posts/{id}` 화면: 큰 사진, 작성자, 시간, 글, 작은 지도, 좋아요, 댓글 목록과 입력
- [ ] 방문 인증된 글이면 연결된 코스로 가는 링크가 있다
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### 4.4 방문 인증

#### US-030: 방문 판정 (P0, M5)
**설명:** 사용자로서, 랜덤으로 뽑힌 곳이나 코스의 장소에 실제로 다녀왔음을 사진으로 남기고 싶다.

**완료 기준:**
- [x] `POST /posts`가 게시글을 만든 뒤 FR-19–FR-21대로 방문을 판정하고, 맞으면 `visits`에 행을 만든다. 판정 규칙은 `app/visits.py`의 순수 함수 `judge`, 저장은 DB 함수 `add_visit`(`0005_visits.sql`). 판정이 실패해도 게시글은 그대로 저장된다 (인증만 빠진다)
- [x] 응답의 `visit`에 판정 결과가 있다 (`null` = 인증 없음). 랜덤 지점과 장소가 함께 맞으면 `visits`에 둘 다 있고 `visit`은 랜덤 지점이다
- [x] 같은 코스의 같은 장소(또는 같은 랜덤 지점)는 한 번만 인증된다 (두 번째 사진은 `is_new: false`로 기존 인증을 돌려준다)
- [x] 테스트: 반경 안·밖, 장소 크기별 반경, 촬영 시각이 코스 생성 전, 7일이 지난 코스, 남의 코스, `location_source = "manual"`(인증하지 않음), 판정 실패 시에도 게시 성공 (`tests/test_visits.py` 10개, `tests/test_random_api.py` 4개)
- 정한 것: 카메라 시계가 서버보다 조금 늦을 수 있어 촬영 시각은 코스 생성 10분 전까지 인정한다 (`VISIT_CLOCK_LEEWAY_MIN`). 반경 안의 장소가 여럿이면 가장 가까운 한 곳만 인증한다 (사진 한 장은 한 장소를 찍은 것으로 본다)

#### US-031: 방문 인증 표시 (P0, M5)
**설명:** 사용자로서, 내가 다녀온 곳이 코스와 피드에 표시되면 좋겠다.

**완료 기준:**
- [x] 코스 화면과 여행 모드의 장소 카드에 인증되면 "✅ 다녀옴"과 그 사진의 작은 썸네일이 보인다. 여행 모드의 현재 장소 카드에는 "📷 사진 올리기"(코스 id 포함)도 있다
- [x] 랜덤 지점을 인증하면 배너에 "🎲 랜덤 지점 정복!"이 보인다. 배너는 여행을 시작한 뒤에도 보이고, "다른 곳 굴리기"만 시작 전에 보인다
- [x] 피드 카드와 사진 지도 시트에 배지가 보인다: "🎲 랜덤 지점 다녀옴" 또는 "📍 {장소 이름} 다녀옴" (같은 `PostCard`). 올리기 직후 피드에 "🎲 다녀옴 인증!"
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19, 실제 DB: EXIF GPS가 든 사진 두 장으로 한경면 랜덤 지점 약 50m → 랜덤 지점 인증, 생각하는 정원(공원, 500m) → 장소 인증, 코스 배너 "정복!"과 장소 카드 "다녀옴" 확인. 확인용 게시글 2개와 인증 2개가 실제 DB에 남아 있다)

### 4.5 한국어 기본

#### US-040: 기본 언어를 한국어로 (P0, M3)
**설명:** 국내 사용자로서, 처음 열었을 때 한국어 화면을 보고 싶다.

**완료 기준:**
- [x] 기본 언어를 `"ko"`로 바꾼다. 브라우저 언어 감지(en/ja/zh)와 언어 선택은 그대로 둔다. (실제로 언어를 정하는 곳은 `lib/locale.ts`가 아니라 `lib/i18n.ts`의 `useLocale`이었다: 저장된 선택 → 브라우저 언어 → 한국어 순으로 고친다. `<html lang="ko">`, 페이지 제목도 한국어로)
- [x] 새 화면(랜덤, 사진 지도, 피드, 올리기)의 모든 문구가 `lib/messages/{ko,en,ja,zh}.ts`에 있다. 화면 코드에 한국어 문자열을 직접 쓰지 않는다
- [x] 언어가 ko이면 "Show to driver" 카드와 현지 문장 카드를 숨긴다 (외국인용 기능)
- [x] 게시판 카테고리 이름이 4개 언어로 나온다 (DB 값은 한국어 enum 그대로, 화면 이름만 바꾼다)
- [x] 서비스 이름을 화면 전체에서 Random Jeju로 바꾼다 (Q-01)
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19: 브라우저 언어 ko에서 한국어로 열림, 영어로 바꾸면 영어)

#### US-041: 장소 설명 한국어 (P0, M6)
**설명:** 국내 사용자로서, 모든 장소 설명을 한국어로 읽고 싶다.

**완료 기준:**
- [x] `places`에 `description_ko text`, `description_ko_status text check (in ('reviewed','machine'))`를 더한다 (M1의 `0002_merge.sql`)
- [x] `frontend/lib/content/descriptions.ko.ts`의 검수된 번역을 `reviewed`로 넣는다. 실제로는 66곳이었고, 영어 원문의 해시(프론트와 같은 FNV-1a)가 지금 원문과 맞는 것만 쓴다 (66곳 모두 맞음)
- [x] `scripts/translate_places.py`가 나머지 장소의 `description_en`을 LLM으로 한 번 번역해 `data/seed/places_ko.csv`(id, status, src 해시, 번역)에 저장하고, `build_places.py`가 `places.json`에, `seed_supabase.py`가 DB에 넣는다. 고유명사(장소 이름)는 `name_ko`를 쓰게 프롬프트에 준다. 2026-11-19: Gemini(`gemini-3.1-flash-lite`)로 999곳, 거부 0건. 영어 원문이 바뀌면 그 장소만 다시 번역한다 (src 해시)
- [x] 언어가 ko이면 `description_ko ?? description_en`을 보여준다. `machine`이면 "기계 번역 · 영어 원문" 접힘을 달아 원문을 볼 수 있다. 지도 하단 카드도 같다
- [x] Typecheck/lint passes
- [x] Verify in browser (2026-11-19: 새 랜덤 코스 7곳 모두 한국어 소개, "영어 소개를 확인해 주세요" 안내가 화면에서 사라짐, 영어로 바꾸면 원문)

#### US-042: 코스 추천 이유와 빈 식사 시간 문구 한국어 (P0, M6)
**설명:** 국내 사용자로서, 왜 이 장소를 넣었는지 한국어로 보고 싶다.

**완료 기준:**
- [x] `course_items`에 `reason_ko text`를 더한다 (`0002_merge.sql`). 규칙 이유는 `planner.rule_reason_ko`가 만든다. 문장은 그동안 프론트가 영어 규칙 문장을 바꿔 보여주던 한국어와 같게 했다. 모든 정류장 행은 `_rows` 한 곳을 지나므로 거기서 채운다 (LLM이 쓴 한국어가 있으면 그것, 없으면 규칙 문장)
- [x] LLM 출력 스키마에 `reason_ko`를 더하고(Gemini·Claude 스키마 모두 필수 항목, Pydantic은 선택), 시스템 프롬프트에 "같은 내용을 자연스러운 한국어(해요체)로, 장소 이름은 name_ko"를 더했다. 후보에 `name_ko`도 보낸다. 비어 있으면 규칙 문장으로 채우고 실패로 보지 않는다. 실제 Gemini 호출로 확인 ("수산저수지에서 … 평화로운 자연을 즐겨보세요.")
- [x] `meal_gaps`의 각 항목에 `message_ko`를 더한다 (`planner.gap_row`)
- [x] 언어가 ko이면 `reason_ko`를 먼저 쓴다. 없으면(예전 코스) 지금처럼 프론트의 규칙 문장 변환, 그다음 번역 API. 빈 식사 시간 카드는 이미 4개 언어로 검수된 문구가 프론트에 있어 그것을 계속 쓴다 (`message_ko`는 API에만)
- [x] 기존 저장된 코스(`reason_ko` 없음)도 오류 없이 열린다 (응답에서 `reason_ko: null`)
- [x] Typecheck/lint passes (테스트 `tests/test_korean.py` 10개)

### 4.6 전환

#### US-050: 옛 서버 끄기 (P0, M7)
**설명:** 운영자로서, 쓰지 않는 서버와 DB를 정리해 비용과 보안 위험을 줄이고 싶다.

**완료 기준:**
- [x] (M0에 먼저) Supabase A의 DB 비밀번호를 바꾼다. 옛 비밀번호는 `random-jeju-api`의 `src/main/resources/application.conf`에 커밋돼 있었다. Ktor 서버의 `.env`도 새 값으로 바꾸거나, 서버를 먼저 끈다 (2026-11-19 완료. 옛 비밀번호로는 접속이 거부되고, 새 `.env`로는 접속된다)
- [x] (M0에 먼저) 8.6의 RLS 긴급 조치를 적용하고, anon 키로 `users`, `photos`, `locations`를 읽거나 지울 수 없음을 확인한다 (2026-11-19 완료)
- [x] (M7) `users`의 임시 정책 2개와 `posts`·`comments`·`post_likes`의 정책 10개를 지운다 (FR-34). 2026-11-19 `0006_cleanup.sql`로 적용. `public`에 정책 0개, 6개 테이블 RLS 켜짐 그대로
- [x] Render/Cloud Run의 Ktor 서비스를 멈춘다. Android 앱의 API 호출은 이때부터 실패한다 (4장 비목표). 2026-11-19 Cloud Run 서비스 `random-jeju`(asia-northeast3)에서 `allUsers`의 `roles/run.invoker`를 뺐다. 이제 모든 요청이 403이다. 서비스와 이미지는 지우지 않았다. 되돌리기: `gcloud run services add-iam-policy-binding random-jeju --region asia-northeast3 --member=allUsers --role=roles/run.invoker`. Render: Android 앱(`NetworkModule.kt`)과 Ktor 저장소에 Render 주소가 없어 확인할 대상이 없다 (앱은 Cloud Run만 부른다)
- [ ] ~~Supabase B의 데이터가 A와 같음을 확인한 뒤 B를 일시 정지한다~~ **하지 않는다 (2026-11-19 사용자 결정).** B는 해커톤 웹앱이 계속 쓰므로 그대로 둔다
- [ ] ~~해커톤 저장소의 README에 새 저장소 주소를 적는다~~ **하지 않는다 (2026-11-19 사용자 결정).** 해커톤 저장소는 팀 저장소라 손대지 않는다

---

## 5. 기능 요구사항

### 5.1 랜덤 지점

- **FR-0 뽑을 칸 정하기 (Q-06, Q-07).** 지금 `grids`는 500m×500m 칸 7,969개이고 `blacklist`가 모두 `false`다. 그래서 Ktor는 바다(육지가 25% 미만인 칸 274개), 추자도, 한라산 한가운데도 뽑았다. `scripts/mark_grids.py`가 칸마다 아래를 계산해 저장한다.
  - `land_cell geometry`: 칸과 `admin_areas` 합집합의 교집합. 점은 여기서만 만든다.
  - `blacklist = true`인 칸: (a) 육지 비율 50% 미만, (b) 칸 중심의 지역(`areas.area_of_point`)이 고를 수 없는 지역(지금은 우도·추자도), (c) 고를 수 있는 지역의 **밀집 장소**가 5km(`GRID_REACH_KM`) 안에 없음. 밀집 장소 = 반경 `ANCHOR_RADIUS_KM`(2.5km) 안에 장소가 `HUB_MIN_PLACES`(8)곳 이상인 장소 (프로필 없이 계산한 동네 후보).
  - 2026-11-19 데이터로 미리 계산한 결과: 중심이 육지인 7,569칸 중 (c)를 통과하는 칸은 6,707칸(89%)이다. 가장 가까운 밀집 장소까지 거리는 중앙값 1.5km, p90 5.3km다. 많이 빠지는 곳: 추자면 전부, 중문동 41%, 남원읍 38%, 노형동·대천동 약 25% (한라산 쪽 칸).
  - 실제 적용(2026-11-19, `mark_grids.py`): 밀집 장소를 지역 안의 장소로만 세어서 조금 더 엄격하다. 6,614칸 사용, 1,355칸 제외 (바다 408, 장소에서 멂 883, 준비 안 된 지역 64).
- **FR-1** `random_point()`는 `blacklist = false`인 칸 하나를 같은 확률로 고르고(`order by random() limit 1`, 7천여 행이라 충분히 빠르다), `ST_GeneratePoints(land_cell, 1)`로 칸의 육지 안에 점 하나를 만든다. 반환: `lat`, `lng`, `adm_nm`(마지막 단어, 예: "애월읍"), `grid_id`. Ktor `RandomLocationService.kt:13-30`과 다른 점은 `land_cell`과 FR-0의 `blacklist`뿐이다.
- **FR-2** `grids.weight`(지금 모두 1.0)는 쓰지 않는다. 나중에 지역별 확률을 바꾸고 싶으면 이 열을 쓴다.
- **FR-3** `POST /random-points` (토큰 필수, 본문 없음) → 201
  ```json
  {
    "location_id": 1234,
    "lat": 33.4631, "lng": 126.3312,
    "adm_nm": "애월읍",
    "area_id": "aewol",
    "nearest_hub": {"place_id": 512, "name_ko": "한담해안산책로", "name_en": "Handam Coastal Walk", "km": 1.2},
    "preview_places": [{"id": 512, "name_ko": "…", "name_en": "…", "category": "nature", "image_url": "…", "km": 1.2}]
  }
  ```
  - `locations`에 `user_id`를 넣어 저장한다. `address` 열에는 지금처럼 `adm_nm`을 넣는다.
  - `area_id`는 FR-4의 결과, `nearest_hub`는 프로필 없이(모든 관심사, 식사 없음) FR-6으로 찾은 동네, `preview_places`는 지점에서 가까운 순 3곳(사진 있는 곳 먼저, 5km 안)이다. 5km 안에 장소가 없으면 빈 배열이다.

### 5.2 랜덤 지점에서 코스 만들기

- **FR-4 지역 정하기.** 코스의 지역은 지점이 있는 지역이 아니라 **FR-6이 고른 동네의 지역**이다. 지역 경계 근처의 지점은 옆 지역의 동네가 더 가까울 수 있기 때문이다. 고를 수 있는 지역(`GET /areas`에서 "Coming soon"이 아닌 지역)만 본다.
- **FR-5 그 뒤의 파이프라인.** `new_course`와 같다: `in_area` → 필터(F-1–F-10) → 동네 찾기 → 후보 → LLM/규칙 → 검증 → 시간 계산. 바뀌는 것은 FR-6의 동네 고르기 하나뿐이다.
- **FR-6 동네 고르기.** `random_course`는 고를 수 있는 지역마다 그 지역의 장소로 필터와 `find_hubs`를 돌려 동네 목록을 모은다. 그다음 무작위(밀집도 가중치) 대신 이렇게 고른다:
  1. 동네 중심 장소가 지점에서 가장 가까운 동네를 찾는다. 거리는 `km_between`(직선거리)이다.
  2. 필요한 식사를 모두 채울 수 있는 동네(`Hub.fed`) 중 그보다 `RANDOM_FED_DETOUR_KM`(3km) 이내로 더 먼 곳이 있으면, 그중 가장 가까운 곳을 고른다. 없으면 1의 동네다. 그 동네에서 식사를 못 채우면 빈 식사 시간 카드가 나온다 (해커톤 P1 FR-11).
  - 바뀐 이유 (2026-11-19 평가): 처음 규칙("식사를 채울 수 있는 동네를 어디서든 우선")은 비건 식당이 제주시에 몰려 있어서 한림의 지점도 30km 넘게 옮겼다 (중앙값 9.9km, p90 33.6km, 한 동네에 17%). 지금 규칙은 중앙값 3.7km, p90 6.7km, 점심 100%·저녁 91%다. 대신 비건 여행자의 식사는 대부분 빈 식사 시간 카드가 된다 (5%만 비건 식당). 식단이 있는 사람에게 8–12km까지 허용해 봤지만 비건 식사는 9–18%로만 올라서 쓰지 않았다.
  - 고른 동네의 지역으로 `new_course`와 같은 `TripCtx`를 만들고, `ctx.near`에 그 동네 중심 장소를 넣어 `pick_anchor`가 그 장소를 앵커로 쓰게 한다.
  - 무작위성은 지점이 이미 줬으므로 동네 고르기에는 `rng`를 쓰지 않는다. 후보 고르기의 `rng`(seed)는 그대로 쓴다.
- **FR-7 `snap_km`.** 지점에서 고른 동네 중심 장소까지의 직선거리(km, 소수 첫째 자리)를 `random_origin.snap_km`으로 돌려준다.
- **FR-8 실패.** 필터 뒤 후보가 모자라면 해커톤과 같은 409 `NO_CANDIDATES`다. 화면은 "이 조건으로는 이 근처에서 코스를 못 짰어요"와 함께 "🎲 다시 굴리기", "취향 다시 고르기"를 보여준다. 서버가 몰래 다시 굴리지 않는다 (사용자가 본 지점과 코스가 어긋나지 않게).
- **FR-9** `POST /random-courses` (토큰 필수) 요청:
  ```json
  {
    "location_id": 1234,
    "user_profile": { "interests": ["nature","cafe"], "fitness_level": 2, "max_walk_min": 20,
                      "avoid_slopes": false, "condition_today": "normal", "diet": "none" },
    "start_time": "10:00",
    "end_time": "18:00"
  }
  ```
  - `user_profile`, 시간 검사는 `POST /courses`와 같다(`UserProfileIn`, `check_time_window`).
  - `location_id`가 없거나 다른 사용자의 것이면 404 `LOCATION_NOT_FOUND`.
  - 성공하면 `courses.kind = 'random'`, `courses.owner_id`, `courses.origin_location_id`를 저장하고 `locations.course_id`를 채운다.
- **FR-10** `Course` 응답에 더하는 필드 (해커톤 9.3의 `Course`에 추가):
  ```json
  {
    "kind": "random",
    "random_origin": { "location_id": 1234, "lat": 33.4631, "lng": 126.3312, "adm_nm": "애월읍",
                       "area_id": "aewol", "snap_km": 1.2, "hub_name_ko": "한담해안산책로" },
    "visits": [ { "kind": "course_place", "place_id": 512, "post_id": "…", "thumb_url": "…" } ]
  }
  ```
  `kind = "pick"`이면 `random_origin`은 `null`이다. `POST /courses`도 토큰이 있으면 `owner_id`를 저장한다 (토큰은 선택).

### 5.3 사진 게시글

- **FR-11** `POST /posts` (토큰 필수, multipart):
  - `image`: 파일. `image/jpeg`, `image/png`, `image/webp`. 15MB 이하.
  - `meta`: JSON 문자열
    ```json
    { "lat": 33.46, "lng": 126.33, "location_source": "exif",
      "taken_at": "2026-11-20T14:03:00+09:00", "content": "노을이 예뻤어요",
      "category": "관광", "course_id": "…" }
    ```
    - `location_source`: `exif` | `device` | `manual`. 위치가 없으면 `lat`, `lng`, `location_source` 모두 생략한다 (그 사진은 지도에 나오지 않는다).
    - `category`는 `post_category` enum 값 중 하나. `content`는 500자 이하. `course_id`는 선택.
  - 응답 201: `{ "post": Post, "visit": Visit | null }`
- **FR-12 사진 처리** (Pillow):
  1. `ImageOps.exif_transpose`로 방향을 바로 세운다.
  2. 긴 변이 2048px보다 크면 줄인다. JPEG 품질 85로 저장하고 EXIF를 남기지 않는다.
  3. 썸네일은 가운데를 정사각형으로 잘라 280×280(화면 140px의 2배) JPEG로 만든다.
  4. Storage `photos/{uuid}.jpg`, `thumbnails/{uuid}_thumb.jpg`에 올린다. DB에는 경로만 저장하고 공개 URL은 응답할 때 `SUPABASE_URL`로 만든다. (기존 행은 전체 URL이 저장돼 있으므로 `http`로 시작하면 그대로 쓴다.)
- **FR-13** `photos`와 `posts`는 DB 함수 `create_photo_post(...)` 하나로 만든다. `geom`은 `ST_SetSRID(ST_MakePoint(lng, lat), 4326)`, `admin_area_id`는 `admin_areas`에서 `ST_Contains`로 찾는다 (`sql/001_photos_geom_and_admin_area.sql`과 같은 규칙).

### 5.4 사진 지도

- **FR-13a 공개 좌표 흐리기 (Q-11).** DB에는 정확한 좌표를 저장하고 방문 판정(FR-20)에만 쓴다. API가 밖으로 내보내는 사진·게시글 좌표(FR-14–FR-16, 게시글 화면)는 모두 소수 셋째 자리로 반올림한다 (위도 약 111m, 경도 약 93m). 반올림은 응답을 만들 때 한 함수(`public_coord`)에서만 한다. 랜덤 지점과 코스 장소의 좌표는 흐리지 않는다 (개인 위치가 아니다).
- **FR-14** `GET /photos/map?min_lat&min_lng&max_lat&max_lng` → `{ "photos": [{ "photo_id", "post_id", "lat", "lng", "thumb_url" }] }`. `geom && ST_MakeEnvelope(...)`로 거른다. `thumb_path`가 있는 사진만, 최신순 300장까지.
- **FR-15** `GET /photos/clusters?min_lat&min_lng&max_lat&max_lng` → `{ "clusters": [{ "admin_area_id", "name", "count", "lat", "lng", "thumb_url" }] }`. `admin_area_id`로 묶는다. `name`은 `adm_nm`의 마지막 단어(예: "애월읍"), `lat`/`lng`는 그 읍면동 사진들의 평균, `thumb_url`은 가장 최근 사진이다.
- 범위 값이 빠졌거나 `min >= max`이면 422 `INVALID_BBOX`.

### 5.5 피드·좋아요·댓글

- **FR-16** `GET /posts?category=&cursor=&limit=20` (토큰 선택) →
  ```json
  { "posts": [{ "post_id": "…", "author": {"nickname": "귤좋아"}, "created_at": "2026-11-20T14:05:12+09:00",
                "content": "…", "category": "관광", "image_url": "…", "thumb_url": "…",
                "lat": 33.46, "lng": 126.33, "like_count": 3, "comment_count": 1, "is_liked": false,
                "visit": { "kind": "random_point", "place_name_ko": null } }],
    "next_cursor": "2026-11-20T14:05:12+09:00|…" }
  ```
  - 정렬은 `created_at desc, id desc`. 커서는 마지막 게시글의 `(created_at, id)`. `limit`은 1–50.
- **FR-17** `POST /posts/{id}/like` (토큰 필수) → `{ "liked": true, "like_count": 4 }`. DB 함수 `toggle_like(post_id, user_id)`가 `insert ... on conflict do nothing`이 0행이면 지우는 방식으로 한 번에 처리한다.
- **FR-18** `GET /posts/{id}/comments` (토큰 선택) → `{ "comments": [{ "id", "author": {"nickname"}, "content", "created_at" }] }`, 오래된 순, 200개까지. `POST /posts/{id}/comments` (토큰 필수) `{ "content": "…" }` → 201 `Comment`. 없는 게시글은 404 `POST_NOT_FOUND`.
- 모든 오류 응답은 해커톤 9.2의 모양 `{ "error": { "code", "message" } }`을 따른다. Ktor처럼 평문 오류를 내지 않는다.

### 5.6 방문 인증

- **FR-19 인증 대상.** 게시글을 올린 사용자가 주인(`owner_id`)인 코스. `meta.course_id`가 있으면 그 코스만, 없으면 그 사용자의 최근 7일 코스 전부를 본다.
- **FR-20 판정.** 아래를 모두 만족하면 인증한다.
  1. `location_source`가 `exif` 또는 `device`다 (`manual`은 인증하지 않는다).
  2. 코스가 만들어진 지 7일이 지나지 않았다.
  3. 촬영 시각(`taken_at`, 없으면 업로드 시각)이 코스가 만들어진 시각 이후다.
  4. 사진 위치가 랜덤 지점에서 `VISIT_RADIUS_RANDOM_M`(500m) 안이면 `kind = "random_point"`. 코스의 어느 장소에서 그 장소의 반경 안이면 `kind = "course_place"`와 그 `place_id`. 둘 다 맞으면 둘 다 만든다.
  5. 장소 반경 (Q-08): `place_type`이 넓은 장소(`beach`, `oreum_hike`, `park`, `forest`, `waterfall`, `nature`)이면 `VISIT_RADIUS_WIDE_M`(500m), 그 밖은 `VISIT_RADIUS_PLACE_M`(200m). 장소 좌표는 점 하나라서 성산일출봉 정상이나 해변 끝에서 찍은 사진이 200m 밖으로 나갈 수 있기 때문이다.
  - 값은 모두 `config.py`에 둔다. 거리는 정확한 좌표로 계산한다 (FR-13a의 흐린 좌표가 아니다).
- **FR-21** 한 코스에서 같은 `place_id`(또는 같은 랜덤 지점)는 한 번만 인증한다. 이미 있으면 새 행을 만들지 않고 `visit`에 기존 인증을 돌려준다.

### 5.7 DB 변경 (`0002_merge.sql`)

- **FR-30**
  ```sql
  alter table locations add column if not exists user_id uuid references auth.users(id);
  alter table locations add column if not exists course_id uuid references courses(id) on delete set null;
  alter table courses add column if not exists owner_id uuid references auth.users(id);
  alter table courses add column if not exists kind text not null default 'pick' check (kind in ('pick','random'));
  alter table courses add column if not exists origin_location_id integer references locations(location_id);
  alter table course_items add column if not exists reason_ko text;
  alter table places add column if not exists description_ko text;
  alter table places add column if not exists description_ko_status text check (description_ko_status in ('reviewed','machine'));
  alter table photos add column if not exists location_source text check (location_source in ('exif','device','manual'));

  create table if not exists visits (
    id            bigint generated always as identity primary key,
    user_id       uuid not null references auth.users(id),
    course_id     uuid not null references courses(id) on delete cascade,
    kind          text not null check (kind in ('random_point','course_place')),
    place_id      integer references places(id),
    location_id   integer references locations(location_id),
    post_id       uuid not null references posts(id) on delete cascade,
    created_at    timestamptz not null default now()
  );
  create unique index if not exists visits_once on visits (course_id, kind, coalesce(place_id, 0));

  alter table grids add column if not exists land_cell geometry(Geometry, 4326);   -- FR-0
  -- post_likes는 이미 기본 키가 (post_id, user_id)다. 같은 정의의 중복 제약만 지운다.
  alter table post_likes drop constraint if exists post_likes_unique_post_user;
  ```
  열 타입은 2026-11-19 조회 결과(8.5)에 맞췄다: `locations.location_id`는 `integer`, `posts.id`는 `uuid`, `posts.user_id`·`comments.user_id`·`post_likes.user_id`·`users.id`는 `auth.users(id)`를 참조한다. 그래서 익명 사용자도 같은 외래 키로 글을 쓸 수 있다.
- **FR-31** DB 함수: `random_point()`, `create_photo_post(...)`, `photos_in_bbox(...)`, `photo_clusters(...)`, `toggle_like(...)`. FastAPI는 supabase-py의 `rpc()`로 부른다. PostgREST로는 공간 쿼리를 쓸 수 없기 때문이다. `posts.like_count`, `posts.comment_count` 열이 이미 있으므로 `toggle_like`와 댓글 추가·삭제가 이 값도 함께 고친다. 피드는 이 열을 읽는다 (매번 세지 않는다).
- **FR-32 시간 열 (Q-09).** DB 시간대는 UTC이고, 타임존 없는 열은 아래처럼 저장돼 있다. 조회로 확인한 근거: 사진 109번의 `image_time`은 19:02:55, 업로드 시각 `timestamp`는 10:03:38로 9시간 차이다.
  ```sql
  -- 기본값 CURRENT_TIMESTAMP로 들어간 열 = UTC
  alter table locations alter column created_at type timestamptz using created_at at time zone 'UTC';
  alter table photos    alter column "timestamp" type timestamptz using "timestamp" at time zone 'UTC';
  alter table users     alter column join_date  type timestamptz using join_date  at time zone 'UTC';
  -- EXIF 촬영 시각 = 한국 시간
  alter table photos    alter column image_time type timestamptz using image_time at time zone 'Asia/Seoul';
  ```
  `posts`, `comments`, `post_likes`의 시간 열은 이미 `timestamptz`다. 새 업로드의 `taken_at`은 오프셋이 붙은 ISO 문자열로 받고, 오프셋이 없으면 한국 시간으로 본다.
  **2026-11-19 적용 (`0006_cleanup.sql`, M7).** 네 열 모두 `timestamptz`가 됐다. 사진 109번은 촬영 10:02:55 UTC, 업로드 10:03:38 UTC로 1분 차이가 됐다. `create_photo_post`는 `p_image_time timestamptz`를 받고, 백엔드는 `+09:00`이 붙은 한국 시간을 보낸다 (롤백한 트랜잭션에서 14:03 KST가 05:03 UTC로 저장됨을 확인).
- **FR-33** `users`는 지금 `id, nickname, profile_image, age_group, home_region, preferences, join_date`다. 열은 그대로 두고, 익명 사용자의 행은 닉네임을 정할 때 `id`, `nickname`만 넣어 만든다. 기존 이메일 사용자 2명의 행과 게시글은 그대로 둔다 (Q-03).
- **FR-34** 모든 `public` 테이블은 RLS가 켜져 있고 정책이 없다. 브라우저는 Supabase를 Auth에만 쓰고, 데이터는 모두 FastAPI(서비스 키)를 거친다 (해커톤 1.3의 "프론트는 FastAPI만 호출한다"를 지킨다). 그래서 지금 `posts`, `comments`, `post_likes`에 있는 정책 10개(`auth.uid() = user_id`로 쓰기 허용)는 지운다. 남겨 두면 익명 세션을 가진 브라우저가 FastAPI의 검사(글자 수, 하루 업로드 제한)를 건너뛰고 직접 쓸 수 있다.

### 5.8 사용자

- **FR-35** `GET /me` (토큰 필수) → `{ "user_id", "nickname": "귤좋아" | null, "is_anonymous": true }`. `POST /me` `{ "nickname" }` → 닉네임 2–12자, 앞뒤 공백 제거, 비면 422 `INVALID_NICKNAME`. 중복은 허용한다.

---

## 6. 비목표 (이번에 만들지 않는 것)

- **Android 앱.** 웹으로 옮기고 Android 앱은 끝낸다. 업데이트하지 않고, 웹을 감싼 앱도 만들지 않는다. Ktor 서버를 끄면 Android 앱의 랜덤·업로드·게시판은 동작하지 않는다 (Q-04).
- **이메일·소셜 로그인, 프로필 화면, 비밀번호 찾기.** 이번에는 익명 세션과 닉네임만 쓴다. 기존 이메일 가입자 2명의 게시글은 닉네임과 함께 계속 보이지만, 그 계정으로 웹에 로그인하지는 못한다 (Q-03).
- **유료 기능.** 프리미엄 잠금과 구매 목업은 설정으로 끈다 (US-017, Q-05). 실제 결제는 만들지 않는다.
- **피드 추천 정렬.** Supabase A에 RandomJeju 때 설계만 하고 쓰지 않은 추천 테이블이 있다: `reco_config`(취향·거리·최신성·인기도(Wilson 하한)·미방문 읍면동·시간대 가중치, 반경 15km 등 14개 값), `preference_category_map`(가입 취향 → 게시판 카테고리 가중치 12행), `user_events`·`user_profile_settings`·`user_profile_stats`(모두 0행). 이번에는 피드를 최신순으로만 보여주고 이 테이블들은 건드리지 않는다. 피드 개인화를 할 때 다시 본다.
- **회원 취향(가입 때 고른 풍경·카페·오름 …)을 추천에 쓰기.** 취향은 온보딩 프로필(`localStorage`)로만 받는다.
- **랜덤 지점에 취향 가중치 주기.** 지점은 지금처럼 균등하게 뽑는다. 취향은 코스 단계에서만 쓴다.
- **검색.** Android 검색 탭은 연결되지 않은 화면이었다. 장소·주소 검색은 만들지 않는다.
- **여러 지역을 잇는 코스, 이틀 이상 일정, 실제 도로 길찾기, 날씨 자동 감지, 실제 결제.** 해커톤 PRD 4.4와 같다.
- **게시글 신고, 관리자 화면, 푸시 알림, 팔로우.**
- **사진 여러 장 올리기, 동영상, HEIC 직접 처리** (HEIC는 P1에서 `pillow-heif`로).
- **Android의 목업 데이터** (`FullscreenImageDialog`의 가짜 좋아요·댓글·해시태그, 프로필의 고정 통계).

---

## 7. 디자인 고려 사항

- **기반 UI는 해커톤 V9 UI**(`frontend/components/V9Header.tsx`, `frontend/app/v9.css`, 랜딩 `components/landing/`)를 쓴다. 새 화면도 같은 색·글꼴·아이콘(`components/Icon.tsx`, `CategoryIcon.tsx`)을 쓴다.
- **지도는 하나의 컴포넌트.** `components/KakaoMap.tsx`를 랜덤 탭, 사진 지도, 코스에서 같이 쓴다. 마커 종류만 더한다: 주사위(랜덤 지점), 사진 말풍선, 읍면동 클러스터. 카카오 SDK를 못 불러오면 `FallbackMap.tsx`가 뜨는 지금 동작을 유지한다.
- **랜덤 연출이 이 서비스의 얼굴이다.** 주사위 회전(최대 1초) → 카메라 이동(0.6초) → 마커가 툭 떨어짐 → 카드가 올라옴. `prefers-reduced-motion`이면 회전과 이동을 생략한다 (`lib/motion.ts`).
- **카드 구성**은 Android `RandomView.kt`의 결과 카드를 따르되 가짜 값을 빼고 실제 값으로 채운다: 읍면동 이름, 좌표, 가장 가까운 동네, 근처 장소 3곳.
- **모바일 우선.** 375px 폭에서 가로 스크롤이 없어야 한다. 데스크톱은 지도 + 왼쪽 패널(카드·피드) 두 칸.
- **사진 올리기 안내 문구**에 위치 공개 사실을 분명히 적는다 (Q-11).

---

## 8. 기술 고려 사항

### 8.1 구현 순서

| 단계 | 내용 | 스토리 | 끝났다는 기준 |
|---|---|---|---|
| M0 준비 | 새 저장소 만들기(해커톤 `frontend/`, `backend/`, `data/`를 복사, Q-02), Supabase A DB 비밀번호 교체, RLS 긴급 조치(8.6) | US-050 첫 항목 | 새 저장소가 Vercel·Railway 미리보기로 뜬다. anon 키로 `users`, `photos`를 읽을 수 없다 |
| M1 DB 통합 | 해커톤 스키마·데이터를 A로, RandomJeju 스키마 덤프, 배포 환경 변수 | US-001, 002, 005 | 해커톤 기능이 A 위에서 그대로 동작, 평가 결과 동일 |
| M2 인증 | 익명 세션, 토큰 검증, `/me` | US-003, 004 | 토큰 없이 쓰기가 401, 위장 불가 |
| M3 랜덤 코스 (핵심) | 격자 표시, `random_point`, 플래너 `near`, API, 랜덤 탭, 배너, 온보딩 랜덤 모드, 프리미엄 끄기, 한국어 기본 | US-010–017, 040 | 굴리기 → 코스가 배포 환경에서 된다, 평가 결과 기록 |
| M4 사진·지도·피드 | 업로드, 사진 지도, 피드, 좋아요, 댓글 | US-020–027 | Android에서 되던 것이 웹에서 모두 된다 |
| M5 방문 인증 | 판정, 표시 | US-030, 031 | 핵심 흐름(G1)이 끝까지 된다 |
| M6 한국어 완성 | 장소 설명, 추천 이유 | US-041, 042 | 한국어 화면에 영어 문장이 남지 않는다 |
| M7 전환 | Ktor 종료, Supabase B 정지 | US-050 | 옛 서버 트래픽 0 |
| 그 뒤 (P1) | 글·댓글 삭제, 게시글 화면, HEIC, 익명 세션 CAPTCHA | US-028, 029 | |

M3을 M4보다 먼저 하는 이유: 랜덤 + 추천이 이 통합의 새 가치다. 사진·피드는 이미 있던 기능을 옮기는 일이라 일정이 밀려도 위험이 작다.

### 8.2 저장소와 코드 구조 [제안]

```
random-jeju-web/            (새 저장소, Q-02. 이름은 바꿔도 된다)
  frontend/   Next.js 14    → Vercel (Root: frontend)
    app/random, app/map, app/feed, app/upload, app/posts/[id]   (새로)
    lib/supabase.ts          Auth 전용 클라이언트
  backend/    FastAPI       → Railway (Root: backend)
    app/auth.py              토큰 검증
    app/random_point.py      FR-1–FR-3
    app/posts.py, app/photos.py, app/visits.py
    app/planner.py           FR-6만 고침
  supabase/migrations/       0000_randomjeju_baseline.sql, 0001_mypace.sql, 0002_merge.sql
  data/
```

### 8.3 백엔드

- 새 의존성: `Pillow`, `python-multipart`(FastAPI 파일 업로드에 필요), `PyJWT[crypto]`. 방향별 테스트 사진 8장은 파일로 두지 않고 테스트가 Pillow로 만든다.
- **Supabase 클라이언트는 HTTP/1.1 연결 풀로 만든다** (`store.py`). supabase-py 기본값은 HTTP/2 연결 하나를 같이 쓰는데, FastAPI가 동기 함수를 여러 스레드에서 돌려 두 요청이 동시에 그 연결을 쓰면 Supabase가 연결을 끊었다 ("Server disconnected", 2026-11-19 댓글 목록에서 재현). 배포에서 사용자가 늘면 더 자주 났을 문제다.
- 플래너는 `TripCtx.near`와 `course_hub`의 한 갈래, `random_course` 함수만 더한다. 나머지는 손대지 않는다. 해커톤 PRD 10장의 LLM 입력·검증은 그대로다.
- Storage 업로드가 DB보다 먼저라서, DB가 실패하면 올린 파일을 지운다 (FR-13 실패 시 보상). Ktor에서는 고아 파일이 남았다.
- Railway 메모리: 15MB 사진을 Pillow로 열면 수백 MB를 쓸 수 있다. `Image.MAX_IMAGE_PIXELS`를 4,000만으로 두고 넘으면 413을 낸다.
- 익명 세션 남용: Supabase의 익명 로그인 속도 제한(기본 IP당 시간당 30회)을 유지하고, P1에서 Turnstile CAPTCHA를 켠다. 업로드는 사용자당 하루 30장(US-020).

### 8.4 프론트엔드

- `@supabase/supabase-js`는 Auth에만 쓴다. API 호출은 `frontend/lib/api.ts`에 함수를 더하고 `Authorization` 헤더를 붙인다.
- `exifr`로 브라우저에서 EXIF를 읽는다. **iOS Safari 등 일부 브라우저는 사진을 고를 때 위치 정보를 지울 수 있다.** 그래서 US-021의 "현재 위치 사용"이 대안이고, 방문 인증도 `device` 위치를 받아 준다.
- 카카오 지도 레벨은 1(가장 가까움)–14다. `CLUSTER_MIN_LEVEL = 7`은 `frontend/config/map.ts`에 두고 실제 데이터로 조정한다.

### 8.5 데이터

- 장소 사진은 외부 URL이다 (한국관광공사 1,025곳, 비짓제주 27곳, 위키미디어 7곳, 없음 6곳). Supabase B의 Storage에서 옮길 파일이 없다.
- 해커톤 테이블과 RandomJeju 테이블은 이름이 겹치지 않는다 (2026-11-19 조회로 확인: A에 해커톤 테이블 이름이 하나도 없다). 다만 `areas`(해커톤 14개 지역)와 `admin_areas`(RandomJeju 읍면동 43개)는 다른 개념이다. 코스는 `areas`, 사진 클러스터는 `admin_areas`를 쓴다.
- **Supabase A 조회 결과 (2026-11-19, 읽기 전용)**
  - PostgreSQL 17.6, PostGIS 3.3.7, DB 시간대 UTC. `tsm_system_rows`는 설치돼 있지 않다 (필요 없다).
  - 행 수: `grids` 7,969, `locations` 274, `admin_areas` 43, `photos` 32, `posts` 27, `post_likes` 25, `comments` 8, `users` 2, `auth.users` 2(모두 이메일).
  - `grids`: 500m×500m(약 0.25km²) 다각형, SRID 4326, `blacklist` 전부 `false`, `weight` 전부 1.0. 범위가 추자도(북위 34.01°)까지다. 육지 비율 25% 미만 274칸, 25–50% 134칸, 50–75% 149칸, 75% 이상 7,412칸.
  - `post_category` enum: 맛집, 카페, 쇼핑, 관광, 문화, 스포츠 (Android와 같다). 지금 게시글은 관광 22, 맛집 3, 카페 2.
  - `posts`에 `like_count`, `comment_count`, `updated_at`, `grid_id` 열이 있다. `photos`에도 `grid_id`가 있다 (Ktor는 쓰지 않는다).
  - 인덱스: `photos.geom`, `grids.cell`, `admin_areas.geom`에 GiST 인덱스가 있다. `admin_areas.geom`에는 같은 인덱스가 두 개(`admin_areas_geom_geom_idx`, `idx_admin_geom`) 있으니 하나를 지운다.
- Supabase B의 `courses`, `course_items`, `place_reports`에 남길 데이터가 있으면 M7 전에 A로 복사한다. 데모 코스는 `reset_emma.py`로 다시 만든다.

### 8.6 보안

- **열려 있던 구멍 (2026-11-19 적용 완료).** Supabase A의 `public` 테이블 13개 중 10개가 RLS가 꺼져 있었고, `anon` 역할이 SELECT·INSERT·DELETE 권한을 가진다: `users`, `photos`, `locations`, `grids`, `admin_areas`, `reco_config`, `preference_category_map`, `user_events`, `user_profile_settings`, `user_profile_stats`. anon 키는 Android 소스(`auth/SupabaseClient.kt:13`)에 그대로 들어 있다. 그래서 지금 누구나 PostgREST로 사용자 정보와 사진 기록을 읽고, 고치고, 지울 수 있다. 조치:
  ```sql
  alter table users enable row level security;            -- 나머지 9개도 같은 문장
  -- Android 앱이 끝날 때(M7)까지 가입·프로필 화면이 동작하도록 users에만 임시 정책
  create policy "own row read"   on users for select using (auth.uid() = id);
  create policy "own row insert" on users for insert with check (auth.uid() = id);
  ```
  Ktor 서버는 `postgres` 계정(테이블 소유자, `rolbypassrls`)으로 접속하므로 RLS의 영향을 받지 않는다. M7에서 `users`의 임시 정책 두 개와 `posts`·`comments`·`post_likes`의 정책 10개를 지운다 (FR-34). **2026-11-19 지웠다 (`0006_cleanup.sql`).**
  - 적용 결과 (2026-11-19): 정책은 `authenticated` 역할에만 걸었다. `anon` 역할로는 10개 테이블이 모두 0행으로 보이고(`posts`는 기존 공개 읽기 정책대로 27행), 로그인한 사용자는 자기 `users` 행 1개만 보인다. `postgres`로는 행 수가 그대로다. Ktor의 `/api/photos/map`(28개), `/api/photos/clusters`(12개) 응답이 적용 전과 같다.
  - 되돌리기: 두 정책을 `drop policy`하고 10개 테이블에 `disable row level security`.
  - 남은 영향: Android 가입 때 이메일 확인이 켜져 있어 세션 없이 `users`에 넣는 경우, 그 넣기는 이제 실패한다. 사용자 2명뿐이고 Android는 끝낼 예정이라 그대로 둔다.
- Supabase A의 DB 비밀번호가 `random-jeju-api`의 git 기록에 있다 (`src/main/resources/application.conf`). M0에서 바꾼다.
- 서비스 키는 Railway에만 둔다. 브라우저에는 anon 키만 간다 (anon 키는 공개돼도 되는 키이고, RLS에 정책이 없으므로 anon 키로는 데이터에 접근할 수 없다).
- Android 앱 소스에 하드코딩된 키(Supabase anon 키, 카카오 네이티브 키)는 웹에서 쓰지 않는다. 웹은 카카오 JavaScript 키를 새로 쓰고 도메인을 등록한다.

---

## 9. 성공 지표

| 지표 | 목표 | 재는 방법 |
|---|---|---|
| 굴리기 응답 (`POST /random-points`) | p95 500ms 이하 | Railway 로그 |
| 랜덤 코스 생성 (`POST /random-courses`) | 규칙 플래너 p95 3초, LLM p95 8초 이하 | Railway 로그 |
| 랜덤 코스 품질 | 성공률 95% 이상, 이동 30분 초과·식사 보장 위반·영업시간 위반 0건 | US-015 평가 (300회) |
| 랜덤 다양성 | 300회에서 서로 다른 동네 30곳 이상, 한 동네가 10% 넘게 나오지 않음 | US-015 평가 |
| 동네까지 거리 (`snap_km`) | 중앙값 4km 이하, p90 7km 이하. (처음 목표 2km·5km는 프로필 없이 계산한 밀집 장소 거리에서 나왔다. 관심사·식사 필터를 거친 동네는 그보다 드물다.) 2026-11-19: 중앙값 3.7km, p90 6.7km로 통과 | US-015 평가 |
| 사진 업로드 | 성공률 98% 이상, 썸네일 방향 오류 0건 | 서버 로그, Orientation 테스트 |
| 핵심 흐름 | 굴리기 → 코스 → 업로드 → 인증이 배포 환경에서 끊기지 않음 | 수동 시나리오 1회 + E2E 테스트 |
| 전환 | Ktor 서버 요청 0 (2026-11-19부터 공개 호출 403). Supabase B는 정지하지 않기로 했다 (US-050) | Cloud Run 콘솔 |

---

## 10. 결정 기록

2026-11-19에 모두 정했다. Q-07, Q-09, Q-10은 Supabase A를 읽기 전용으로 조회해 확인했다.

| # | 질문 | 결정 | 반영한 곳 |
|---|---|---|---|
| Q-01 | 서비스 이름 | **Random Jeju (랜덤제주).** MyPace라는 이름은 쓰지 않는다 | 1.3 |
| Q-02 | 저장소 | **새 GitHub 저장소.** 해커톤 `frontend/`, `backend/`, `data/`를 복사해 시작한다. 해커톤 저장소(`ai-bootcamp/hackathon`)는 부트캠프 기록으로 그대로 둔다 | 8.1 M0, 8.2 |
| Q-03 | 기존 이메일 가입자 | **게시글만 남긴다.** 2명의 게시글 27개는 닉네임과 함께 계속 보인다. 그 계정으로 웹에 로그인하지는 못한다. 이메일 로그인과 익명 계정 잇기는 나중(P2)에 만든다 | 6장, FR-33 |
| Q-04 | Android 앱 | **끝낸다.** 업데이트하지 않는다. 필요하면 나중에 웹을 PWA로 설치하게 한다 | 6장, US-050 |
| Q-05 | 프리미엄 | **모두 무료.** 잠금과 구매 화면을 설정으로 끈다. 코드는 남긴다 | US-017 |
| Q-06 | 랜덤 지점이 갈 곳에서 멀 때 | **먼 칸은 뽑지 않는다.** 밀집 장소가 5km 안에 없는 칸, 육지가 절반 미만인 칸, 우도·추자도 칸을 `blacklist`로 표시한다. 2km 넘게 옮기면 안내 문구는 그대로 보인다 | FR-0, US-010, US-014 |
| Q-07 | 격자 칸 수와 `blacklist` 기준 | 7,969칸(500m×500m), `blacklist`는 쓰이지 않고 있었다 (전부 `false`). FR-0 기준을 적용하면 중심이 육지인 7,569칸 중 약 6,700칸이 남는다 (정확한 수는 `mark_grids.py`가 출력) | FR-0, FR-1, 8.5 |
| Q-08 | 방문 인증 기준 | **장소 크기별 반경.** 랜덤 지점 500m, 넓은 장소(해변·오름·공원·숲·폭포·자연) 500m, 그 밖 200m. 코스를 만든 뒤 7일 안 | FR-20 |
| Q-09 | 시간 열의 시간대 | 기본값으로 들어간 `locations.created_at`, `photos.timestamp`, `users.join_date`는 **UTC**, EXIF에서 온 `photos.image_time`은 **한국 시간**. 모두 `timestamptz`로 바꾼다 | FR-32 |
| Q-10 | `post_category` 값 | 맛집, 카페, 쇼핑, 관광, 문화, 스포츠 (Android와 같다) | FR-11, US-025 |
| Q-11 | 사진 위치 공개 정밀도 | **공개는 약 100m로 흐리게.** 정확한 좌표는 DB에만 두고 방문 판정에만 쓴다 | FR-13a, US-021 |
| Q-12 | RLS 긴급 조치를 통합 작업과 별개로 지금 적용하나? | **2026-11-19에 적용했다.** 10개 테이블 RLS 켬, `users`에 본인 행 정책 2개 | 8.6, US-050 |

### 10.1 남은 질문

| # | 질문 | 기본값 |
|---|---|---|
| Q-13 | 피드를 언제 개인화하나? (`reco_config` 등 설계만 된 추천 테이블, 6장) | 이번 통합 범위 밖. 로그인(Q-03의 P2)과 함께 다시 정한다 |
