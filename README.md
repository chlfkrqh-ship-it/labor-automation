# 설치·동기화 안내

## GPT·Claude 공통 운영 (2026. 9. 10.)

현재 사용법은 `공통/운영.md`가 우선한다. Claude Code와 로컬 Codex에서 같은 사건·규칙·스크립트를 사용한다. 모델별 역할 분담이나 자동 API 호출은 설정하지 않았다.

- 공통 규칙: 루트 `AGENTS.md`. 업무별 원본은 기존 각 폴더 `CLAUDE.md`를 유지한다.
- 공통 명령어: `공통/명령어/`. Claude 슬래시 명령어와 GPT의 `labor-workflow` 스킬이 연결한다.
- 사건 상태·변경분·추출 캐시: `공통/사건상태.md`.
- 같은 입력의 GPT·Claude 결과 비교: `공통/결과비교.md`.
- `python 공통/scripts/system.py check`로 연결 상태 확인. 원본 수정 후 `sync`로 미리 보고 `sync --apply`로 갱신한다.

아래 설치 이력의 Claude 전용 시작 명령은 Claude Code에만 해당한다. Codex는 이 폴더를 프로젝트로 열어 사용한다. 두 제품 모두 필요한 로컬 실행 환경과 LBOX 브라우저 연결을 별도로 확인한다.

**처음 설치하는 것이라면 `시작하기.md` 를 먼저 본다.** 이 문서는 구조와 규칙을 적어 둔 참고용이다.

시스템 전체를 회사 OneDrive에 두고, 회사·집 두 PC가 같은 폴더를 본다.

```
%OneDrive%\노동사건자동화\        ← 지침·명령어·엔진·양식·사건 자료 전부
%LOCALAPPDATA%\노동사건자동화\    ← 파이썬 가상환경, 음성 모델 (동기화하지 않음)
```

**파이썬 가상환경과 모델 파일은 OneDrive에 두지 않는다.** 5_녹취록의 환경은 torch 와 음성 모델을 포함해 수 GB이고, PC마다 따로 설치해야 한다. 동기화하면 용량만 먹는 것이 아니라 서로의 환경을 깨뜨린다.

**시스템 파일은 git으로 관리하고, 사건 자료는 git에 올리지 않는다.** `.git/`을 OneDrive 안에 두면 두 PC의 index·lock 파일이 충돌해 저장소가 깨지므로, **저장소만 `%LOCALAPPDATA%\labor-automation
epo.git` 에 두고 작업본은 이 폴더 그대로 쓴다.** 폴더를 옮기지 않으므로 상대경로 규칙과 기존 스크립트가 그대로 돈다.

```
%LOCALAPPDATA%\labor-automation
epo.git\   ← .git (PC마다 따로, 동기화하지 않음)
%OneDrive%\노동사건자동화\                    ← 작업본
%LOCALAPPDATA%\노동사건자동화\                ← 파이썬 가상환경, 음성 모델
```

원격은 `https://github.com/chlfkrqh-ship-it/labor-automation`(private)이다. 무엇이 왜 제외되는지와 시행 기록은 `공통/git-분리-검토.md` 에 있다.

---

## 1. 첫 번째 PC

### 1-1. 폴더 배치

`노동사건자동화` 폴더를 OneDrive 안으로 옮긴다. 기존 `C:\노동사건자동화`가 있으면 그것을 그대로 옮기고, 이 배포본의 새 폴더들(`1_`~`3_`, `5_`, `6_`)을 합친다.

```
%OneDrive%\노동사건자동화\
├─ CLAUDE.md  README.md  .gitignore  백업.ps1
├─ .claude\  (skills, commands, settings.json)
├─ 1_검토의견  2_판례검색  3_서면보강  4_서면작성  5_녹취록  6_손해배상계산
```

**폴더를 "이 디바이스에 항상 유지"로 지정한다.** 폴더 우클릭에서 설정한다. 이걸 하지 않으면 OneDrive가 파일을 자리표시자로 바꿔 두어, 오프라인일 때 파이썬이 파일을 읽지 못한다.

### 1-2. 양식 파일 배치

- `1_검토의견\templates\샘플\` — 기존 검토의견서 완성본 (서면 전환의 작업 베이스)

### 1-3. 파이썬 환경

**6_손해배상계산 · 4_서면작성** — 의존성이 가벼워 시스템에 그대로 깐다. **두 폴더 모두 깐다.**
`4_서면작성` 을 빠뜨리면 증거 정리(`evidence_check.py`)가 PyMuPDF 를 찾지 못해 멈춘다.

```powershell
cd "$env:OneDrive\노동사건자동화\6_손해배상계산"
pip install -r requirements.txt
python -m pytest tests\ -q

