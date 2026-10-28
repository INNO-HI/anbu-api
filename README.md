# anbu-api

**제주 안부똑똑 데이터 관리·전송 체계** — IoT-LED 실증 데이터를 본교 서버에 누적 관리하고, 가명처리를 거쳐 참여 대학에 구독형(MQTT/TLS)으로 전송하며, 실시간 운영 대시보드로 확인하는 시스템.

> 동국대학교 COSS사업단 발주 / 첨단분야(사물인터넷) 혁신융합대학(COSS) 사업
> 과업지시서: [`docs/`](docs/) · 개발 계획: [`docs/개발계획서.md`](docs/개발계획서.md) · 운영: [`docs/운영매뉴얼.md`](docs/운영매뉴얼.md)

## 데이터 흐름

```
원시스템 수집 ──▶ 누적 DB(원본·시계열) ──▶ 전송용 DB(가명처리본 7테이블) ──┬─▶ 참여 대학 구독 전송 (MQTT/TLS)
                 · 점등 구간 파생(SFR-002)   · 무작위 토큰 치환(SFR-004)      └─▶ 수신 확인 → 제공 실적 집계
                 · 장비 상태 이력            · 암호화 매핑 분리 보관
                 └─▶ 실시간 운영 대시보드(SFR-005) · 3단계 권한·화면 마스킹(SFR-007)
```

- **원본은 본교 서버 보존**, 외부 제공은 **가명처리본만**. 직접식별자는 전송 스키마에 컬럼 자체가 없다.
- DB 3개 물리 분리: 누적(accum) / 전송용(transfer) / 운영(ops: 암호화 매핑·이력·계정).

## SFR 구현 현황

| ID | 과업 | 구현 | 테스트 |
|---|---|---|---|
| SFR-001 | 서버 진단·증설 시점 산정 | [`diagnostics/`](src/anbu_api/diagnostics/) | ✅ |
| SFR-002 | 누적 DB 재구조화(점등 구간·상태 이력·보존) | [`etl/`](src/anbu_api/etl/) | ✅ |
| SFR-003 | 데이터 사전(테이블·필드·코드·결측 표준) | [`dictionary/`](src/anbu_api/dictionary/) | ✅ |
| SFR-004 | 전송용 DB 분리·가명처리·전송 암호화 | [`pseudonym/`](src/anbu_api/pseudonym/) | ✅ |
| SFR-005 | 실시간 운영 대시보드 연계·확장 | [`api/`](src/anbu_api/api/) + [대시보드](src/anbu_api/api/templates/dashboard.html) | ✅ |
| SFR-006 | 구독형 전송(MQTT·구독 권한·전송 이력) | [`transport/`](src/anbu_api/transport/) | ✅ |
| SFR-007 | 3단계 권한·화면 마스킹 | [`api/auth.py`](src/anbu_api/api/auth.py) · [`masking.py`](src/anbu_api/api/masking.py) | ✅ |
| SFR-008 | 운영 이관·교육 | [`docs/운영매뉴얼.md`](docs/운영매뉴얼.md) | — |
| SFR-009 | (조건부) 전력 AMI 2종 통합·계량기 가명처리 | [`ami/`](src/anbu_api/ami/) | ✅ |
| SFR-010 | (선택) 자유기술 정밀 가명처리·재식별 시험·추가검수 | [`freetext/`](src/anbu_api/freetext/) | ✅ |

## 빠른 시작 (로컬 개발)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e . --no-deps

alias anbu=".venv/bin/python -m anbu_api.cli"
anbu init-db                          # sqlite 3개 DB 생성(운영은 .env로 MariaDB 지정)
anbu seed --subjects 6 --days 2       # 합성 데이터(개발 전용)
anbu etl intervals && anbu etl status && anbu etl inactivity
anbu ami-load                         # SFR-009
anbu pseudo-run --include-memo        # SFR-004 (+SFR-010 메모 포함)
anbu publish --dry-run                # SFR-006 (실발행은 브로커 기동 후 --dry-run 제거)
anbu create-user --username admin --role super_admin
anbu serve                            # http://127.0.0.1:8000/dashboard
```

테스트: `.venv/bin/python -m pytest` (41 tests)

산출물 생성:
```bash
anbu diag --out build/서버진단보고서.md
anbu dictionary --out-dir build
anbu pseudo-run --record build/가명처리결과기록.md
anbu freetext-test --out build/재식별시험결과서.md --review-sheet build/검수시트.csv --review-record build/추가검수기록.md
anbu gen-acl --out deploy/mosquitto/config/acl
.venv/bin/python db/generate_ddl.py   # 운영 MariaDB DDL → db/migrations/
```

MQTT 브로커(개발): `docker compose -f deploy/docker-compose.yml up -d`

## 리포지토리 구성

```
├── docs/                   # 과업지시서(hwp/pdf), 개발계획서, 데이터모델,
│                           # 가명처리기준서·보존정책서·권한정의서·전송인터페이스정의서·운영매뉴얼
├── db/
│   ├── generate_ddl.py     # 모델 → MariaDB DDL
│   └── migrations/         # 001 누적 / 002 전송용 / 003 운영 DDL
├── deploy/                 # docker-compose(MariaDB+Mosquitto), mosquitto 설정
├── src/anbu_api/
│   ├── models/             # 누적·전송용·운영 3개 DB 모델(스키마 단일 원천)
│   ├── etl/                # SFR-002 │ pseudonym/  SFR-004 │ transport/ SFR-006
│   ├── diagnostics/        # SFR-001 │ dictionary/ SFR-003 │ ami/       SFR-009
│   ├── freetext/           # SFR-010 │ api/        SFR-005/007
│   ├── seed.py             # 합성 데이터(개발 전용) │ cli.py  운영 CLI
└── tests/                  # 모듈별 41개 테스트(in-memory sqlite)
```

## 보안·컴플라이언스 원칙(과업지시서 공통사항)
- 개인정보 포함 데이터는 본교 서버 밖 반출·외부 클라우드 AI 입력 금지 — SFR-010도 서버 내 규칙 기반+사람 검수.
- 가명 식별자는 무작위 토큰(단순 해시 미사용), 원 식별자는 Fernet 암호화 매핑으로 분리 보관, 재식별은 발주기관 전용(super_admin)+감사 로그.
- 전송 구간 TLS, 구독 권한 ACL, 전송·수신 이력 전건 기록.
- 원시스템 소스는 수정하지 않는다(읽기 전용 연계). 무상 라이선스 도구만 사용.
