"""
main.py  —  Ytmax
Redesigned modern dark GUI for high-quality YouTube downloads.
"""
from __future__ import annotations

import io
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Optional
from urllib.request import urlopen, Request

import customtkinter as ctk
from PIL import Image, ImageDraw

import downloader as dl

# ── Design Tokens ──────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT      = "#bef0ee"     # light mint teal
ACCENT_H    = "#a4d8d5"     # mint hover
ACCENT_TXT  = "#1a2d38"     # dark text for use ON accent buttons
BG_BASE     = "#111d25"     # deepest window bg
BG_LAYER    = "#2c4151"     # topbar / statusbar
BG_CARD     = "#1a2f3d"     # card surfaces
BG_INPUT    = "#243646"     # input fields
BORDER      = "#3b5468"     # borders / dividers
TEXT_PRI    = "#e4f2f1"     # primary text
TEXT_SEC    = "#7fa8b8"     # secondary text
TEXT_DIM    = "#4e7080"     # muted / labels
SUCCESS     = "#34D399"
ERROR       = "#F87171"

FONT_BRAND  = ("Segoe UI", 18, "bold")
FONT_TITLE  = ("Segoe UI", 14, "bold")
FONT_BODY   = ("Segoe UI", 11)
FONT_BTN    = ("Segoe UI", 11, "bold")
FONT_SMALL  = ("Segoe UI", 10)
FONT_TINY   = ("Segoe UI", 9)

THUMB_W, THUMB_H = 300, 169   # 16:9 thumbnail

# Window geometry constants
_W        = 740
_H_INIT   = 215   # search bar only
_H_CARD   = 650   # expanded height for video card
_H_SET    = 230   # settings panel height approx


# ── Image helpers ──────────────────────────────────────────────────────────────

def _mk_placeholder() -> ctk.CTkImage:
    img = Image.new("RGB", (THUMB_W, THUMB_H), "#131e28")
    d   = ImageDraw.Draw(img)
    cx, cy, r = THUMB_W // 2, THUMB_H // 2, 30
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#1f3040")
    d.polygon([(cx - 10, cy - 15), (cx + 18, cy), (cx - 10, cy + 15)], fill=ACCENT)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))


def _load_thumb(url: str) -> Optional[ctk.CTkImage]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=7) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB").resize(
            (THUMB_W, THUMB_H), Image.LANCZOS
        )
        return ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))
    except Exception:
        return None


# ── System checks ──────────────────────────────────────────────────────────────

def _check_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None


def _check_nodejs() -> bool:
    import shutil
    if shutil.which("node"):
        return True
    if os.name == "nt":
        for p in [r"C:\Program Files\nodejs", r"C:\Program Files (x86)\nodejs"]:
            if os.path.exists(os.path.join(p, "node.exe")):
                os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
                return True
    return False


# ── Application ────────────────────────────────────────────────────────────────