cd "$env:OneDrive\노동사건자동화\4_서면작성"
pip install -r requirements.txt
```

409건이 모두 통과해야 한다(신체손해 62건 + 노동 금액 347건). 이어서 `6_손해배상계산\노임표-추출-절차.md` 를 보고 노임표·생명표를 뽑는다. **대법원 프로그램이 깔린 PC에서 한 번만 하면 되고**, 결과 CSV는 OneDrive로 다른 PC에도 넘어간다.

**5_녹취록** — 가상환경을 OneDrive 밖에 만든다. `setup.ps1` 이 알아서 `%LOCALAPPDATA%` 에 잡는다.

```powershell
cd "$env:OneDrive\노동사건자동화\5_녹취록"
.\setup.ps1
```

전사 전용(CPU)으로 구성된다. 보유 PC 두 대 모두 GPU 화자 분리를 쓸 수 없으므로 HuggingFace 토큰은 넣지 않아도 된다.

---

## 2. 두 번째 PC

같은 OneDrive 계정으로 로그인하면 폴더가 그대로 내려온다. 그다음 이 PC에서 할 일은 셋이다.

1. 폴더를 **"이 디바이스에 항상 유지"** 로 지정
2. `6_손해배상계산` 과 `4_서면작성` — 각각 `pip install -r requirements.txt`
3. `5_녹취록` — `.\setup.ps1` (이 PC에도 가상환경과 모델을 새로 받는다)

노임표 CSV와 양식·샘플은 이미 동기화되어 있으므로 다시 준비하지 않는다.

LBOX는 이 PC에서도 인앱 브라우저의 로그인 상태를 먼저 보고, 로그인되어 있지 않으면 엣지 브라우저로 쓴다. 한 계정에 동시에 3곳까지만 로그인되므로, 엣지에 Claude in Chrome 확장을 설치하고 lbox.kr 에 로그인해 둔다. 자세한 내용은 `공통/브라우저.md` 에 있다.

---

## 3. 매일 쓰는 흐름

```powershell
cd "$env:OneDrive\노동사건자동화"
claude --chrome
```

어느 사건이 어디까지 갔는지는 `현황.bat` 을 눌러 본다. 폴더에 있는 자료만 읽어 표 한 장을 만든다.

```powershell
python 공통/scripts/dashboard.py --open
```

작업을 시작할 때 OneDrive 동기화가 끝났는지(트레이 아이콘) 한 번 보고 들어간다.

**같은 파일을 양쪽 PC에서 동시에 열지 않는다.** OneDrive는 충돌하면 병합하지 않고 `파일명-PC이름.md` 같은 사본을 만든다. 사건 단위로 한쪽에서만 작업하는 편이 안전하다.

시스템 파일을 고쳤으면 커밋한다.

```
공통\scripts\g.bat status
공통\scripts\g.bat add -A
공통\scripts\g.bat commit -m "무엇을 고쳤는지"
공통\scripts\g.bat push
```

**다른 PC에서 받을 때는 `pull` 이 아니라 아래 세 줄이다.** 작업본은 OneDrive 가 이미 날라 주었는데
`.git` 은 PC마다 따로여서, 그 PC의 git 은 이미 도착한 파일을 '커밋 안 한 내 변경'으로 본다.
그 상태에서 `pull` 하면 `Your local changes to the following files would be overwritten by merge` 로 멈춘다.

```
공통\scripts\g.bat fetch origin main
공통\scripts\g.bat diff origin/main --stat     ← 비어 있으면 OneDrive 가 이미 날라 준 것
공통\scripts\g.bat reset --mixed origin/main   ← 파일은 그대로 두고 이력만 맞춘다
```

**가운데 줄이 비어 있을 때만 `reset` 한다.** 비어 있지 않으면 OneDrive 동기화가 덜 끝났거나
그 PC에서 따로 고친 것이 있다는 뜻이다. 동기화를 기다려 다시 보고, 그래도 남으면
그 PC에서 먼저 커밋한 뒤 `g.bat pull` 한다.

사건 자료는 git 에 올라가지 않는다. 사건 산출물(서면초안·호증목록·작업 메모)의 별도 묶음이 필요하면 `.\백업.ps1` 이 `%OneDrive%\노동사건자동화-백업\` 에 zip 을 남긴다. 다만 이 PC의 PowerShell 실행 정책이 `Restricted` 이면 `powershell -ExecutionPolicy Bypass -File .\백업.ps1` 로 실행해야 한다.

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

**사건 작업을 다른 곳에서 이어가는 수단은 Remote Control 이다.** LBOX 검색·하이라이트는 사용자가 로그인한 브라우저를, docx 면수 확인은 Word 를, 한글 양식은 한컴오피스를, 녹취는 로컬 음성 모델을 각각 필요로 하므로 클라우드로 옮길 수 없다. 클라우드에서 되는 것은 계산 엔진·스크립트·지침 작업이고, `6_손해배상계산` 의 pytest 409건은 그대로 돈다.

---

## 6. 점검

- `/검토의견` — LBOX 검색이 붙고 노란 하이라이트가 남는지
- `/판례검색` — 표 형식과 불리한 판례 포함 여부
- `/서면` — 프레임 병합과 최종 docx 생성까지
- `/손배계산` — 짧은 사건 하나로 사건.yaml 초안까지
- `python -m pytest tests/ -q` — 6_손해배상계산에서 409건
- `python 4_서면작성/scripts/evidence_check.py --help` — 증거 스크립트가 PyMuPDF 를 찾는지
- `python cli.py cases/labor_sample.yaml -o "$env:TEMP\노동.xlsx"` — 노동 금액 계산표가 나오는지
- 녹취 — 짧은 음성 하나로 전사·화자 분리
