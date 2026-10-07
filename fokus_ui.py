"""Fokus Laufen PC 동기화 — 설정·상태 창 (tkinter, 파이썬 기본 포함이라 추가 설치 없음)"""

from __future__ import annotations

import queue
import re
import shutil
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import fokus_app as fa
import fokus_sync as fs

WHITE = "#ffffff"
INK = "#1d2730"
MUTED = "#5f6b76"
LINE = "#e3e8ec"
SOFT = "#f3f8fb"
OK = "#1f9d55"
WARN = "#c2410c"
FAMILY = "Malgun Gothic" if fa.IS_WIN else "TkDefaultFont"


def F(size: int = 10, bold: bool = False):
    return (FAMILY, size, "bold") if bold else (FAMILY, size)


def nice_day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    if d == date.today():
        return "오늘"
    if (date.today() - d).days == 1:
        return "어제"
    return f"{d.month}월 {d.day}일"


class MainWindow(tk.Tk):
    def __init__(self, server=None):
        super().__init__()
        self.q: queue.Queue = queue.Queue()
        self.syncing = False
        self.hide_after_sync = False
        self.phase = ""
        self.view = ""
        self.refs: dict = {}
        sys.stdout = sys.stderr = fa.LogSink(on_line=lambda line: self.q.put(("log", line)))
        fa.trim_log()

        self.title("Fokus Laufen PC 동기화")
        scale = self.winfo_fpixels("1i") / 96
        self.geometry(f"{int(560 * scale)}x{int(640 * scale)}")
        self.minsize(int(480 * scale), int(520 * scale))
        self.configure(bg=WHITE)
        self._set_icon()
        self._style()
        self._header()
        self.body = tk.Frame(self, bg=WHITE)
        self.body.pack(fill="both", expand=True, padx=24, pady=(16, 16))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if server is not None:
            threading.Thread(target=self._serve, args=(server,), daemon=True).start()
        self.after(100, self._pump)
        self.after(20_000, self._tick)
        self.start_view()

    # ── 공통 ──────────────────────────────────────────
    def _set_icon(self):
        try:
            if fa.IS_WIN:
                self.iconbitmap(default=str(fa.RES / "icon.ico"))
            else:
                self.iconphoto(True, tk.PhotoImage(file=str(fa.RES / "icon-256.png")))
        except tk.TclError:
            pass

    def _style(self):
        s = ttk.Style(self)
        if "vista" in s.theme_names():
            s.theme_use("vista")
        elif "clam" in s.theme_names():
            s.theme_use("clam")
        for w in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
            s.configure(w, background=WHITE, foreground=INK, font=F())
        s.configure("TButton", font=F(), padding=(10, 4))
        s.configure("TEntry", padding=4)
        s.configure("Brand.Horizontal.TProgressbar", troughcolor=SOFT, background=fa.BRAND)
        self.option_add("*Font", F())

    def _header(self):
        h = tk.Frame(self, bg=fa.BRAND)
        h.pack(fill="x")
        try:
            self._logo = tk.PhotoImage(file=str(fa.RES / "icon-48.png"))
            tk.Label(h, image=self._logo, bg=fa.BRAND).pack(side="left", padx=(20, 10), pady=12)
        except tk.TclError:
            pass
        t = tk.Frame(h, bg=fa.BRAND)
        t.pack(side="left", pady=12)
        tk.Label(t, text="Fokus Laufen", font=F(15, True), fg=WHITE, bg=fa.BRAND).pack(anchor="w")
        tk.Label(t, text="가민 기록을 앱으로 자동으로 보내는 PC 프로그램", font=F(9), fg="#e6f6fd", bg=fa.BRAND).pack(anchor="w")
        tk.Label(h, text=f"v{fs.VERSION}", font=F(9), fg="#cdeefc", bg=fa.BRAND).pack(side="right", padx=16)

    def clear(self, view: str):
        for w in self.body.winfo_children():
            w.destroy()
        self.refs = {}
        self.view = view

    def label(self, parent, text, size=10, bold=False, color=INK, wrap=True, **pack):
        lb = tk.Label(parent, text=text, font=F(size, bold), fg=color, bg=parent["bg"], justify="left", anchor="w")
        if wrap:
            lb.bind("<Configure>", lambda e: lb.configure(wraplength=max(e.width - 4, 100)))
        lb.pack(fill="x", **pack)
        return lb

    def link(self, parent, text, cmd, **pack):
        lb = tk.Label(parent, text=text, font=(FAMILY, 9, "underline"), fg=fa.BRAND_DARK, bg=parent["bg"], cursor="hand2")
        lb.bind("<Button-1>", lambda e: cmd())
        lb.pack(anchor="w", **pack)
        return lb

    def primary(self, parent, text, cmd):
        b = tk.Button(parent, text=text, command=cmd, font=F(10, True), bg=fa.BRAND, fg=WHITE,
                      activebackground=fa.BRAND_DARK, activeforeground=WHITE, disabledforeground="#eaf7fe",
                      relief="flat", bd=0, padx=18, pady=7, cursor="hand2")
        return b

    @staticmethod
    def enable(btn: tk.Button, on: bool):
        btn.configure(state="normal" if on else "disabled", bg=fa.BRAND if on else "#9fd6f3")

    def qr(self, parent, data: str, px: int = 4, bg=WHITE):
        """QR 코드를 캔버스에 그림 (segno: 순수 파이썬, 그림 라이브러리 필요 없음)"""
        import segno
        m = [list(r) for r in segno.make(data, error="m").matrix]
        n, border = len(m), 3
        scale = self.winfo_fpixels("1i") / 96
        px = max(2, round(px * scale))
        size = (n + border * 2) * px
        cv = tk.Canvas(parent, width=size, height=size, bg=WHITE, highlightthickness=0)
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    x0, y0 = (x + border) * px, (y + border) * px
                    cv.create_rectangle(x0, y0, x0 + px, y0 + px, fill="#000000", width=0)
        return cv

    def steps(self, current: int):
        row = tk.Frame(self.body, bg=WHITE)
        row.pack(fill="x", pady=(0, 14))
        for i, name in enumerate(("동기화 키", "가민 로그인", "시작"), 1):
            on = i == current
            done = i < current
            c = fa.BRAND if (on or done) else "#b7c2cb"
            tk.Label(row, text=("✓" if done else str(i)), font=F(9, True), fg=WHITE, bg=c, width=2).pack(side="left")
            tk.Label(row, text=name, font=F(9, on), fg=INK if on else MUTED, bg=WHITE).pack(side="left", padx=(5, 14))

    def card(self, parent=None, bg=SOFT):
        c = tk.Frame(parent or self.body, bg=bg, highlightthickness=1, highlightbackground=LINE)
        c.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(c, bg=bg)
        inner.pack(fill="x", padx=16, pady=14)
        return inner

    # ── 스레드 ↔ 화면 ──────────────────────────────────
    def ui(self, fn):
        self.q.put(("call", fn))

    def bg(self, work, done):
        def run():
            try:
                r = work()
            except BaseException as e:  # SystemExit 계열 포함
                r = e
            self.ui(lambda: done(r))
        threading.Thread(target=run, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, v = self.q.get_nowait()
                if kind == "call":
                    v()
                elif kind == "log":
                    self.on_log(v)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _serve(self, srv):
        while True:
            try:
                c, _ = srv.accept()
                with c:
                    if c.recv(16) == b"show":
                        self.ui(self.bring_front)
            except OSError:
                return

    def bring_front(self):
        self.hide_after_sync = False
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _tick(self):
        if self.view == "home" and not self.syncing and self.state() != "withdrawn":
            self.refresh_status()  # 자동 실행(--auto)이 그사이 올렸을 수 있음
        self.after(20_000, self._tick)

    def ask_mfa(self) -> str:
        box, ev = {}, threading.Event()

        def ask():
            box["v"] = simpledialog.askstring(
                "가민 2단계 인증", "가민이 이메일(또는 문자)로 보낸 인증 코드를 입력하세요:", parent=self) or ""
            ev.set()
        self.ui(ask)
        ev.wait()
        return box["v"].strip()

    def on_close(self):
        if self.syncing:
            if not messagebox.askokcancel(
                    "동기화 중", "창을 닫아도 동기화는 끝까지 계속돼요.\n끝나면 Windows 알림으로 알려드릴게요.", parent=self):
                return
            self.hide_after_sync = True
            self.withdraw()
            return
        self.destroy()

    # ── 처음 화면 고르기 ──────────────────────────────
    def start_view(self):
        cfg = fs.load_config()
        if not cfg.get("syncKey"):
            self.show_key()
        elif not fs.TOKENS.exists():
            self.show_login()
        else:
            self.show_home()
            # 예전 setup.bat 이 만든 작업(검은 창)이 남아 있으면 새 방식으로 바꿔 둠
            if fa.task_exists() and not fa.task_is_ours():
                fa.register_task()

    # ── 1. 동기화 키 ──────────────────────────────────
    def show_key(self, cancel: bool = False):
        self.clear("key")
        if not cancel:
            self.steps(1)
        self.label(self.body, "휴대폰 앱에서 동기화 키를 가져오세요", 13, True, pady=(0, 8))
        c = self.card()
        row0 = tk.Frame(c, bg=SOFT)
        row0.pack(fill="x")
        try:
            qbox = tk.Frame(row0, bg=SOFT)
            qbox.pack(side="right", padx=(12, 0))
            self.qr(qbox, fa.PC_SYNC_URL).pack()
            tk.Label(qbox, text="휴대폰 카메라로 찍기", font=F(8), fg=MUTED, bg=SOFT).pack(pady=(3, 0))
        except Exception:  # QR 을 못 그려도 글 안내는 그대로
            pass
        texts = tk.Frame(row0, bg=SOFT)
        texts.pack(side="left", fill="both", expand=True)
        for i, t in enumerate((
                "휴대폰 카메라로 오른쪽 QR 코드를 찍으면 Fokus Laufen 앱의 'PC 동기화' 화면이 열려요 "
                "(또는 앱 → 내 정보 → PC 동기화)",
                "'키 만들기' → 'PC로 보내기'로 카카오톡 '나와의 채팅'이나 메일에 보내기",
                "PC에서 그 키를 복사해 아래 칸에 붙여 넣기 (fl_ 로 시작해요)"), 1):
            self.label(texts, f"{i}.  {t}", 10, pady=3)

        row = tk.Frame(self.body, bg=WHITE)
        row.pack(fill="x", pady=(4, 4))
        var = tk.StringVar()
        ent = ttk.Entry(row, textvariable=var, font=F(11))
        ent.pack(side="left", fill="x", expand=True, ipady=3)

        def paste():
            try:
                var.set(self.clipboard_get().strip())
            except tk.TclError:
                pass
        ttk.Button(row, text="붙여넣기", command=paste).pack(side="left", padx=(8, 0))
        msg = self.label(self.body, "", 9, color=MUTED, pady=(2, 10))

        btns = tk.Frame(self.body, bg=WHITE)
        btns.pack(fill="x")
        nxt = self.primary(btns, "다음", lambda: go())
        nxt.pack(side="right")
        if cancel:
            ttk.Button(btns, text="취소", command=self.show_home).pack(side="right", padx=8)

        def go():
            key = var.get().strip()
            if not key:
                msg.configure(text="키를 붙여 넣어 주세요.", fg=WARN)
                return
            self.enable(nxt, False)
            msg.configure(text="키 확인 중…", fg=MUTED)

            def done(r):
                self.enable(nxt, True)
                if isinstance(r, BaseException):
                    msg.configure(text=str(r) or "키를 확인하지 못했어요.", fg=WARN)
                    return
                msg.configure(text=f"확인됐어요: {r}", fg=OK)
                if cancel and fs.TOKENS.exists():
                    self.after(600, self.show_home)
                else:
                    self.after(600, lambda: self.show_login())
            self.bg(lambda: fs.verify_key(key), done)

        ent.bind("<Return>", lambda e: go())
        ent.focus_set()

        if not cancel:
            tk.Frame(self.body, bg=WHITE, height=16).pack()
            self.link(self.body, "아직 앱을 안 쓰나요? fokus-laufen.web.app 열기", lambda: webbrowser.open(fa.APP_URL))
            self.link(self.body, "예전 버전(setup.bat)을 쓰고 있었다면: 그 폴더에서 설정 가져오기", self.import_legacy, pady=(6, 0))

    def import_legacy(self):
        d = filedialog.askdirectory(parent=self, title="예전 pc-sync 폴더 선택 (setup.bat 이 있는 폴더)")
        if not d:
            return
        src = Path(d)
        if not (src / "config.json").exists():
            messagebox.showwarning("가져오기", "이 폴더에 config.json 이 없어요.\nsetup.bat 이 들어 있는 폴더를 골라 주세요.", parent=self)
            return
        if src.resolve() == fs.HERE.resolve():
            messagebox.showinfo("가져오기", "이미 이 폴더를 쓰고 있어요.", parent=self)
            return
        try:
            fs.HERE.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / "config.json", fs.CONFIG)
            for name in (".garmin_tokens", "data"):
                if (src / name).is_dir():
                    shutil.copytree(src / name, fs.HERE / name, dirs_exist_ok=True)
            (fs.DATA / ".sync.lock").unlink(missing_ok=True)
        except OSError as e:
            messagebox.showerror("가져오기", f"복사하지 못했어요: {e}", parent=self)
            return
        messagebox.showinfo("가져오기", "동기화 키와 가민 로그인, 받은 기록을 가져왔어요.\n예전 폴더는 이제 지워도 돼요.", parent=self)
        self.show_start() if fs.TOKENS.exists() else self.show_login()

    # ── 2. 가민 로그인 ────────────────────────────────
    def show_login(self, cancel: bool = False):
        self.clear("login")
        if not cancel:
            self.steps(2)
        self.label(self.body, "가민 Connect 에 로그인하세요", 13, True, pady=(0, 4))
        self.label(self.body, "가민 시계 앱(Garmin Connect)에 쓰는 이메일과 비밀번호예요.", 10, color=MUTED, pady=(0, 12))

        form = tk.Frame(self.body, bg=WHITE)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        email, pw = tk.StringVar(), tk.StringVar()
        tk.Label(form, text="이메일", font=F(), bg=WHITE, fg=INK).grid(row=0, column=0, sticky="w", pady=5)
        e1 = ttk.Entry(form, textvariable=email, font=F(11))
        e1.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=5, ipady=3)
        tk.Label(form, text="비밀번호", font=F(), bg=WHITE, fg=INK).grid(row=1, column=0, sticky="w", pady=5)
        e2 = ttk.Entry(form, textvariable=pw, font=F(11), show="•")
        e2.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=5, ipady=3)

        c = self.card(bg=WHITE)
        self.label(c, "🔒  비밀번호는 이 PC에서 가민에 로그인할 때 한 번만 쓰고, 어디에도 저장하거나 보내지 않아요. "
                      "로그인 상태(토큰)만 이 PC에 남아서 다음부터는 묻지 않아요.", 9, color=MUTED)

        msg = self.label(self.body, "", 9, color=MUTED, pady=(0, 10))
        btns = tk.Frame(self.body, bg=WHITE)
        btns.pack(fill="x")
        go_btn = self.primary(btns, "로그인", lambda: go())
        go_btn.pack(side="right")
        if cancel:
            ttk.Button(btns, text="취소", command=self.show_home).pack(side="right", padx=8)
        else:
            ttk.Button(btns, text="이전", command=self.show_key).pack(side="right", padx=8)

        def go():
            if not email.get().strip() or not pw.get():
                msg.configure(text="이메일과 비밀번호를 넣어 주세요.", fg=WARN)
                return
            self.enable(go_btn, False)
            msg.configure(text="가민에 로그인하는 중… (최대 1분)", fg=MUTED)
            em, p = email.get().strip(), pw.get()
            pw.set("")

            def done(r):
                self.enable(go_btn, True)
                if isinstance(r, BaseException):
                    msg.configure(text=str(r) or "로그인하지 못했어요.", fg=WARN)
                    e2.focus_set()
                    return
                fa._set_error(None)
                if cancel:
                    self.show_home()
                    self.start_sync()
                else:
                    self.show_start()
            self.bg(lambda: fs.garmin_login_with(em, p, self.ask_mfa), done)

        e1.bind("<Return>", lambda e: e2.focus_set())
        e2.bind("<Return>", lambda e: go())
        e1.focus_set()

    # ── 3. 시작 ───────────────────────────────────────
    def show_start(self):
        self.clear("start")
        self.steps(3)
        first = not fs.last_success()
        self.label(self.body, "준비됐어요!", 13, True, pady=(0, 10))

        auto = tk.BooleanVar(value=True)
        note = tk.BooleanVar(value=fs.load_config().get("notifySuccess", True))
        c = self.card()
        ttk.Checkbutton(c, text="자동으로 받기 (권장)", variable=auto, style="Soft.TCheckbutton").pack(anchor="w")
        self.label(c, "PC에 로그인하고 3분 뒤, 그리고 매일 오전 9시(꺼져 있었으면 켜진 뒤)에 하루 한 번 받아요. "
                      "창은 뜨지 않고, 끝나면 화면 오른쪽 아래에 알림만 떠요.", 9, color=MUTED, padx=(24, 0), pady=(0, 8))
        ttk.Checkbutton(c, text="다 올리면 알림 보기", variable=note, style="Soft.TCheckbutton").pack(anchor="w")
        ttk.Style(self).configure("Soft.TCheckbutton", background=SOFT)
        ttk.Style(self).configure("Soft.TRadiobutton", background=SOFT)

        days = tk.IntVar(value=fs.FIRST_RUN_DAYS)
        if first:
            self.label(self.body, "처음에 받을 기간", 10, True, pady=(4, 4))
            c2 = self.card()
            ttk.Radiobutton(c2, text=f"최근 {fs.FIRST_RUN_DAYS}일 — 10~20분 (권장)", variable=days,
                            value=fs.FIRST_RUN_DAYS, style="Soft.TRadiobutton").pack(anchor="w")
            ttk.Radiobutton(c2, text="최근 1년 — 40분~1시간", variable=days, value=365,
                            style="Soft.TRadiobutton").pack(anchor="w", pady=(4, 0))
        self.label(self.body, "첫 동기화 중에는 창을 닫아도 계속 받아요.", 9, color=MUTED, pady=(0, 10))

        btns = tk.Frame(self.body, bg=WHITE)
        btns.pack(fill="x")

        def go():
            cfg = fs.load_config()
            cfg["notifySuccess"] = bool(note.get())
            fs.save_config(cfg)
            if auto.get():
                err = fa.register_task()
                if err:
                    messagebox.showwarning("자동 실행", f"자동 실행을 등록하지 못했어요:\n{err}\n\n"
                                           "이 창의 '지금 동기화'로는 계속 받을 수 있어요.", parent=self)
            else:
                fa.unregister_task()
            self.show_home()
            self.start_sync(days=days.get() if first else None)
        self.primary(btns, "첫 동기화 시작" if first else "완료하고 지금 동기화", go).pack(side="right")

    # ── 홈 ────────────────────────────────────────────
    def show_home(self):
        self.clear("home")
        c = self.card()
        top = tk.Frame(c, bg=SOFT)
        top.pack(fill="x")
        dot = tk.Label(top, text="●", font=F(14), bg=SOFT, fg=MUTED)
        dot.pack(side="left", padx=(0, 8))
        title = tk.Label(top, text="", font=F(12, True), bg=SOFT, fg=INK, anchor="w", justify="left")
        title.pack(side="left", fill="x", expand=True)
        sub = self.label(c, "", 9, color=MUTED, pady=(4, 0))
        prog = ttk.Progressbar(c, style="Brand.Horizontal.TProgressbar", mode="indeterminate")
        btns = tk.Frame(c, bg=SOFT)
        btns.pack(fill="x", pady=(12, 0))
        main_btn = self.primary(btns, "지금 동기화", lambda: self.start_sync())
        main_btn.pack(side="left")
        ttk.Button(btns, text="앱 열기", command=lambda: webbrowser.open(fa.APP_URL)).pack(side="left", padx=8)
        self.refs.update(dot=dot, title=title, sub=sub, prog=prog, main_btn=main_btn, card=c, btns=btns)

        # 자동 실행
        self.label(self.body, "자동 실행", 10, True, pady=(4, 4))
        auto = tk.BooleanVar(value=fa.task_exists())
        note = tk.BooleanVar(value=fs.load_config().get("notifySuccess", True))

        def toggle_auto():
            if auto.get():
                err = fa.register_task()
                if err:
                    auto.set(False)
                    messagebox.showwarning("자동 실행", f"등록하지 못했어요:\n{err}", parent=self)
            else:
                fa.unregister_task()

        def toggle_note():
            cfg = fs.load_config()
            cfg["notifySuccess"] = bool(note.get())
            fs.save_config(cfg)
        ttk.Checkbutton(self.body, text="자동으로 받기 — PC 로그인 3분 뒤 · 매일 오전 9시, 하루 한 번 (창 없이)",
                        variable=auto, command=toggle_auto).pack(anchor="w")
        ttk.Checkbutton(self.body, text="다 올리면 Windows 알림 보기 (실패 알림은 항상 떠요)",
                        variable=note, command=toggle_note).pack(anchor="w", pady=(2, 10))

        # 더 하기
        self.label(self.body, "더 하기", 10, True, pady=(4, 4))
        more = tk.Frame(self.body, bg=WHITE)
        more.pack(fill="x")
        for i, (t, cmd) in enumerate((
                ("예전 기록 더 받기…", self.ask_more_days),
                ("가민 다시 로그인", lambda: self.show_login(cancel=True)),
                ("동기화 키 바꾸기", lambda: self.show_key(cancel=True)),
                ("기록 파일 보기", lambda: fa.open_path(fa.LOG) if fa.LOG.exists() else None))):
            b = ttk.Button(more, text=t, command=cmd)
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 6, 0), pady=3)
            self.refs.setdefault("more", []).append(b)
        more.columnconfigure(0, weight=1)
        more.columnconfigure(1, weight=1)

        # 자세한 기록
        self.label(self.body, "진행 기록", 10, True, pady=(14, 4))
        box = tk.Frame(self.body, bg=WHITE, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill="both", expand=True)
        txt = tk.Text(box, height=6, font=("Consolas" if fa.IS_WIN else "TkFixedFont", 9), bg=WHITE, fg=MUTED,
                      relief="flat", wrap="word", padx=8, pady=6)
        sb = ttk.Scrollbar(box, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        try:
            tail = fa.LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            txt.insert("end", "\n".join(tail) + ("\n" if tail else ""))
        except OSError:
            pass
        txt.see("end")
        txt.configure(state="disabled")
        self.refs["log"] = txt

        foot = tk.Frame(self.body, bg=WHITE)
        foot.pack(fill="x", pady=(10, 0))
        tk.Label(foot, text="가민 비밀번호는 저장하지 않아요.", font=F(8), fg=MUTED, bg=WHITE).pack(side="left")
        self.link(foot, "데이터 폴더 열기", lambda: fa.open_path(fs.HERE)).pack(side="right")
        self.refresh_status()

    def refresh_status(self):
        r = self.refs
        if self.view != "home" or "title" not in r:
            return
        st = fs._state()
        err = st.get("lastError")
        last = st.get("lastSuccess")
        res = st.get("lastResult") or {}
        btn = r["main_btn"]
        for b in r.get("more", []):
            b.state(["disabled"] if self.syncing else ["!disabled"])
        btn.configure(command=lambda: self.start_sync(), text="지금 동기화")
        if self.syncing:
            r["dot"].configure(fg=fa.BRAND)
            r["title"].configure(text=self.phase)
            r["sub"].configure(text="창을 닫아도 끝까지 받아요. 처음엔 10~20분 걸릴 수 있어요.")
            r["prog"].pack(fill="x", pady=(10, 0), before=r["btns"])
            self.enable(btn, False)
            return
        r["prog"].stop()
        r["prog"].pack_forget()
        self.enable(btn, True)
        if err and (not last or err["at"][:10] >= last):
            r["dot"].configure(fg=WARN)
            if err["kind"] == "login":
                r["title"].configure(text="가민에 다시 로그인해 주세요")
                btn.configure(text="가민 다시 로그인", command=lambda: self.show_login(cancel=True))
            elif err["kind"] == "key":
                r["title"].configure(text="동기화 키를 다시 등록해 주세요")
                btn.configure(text="동기화 키 바꾸기", command=lambda: self.show_key(cancel=True))
            else:
                r["title"].configure(text="지난번 동기화가 실패했어요")
            msg = re.sub(r"^\[[^\]]*\]\s*", "", err["msg"])
            r["sub"].configure(text=f"{nice_day(err['at'])} {err['at'][11:16]} · {msg}")
        elif last:
            today = last == date.today().isoformat()
            r["dot"].configure(fg=OK if today else MUTED)
            at = res.get("at") if (res.get("at") or "")[:10] == last else None
            when = f"{nice_day(last)} {at[11:16]}에" if at else f"{nice_day(last)}"
            r["title"].configure(text=f"{when} 올렸어요" if today or at else f"마지막으로 {when} 올렸어요")
            detail = summary_line(res) if at else ""
            nxt = "" if today else " · 다음 자동 실행 때 받아요"
            r["sub"].configure(text=(detail + nxt).strip(" ·") or "앱에서 활동 탭과 오늘 탭을 확인하세요.")
        else:
            r["dot"].configure(fg=MUTED)
            r["title"].configure(text="아직 한 번도 올리지 않았어요")
            r["sub"].configure(text="'지금 동기화'를 누르면 시작해요.")

    def on_log(self, line: str):
        t = self.refs.get("log")
        if t is not None and t.winfo_exists():
            t.configure(state="normal")
            t.insert("end", line + "\n")
            if int(t.index("end-1c").split(".")[0]) > 400:
                t.delete("1.0", "100.0")
            t.see("end")
            t.configure(state="disabled")
        if not self.syncing:
            return
        p = self.refs.get("prog")
        m = re.search(r"일별 \S+ \((\d+)/(\d+)\)", line)
        if m and p is not None:
            i, n = int(m.group(1)), int(m.group(2))
            p.stop()
            p.configure(mode="determinate", maximum=n, value=i)
            self.phase = f"가민에서 받는 중… {i}/{n}일"
        elif line.strip().startswith("달리기 "):
            self.phase = "달리기 원본 받는 중…"
        elif line.startswith("[업로드"):
            self.phase = "앱에 올리는 중…"
            if p is not None:
                p.configure(mode="indeterminate")
                p.start(12)
        elif "가민 요청이 많아" in line:
            self.phase = "가민이 잠시 쉬래요. 기다리는 중…"
        else:
            return
        if "title" in self.refs:
            self.refs["title"].configure(text=self.phase)

    def ask_more_days(self):
        top = tk.Toplevel(self, bg=WHITE)
        top.title("예전 기록 더 받기")
        top.transient(self)
        top.resizable(False, False)
        f = tk.Frame(top, bg=WHITE)
        f.pack(padx=20, pady=16)
        self.label(f, "얼마나 예전까지 받을까요?", 11, True, wrap=False, pady=(0, 8))
        v = tk.IntVar(value=365)
        for d, t in ((180, "최근 6개월 — 20~30분"), (365, "최근 1년 — 40분~1시간"), (730, "최근 2년 — 1~2시간")):
            ttk.Radiobutton(f, text=t, variable=v, value=d).pack(anchor="w", pady=2)
        self.label(f, "이미 올린 기록은 자동으로 건너뛰어요.", 9, color=MUTED, wrap=False, pady=(8, 10))
        b = tk.Frame(f, bg=WHITE)
        b.pack(fill="x")

        def ok():
            top.destroy()
            self.start_sync(days=v.get())
        self.primary(b, "받기", ok).pack(side="right")
        ttk.Button(b, text="취소", command=top.destroy).pack(side="right", padx=8)
        top.grab_set()

    # ── 동기화 ────────────────────────────────────────
    def start_sync(self, days: int | None = None):
        if self.syncing:
            return
        self.syncing = True
        self.phase = "가민에 연결하는 중…"
        if self.view != "home":
            self.show_home()
        self.refresh_status()
        p = self.refs.get("prog")
        if p is not None:
            p.configure(mode="indeterminate")
            p.start(12)
        self.bg(lambda: fa.run_and_record(days=days), self.sync_done)

    def sync_done(self, r):
        self.syncing = False
        kind, res = r if isinstance(r, tuple) else ("fail", str(r))
        hidden = self.hide_after_sync
        if kind == "busy":
            messagebox.showinfo("동기화", "자동 실행이 지금 받고 있어요. 잠시 뒤에 다시 확인해 주세요.", parent=self)
        if hidden:
            if kind == "ok":
                fa.notify("가민 기록을 앱에 올렸어요", fa.summary(res) + " — 앱에서 새로고침하세요")
            elif kind in ("login", "key", "fail"):
                fa.notify("가민 동기화를 못 했어요", str(res))
            self.destroy()
            return
        self.refresh_status()


def summary_line(res: dict) -> str:
    if not res:
        return ""
    return fa.summary(res) + " · 앱에서 새로고침하면 보여요"
