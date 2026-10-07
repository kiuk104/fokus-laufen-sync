"""
Fokus Laufen PC 동기화 — 창 프로그램 (설치판 FokusLaufen.exe)

    FokusLaufen.exe               설정·상태 창 (처음이면 설정 마법사)
    FokusLaufen.exe --auto        작업 스케줄러용: 창 없이 하루 한 번 받고 올린 뒤 Windows 알림
    FokusLaufen.exe --unregister  자동 실행 작업 지우기 (제거 프로그램이 부름)
    FokusLaufen.exe --selftest    빌드 확인용

평소에는 아무것도 떠 있지 않아요(트레이 상주 없음). 자동 실행은 Windows 작업 스케줄러의
"Fokus Laufen 동기화" 작업이 PC 로그인 3분 뒤 + 매일 오전 9시(꺼져 있었으면 켜진 뒤)에 이 파일을
--auto 로 부르고, 하루 한 번만 실제로 받습니다.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import fokus_sync as fs

APP_NAME = "Fokus Laufen"
AUMID = "FokusLaufen.PCSync"          # 설치 프로그램이 시작 메뉴 바로가기에 같은 ID 를 붙임 (알림에 이름·아이콘 표시)
TASK_NAME = "Fokus Laufen 동기화"
APP_URL = "https://fokus-laufen.web.app"
PC_SYNC_URL = APP_URL + "/?open=pc-sync"   # 앱이 이 주소로 열리면 PC 동기화 화면을 바로 띄움 (home_screen.dart)
PORT = 47613                          # 창이 이미 열려 있으면 그 창을 앞으로 (중복 실행 방지)
IS_WIN = sys.platform == "win32"
FROZEN = getattr(sys, "frozen", False)
RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"
NO_WINDOW = 0x08000000                # CREATE_NO_WINDOW: 보조 명령(schtasks·powershell)이 검은 창을 띄우지 않게
LOG = fs.DATA / "sync.log"
LOCK = fs.DATA / ".sync.lock"
BRAND = "#11a9ed"
BRAND_DARK = "#0b8cc6"


# ── 기록 ───────────────────────────────────────────────
class LogSink:
    """print 출력을 data/sync.log 에 쓰고, 창이 있으면 한 줄씩 넘겨줌"""

    def __init__(self, on_line=None):
        self.on_line = on_line
        self._buf = ""
        self._lock = threading.Lock()

    def write(self, s: str) -> int:
        with self._lock:
            try:
                LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(s)
            except OSError:
                pass
            if self.on_line:
                self._buf += s
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    self.on_line(line)
        return len(s)

    def flush(self) -> None:
        pass


def trim_log(max_bytes: int = 1_000_000, keep: int = 200_000) -> None:
    try:
        if LOG.stat().st_size > max_bytes:
            b = LOG.read_bytes()[-keep:]
            LOG.write_bytes(b[b.find(b"\n") + 1:])
    except OSError:
        pass


# ── 동시에 두 번 돌지 않게 ──────────────────────────────
class Busy(Exception):
    pass


class SyncLock:
    STALE_SEC = 3 * 3600  # 1년 치 첫 동기화도 이 안에 끝남. 비정상 종료로 남은 잠금은 이후 무시

    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        try:
            if LOCK.exists() and time.time() - LOCK.stat().st_mtime > self.STALE_SEC:
                LOCK.unlink()
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            raise Busy()
        return self

    def __exit__(self, *a):
        try:
            LOCK.unlink()
        except OSError:
            pass


def _set_error(kind: str | None, msg: str = "") -> None:
    st = fs._state()
    if kind:
        st["lastError"] = {"at": datetime.now().isoformat(timespec="seconds"), "kind": kind, "msg": msg}
    else:
        st.pop("lastError", None)
    fs._save_state(st)


def run_and_record(days: int | None = None, auto: bool = False, prompt_mfa=None) -> tuple[str, object]:
    """받고 올리고 결과를 상태 파일에 남김.
    돌려줌: ("ok", 결과) / ("skipped", {}) / ("busy"|"login"|"key"|"fail", 메시지)"""
    try:
        with SyncLock():
            res = fs.run_sync(days=days, auto=auto)
    except Busy:
        return "busy", "다른 동기화가 이미 진행 중이에요."
    except fs.NeedLogin as e:
        kind, msg = "login", str(e)
    except fs.BadKey as e:
        kind, msg = "key", str(e)
    except SystemExit as e:
        kind, msg = "fail", str(e) or "동기화하지 못했어요."
    except Exception as e:  # 예상 못 한 오류도 기록에 남기고 알림
        print(traceback.format_exc())
        kind, msg = "fail", f"{type(e).__name__}: {e}"
    else:
        _set_error(None)
        return ("skipped" if res.get("skipped") else "ok"), res
    print(msg)
    _set_error(kind, msg)
    return kind, msg


def summary(res: dict) -> str:
    parts = [f"새 달리기 {res.get('added', res.get('fits', 0))}개"]
    if res.get("wellnessDays") is not None:
        parts.append(f"수면·HRV {res.get('wellnessDays', 0)}일")
    return " · ".join(parts)


# ── Windows 알림 · 작업 스케줄러 ────────────────────────
def notify(title: str, body: str) -> None:
    """Windows 알림 센터 토스트. 실패해도 조용히 넘어감"""
    if not IS_WIN:
        print(f"[알림] {title} — {body}")
        return
    aumid = AUMID if FROZEN else r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    xml = ('<toast><visual><binding template="ToastGeneric">'
           f"<text>{escape(title)}</text><text>{escape(body)}</text>"
           "</binding></visual></toast>")
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
          "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
          "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($env:FL_TOAST);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:FL_AUMID)"
          ".Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       env=dict(os.environ, FL_TOAST=xml, FL_AUMID=aumid),
                       creationflags=NO_WINDOW, capture_output=True, timeout=30)
    except Exception:
        pass


def _auto_command() -> tuple[str, str]:
    if FROZEN:
        return sys.executable, "--auto"
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")  # 개발용: 창 없는 파이썬
    return str(pyw if pyw.exists() else exe), f'"{Path(__file__).resolve()}" --auto'


def task_xml() -> str:
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".lstrip("\\")
    cmd, args = _auto_command()
    desc = ("Fokus Laufen: 가민 커넥트에서 최근 달리기·수면·HRV 를 받아 Fokus Laufen 앱에 올립니다 (하루 한 번, 창 없이). "
            f"설정·끄기: 시작 메뉴 → Fokus Laufen. 기록: {LOG}")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Fokus Laufen</Author>
    <Description>{escape(desc)}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{escape(user)}</UserId>
      <Delay>PT3M</Delay>
    </LogonTrigger>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(cmd)}</Command>
      <Arguments>{escape(args)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, creationflags=NO_WINDOW, timeout=30)


def task_exists() -> bool:
    if not IS_WIN:
        return False
    try:
        return _schtasks("/Query", "/TN", TASK_NAME).returncode == 0
    except Exception:
        return False


def task_is_ours() -> bool:
    """예전 setup.bat 이 만든 작업(cmd.exe → sync_today.bat)이면 False"""
    try:
        r = _schtasks("/Query", "/TN", TASK_NAME, "/XML")
        return r.returncode == 0 and _auto_command()[0].lower() in r.stdout.decode("utf-16", "replace").lower()
    except Exception:
        return False


def register_task() -> str | None:
    """자동 실행 등록(이미 있으면 덮어씀). 실패하면 이유를 돌려줌"""
    if not IS_WIN:
        return "Windows 에서만 자동 실행을 등록할 수 있어요."
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        Path(path).write_text(task_xml(), encoding="utf-16")
        r = _schtasks("/Create", "/TN", TASK_NAME, "/XML", path, "/F")
        if r.returncode != 0:
            return (r.stderr or r.stdout).decode("mbcs" if IS_WIN else "utf-8", "replace").strip() or "등록 실패"
        return None
    except Exception as e:
        return str(e)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def unregister_task() -> None:
    if IS_WIN:
        try:
            _schtasks("/Delete", "/TN", TASK_NAME, "/F")
        except Exception:
            pass


def open_path(p: Path) -> None:
    if IS_WIN:
        os.startfile(str(p))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(p)])


# ── 창 없이 자동 실행 ───────────────────────────────────
def auto_main() -> None:
    sys.stdout = sys.stderr = LogSink()
    trim_log()
    if not fs.load_config().get("syncKey"):
        return
    kind, res = run_and_record(auto=True)
    cfg = fs.load_config()
    if kind == "ok":
        if cfg.get("notifySuccess", True):
            notify("가민 기록을 앱에 올렸어요", summary(res) + " — 앱에서 새로고침하세요")
    elif kind == "login":
        notify("가민 로그인이 필요해요", "시작 메뉴에서 Fokus Laufen 을 열고 '가민 다시 로그인'을 눌러 주세요.")
    elif kind == "key":
        notify("동기화 키를 다시 등록해 주세요", "앱에서 새 키를 만든 뒤, 시작 메뉴 → Fokus Laufen → '동기화 키 바꾸기'.")
    elif kind == "fail":
        notify("오늘 가민 동기화를 못 했어요", f"{res}\n다음 자동 실행 때 다시 시도해요.")


# ── 설정·상태 창 ────────────────────────────────────────
def window_main() -> None:
    # 이미 창이 열려 있으면 그 창을 앞으로 부르고 끝
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", PORT))
        srv.listen(2)
    except OSError:
        srv.close()
        srv = None
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=2) as c:
                c.sendall(b"show")
            return
        except OSError:
            pass  # 다른 프로그램이 포트를 쓰는 경우 — 그냥 연다

    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
        except Exception:
            pass

    from fokus_ui import MainWindow
    app = MainWindow(server=srv)
    app.mainloop()


def selftest() -> int:
    """빌드 확인용 (GitHub Actions): 묶인 모듈·아이콘이 다 들어갔는지"""
    try:
        import tkinter  # noqa: F401
        import curl_cffi  # noqa: F401
        import garminconnect  # noqa: F401
        import fokus_ui  # noqa: F401
        import segno  # noqa: F401
        assert (RES / "icon.ico").exists() and (RES / "icon-48.png").exists()
        task_xml()
        return 0
    except Exception:
        return 1


def main() -> None:
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    elif "--unregister" in a:
        unregister_task()
    elif "--auto" in a:
        auto_main()
    else:
        window_main()


if __name__ == "__main__":
    main()
