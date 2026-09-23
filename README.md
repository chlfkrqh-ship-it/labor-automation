# 구조·동기화 안내

## 운영

현재 사용법은 `공통/운영.md`가 우선한다. Claude Code 하나로 사건·규칙·스크립트를 쓴다.

- 공통 규칙: 루트 `CLAUDE.md`. 업무별 규칙: 각 폴더 `CLAUDE.md`.
- 명령어: `.claude/commands/`. 스킬: `.claude/skills/`. 파일마다 원본 하나이고 사본이 없다.
- 사건 상태·변경분·추출 캐시: `공통/사건상태.md`.
- `python 공통/scripts/system.py check`로 명령어·스킬이 제자리에 있는지 확인한다.

필요한 로컬 실행 환경과 LBOX 브라우저 연결은 PC마다 따로 확인한다.

**설치·이전 절차는 `시작하기.md` 에만 적는다.** 이 문서는 구조와 규칙을 적어 둔 참고용이다.

시스템 전체를 회사 OneDrive에 두고, 회사·집 두 PC가 같은 폴더를 본다.

```
%OneDrive%\노동사건자동화\        ← 지침·명령어·엔진·양식·사건 자료 전부
%LOCALAPPDATA%\노동사건자동화\    ← 파이썬 가상환경, 음성 모델 (동기화하지 않음)
```

**파이썬 가상환경과 모델 파일은 OneDrive에 두지 않는다.** 5_녹취록의 환경은 가상환경과 전사 모델을 합쳐 수 GB이고, PC마다 따로 설치해야 한다. 동기화하면 용량만 먹는 것이 아니라 서로의 환경을 깨뜨린다. 화자 분리 모델(35MB)만 예외로 `5_녹취록/models/` 에 둔다(루트 `CLAUDE.md`).

**시스템 파일은 git으로 관리하고, 사건 자료는 git에 올리지 않는다.** `.git/`을 OneDrive 안에 두면 두 PC의 index·lock 파일이 충돌해 저장소가 깨지므로, **저장소만 `%LOCALAPPDATA%\labor-automation\repo.git` 에 두고 작업본은 이 폴더 그대로 쓴다.** 폴더를 옮기지 않으므로 상대경로 규칙과 기존 스크립트가 그대로 돈다.

```
%LOCALAPPDATA%\labor-automation\repo.git\   ← .git (PC마다 따로, 동기화하지 않음)
%OneDrive%\노동사건자동화\                    ← 작업본
%LOCALAPPDATA%\노동사건자동화\                ← 파이썬 가상환경, 음성 모델
```

원격은 `https://github.com/chlfkrqh-ship-it/labor-automation`(private)이다. 무엇이 왜 제외되는지와 시행 기록은 `공통/git-분리-검토.md` 에 있다.

---

## 1. 첫 번째 PC

설치 절차는 `시작하기.md` 에 있다. 두 문서에 나누어 적으면 한쪽만 고쳐져 갈리므로 여기에는 옮겨 적지 않는다.

설치가 끝난 폴더의 맨 위는 아래와 같다.

```
%OneDrive%\노동사건자동화\
├─ CLAUDE.md  README.md  시작하기.md  .gitignore  백업.ps1  현황.bat
├─ .claude\  (skills, commands, settings.json)
├─ 1_검토의견  2_판례검색  3_서면보강  4_서면작성  5_녹취록  6_손해배상계산
├─ 공통\  (운영 규칙·공통 스크립트·판례기록)
```

---

## 2. 두 번째 PC

같은 OneDrive 계정으로 로그인하면 폴더가 그대로 내려온다. 그 PC에서 할 일은 `시작하기.md` '두 번째 PC' 에 있다. 특히 git 저장소 붙이기를 빠뜨리면 그 PC에서 고친 시스템 파일이 이력에 남지 않는다(`공통/운영.md` '시스템 파일 올리기'는 저장소가 없으면 건너뛴다).

---

## 3. 매일 쓰는 흐름

```powershell
cd "$env:OneDrive\노동사건자동화"
claude --chrome
```

어느 사건이 어디까지 갔는지는 `현황.bat` 을 눌러 본다. 폴더에 있는 자료만 읽어 표 한 장을 만든다.

```powershell
python -B 공통/scripts/dashboard.py --open
```

