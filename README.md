# Fokus Laufen PC 동기화

PC가 있으면 매일 아침 **달리기 기록(원본 FIT)과 수면·HRV·안정시 심박**이 Fokus Laufen 앱에 자동으로 들어가요. 휴대폰으로 파일을 받고 올릴 필요가 없어져요.

- 가민 **비밀번호는 이 PC에서 가민에 로그인할 때 한 번만** 쓰고, 저장하거나 앱 서버로 보내지 않아요.
- 앱에는 **동기화 키**로 올려요. 이 키는 **내 폴더에 올리기만** 할 수 있어요(읽기·지우기 불가). 잃어버리면 앱에서 다시 만들면 이전 키는 바로 막혀요.
- Windows 10/11 기준이에요. **Python 설치는 필요 없어요.**

## 처음 한 번 (5분 + 첫 동기화)

0. **먼저 앱 가입** — 휴대폰으로 https://fokus-laufen.web.app 열기 → Google 로그인 → 동의 → 브라우저 메뉴의 **홈 화면에 추가**. (이미 쓰고 있으면 건너뛰기)
1. **동기화 키 만들기** — 휴대폰 앱 **내 정보 → PC 동기화 → 키 만들기 → 복사**. 키는 이때 한 번만 보여요. 카카오톡 '나와의 채팅'이나 메일로 PC에 보내 두세요.
2. **PC에서 설치 파일 받기** — **[FokusLaufen-Setup.exe 받기](https://github.com/kiuk104/fokus-laufen-sync/releases/latest/download/FokusLaufen-Setup.exe)** → 더블클릭
   - Windows가 **"Windows의 PC 보호"** 창을 띄우면 **추가 정보 → 실행**. (작은 개인 프로그램이라 유료 인증서가 없어서 뜨는 안내예요)
   - 관리자 권한은 필요 없어요. 내 계정에만 설치돼요.
3. **설치가 끝나면 Fokus Laufen 창이 열려요** — 순서대로 하면 끝이에요.
   1. 동기화 키 붙여 넣기
   2. 가민 이메일·비밀번호로 로그인 (2단계 인증을 쓰면 코드 입력 창이 떠요)
   3. "자동으로 받기" 켜 둔 채로 **첫 동기화 시작** — 처음엔 최근 90일이라 10~20분 걸려요. 창을 닫아도 계속되고 끝나면 알림이 떠요.

## 그다음부터

- **아무것도 안 해도 돼요.** 평소에는 아무 창도 떠 있지 않아요. PC에 로그인하고 3분 뒤(또는 PC가 켜져 있으면 매일 오전 9시) **하루 한 번** 조용히 받고 올린 뒤, 화면 오른쪽 아래에 **"가민 기록을 앱에 올렸어요"** 알림만 떠요.
- 지금 바로 올리고 싶거나 상태를 보고 싶으면 **시작 메뉴 → Fokus Laufen** → **지금 동기화**
- 가민이 오늘 수면·HRV를 갖고 있으려면 시계가 휴대폰 가민 앱과 먼저 동기화돼 있어야 해요. 아침에 휴대폰을 한 번 연 다음 PC를 켜면 가장 확실해요.

## 이럴 땐

| 알림·화면 | 해결 |
|---|---|
| 가민 로그인이 필요해요 | 시작 메뉴 → Fokus Laufen → **가민 다시 로그인** |
| 동기화 키를 다시 등록해 주세요 | 앱에서 키를 다시 만들고 → Fokus Laufen → **동기화 키 바꾸기** |
| 오늘 가민 동기화를 못 했어요 | 대개 인터넷이나 가민 쪽 일시 문제예요. 다음 자동 실행 때 다시 해요. 계속되면 Fokus Laufen 창의 **진행 기록**을 확인 |
| 더 오래된 기록도 올리고 싶음 | Fokus Laufen → **예전 기록 더 받기…** (6개월·1년·2년) |
| 자동 실행을 끄고 싶음 | Fokus Laufen → "자동으로 받기" 체크 해제 |
| 알림이 귀찮음 | Fokus Laufen → "다 올리면 Windows 알림 보기" 체크 해제 (실패 알림은 계속 떠요) |
| 그만 쓰고 싶음 | 앱에서 **키 삭제** → Windows **설정 → 앱 → Fokus Laufen PC 동기화 → 제거**. 제거할 때 이 PC의 로그인 정보·받은 기록도 지울지 물어봐요 |

### 예전 버전(setup.bat)을 쓰고 있었다면

새 설치 파일을 설치하고, 처음 창에서 **"예전 버전(setup.bat)을 쓰고 있었다면: 그 폴더에서 설정 가져오기"** → 예전 폴더 선택. 키·가민 로그인·받은 기록을 그대로 가져와요. 자동 실행도 새 방식(창 없음)으로 바뀌어요. 그다음 예전 폴더는 지워도 돼요.

## 이 PC에 저장되는 것

`%LOCALAPPDATA%\FokusLaufen` 폴더에 `config.json`(동기화 키), `.garmin_tokens\`(가민 로그인 토큰), `data\`(받은 파일·`sync.log` 기록)가 있어요. 다른 사람과 공유하지 마세요. Fokus Laufen 창 아래 **데이터 폴더 열기**로 바로 열 수 있어요.

---

## 개발자용

| 파일 | 하는 일 |
|---|---|
| `fokus_sync.py` | 가민에서 받기·앱 서버로 올리기 (명령 창 버전도 이것 하나로: `python fokus_sync.py setup` / `run [--auto] [--days N]`) |
| `fokus_app.py` | 설치판 진입점. 창 없이 `--auto`(작업 스케줄러), Windows 알림, 작업 스케줄러 등록 |
| `fokus_ui.py` | 설정·상태 창 (tkinter) |
| `FokusLaufen.spec` · `installer/FokusLaufen.iss` | PyInstaller → Inno Setup 으로 `FokusLaufen-Setup.exe` |
| `.github/workflows/release.yml` | 태그 `vX.Y.Z` 를 올리면 Windows 에서 빌드해 Releases 에 첨부 |
| `setup.bat` · `sync_today.bat` · `register_task.ps1` | 예전(1.x) 명령 창 방식. Python 이 있는 개발자용으로 남겨 둠 |

- 창 프로그램을 스크립트로 띄우기: `pip install -r requirements.txt` → `python fokus_app.py` (저장 위치는 이 폴더, `FOKUS_LAUFEN_HOME` 으로 바꿀 수 있음)
- 새 버전 배포: `fokus_sync.py` 의 `VERSION` 올림 → 커밋 → `git tag v2.0.1` → `git push --tags` → Actions 가 끝나면 Releases 에 `FokusLaufen-Setup.exe`
- 테스트: `python -m pytest -q tests`