class YtmaxApp(ctk.CTk):
    DEFAULT_DL = Path.home() / "Downloads"

    def __init__(self) -> None:
        super().__init__()
        self.title("Ytmax")
        self.configure(fg_color=BG_BASE)
        self.minsize(700, _H_INIT)
        self.resizable(False, False) # Keep it consistent for centering logic

        # App state
        self._output_dir    = self.DEFAULT_DL
        self._info: Optional[dl.VideoInfo] = None
        self._active        = False
        self._thumb_img: Optional[ctk.CTkImage] = None
        self._settings_open = False
        self._card_visible  = False

        # Window icon
        icon_path = Path(__file__).parent / "ytmax.ico"
        png_path  = Path(__file__).parent / "ytmax.png"
        try:
            if os.name == "nt" and icon_path.exists():
                self.iconbitmap(str(icon_path))
            elif png_path.exists():
                img = tk.PhotoImage(file=str(png_path))
                self.wm_iconphoto(True, img)
        except Exception:
            pass

        # Tk variables
        self._url_var      = tk.StringVar()
        self._quality_var  = tk.StringVar(value="best")
        self._audio_var    = tk.BooleanVar(value=False)
        self._folder_var   = tk.StringVar(value=str(self.DEFAULT_DL))
        self._cookies_var  = tk.StringVar(
            value=str(self.DEFAULT_DL / "youtube.txt")
        )
        self._progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._place(_W, _H_INIT)

    # ── Window positioning ─────────────────────────────────────────────────────

    def _place(self, w: int, h: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")

    def _resize(self, h: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(0, (sw - _W) // 2)
        y  = max(0, (sh - h)  // 2)
        self.geometry(f"{_W}x{h}+{x}+{y}")

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_topbar()
        self._build_statusbar()

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self._scroll.pack(side="top", fill="both", expand=True)
        self._scroll._scrollbar.grid_remove()

        self._build_searchbar()
        self._build_card()       # hidden until video fetched
        self._build_settings()   # hidden until gear clicked

    # ── Topbar ─────────────────────────────────────────────────────────────────

    def _build_topbar(self) -> None:
        tb = ctk.CTkFrame(self, fg_color=BG_LAYER, corner_radius=0, height=50)
        tb.pack(side="top", fill="x")
        tb.pack_propagate(False)

        # Brand logo
        logo_path = Path(__file__).parent / "ytmax.png"
        try:
            if not logo_path.exists():
                raise FileNotFoundError
            limg = Image.open(logo_path).convert("RGBA")
            self._logo_img = ctk.CTkImage(
                light_image=limg, dark_image=limg, size=(28, 28)
            )
            ctk.CTkLabel(tb, text="", image=self._logo_img).pack(
                side="left", padx=(16, 8)
            )
        except Exception:
            badge = ctk.CTkFrame(
                tb, width=28, height=28, corner_radius=7, fg_color=BG_BASE
            )
            badge.pack(side="left", padx=(16, 8))
            badge.pack_propagate(False)
            ctk.CTkLabel(
                badge, text="▶", font=("Segoe UI", 11, "bold"), text_color=ACCENT
            ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            tb, text="Ytmax", font=FONT_BRAND, text_color=TEXT_PRI
        ).pack(side="left")

        ctk.CTkLabel(
            tb, text=" ",
            font=("Segoe UI", 10), text_color=TEXT_DIM
        ).pack(side="left")

        # Settings toggle (gear)
        self._settings_btn = ctk.CTkButton(
            tb, text="⚙", width=36, height=36, corner_radius=18,
            font=("Segoe UI", 17), fg_color="transparent",
            hover_color=BG_CARD, text_color=TEXT_DIM,
            command=self._toggle_settings,
        )
        self._settings_btn.pack(side="right", padx=(0, 14))

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        sb = ctk.CTkFrame(self, fg_color=BG_LAYER, corner_radius=0, height=26)
        sb.pack(side="bottom", fill="x")
        sb.pack_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            sb, text="Ready", font=FONT_TINY, text_color=TEXT_DIM
        )
        self._status_lbl.pack(side="left", padx=16)

        for name, ok in [("Node.js", _check_nodejs()), ("FFmpeg", _check_ffmpeg())]:
            color = SUCCESS if ok else ERROR
            ctk.CTkLabel(
                sb, text=f"● {name}", font=FONT_TINY, text_color=color
            ).pack(side="right", padx=(0, 14))

    # ── Search bar ─────────────────────────────────────────────────────────────

    def _build_searchbar(self) -> None:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(14, 10))
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            row, text="📋  Paste", width=90, height=44, corner_radius=22,
            font=FONT_SMALL, fg_color=BG_CARD, hover_color=BG_INPUT,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._on_paste_fetch,
        ).grid(row=0, column=0, padx=(0, 8))

        self._url_entry = ctk.CTkEntry(
            row, textvariable=self._url_var,
            placeholder_text="Paste a YouTube or YouTube Music URL…",
            font=FONT_BODY, height=44, corner_radius=22,
            fg_color=BG_CARD, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        )
        self._url_entry.grid(row=0, column=1, sticky="ew")
        self._url_entry.bind("<Return>", lambda _: self._on_fetch())

        self._fetch_btn = ctk.CTkButton(
            row, text="Fetch  →", width=100, height=44, corner_radius=22,
            font=FONT_BTN, fg_color=ACCENT, hover_color=ACCENT_H,
            text_color=ACCENT_TXT, command=self._on_fetch,
        )
        self._fetch_btn.grid(row=0, column=2, padx=(8, 0))

    # ── Content card (thumbnail LEFT · info RIGHT) ─────────────────────────────

    def _build_card(self) -> None:
        self._card = ctk.CTkFrame(
            self._scroll, fg_color=BG_CARD,
            corner_radius=20, border_width=1, border_color=BORDER,
        )
        # Not packed yet — shown after first successful fetch

        # ── Left column: thumbnail ──
        left = ctk.CTkFrame(self._card, fg_color="transparent")
        left.pack(side="left", padx=(16, 0), pady=16)

        self._thumb_lbl = ctk.CTkLabel(left, text="", image=_mk_placeholder())
        self._thumb_lbl.pack()

        # ── Vertical separator ──
        ctk.CTkFrame(self._card, fg_color=BORDER, width=1).pack(
            side="left", fill="y", padx=16, pady=14
        )

        # ── Right column: metadata + controls ──
        right = ctk.CTkFrame(self._card, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(0, 24), pady=(24, 32))

        # Title
        self._title_lbl = ctk.CTkLabel(
            right, text="—", font=FONT_TITLE, text_color=TEXT_PRI,
            wraplength=300, justify="left", anchor="w",
        )
        self._title_lbl.pack(fill="x")

        # Channel · duration
        self._meta_lbl = ctk.CTkLabel(
            right, text="", font=FONT_SMALL, text_color=TEXT_SEC,
            justify="left", anchor="w",
        )
        self._meta_lbl.pack(fill="x", pady=(4, 0))

        # Max quality badge
        self._badge_lbl = ctk.CTkLabel(
            right, text="", font=("Segoe UI", 9, "bold"),
            text_color=ACCENT, anchor="w",
        )
        self._badge_lbl.pack(fill="x", pady=(3, 14))

        # ── Quality & Audio row ──
        qrow = ctk.CTkFrame(right, fg_color="transparent")
        qrow.pack(fill="x", pady=(0, 14))

        q_grp = ctk.CTkFrame(qrow, fg_color="transparent")
        q_grp.pack(side="left")
        ctk.CTkLabel(
            q_grp, text="QUALITY", font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w")
        self._quality_menu = ctk.CTkOptionMenu(
            q_grp,
            values=["4K", "1440p", "1080p", "720p", "best"],
            variable=self._quality_var,
            font=FONT_SMALL, width=116, height=34, corner_radius=17,
            fg_color=BG_INPUT, button_color=ACCENT, text_color=TEXT_PRI,
        )
        self._quality_menu.pack(anchor="w", pady=(4, 0))

        ctk.CTkFrame(qrow, fg_color="transparent", width=20).pack(side="left")

        a_grp = ctk.CTkFrame(qrow, fg_color="transparent")
        a_grp.pack(side="left")
        ctk.CTkLabel(
            a_grp, text="AUDIO ONLY", font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w")
        ctk.CTkSwitch(
            a_grp, text="", variable=self._audio_var,
            progress_color=ACCENT, width=44, height=22,
        ).pack(anchor="w", pady=(4, 0))

        # ── Download button ──
        self._dl_btn = ctk.CTkButton(
            right, text="⬇   Download", height=46, corner_radius=23,
            font=FONT_BTN, fg_color=ACCENT, hover_color=ACCENT_H,
            text_color=ACCENT_TXT, command=self._on_download,
        )
        self._dl_btn.pack(fill="x", pady=(0, 10))

        # ── Progress ──
        self._progress_bar = ctk.CTkProgressBar(
            right, variable=self._progress_var,
            fg_color=BG_INPUT, progress_color=ACCENT,
            height=5, corner_radius=3,
        )
        self._progress_bar.pack(fill="x", pady=(0, 5))
        self._progress_bar.set(0)

        self._progress_lbl = ctk.CTkLabel(
            right, text="", font=FONT_TINY, text_color=TEXT_DIM, anchor="w"
        )
        self._progress_lbl.pack(fill="x")

    # ── Settings panel (collapsible) ───────────────────────────────────────────

    def _build_settings(self) -> None:
        self._settings_panel = ctk.CTkFrame(
            self._scroll, fg_color=BG_CARD,
            corner_radius=16, border_width=1, border_color=BORDER,
        )
        # Not packed yet

        ctk.CTkLabel(
            self._settings_panel, text="Advanced Settings",
            font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC,
        ).pack(anchor="w", padx=18, pady=(14, 10))

        body = ctk.CTkFrame(self._settings_panel, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)

        # Download folder
        ctk.CTkLabel(
            body, text="DOWNLOAD FOLDER",
            font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        f_row = ctk.CTkFrame(body, fg_color="transparent")
        f_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        f_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            f_row, textvariable=self._folder_var,
            font=FONT_SMALL, height=34, corner_radius=17,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            f_row, text="Browse", width=76, height=34, corner_radius=17,
            font=FONT_SMALL, fg_color=BG_INPUT, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._browse_folder,
        ).grid(row=0, column=1, padx=(8, 0))

        # Cookies file
        ctk.CTkLabel(
            body, text="COOKIES FILE (.TXT)",
            font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))

        ctk.CTkEntry(
            body, textvariable=self._cookies_var,
            font=FONT_SMALL, height=34, corner_radius=17,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        ).grid(row=3, column=0, columnspan=2, sticky="ew")

        ctk.CTkLabel(
            self._settings_panel,
            text=(
                "ℹ  Cookies are optional — only needed for age-restricted or "
                "sign-in protected videos. Export from your browser using the "
                "'Get cookies.txt LOCALLY' extension (Netscape format)."
            ),
            font=FONT_TINY, text_color=TEXT_DIM,
            justify="left", wraplength=600,
        ).pack(anchor="w", padx=18, pady=(8, 14))

    # ── Visibility helpers ─────────────────────────────────────────────────────

    def _show_card(self) -> None:
        if not self._card_visible:
            self._card.pack(fill="x", padx=18, pady=(0, 14))
            self._card_visible = True
            target = _H_CARD + (_H_SET if self._settings_open else 0)
            self.after(50, lambda: self._resize(target))
            self.after(100, lambda: self._scroll._scrollbar.grid())

    def _toggle_settings(self) -> None:
        self._settings_open = not self._settings_open
        if self._settings_open:
            self._settings_panel.pack(fill="x", padx=18, pady=(0, 14))
            self._settings_btn.configure(text_color=ACCENT)
            self._scroll._scrollbar.grid()
            self.after(50, lambda: self._resize(self.winfo_height() + _H_SET))
        else:
            self._settings_panel.pack_forget()
            self._settings_btn.configure(text_color=TEXT_DIM)
            new_h = max(self.winfo_height() - _H_SET, _H_INIT)
            self.after(50, lambda: self._resize(new_h))
            if not self._card_visible:
                self._scroll._scrollbar.grid_remove()

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        d = filedialog.askdirectory(initialdir=self._folder_var.get())
        if d:
            self._folder_var.set(d)

    def _on_paste_fetch(self) -> None:
        try:
            self._url_var.set(self.clipboard_get())
            self._on_fetch()
        except tk.TclError:
            self._set_status("⚠  Clipboard is empty.")

    def _on_fetch(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            self._set_status("⚠  Paste a URL first.")
            return

        self._audio_var.set("music.youtube.com" in url)

        if self._active:
            self._set_status("⚠  A download is already in progress.")
            return

        self._set_status("Fetching info…")
        self._fetch_btn.configure(state="disabled", text="Fetching…")
        cookies = self._cookies_var.get().strip()

        def _worker() -> None:
            try:
                info = dl.fetch_info(url, cookies_file=cookies)
                self.after(0, self._show_info, info)
            except Exception as exc:
                err = str(exc)
                if dl.is_bot_error(err):
                    print("⚠ YouTube bot check triggered.")
                else:
                    print(f"Fetch error: {err}")
                self.after(0, self._set_status, "Fetch failed — check the URL.")
            finally:
                self.after(
                    0,
                    lambda: self._fetch_btn.configure(state="normal", text="Fetch  →"),
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _show_info(self, info: dl.VideoInfo) -> None:
        self._info = info
        self._show_card()

        self._title_lbl.configure(text=info.title[:72])
        self._meta_lbl.configure(
            text=f"{info.uploader}  ·  {dl.fmt_duration(info.duration)}"
        )
        self._badge_lbl.configure(
            text=f"▲ Max quality: {info.best_height}p" if info.best_height else ""
        )
        self._set_status(f"Loaded: {info.title[:55]}")

        # Build quality options from real format list
        if hasattr(info, "formats") and info.formats:
            heights = sorted(
                {
                    f.get("height", 0)
                    for f in info.formats
                    if f.get("vcodec") != "none"
                    and isinstance(f.get("height"), int)
                    and f["height"] > 0
                },
                reverse=True,
            )
            opts: list[str] = []
            for h in heights:
                key = "4K" if h >= 2160 else f"{h}p"
                if key not in opts:
                    opts.append(key)
            if not opts:
                opts = ["best"]
            else:
                opts.append("best")
            self._quality_menu.configure(values=opts)
            if self._quality_var.get() not in opts:
                self._quality_var.set(opts[0])

        # Load thumbnail asynchronously
        def _load() -> None:
            urls: list[str] = []
            if info.thumbnail:
                urls.append(info.thumbnail)
            if hasattr(info, "thumbnails") and info.thumbnails:
                urls.extend(reversed(info.thumbnails))
            for u in urls:
                if not u:
                    continue
                img = _load_thumb(u)
                if img:
                    self._thumb_img = img
                    self.after(0, lambda i=img: self._thumb_lbl.configure(image=i))
                    break

        threading.Thread(target=_load, daemon=True).start()

    def _on_download(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            self._set_status("⚠  No URL entered.")
            return
        if self._active:
            self._set_status("⚠  A download is already in progress.")
            return

        out_str = self._folder_var.get().strip() or str(self.DEFAULT_DL)
        self._output_dir = Path(out_str)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._active = True
        self._dl_btn.configure(text="Downloading…", state="disabled")
        self._progress_var.set(0)
        self._set_status(f"Downloading ({self._quality_var.get()})…")

        task = dl.DownloadTask(
            url          = url,
            output_dir   = self._output_dir,
            quality      = self._quality_var.get(),
            audio_only   = self._audio_var.get(),
            cookies_file = self._cookies_var.get().strip(),
            on_progress  = self._on_progress,
            on_complete  = self._on_complete,
            on_error     = self._on_dl_error,
        )
        dl.download(task)

    def _on_progress(self, pct: float, speed: float, eta: int, fname: str) -> None:
        self.after(0, self._update_progress, pct, speed, eta, fname)

    def _update_progress(self, pct: float, speed: float, eta: int, fname: str) -> None:
        self._progress_var.set(pct / 100)
        speed_s = dl.fmt_size(speed) if speed else ""
        eta_s   = f"  ·  {dl.fmt_time(eta)} left" if eta else ""
        self._progress_lbl.configure(text=f"{pct:.1f}%  {speed_s}{eta_s}")

    def _on_complete(self) -> None:
        self.after(0, self._finish_download, True)

    def _on_dl_error(self, msg: str) -> None:
        self.after(0, self._finish_download, False, msg)

    def _finish_download(self, ok: bool, error: str = "") -> None:
        self._active = False
        self._dl_btn.configure(text="⬇   Download", state="normal")
        if ok:
            self._progress_var.set(1.0)
            self._set_status("✔  Download complete")
            self._progress_lbl.configure(text=f"Saved to: {self._output_dir}")
        else:
            self._progress_var.set(0)
            self._progress_lbl.configure(text="")
            if dl.is_age_error(error):
                self._set_status("⚠  Age-restricted — load a cookies.txt")
            elif dl.is_bot_error(error):
                self._set_status("⚠  Bot check — load a cookies.txt")
            else:
                self._set_status("✖  Download failed")

    def _set_status(self, msg: str) -> None:
        self._status_lbl.configure(text=msg)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = YtmaxApp()
    app.mainloop()