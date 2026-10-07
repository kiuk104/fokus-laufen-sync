r"""
Fokus Laufen PC 동기화 (회원용)

가민 Connect 에서 내 달리기 원본(FIT)과 일별 수면·HRV·안정시 심박을 받아
Fokus Laufen 앱에 올립니다. 앱 서버에는 '동기화 키'로 내 폴더에만 올라갑니다.

    python fokus_sync.py setup          처음 한 번: 동기화 키 등록 + 가민 로그인
    python fokus_sync.py run            지금 받고 올리기
    python fokus_sync.py run --auto     자동 실행용: 오늘 이미 성공했으면 건너뜀
    python fokus_sync.py run --days 120 처음에 더 긴 기간 받기 (기본: 첫 실행 90일, 이후 마지막 실행 이후)

일반 사용자는 설치 파일(FokusLaufen-Setup.exe)의 트레이 앱(fokus_app.py)을 씁니다.
그때 저장 위치는 %LOCALAPPDATA%\FokusLaufen, 스크립트로 실행하면 이 폴더입니다
(환경 변수 FOKUS_LAUFEN_HOME 으로 바꿀 수 있음).

저장되는 것 (깃허브에 올라가지 않음, .gitignore):
    config.json      동기화 키
    .garmin_tokens/  가민 로그인 토큰 (비밀번호는 저장하지 않음)
    data/            받은 파일, 업로드 기록
가민 비밀번호는 이 PC 에서 가민에 로그인할 때만 쓰고 어디에도 보내거나 저장하지 않습니다.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path

VERSION = "2.0.1"


def _home() -> Path:
    """설정·토큰·받은 파일 위치. 설치판(.exe)은 Program Files 가 아니라 사용자 폴더에 저장"""
    if os.environ.get("FOKUS_LAUFEN_HOME"):
        return Path(os.environ["FOKUS_LAUFEN_HOME"])
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "FokusLaufen"
    return Path(__file__).resolve().parent


HERE = _home()
CONFIG = HERE / "config.json"
TOKENS = HERE / ".garmin_tokens"
DATA = HERE / "data"
DEFAULT_ENDPOINT = "https://europe-west3-fokus-laufen.cloudfunctions.net/pc_sync"

FIRST_RUN_DAYS = 90
OVERLAP_DAYS = 2           # 최근 며칠은 가민 값이 아직 바뀌는 중이라 다시 받음
DELAY_SEC = 1.2            # 가민 요청 간격 (429 방지)
MAX_FITS_PER_ZIP = 20
MAX_ZIP_BYTES = 20 * 1024 * 1024
DAILY = {  # 서버가 쓰는 것만 (wellness_core 의 sync 형식)
    "stats": lambda api, d: api.get_stats(d),
    "sleep": lambda api, d: api.get_sleep_data(d),
    "hrv": lambda api, d: api.get_hrv_data(d),
}

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ── 설정 ───────────────────────────────────────────────
def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_config(c: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def _state() -> dict:
    try:
        return json.loads((DATA / ".state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_state(s: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / ".state.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


class NeedLogin(SystemExit):
    """저장된 가민 로그인이 없거나 만료됨 — 사용자가 다시 로그인해야 함"""


class BadKey(SystemExit):
    """동기화 키가 없거나 막힘 — 앱에서 새 키를 받아야 함"""


# ── 앱 서버 (pc_sync) ──────────────────────────────────
def api_call(cfg: dict, action: str, *, body: bytes | None = None, extra: str = "") -> dict:
    url = f"{cfg.get('endpoint') or DEFAULT_ENDPOINT}?action={action}{extra}"
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET",
                                 headers={"Authorization": f"Bearer {cfg['syncKey']}",
                                          "Content-Type": "application/zip" if body is not None else "application/json",
                                          "User-Agent": f"fokus-sync/{VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error")
        except Exception:
            msg = None
        if e.code in (401, 403):
            raise BadKey(f"[동기화 키 오류] {msg or '키가 올바르지 않거나 막혔어요'}. 앱 → 내 정보 → PC 동기화에서 새 키를 만들어 주세요.")
        raise SystemExit(f"[앱 서버 오류 {e.code}] {msg or e.reason}")
    except urllib.error.URLError as e:
        raise SystemExit(f"[연결 실패] 인터넷 연결을 확인하세요: {e.reason}")


# ── 가민 ───────────────────────────────────────────────
def garmin_login(interactive: bool):
    """저장된 토큰으로 로그인. 없거나 만료되면 interactive 일 때만 명령 창에서 물어봄"""
    from garminconnect import Garmin
    if TOKENS.exists():
        api = Garmin()
        try:
            api.login(str(TOKENS))
            return api
        except Exception as e:
            print(f"저장된 가민 로그인이 만료됐어요: {e}")
    if not interactive:
        raise NeedLogin("[가민 로그인 필요] 가민에 다시 로그인해 주세요.")
    email = input("가민 이메일: ").strip()
    pw = getpass("가민 비밀번호 (입력해도 화면에 안 보여요): ")
    return garmin_login_with(email, pw, lambda: input("2단계 인증 코드: ").strip())


def garmin_login_with(email: str, password: str, prompt_mfa):
    """이메일·비밀번호로 새로 로그인하고 토큰만 저장 (비밀번호는 저장하지 않음)"""
    from garminconnect import Garmin
    TOKENS.parent.mkdir(parents=True, exist_ok=True)
    api = Garmin(email, password, prompt_mfa=prompt_mfa)
    try:
        api.login(str(TOKENS))
    except Exception as e:
        t = str(e)
        if "401" in t or "403" in t or "nauthorized" in t or "credentials" in t.lower():
            raise SystemExit("[가민 로그인 실패] 이메일이나 비밀번호가 맞지 않아요.")
        if "429" in t or "Too Many" in t:
            raise SystemExit("[가민 로그인 실패] 가민이 잠시 로그인을 막았어요. 1시간쯤 뒤에 다시 해 주세요.")
        raise SystemExit(f"[가민 로그인 실패] {t}")
    print("가민 로그인 성공. 다음부터는 비밀번호 없이 실행돼요.")
    return api


def retry(fn, *args, tries=3):
    for i in range(1, tries + 1):
        try:
            return fn(*args)
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                print(f"  가민 요청이 많아 {60 * i}초 기다려요...")
                time.sleep(60 * i)
            elif i == tries:
                raise
            else:
                time.sleep(5)
    return None


def fetch(api, start: date, end: date) -> tuple[int, int]:
    raw = DATA / "raw"
    n_days = (end - start).days + 1
    for i in range(n_days):
        d = (start + timedelta(days=i)).isoformat()
        for name, fn in DAILY.items():
            try:
                v = retry(fn, api, d)
                p = raw / name / f"{d}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print(f"  [{d}] {name} 실패: {e}")
            time.sleep(DELAY_SEC)
        print(f"  일별 {d} ({i + 1}/{n_days})")

    from garminconnect import Garmin
    acts = retry(api.get_activities_by_date, start.isoformat(), end.isoformat()) or []
    fit_dir = DATA / "fit"
    fit_dir.mkdir(parents=True, exist_ok=True)
    have = {p.stem.rsplit("_", 1)[-1] for p in fit_dir.glob("*.fit")}
    n_fit = 0
    for a in acts:
        if "run" not in ((a.get("activityType") or {}).get("typeKey") or ""):
            continue
        aid = str(a.get("activityId"))
        if aid in have:
            continue
        day = (a.get("startTimeLocal") or "")[:10]
        km = (a.get("distance") or 0) / 1000
        try:
            b = retry(api.download_activity, a["activityId"], Garmin.ActivityDownloadFormat.ORIGINAL)
            try:
                with zipfile.ZipFile(io.BytesIO(b)) as z:
                    names = [x for x in z.namelist() if x.lower().endswith(".fit")] or z.namelist()
                    b = z.read(names[0])
            except zipfile.BadZipFile:
                pass
            (fit_dir / f"{day}_{km:.1f}km_{aid}.fit").write_bytes(b)
            n_fit += 1
            print(f"  달리기 {day} {km:.1f}km")
        except Exception as e:
            print(f"  [{day}] 달리기 받기 실패: {e}")
        time.sleep(DELAY_SEC)
    return n_days, n_fit


# ── 업로드 ─────────────────────────────────────────────
def _sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def plan(log: dict) -> list[list[tuple[str, str]]]:
    fits, jsons = [], []
    for p in sorted((DATA / "fit").glob("*.fit")):
        rel, h = f"fit/{p.name}", _sha1(p)
        if log.get(rel) != h:
            fits.append((rel, h, p.stat().st_size))
    for kind in DAILY:
        for p in sorted((DATA / "raw" / kind).glob("*.json")):
            rel, h = f"raw/{kind}/{p.name}", _sha1(p)
            if log.get(rel) != h:
                jsons.append((rel, h, p.stat().st_size))
    batches, cur, size = [], [], 0
    for f in fits:  # 개수·크기 둘 다 제한
        if cur and (len(cur) >= MAX_FITS_PER_ZIP or size + f[2] > MAX_ZIP_BYTES):
            batches.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += f[2]
    if cur:
        batches.append(cur)
    if jsons:
        batches = batches or [[]]
        batches[0] += jsons
    return [[(r, h) for r, h, _ in b] for b in batches]


def build_zip(batch) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, _ in batch:
            z.write(DATA / rel, rel)
    return buf.getvalue()


def upload(cfg: dict, totals: dict | None = None) -> bool:
    log_p = DATA / ".upload_log.json"
    try:
        log = json.loads(log_p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        log = {}
    batches = plan(log)
    if not batches:
        print("[업로드] 새로 올릴 것이 없어요")
        return True
    ok = True
    for i, batch in enumerate(batches, 1):
        n_fit = sum(1 for r, _ in batch if r.startswith("fit/"))
        r = api_call(cfg, "upload", body=build_zip(batch))
        uid = r["uploadId"]
        print(f"[업로드 {i}/{len(batches)}] 달리기 {n_fit}개, 일별 {len(batch) - n_fit}개 → 서버 처리 중...")
        st = None
        for _ in range(36):  # 최대 3분
            time.sleep(5)
            st = api_call(cfg, "status", extra=f"&id={uid}")
            if st.get("status") in ("done", "error"):
                break
        if st and st.get("status") == "done":
            for rel, h in batch:
                log[rel] = h
            log_p.write_text(json.dumps(log, indent=0, sort_keys=True), encoding="utf-8")
            print(f"  완료: 새 달리기 {st['added']}개, 중복 {st['duplicates']}개, 일별 {st['wellnessDays']}일, 실패 {st['failed']}개")
            if totals is not None:
                for k in ("added", "wellnessDays"):
                    totals[k] = totals.get(k, 0) + (st.get(k) or 0)
        elif st and st.get("status") == "error":
            ok = False
            print(f"  서버 처리 실패: {st.get('error')} (다음 실행 때 다시 올려요)")
        else:
            print("  서버 처리 확인이 늦어요. 앱에서 확인해 주세요 (다음 실행 때 다시 확인)")
    return ok


# ── 공통 동작 (명령 창·트레이 앱이 같이 씀) ──────────────
def verify_key(key: str) -> str:
    """키를 확인하고 저장. 계정 이름을 돌려줌"""
    key = key.strip()
    if not key.startswith("fl_"):
        raise BadKey("키는 fl_ 로 시작해요. 앱에서 복사한 그대로 붙여 넣어 주세요.")
    cfg = load_config()
    cfg.update(syncKey=key, endpoint=cfg.get("endpoint") or DEFAULT_ENDPOINT)
    who = api_call(cfg, "whoami")
    save_config(cfg)
    return who.get("name") or "내 계정"


def is_configured() -> bool:
    return bool(load_config().get("syncKey")) and TOKENS.exists()


def last_success() -> str | None:
    return _state().get("lastSuccess")


def run_sync(days: int | None = None, auto: bool = False, interactive: bool = False) -> dict:
    """받고 올리기. 결과: {"skipped", "days", "fits", "added", "wellnessDays"}. 실패하면 SystemExit 계열"""
    cfg = load_config()
    if not cfg.get("syncKey"):
        raise BadKey("[설정 필요] 동기화 키를 먼저 등록해 주세요.")
    DATA.mkdir(parents=True, exist_ok=True)
    today = date.today()
    st = _state()
    st["lastAttempt"] = datetime.now().isoformat(timespec="seconds")
    _save_state(st)
    if auto and st.get("lastSuccess") == today.isoformat():
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] 오늘은 이미 올렸어요. 건너뜁니다.")
        return {"skipped": True}
    if days:
        start = today - timedelta(days=days - 1)
    elif st.get("lastSuccess"):
        start = date.fromisoformat(st["lastSuccess"]) - timedelta(days=OVERLAP_DAYS)
    else:
        start = today - timedelta(days=FIRST_RUN_DAYS - 1)
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 가민에서 {start} ~ {today} 받는 중...")
    api = garmin_login(interactive=interactive)
    n_days, n_fit = fetch(api, start, today)
    print(f"받기 끝: 일별 {n_days}일, 새 달리기 {n_fit}개")
    totals: dict = {}
    if not upload(cfg, totals):
        raise SystemExit("[업로드 일부 실패] 다음 실행 때 다시 올려요.")
    st = _state()
    st["lastSuccess"] = today.isoformat()
    st["lastResult"] = {"at": datetime.now().isoformat(timespec="seconds"), "fits": n_fit, **totals}
    _save_state(st)
    print("\n[완료] 앱에서 활동 탭과 오늘 탭을 새로고침하세요.")
    return {"skipped": False, "days": n_days, "fits": n_fit, **totals}


# ── 명령 ───────────────────────────────────────────────
def cmd_setup(args) -> None:
    print(f"Fokus Laufen PC 동기화 {VERSION} — 처음 설정\n")
    print("1) 앱 → 내 정보 → PC 동기화 → '키 만들기' 에서 나온 키를 붙여 넣으세요 (fl_ 로 시작).")
    name = verify_key(input("   동기화 키: "))
    print(f"   확인됨: {name}\n")
    print("2) 가민 Connect 로그인 (이 PC 에만 로그인 토큰이 저장돼요)")
    garmin_login(interactive=True)
    print("\n설정 끝. 이제 sync_today.bat 을 실행하면 받고 올려요.")


def cmd_run(args) -> None:
    try:
        run_sync(days=args.days, auto=args.auto, interactive=not args.auto)
    except NeedLogin as e:
        raise SystemExit(f"{e} (setup.bat 을 다시 실행)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fokus Laufen PC 동기화")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    r = sub.add_parser("run")
    r.add_argument("--auto", action="store_true", help="오늘 이미 성공했으면 건너뜀 (자동 실행용)")
    r.add_argument("--days", type=int, help="최근 며칠을 받을지 (기본: 첫 실행 90일, 이후 지난 성공 이후)")
    a = ap.parse_args()
    {"setup": cmd_setup, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
