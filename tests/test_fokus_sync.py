"""fokus_sync: 업로드 나누기·기록·실패 시 재시도 (가민·서버 호출은 가짜)"""

import json
import os
import sys
import zipfile
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fokus_sync as fs  # noqa: E402


def _setup(tmp_path, monkeypatch, n_fit=45, fit_size=1000):
    monkeypatch.setattr(fs, "DATA", tmp_path)
    monkeypatch.setattr(fs.time, "sleep", lambda s: None)
    (tmp_path / "fit").mkdir()
    for i in range(n_fit):
        (tmp_path / "fit" / f"2026-09-{i % 28 + 1:02d}_5.0km_{1000 + i}.fit").write_bytes(os.urandom(fit_size))
    for k in ("stats", "sleep", "hrv"):
        (tmp_path / "raw" / k).mkdir(parents=True)
        (tmp_path / "raw" / k / "2026-10-05.json").write_text("{}")


def test_plan_splits_by_count_and_puts_daily_in_first(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    b = fs.plan({})
    assert [sum(1 for r, _ in x if r.startswith("fit/")) for x in b] == [20, 20, 5]
    assert sum(1 for r, _ in b[0] if r.startswith("raw/")) == 3


def test_plan_splits_by_size(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, n_fit=6, fit_size=8 * 1024 * 1024)
    assert [len([r for r, _ in x if r.startswith("fit/")]) for x in fs.plan({})] == [2, 2, 2]


def test_upload_records_only_done_batches(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, n_fit=25)
    calls = []

    def fake(cfg, action, body=None, extra=""):
        if action == "upload":
            calls.append(zipfile.ZipFile(io.BytesIO(body)).namelist())
            return {"uploadId": f"pc-{len(calls)}"}
        status = "done" if extra.endswith("pc-1") else "error"
        return {"status": status, "added": 1, "duplicates": 0, "wellnessDays": 1, "failed": 0, "error": "x"}

    monkeypatch.setattr(fs, "api_call", fake)
    assert fs.upload({"syncKey": "fl_x"}) is False  # 두 번째 묶음 실패
    log = json.loads((tmp_path / ".upload_log.json").read_text())
    assert len(log) == 23 and "raw/hrv/2026-10-05.json" in log  # 첫 묶음(20 FIT + 3 일별)만 기록
    assert len(fs.plan(log)) == 1  # 다음 실행 때 실패한 5개만 다시
