"""fokus_app: 자동 실행 결과 기록·동시 실행 막기·작업 XML (가민·서버·Windows 호출 없음)"""

import os
import sys
import xml.dom.minidom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fokus_app as fa  # noqa: E402
import fokus_sync as fs  # noqa: E402


def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "DATA", tmp_path)
    monkeypatch.setattr(fa, "LOCK", tmp_path / ".sync.lock")
    monkeypatch.setattr(fa, "LOG", tmp_path / "sync.log")


def test_records_error_then_clears_on_success(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)

    def need_login(**k):
        raise fs.NeedLogin("[가민 로그인 필요] 가민에 다시 로그인해 주세요.")
    monkeypatch.setattr(fs, "run_sync", need_login)
    assert fa.run_and_record(auto=True)[0] == "login"
    assert fs._state()["lastError"]["kind"] == "login"

    monkeypatch.setattr(fs, "run_sync", lambda **k: {"skipped": False, "fits": 1, "added": 1, "wellnessDays": 2})
    kind, res = fa.run_and_record()
    assert kind == "ok" and "lastError" not in fs._state()
    assert fa.summary(res) == "새 달리기 1개 · 수면·HRV 2일"
    assert not fa.LOCK.exists()


def test_busy_when_locked(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(fs, "run_sync", lambda **k: {"skipped": True})
    with fa.SyncLock():
        assert fa.run_and_record(auto=True)[0] == "busy"
    assert fa.run_and_record(auto=True)[0] == "skipped"


def test_unexpected_error_is_fail(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)

    def boom(**k):
        raise ValueError("x")
    monkeypatch.setattr(fs, "run_sync", boom)
    sys_stdout = sys.stdout
    assert fa.run_and_record()[0] == "fail"
    sys.stdout = sys_stdout


def test_task_xml_is_valid_and_runs_auto():
    x = fa.task_xml()
    doc = xml.dom.minidom.parseString(x.replace('encoding="UTF-16"', ""))
    assert doc.getElementsByTagName("Arguments")[0].firstChild.data.endswith("--auto")
    assert doc.getElementsByTagName("Delay")[0].firstChild.data == "PT3M"


class _Resp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _release(monkeypatch, tag, assets=("FokusLaufen-Setup.exe",), **extra):
    import json
    rel = {"tag_name": tag, "assets": [{"name": n, "browser_download_url": f"https://x/{n}", "size": 5_000_000}
                                       for n in assets], **extra}
    monkeypatch.setattr(fa.urllib.request, "urlopen", lambda req, timeout=0: _Resp(json.dumps(rel).encode()))


def test_check_update_only_newer(monkeypatch):
    monkeypatch.setattr(fs, "VERSION", "2.0.1")
    _release(monkeypatch, "v2.0.10")
    assert fa.check_update()["version"] == "2.0.10"  # 숫자로 비교 (2.0.10 > 2.0.9)
    _release(monkeypatch, "v2.0.1")
    assert fa.check_update() is None
    _release(monkeypatch, "v1.9.9")
    assert fa.check_update() is None
    _release(monkeypatch, "v3.0.0", assets=("other.zip",))
    assert fa.check_update() is None  # 설치 파일 없는 릴리스
    _release(monkeypatch, "v3.0.0", prerelease=True)
    assert fa.check_update() is None


def test_check_update_offline_is_none(monkeypatch):
    def fail(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(fa.urllib.request, "urlopen", fail)
    assert fa.check_update() is None


def test_updated_notice_once(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(fs, "VERSION", "2.0.2")
    fs._save_state({"pendingUpdate": "2.0.2"})
    assert fa.updated_notice() == "2.0.2"
    assert fa.updated_notice() is None


def test_auto_update_skips_when_not_installed(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(fa, "FROZEN", False)
    assert fa.auto_update() is False
