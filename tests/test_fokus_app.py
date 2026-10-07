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