작업을 시작할 때 OneDrive 동기화가 끝났는지(트레이 아이콘) 한 번 보고 들어간다.

**같은 파일을 양쪽 PC에서 동시에 열지 않는다.** OneDrive는 충돌하면 병합하지 않고 `파일명-PC이름.md` 같은 사본을 만든다. 사건 단위로 한쪽에서만 작업하는 편이 안전하다.

**git 은 사람이 치지 않는다.** 시스템 파일(지침·명령어·엔진·스크립트)을 고치면, 작업을 맡은 AI 가 그 작업을 마칠 때와
다음 작업을 시작할 때 알아서 올린다. 다른 PC에서 따로 받을 것도 없다 — 파일은 OneDrive 가 맞춰 두고, 그 PC의 AI 가
작업을 시작할 때 이력을 맞춘다. 절차는 `공통/운영.md` '시스템 파일 올리기' 에 있다. PC마다 처음 한 번 하는 일(`g.bat` 실행 허락)은 `시작하기.md` 에 있다.

사건 자료는 git 에 올라가지 않는다. 사건 산출물(서면초안·서면 docx·호증목록·작업 메모)의 별도 묶음이 필요하면 `.\백업.ps1` 이 `%OneDrive%\노동사건자동화-백업\` 에 zip 을 남긴다. 다만 이 PC의 PowerShell 실행 정책이 `Restricted` 이면 `powershell -ExecutionPolicy Bypass -File .\백업.ps1` 로 실행해야 한다.

---

## 4. 경로를 쓸 때

OneDrive 경로는 PC마다 다르다. 회사 계정이면 `C:\Users\{사용자}\OneDrive - {회사명}` 형태이고, 두 PC의 계정·테넌트가 다르면 폴더 이름도 달라진다.

- 지침·명령어·스크립트에는 **절대경로를 쓰지 않는다.** 저장소 루트 기준 상대경로만 쓴다.
- 셸에서 필요하면 `%OneDrive%` (PowerShell은 `$env:OneDrive`)를 쓴다.
- 폴더 이름에 공백과 하이픈이 들어가므로(`OneDrive - 법무법인 평안`) 경로는 반드시 따옴표로 감싼다.

---

## 5. 휴대폰

LBOX 검색·하이라이트, 녹취, 손해배상 계산은 모두 로컬 실행이 필요해 휴대폰 단독으로는 되지 않는다.

| 방법 | 되는 것 | 조건 |
|---|---|---|
| Remote Control · Cowork 로 데스크톱 원격 구동 | 전부 | 그 PC가 켜져 있고 Claude 데스크톱 앱 실행 중 |
| Claude Code 웹/모바일(claude.ai/code) | **시스템 파일 작업만** | GitHub 저장소에서 clone 한다. 사건 자료가 없고, LBOX·Word·한컴·음성 모델도 없다 |
| 휴대폰 OneDrive 앱 | 산출물 열람 | 편집은 충돌 위험이 있어 권하지 않음 |

**사건 작업을 다른 곳에서 이어가는 수단은 Remote Control 이다.** LBOX 검색·하이라이트는 사용자가 로그인한 브라우저를, docx 면수 확인은 Word 를, 한글 양식은 한컴오피스를, 녹취는 로컬 음성 모델을 각각 필요로 하므로 클라우드로 옮길 수 없다. 클라우드에서 되는 것은 계산 엔진·스크립트·지침 작업이고, `6_손해배상계산` 의 pytest 는 그대로 돈다.

---

## 6. 점검

- `/검토의견` — LBOX 검색이 붙고 노란 하이라이트가 남는지
- `/판례검색` — 표 형식과 불리한 판례 포함 여부
- `/서면` — 프레임 병합과 최종 docx 생성까지
- `/손배계산` — 짧은 사건 하나로 사건.yaml 초안까지
- `6_손해배상계산` 에서 `python -B -m pytest tests -q -p no:cacheprovider` — 실패(failed) 없이 모두 통과하는지
- 루트에서 `python 4_서면작성/scripts/evidence_check.py --help` — 증거 스크립트가 PyMuPDF 를 찾는지
- `6_손해배상계산` 에서 `python -B cli.py cases/labor_sample.yaml -o "$env:TEMP\노동.xlsx"` — 노동 금액 계산표가 나오는지
- 녹취 — 짧은 음성 하나로 전사·화자 분리
