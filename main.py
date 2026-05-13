"""
main.py  —  YTmax
Premium dark GUI for high-quality YouTube & playlist downloads.
Custom icon system  ·  card elevation  ·  smooth animations.
"""
from __future__ import annotations

import io
import math
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Optional
from urllib.request import urlopen, Request

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter

import downloader as dl


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ── Design Tokens ──────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_BASE    = "#060b14"
BG_LAYER   = "#0d1326"
BG_CARD    = "#111936"
BG_INPUT   = "#182045"
BORDER     = "#1e2d5c"
SHADOW     = "#040812"
ACCENT     = "#6366f1"
ACCENT_H   = "#7877f0"
ACCENT_GLOW= "#818cf8"
ACCENT_DIM = "#4c4fd9"
ACCENT_TXT = "#ffffff"
TEXT_PRI   = "#edf0fc"
TEXT_SEC   = "#909cc2"
TEXT_DIM   = "#5a6794"
SUCCESS    = "#34d399"
ERROR      = "#f87171"
WARNING    = "#fbbf24"

FONT_BRAND = ("Segoe UI Semibold", 18)
FONT_TITLE = ("Segoe UI Semibold", 13)
FONT_BODY  = ("Segoe UI", 11)
FONT_BTN   = ("Segoe UI Semibold", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TINY  = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)

THUMB_W, THUMB_H = 280, 158

_W          = 780
_H_INIT     = 240
_H_CARD     = 690
_H_PLAYLIST = 770
_H_SET      = 280


# ── Icon factory ───────────────────────────────────────────────────────────

def _mk_icon(
    draw_fn, size: int = 24, color: str = ACCENT,
) -> ctk.CTkImage:
    """Build a CTkImage from a PIL drawing callback."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_fn(d, size, color)
    return ctk.CTkImage(
        light_image=img, dark_image=img, size=(size, size),
    )


def _draw_play(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.15
    d.polygon(
        [(m + s * 0.21, m), (s - m, s / 2), (m + s * 0.21, s - m)],
        fill=c,
    )


def _draw_download(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.18
    bw = s * 0.28
    # arrow shaft
    d.rectangle([s / 2 - bw / 2, m, s / 2 + bw / 2, s * 0.60], fill=c)
    # arrow head
    d.polygon(
        [(m, s * 0.60), (s / 2, s - m), (s - m, s * 0.60)], fill=c,
    )
    # top bar
    d.rectangle([m * 0.5, m * 0.5, s - m * 0.5, m], fill=c)


def _draw_settings(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    cx, cy = s / 2, s / 2
    r = s * 0.30
    m = s * 0.15
    # outer ring
    d.ellipse([cx - r - m, cy - r - m, cx + r + m, cy + r + m], outline=c, width=max(2, int(s * 0.10)))
    # inner circle
    d.ellipse([cx - r * 0.40, cy - r * 0.40, cx + r * 0.40, cy + r * 0.40], fill=c)
    # teeth
    for a in range(0, 360, 45):
        rad = math.radians(a)
        x1 = cx + math.cos(rad) * (r + m * 0.7)
        y1 = cy + math.sin(rad) * (r + m * 0.7)
        x2 = cx + math.cos(rad) * (r + m * 1.6)
        y2 = cy + math.sin(rad) * (r + m * 1.6)
        d.ellipse([x2 - m * 0.4, y2 - m * 0.4, x2 + m * 0.4, y2 + m * 0.4], fill=c)


def _draw_folder(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.14
    # tab
    d.rectangle([m, s * 0.22, s * 0.44, s * 0.38], fill=c)
    # body
    d.rounded_rectangle([m, s * 0.32, s - m, s - m], radius=m * 0.6, fill=c)


def _draw_search(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.18
    r = s * 0.28
    cx, cy = m + r, m + r
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=max(3, int(s * 0.10)))
    # handle
    hx, hy = cx + r * 0.70, cy + r * 0.70
    d.line([(hx, hy), (s - m * 0.7, s - m * 0.7)], fill=c, width=max(3, int(s * 0.10)))


def _draw_paste(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.16
    # board
    d.rounded_rectangle([m, s * 0.28, s - m, s - m], radius=m * 0.5, outline=c, width=max(2, int(s * 0.09)))
    # top clip
    d.rectangle([s * 0.30, m * 0.7, s * 0.70, s * 0.30], outline=c, width=max(2, int(s * 0.09)))
    # paper lines
    for y_off in [0.54, 0.68, 0.82]:
        y = s * y_off
        d.line([(s * 0.24, y), (s * 0.76, y)], fill=c, width=2)


def _draw_close(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.24
    w = max(2, int(s * 0.10))
    d.line([(m, m), (s - m, s - m)], fill=c, width=w)
    d.line([(s - m, m), (m, s - m)], fill=c, width=w)


def _draw_list(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.20
    w = max(2, int(s * 0.09))
    for i, y in enumerate([s * 0.22, s * 0.48, s * 0.74]):
        # bullet
        r = s * 0.05
        d.ellipse([m, y - r, m + r * 2, y + r], fill=c)
        # line
        d.line([(s * 0.34, y), (s - m, y)], fill=c, width=w)


def _draw_check(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    m = s * 0.18
    w = max(3, int(s * 0.12))
    d.line([(m, s * 0.50), (s * 0.38, s - m), (s - m, m * 0.80)], fill=c, width=w)


def _draw_spinner(d: ImageDraw.ImageDraw, s: int, c: str) -> None:
    r = s * 0.38
    cx, cy = s / 2, s / 2
    for i in range(8):
        a = math.radians(i * 45 - 90)
        dot_r = s * 0.06
        x = cx + math.cos(a) * r
        y = cy + math.sin(a) * r
        alpha = int(255 * (i + 1) / 8)
        color = _blend_hex(c, "#00000000", alpha / 255)
        d.ellipse(
            [x - dot_r, y - dot_r, x + dot_r, y + dot_r],
            fill=color,
        )


def _blend_hex(hex_color: str, _bg: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    nr = int(r * alpha)
    ng = int(g * alpha)
    nb = int(b * alpha)
    return f"#{nr:02x}{ng:02x}{nb:02x}"


# ── Image helpers ──────────────────────────────────────────────────────────

def _mk_placeholder() -> ctk.CTkImage:
    img = Image.new("RGB", (THUMB_W, THUMB_H), "#0d1326")
    d = ImageDraw.Draw(img)
    cx, cy, r = THUMB_W // 2, THUMB_H // 2, 32
    # outer ring
    d.ellipse(
        [cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
        fill=None, outline=ACCENT, width=2,
    )
    # inner filled circle
    d.ellipse(
        [cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2],
        fill="#182045",
    )
    # play triangle
    d.polygon(
        [(cx - 9, cy - 16), (cx + 18, cy), (cx - 9, cy + 16)],
        fill=ACCENT,
    )
    return ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))


def _load_thumb(url: str) -> Optional[ctk.CTkImage]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=7) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB").resize(
            (THUMB_W, THUMB_H), Image.LANCZOS,
        )
        return ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))
    except Exception:
        return None


# ── System checks ──────────────────────────────────────────────────────────

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


# ── Application ────────────────────────────────────────────────────────────

class YtmaxApp(ctk.CTk):
    DEFAULT_DL = Path.home() / "Downloads"

    def __init__(self) -> None:
        super().__init__()
        self.title("YTmax")
        self.configure(fg_color=BG_BASE)
        self.minsize(720, _H_INIT)
        self.resizable(True, True)

        self._output_dir       = self.DEFAULT_DL
        self._info: Optional[dl.VideoInfo] = None
        self._playlist_info: Optional[dl.PlaylistInfo] = None
        self._active           = False
        self._thumb_img: Optional[ctk.CTkImage] = None
        self._playlist_thumb_img: Optional[ctk.CTkImage] = None
        self._settings_open    = False
        self._card_visible     = False
        self._playlist_visible = False
        self._is_playlist      = False
        self._animating        = False
        self._spinning         = False
        self._spinner_frame   = 0

        icon_path = resource_path("ytmax.ico")
        png_path  = resource_path("ytmax.png")
        try:
            if os.name == "nt" and os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            elif os.path.exists(png_path):
                img = tk.PhotoImage(file=png_path)
                self.wm_iconphoto(True, img)
        except Exception:
            pass

        self._url_var       = tk.StringVar()
        self._quality_var   = tk.StringVar(value="best")
        self._audio_var     = tk.BooleanVar(value=False)
        self._subtitles_var = tk.BooleanVar(value=True)
        self._folder_var    = tk.StringVar(value=str(self.DEFAULT_DL))
        self._cookies_var   = tk.StringVar(value=str(self.DEFAULT_DL / "youtube.txt"))
        self._progress_var  = tk.DoubleVar(value=0)

        self._icons: dict[str, ctk.CTkImage] = {}
        self._init_icons()
        self._build_ui()
        self._place(_W, _H_INIT)

        # global keyboard shortcuts
        self.bind_all("<Control-l>", lambda _e: (self._url_entry.focus_set(), self._url_entry.select_range(0, "end")))
        self.bind_all("<Control-L>", lambda _e: (self._url_entry.focus_set(), self._url_entry.select_range(0, "end")))
        self._url_entry.bind("<Escape>", lambda _e: self._on_clear_url())
        self.bind_all("<Control-comma>", lambda _e: self._toggle_settings())

    # ── Icon initialisation ────────────────────────────────────────────────

    def _init_icons(self) -> None:
        self._icons = {
            "play":     _mk_icon(_draw_play, 26, ACCENT_TXT),
            "download": _mk_icon(_draw_download, 20, ACCENT_TXT),
            "settings": _mk_icon(_draw_settings, 20, TEXT_DIM),
            "settings_a": _mk_icon(_draw_settings, 20, ACCENT),
            "folder":   _mk_icon(_draw_folder, 18, TEXT_SEC),
            "search":   _mk_icon(_draw_search, 16, ACCENT_TXT),
            "paste":    _mk_icon(_draw_paste, 18, TEXT_SEC),
            "close":    _mk_icon(_draw_close, 14, TEXT_DIM),
            "list":     _mk_icon(_draw_list, 16, ACCENT),
            "check":    _mk_icon(_draw_check, 16, SUCCESS),
            "spinner":  _mk_icon(_draw_spinner, 24, ACCENT),
        }

    # ── Window positioning ─────────────────────────────────────────────────

    def _place(self, w: int, h: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")

    def _resize(self, h: int) -> None:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(0, (sw - _W) // 2)
        y  = max(0, (sh - h) // 2)
        self.geometry(f"{_W}x{h}+{x}+{y}")

    def _animate_resize(self, target_h: int, step: int = 0, steps: int = 8) -> None:
        if self._animating:
            self._resize(target_h)
            return
        self._animating = True
        current_h = self.winfo_height()

        def _step(s: int) -> None:
            if s >= steps:
                self._resize(target_h)
                self._animating = False
                return
            t = (s + 1) / steps
            eased = 1 - (1 - t) ** 3
            h = int(current_h + (target_h - current_h) * eased)
            self._resize(h)
            self.after(16, lambda: _step(s + 1))

        _step(0)

    # ── Spinner animation ──────────────────────────────────────────────────

    def _start_spinner(self, lbl: ctk.CTkLabel) -> None:
        self._spinning = True
        self._spinner_frame = 0
        self._spinner_lbl = lbl

        def _spin() -> None:
            if not self._spinning:
                return
            self._spinner_frame = (self._spinner_frame + 1) % 8
            img = self._spinner_frames[self._spinner_frame]
            self._spinner_lbl.configure(image=img)
            self.after(90, _spin)

        self._spinner_frames = []
        for i in range(8):
            frame = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
            d = ImageDraw.Draw(frame)
            r = 8
            cx, cy = 12, 12
            for j in range(8):
                a = math.radians(j * 45 - 90)
                dot_r = 2
                x = cx + math.cos(a) * r
                y = cy + math.sin(a) * r
                alpha_v = 0.20 + 0.10 * ((j - i) % 8)
                c = _blend_hex(ACCENT, "#00000000", alpha_v)
                d.ellipse(
                    [x - dot_r, y - dot_r, x + dot_r, y + dot_r],
                    fill=c,
                )
            self._spinner_frames.append(
                ctk.CTkImage(light_image=frame, dark_image=frame, size=(24, 24)),
            )
        self.after(0, _spin)

    def _stop_spinner(self) -> None:
        self._spinning = False

    # ── Card shadow helper ─────────────────────────────────────────────────

    # ── UI build ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_topbar()
        self._build_statusbar()

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._scroll.pack(side="top", fill="both", expand=True)
        self._scroll._scrollbar.grid_remove()

        self._build_searchbar()
        self._build_card()
        self._build_playlist_card()
        self._build_settings()

    # ── Top bar ────────────────────────────────────────────────────────────

    def _build_topbar(self) -> None:
        tb = ctk.CTkFrame(self, fg_color=BG_LAYER, corner_radius=0, height=50)
        tb.pack(side="top", fill="x")
        tb.pack_propagate(False)

        logo_path = resource_path("ytmax.png")
        try:
            if not os.path.exists(logo_path):
                raise FileNotFoundError
            limg = Image.open(logo_path).convert("RGBA")
            self._logo_img = ctk.CTkImage(
                light_image=limg, dark_image=limg, size=(28, 28),
            )
            ctk.CTkLabel(tb, text="", image=self._logo_img).pack(
                side="left", padx=(20, 10),
            )
        except Exception:
            badge = ctk.CTkFrame(
                tb, width=28, height=28, corner_radius=8, fg_color=ACCENT,
            )
            badge.pack(side="left", padx=(20, 10))
            badge.pack_propagate(False)
            ctk.CTkLabel(
                badge, text="", image=self._icons["play"],
                fg_color="transparent",
            ).place(relx=0.55, rely=0.5, anchor="center")

        ctk.CTkLabel(
            tb, text="YTmax", font=FONT_BRAND, text_color=TEXT_PRI,
        ).pack(side="left", pady=(2, 0))

        ctk.CTkLabel(
            tb, text="  video & playlist downloader",
            font=("Segoe UI", 9), text_color=TEXT_DIM,
        ).pack(side="left")

        self._settings_btn = ctk.CTkButton(
            tb, text="", image=self._icons["settings"],
            width=34, height=34, corner_radius=17,
            fg_color="transparent",
            hover_color=BG_INPUT,
            command=self._toggle_settings,
        )
        self._settings_btn.pack(side="right", padx=(0, 18))

    # ── Status bar ─────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        sb = ctk.CTkFrame(self, fg_color=BG_LAYER, corner_radius=0, height=30)
        sb.pack(side="bottom", fill="x")
        sb.pack_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            sb, text="Ready  —  paste a URL to begin",
            font=FONT_TINY, text_color=TEXT_DIM,
        )
        self._status_lbl.pack(side="left", padx=20)

        for name, ok in [("Node.js", _check_nodejs()), ("FFmpeg", _check_ffmpeg())]:
            color = SUCCESS if ok else ERROR
            dot = "●" if ok else "○"
            ctk.CTkLabel(
                sb, text=f"{dot}  {name}", font=FONT_TINY, text_color=color,
            ).pack(side="right", padx=(0, 18))

    # ── Search bar ─────────────────────────────────────────────────────────

    def _build_searchbar(self) -> None:
        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", padx=18, pady=(16, 10))

        frame = ctk.CTkFrame(outer, fg_color=BG_CARD, corner_radius=18)
        frame.pack(fill="x")
        frame.grid_columnconfigure(1, weight=1)

        self._paste_btn = ctk.CTkButton(
            frame, text=" Paste", image=self._icons["paste"],
            compound="left", width=90, height=42, corner_radius=21,
            font=FONT_SMALL, fg_color=BG_INPUT, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._on_paste_fetch,
        )
        self._paste_btn.grid(row=0, column=0, padx=(12, 8), pady=12)

        self._url_entry = ctk.CTkEntry(
            frame, textvariable=self._url_var,
            placeholder_text="Paste a YouTube video or playlist URL…",
            font=FONT_BODY, height=42, corner_radius=21,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI, placeholder_text_color=TEXT_DIM,
        )
        self._url_entry.grid(row=0, column=1, sticky="ew", pady=12)
        self._url_entry.bind("<Return>", lambda _: self._on_fetch())
        self._url_entry.bind("<FocusIn>", self._on_url_focus)
        self._url_entry.bind("<FocusOut>", self._on_url_focus_out)

        self._clear_btn = ctk.CTkButton(
            frame, text="", image=self._icons["close"],
            width=34, height=42, corner_radius=21,
            fg_color="transparent",
            hover_color=BG_INPUT,
            command=self._on_clear_url,
        )
        self._clear_btn.grid(row=0, column=2, padx=(2, 4), pady=12)

        self._fetch_btn = ctk.CTkButton(
            frame, text="Fetch",
            width=90, height=42, corner_radius=21,
            font=FONT_BTN, fg_color=ACCENT, hover_color=ACCENT_H,
            text_color=ACCENT_TXT, command=self._on_fetch,
        )
        self._fetch_btn.grid(row=0, column=3, padx=(0, 12), pady=12)

    # ── Video card ─────────────────────────────────────────────────────────

    def _build_card(self) -> None:
        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", padx=18, pady=(0, 14))
        outer.pack_forget()

        self._card = ctk.CTkFrame(
            outer, fg_color=BG_CARD,
            corner_radius=18, border_width=1, border_color=BORDER,
        )
        self._card.pack(fill="x")
        self._card_outer = outer

        left = ctk.CTkFrame(self._card, fg_color="transparent")
        left.pack(side="left", padx=(20, 0), pady=20)

        thumb_outer = ctk.CTkFrame(left, fg_color=BG_INPUT, corner_radius=10)
        thumb_outer.pack()
        self._thumb_lbl = ctk.CTkLabel(
            thumb_outer, text="", image=_mk_placeholder(),
        )
        self._thumb_lbl.pack(padx=3, pady=3)

        ctk.CTkFrame(self._card, fg_color=BORDER, width=1).pack(
            side="left", fill="y", padx=18, pady=18,
        )

        right = ctk.CTkFrame(self._card, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=(30, 28))

        title_row = ctk.CTkFrame(right, fg_color="transparent")
        title_row.pack(fill="x")

        self._title_lbl = ctk.CTkLabel(
            title_row, text="—", font=FONT_TITLE, text_color=TEXT_PRI,
            wraplength=260, justify="left", anchor="w",
        )
        self._title_lbl.pack(side="left")

        badge_bg = ctk.CTkFrame(
            title_row, fg_color=ACCENT, corner_radius=4,
        )
        badge_bg.pack(side="right")
        ctk.CTkLabel(
            badge_bg, text=" VIDEO ", font=("Segoe UI", 7, "bold"),
            text_color=ACCENT_TXT,
        ).pack(padx=10, pady=3)

        self._meta_lbl = ctk.CTkLabel(
            right, text="", font=FONT_SMALL, text_color=TEXT_SEC,
            justify="left", anchor="w",
        )
        self._meta_lbl.pack(fill="x", pady=(8, 0))

        self._badge_lbl = ctk.CTkLabel(
            right, text="", font=("Segoe UI", 8, "bold"),
            text_color=ACCENT, anchor="w",
        )
        self._badge_lbl.pack(fill="x", pady=(4, 18))

        qrow = ctk.CTkFrame(right, fg_color="transparent")
        qrow.pack(fill="x", pady=(0, 14))

        qg = ctk.CTkFrame(qrow, fg_color="transparent")
        qg.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(
            qg, text="QUALITY", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        self._make_quality_menu(qg)

        ag = ctk.CTkFrame(qrow, fg_color="transparent")
        ag.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(
            ag, text="AUDIO ONLY", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        self._make_audio_switch(ag)

        sg = ctk.CTkFrame(qrow, fg_color="transparent")
        sg.pack(side="left")
        ctk.CTkLabel(
            sg, text="SUBTITLES", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        self._make_subtitle_switch(sg)

        self._dl_btn = ctk.CTkButton(
            right, text="  Download", image=self._icons["download"],
            compound="left", height=48, corner_radius=24,
            font=FONT_BTN, fg_color=ACCENT, hover_color=ACCENT_H,
            text_color=ACCENT_TXT, command=self._on_download,
        )
        self._dl_btn.pack(fill="x", pady=(0, 14))

        progr = ctk.CTkFrame(right, fg_color="transparent")
        progr.pack(fill="x", pady=(0, 4))

        self._progress_bar = ctk.CTkProgressBar(
            progr, variable=self._progress_var,
            fg_color=BG_INPUT, progress_color=ACCENT,
            height=5, corner_radius=3,
        )
        self._progress_bar.pack(side="left", fill="x", expand=True)
        self._progress_bar.set(0)

        self._progress_pct_lbl = ctk.CTkLabel(
            progr, text="", font=FONT_MONO, text_color=TEXT_SEC, width=40,
        )
        self._progress_pct_lbl.pack(side="right", padx=(10, 0))

        self._progress_lbl = ctk.CTkLabel(
            right, text="", font=FONT_TINY, text_color=TEXT_DIM, anchor="w",
        )
        self._progress_lbl.pack(fill="x")
        self._progress_lbl.bind("<Button-1>", self._open_output_folder)

    def _make_quality_menu(self, parent: ctk.CTkFrame) -> None:
        self._quality_menu = ctk.CTkOptionMenu(
            parent, values=["4K", "1440p", "1080p", "720p", "best"],
            variable=self._quality_var,
            font=FONT_SMALL, width=110, height=32, corner_radius=16,
            fg_color=BG_INPUT, button_color=ACCENT, text_color=TEXT_PRI,
            dropdown_fg_color=BG_CARD, dropdown_hover_color=BG_INPUT,
            dropdown_text_color=TEXT_PRI,
        )
        self._quality_menu.pack(anchor="w", pady=(5, 0))

    def _make_audio_switch(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkSwitch(
            parent, text="", variable=self._audio_var,
            progress_color=ACCENT, width=40, height=20,
            button_color=TEXT_PRI, button_hover_color=TEXT_SEC,
        ).pack(anchor="w", pady=(5, 0))

    def _make_subtitle_switch(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkSwitch(
            parent, text="", variable=self._subtitles_var,
            progress_color=ACCENT, width=40, height=20,
            button_color=TEXT_PRI, button_hover_color=TEXT_SEC,
        ).pack(anchor="w", pady=(5, 0))

    # ── Playlist card ──────────────────────────────────────────────────────

    def _build_playlist_card(self) -> None:
        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", padx=18, pady=(0, 14))
        outer.pack_forget()

        self._playlist_card = ctk.CTkFrame(
            outer, fg_color=BG_CARD,
            corner_radius=18, border_width=1, border_color=BORDER,
        )
        self._playlist_card.pack(fill="x")
        self._playlist_outer = outer

        left = ctk.CTkFrame(self._playlist_card, fg_color="transparent")
        left.pack(side="left", padx=(20, 0), pady=20)

        thumb_outer = ctk.CTkFrame(left, fg_color=BG_INPUT, corner_radius=10)
        thumb_outer.pack()
        self._playlist_thumb_lbl = ctk.CTkLabel(
            thumb_outer, text="", image=_mk_placeholder(),
        )
        self._playlist_thumb_lbl.pack(padx=3, pady=3)

        ctk.CTkFrame(self._playlist_card, fg_color=BORDER, width=1).pack(
            side="left", fill="y", padx=18, pady=18,
        )

        right = ctk.CTkFrame(self._playlist_card, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=(30, 28))

        title_row = ctk.CTkFrame(right, fg_color="transparent")
        title_row.pack(fill="x")

        self._playlist_title_lbl = ctk.CTkLabel(
            title_row, text="—", font=FONT_TITLE, text_color=TEXT_PRI,
            wraplength=260, justify="left", anchor="w",
        )
        self._playlist_title_lbl.pack(side="left")

        badge_bg = ctk.CTkFrame(
            title_row, fg_color=ACCENT_DIM, corner_radius=4,
        )
        badge_bg.pack(side="right")
        ctk.CTkLabel(
            badge_bg, text=" PLAYLIST ", font=("Segoe UI", 7, "bold"),
            text_color=ACCENT_TXT,
        ).pack(padx=10, pady=3)

        self._playlist_meta_lbl = ctk.CTkLabel(
            right, text="", font=FONT_SMALL, text_color=TEXT_SEC,
            justify="left", anchor="w",
        )
        self._playlist_meta_lbl.pack(fill="x", pady=(10, 0))

        sel_row = ctk.CTkFrame(right, fg_color="transparent")
        sel_row.pack(fill="x", pady=(12, 10))

        self._select_all_btn = ctk.CTkButton(
            sel_row, text="Select All", width=80, height=28, corner_radius=14,
            font=FONT_SMALL, fg_color=BG_INPUT, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._select_all_videos,
        )
        self._select_all_btn.pack(side="left")

        self._deselect_all_btn = ctk.CTkButton(
            sel_row, text="Deselect All", width=100, height=28, corner_radius=14,
            font=FONT_SMALL, fg_color=BG_INPUT, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._deselect_all_videos,
        )
        self._deselect_all_btn.pack(side="left", padx=(8, 0))

        self._selected_count_lbl = ctk.CTkLabel(
            sel_row, text="0 / 0 selected", font=FONT_SMALL, text_color=TEXT_SEC,
        )
        self._selected_count_lbl.pack(side="right")

        self._video_list_frame = ctk.CTkScrollableFrame(
            right, fg_color=BG_INPUT, corner_radius=12,
            height=190,
            scrollbar_button_color=BG_CARD,
            scrollbar_button_hover_color=BORDER,
        )
        self._video_list_frame.pack(fill="both", expand=True, pady=(0, 12))
        self._video_list_frame._scrollbar.grid()

        qrow = ctk.CTkFrame(right, fg_color="transparent")
        qrow.pack(fill="x", pady=(0, 14))

        qg = ctk.CTkFrame(qrow, fg_color="transparent")
        qg.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(
            qg, text="QUALITY", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        self._playlist_quality_menu = ctk.CTkOptionMenu(
            qg, values=["4K", "1440p", "1080p", "720p", "best"],
            variable=self._quality_var,
            font=FONT_SMALL, width=110, height=32, corner_radius=16,
            fg_color=BG_INPUT, button_color=ACCENT, text_color=TEXT_PRI,
            dropdown_fg_color=BG_CARD, dropdown_hover_color=BG_INPUT,
            dropdown_text_color=TEXT_PRI,
        )
        self._playlist_quality_menu.pack(anchor="w", pady=(5, 0))

        ag = ctk.CTkFrame(qrow, fg_color="transparent")
        ag.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(
            ag, text="AUDIO ONLY", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        ctk.CTkSwitch(
            ag, text="", variable=self._audio_var,
            progress_color=ACCENT, width=40, height=20,
            button_color=TEXT_PRI, button_hover_color=TEXT_SEC,
        ).pack(anchor="w", pady=(5, 0))

        sg = ctk.CTkFrame(qrow, fg_color="transparent")
        sg.pack(side="left")
        ctk.CTkLabel(
            sg, text="SUBTITLES", font=("Segoe UI", 7, "bold"), text_color=TEXT_DIM,
        ).pack(anchor="w")
        ctk.CTkSwitch(
            sg, text="", variable=self._subtitles_var,
            progress_color=ACCENT, width=40, height=20,
            button_color=TEXT_PRI, button_hover_color=TEXT_SEC,
        ).pack(anchor="w", pady=(5, 0))

        self._playlist_dl_btn = ctk.CTkButton(
            right, text="  Download Playlist", image=self._icons["download"],
            compound="left", height=48, corner_radius=24,
            font=FONT_BTN, fg_color=ACCENT, hover_color=ACCENT_H,
            text_color=ACCENT_TXT, command=self._on_playlist_download,
        )
        self._playlist_dl_btn.pack(fill="x", pady=(0, 14))

        progr = ctk.CTkFrame(right, fg_color="transparent")
        progr.pack(fill="x", pady=(0, 4))

        self._playlist_progress_bar = ctk.CTkProgressBar(
            progr, variable=self._progress_var,
            fg_color=BG_INPUT, progress_color=ACCENT,
            height=5, corner_radius=3,
        )
        self._playlist_progress_bar.pack(side="left", fill="x", expand=True)
        self._playlist_progress_bar.set(0)

        self._playlist_progress_pct_lbl = ctk.CTkLabel(
            progr, text="", font=FONT_MONO, text_color=TEXT_SEC, width=40,
        )
        self._playlist_progress_pct_lbl.pack(side="right", padx=(10, 0))

        self._playlist_progress_lbl = ctk.CTkLabel(
            right, text="", font=FONT_TINY, text_color=TEXT_DIM, anchor="w",
        )
        self._playlist_progress_lbl.pack(fill="x")
        self._playlist_progress_lbl.bind("<Button-1>", self._open_output_folder)

        self._video_checkboxes: dict[int, ctk.CTkCheckBox] = {}

    def _build_video_list(self, videos: list[dl.PlaylistVideo]) -> None:
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._video_checkboxes.clear()

        has_duration = any(v.duration > 0 for v in videos)

        for idx, video in enumerate(videos):
            bg = "#161f3d" if idx % 2 == 0 else "transparent"
            row = ctk.CTkFrame(
                self._video_list_frame, fg_color=bg, corner_radius=6,
            )
            row.pack(fill="x", padx=4, pady=1)

            num_lbl = ctk.CTkLabel(
                row, text=f"{video.index:02d}", font=FONT_MONO,
                text_color=TEXT_DIM, width=26,
            )
            num_lbl.pack(side="left", padx=(6, 0))

            checkbox = ctk.CTkCheckBox(
                row, text=video.title[:52],
                font=("Segoe UI", 9), fg_color=BG_INPUT,
                border_color=BORDER, text_color=TEXT_PRI,
                onvalue=True, offvalue=False,
                corner_radius=4, command=self._update_selected_count,
                checkbox_width=16, checkbox_height=16,
            )
            checkbox.select()
            checkbox.pack(side="left", padx=(6, 6), pady=5, fill="x", expand=True)
            self._video_checkboxes[video.index] = checkbox

            if has_duration and video.duration > 0:
                ctk.CTkLabel(
                    row, text=dl.fmt_duration(video.duration),
                    font=FONT_MONO, text_color=TEXT_DIM,
                ).pack(side="right", padx=(0, 10))

        self._update_selected_count()

    def _select_all_videos(self) -> None:
        for cb in self._video_checkboxes.values():
            cb.select()
        self._update_selected_count()

    def _deselect_all_videos(self) -> None:
        for cb in self._video_checkboxes.values():
            cb.deselect()
        self._update_selected_count()

    def _update_selected_count(self) -> None:
        selected = sum(1 for cb in self._video_checkboxes.values() if cb.get())
        total = len(self._video_checkboxes)
        self._selected_count_lbl.configure(text=f"{selected} / {total} selected")

    # ── Settings panel ─────────────────────────────────────────────────────

    def _build_settings(self) -> None:
        self._settings_panel = ctk.CTkFrame(
            self._scroll, fg_color=BG_CARD,
            corner_radius=16, border_width=1, border_color=BORDER,
        )

        header = ctk.CTkFrame(self._settings_panel, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 10))
        ctk.CTkLabel(
            header, text="", image=self._icons["settings"],
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            header, text="Settings",
            font=("Segoe UI Semibold", 11), text_color=TEXT_SEC,
        ).pack(side="left")

        body = ctk.CTkFrame(self._settings_panel, fg_color="transparent")
        body.pack(fill="x", padx=22, pady=(0, 20))

        folder_frame = ctk.CTkFrame(body, fg_color=BG_INPUT, corner_radius=12)
        folder_frame.pack(fill="x", pady=(0, 10))

        folder_header = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_header.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(
            folder_header, text="", image=self._icons["folder"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            folder_header, text="Download folder",
            font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM,
        ).pack(side="left")

        f_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        f_row.pack(fill="x", padx=16, pady=(4, 12))
        f_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            f_row, textvariable=self._folder_var,
            font=FONT_SMALL, height=34, corner_radius=17,
            fg_color=BG_CARD, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            f_row, text="Browse", width=72, height=34, corner_radius=17,
            font=FONT_SMALL, fg_color=BG_CARD, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT_SEC,
            command=self._browse_folder,
        ).grid(row=0, column=1, padx=(8, 0))

        cookies_frame = ctk.CTkFrame(body, fg_color=BG_INPUT, corner_radius=12)
        cookies_frame.pack(fill="x", pady=(0, 10))

        cookies_header = ctk.CTkFrame(cookies_frame, fg_color="transparent")
        cookies_header.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(
            cookies_header, text="", image=self._icons["settings"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            cookies_header, text="Cookies file  (.txt)",
            font=("Segoe UI", 8, "bold"), text_color=TEXT_DIM,
        ).pack(side="left")

        ctk.CTkEntry(
            cookies_frame, textvariable=self._cookies_var,
            font=FONT_SMALL, height=34, corner_radius=17,
            fg_color=BG_CARD, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        ).pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(
            self._settings_panel,
            text=(
                "Cookies are optional — only needed for age-restricted or "
                "sign-in protected videos.  Export from your browser with the "
                "'Get cookies.txt LOCALLY' extension (Netscape format)."
            ),
            font=FONT_TINY, text_color=TEXT_DIM,
            justify="left", wraplength=640,
        ).pack(anchor="w", padx=22, pady=(0, 16))

    # ── Visibility helpers ─────────────────────────────────────────────────

    def _show_card(self) -> None:
        if self._card_visible:
            return
        if self._playlist_visible:
            self._playlist_outer.pack_forget()
            self._playlist_visible = False
        self._card_outer.pack(fill="x", padx=18, pady=(0, 14))
        self._card_visible = True
        target = _H_CARD + (_H_SET if self._settings_open else 0)
        self.after(50, lambda: self._animate_resize(target))
        self.after(80, lambda: self._scroll._scrollbar.grid())

    def _show_playlist_card(self) -> None:
        if self._card_visible:
            self._card_outer.pack_forget()
            self._card_visible = False
        self._playlist_outer.pack(fill="x", padx=18, pady=(0, 14))
        self._playlist_visible = True
        target = _H_PLAYLIST + (_H_SET if self._settings_open else 0)
        self.after(50, lambda: self._animate_resize(target))
        self.after(80, lambda: self._scroll._scrollbar.grid())

    def _toggle_settings(self) -> None:
        self._settings_open = not self._settings_open
        if self._settings_open:
            self._settings_panel.pack(fill="x", padx=18, pady=(0, 14))
            self._settings_btn.configure(image=self._icons["settings_a"])
            self._scroll._scrollbar.grid()
            self.after(50, lambda: self._animate_resize(self.winfo_height() + _H_SET))
        else:
            self._settings_panel.pack_forget()
            self._settings_btn.configure(image=self._icons["settings"])
            new_h = max(self.winfo_height() - _H_SET, _H_INIT)
            self.after(50, lambda: self._animate_resize(new_h))
            if not self._card_visible and not self._playlist_visible:
                self._scroll._scrollbar.grid_remove()

    # ── Event handlers ─────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        d = filedialog.askdirectory(initialdir=self._folder_var.get())
        if d:
            self._folder_var.set(d)

    def _on_paste_fetch(self) -> None:
        try:
            self._url_var.set(self.clipboard_get())
            self._on_fetch()
        except tk.TclError:
            self._set_status("Clipboard is empty.")

    def _on_url_focus(self, event=None) -> None:
        self._url_entry.configure(border_color=ACCENT, border_width=2)

    def _on_url_focus_out(self, event=None) -> None:
        self._url_entry.configure(border_color=BORDER, border_width=1)

    def _on_clear_url(self) -> None:
        self._url_var.set("")
        self._url_entry.focus()

    def _on_fetch(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            self._set_status("Paste a URL first.")
            return

        if "music.youtube.com" in url:
            self._audio_var.set(True)

        if self._active:
            self._set_status("A download is already in progress.")
            return

        self._set_status("Fetching info…")
        self._fetch_btn.configure(state="disabled", text="  Fetching…")
        self._fetch_btn.configure(fg_color=ACCENT_DIM)
        cookies = self._cookies_var.get().strip()

        def _worker() -> None:
            try:
                if dl.is_playlist_url(url):
                    self._is_playlist = True
                    playlist_info = dl.fetch_playlist_info(url, cookies_file=cookies)
                    self.after(0, self._show_playlist_info, playlist_info)
                else:
                    self._is_playlist = False
                    info = dl.fetch_info(url, cookies_file=cookies)
                    self.after(0, self._show_info, info)
            except Exception as exc:
                err = str(exc)
                msg = "Fetch failed — check the URL or your connection."
                if dl.is_bot_error(err):
                    msg = "Bot check triggered — load a cookies.txt file."
                elif dl.is_age_error(err):
                    msg = "Age-restricted — load a cookies.txt file."
                self.after(0, self._set_status, msg)
            finally:
                self.after(0, self._reset_fetch_btn)

        threading.Thread(target=_worker, daemon=True).start()

    def _reset_fetch_btn(self) -> None:
        self._fetch_btn.configure(state="normal", text="Fetch", fg_color=ACCENT)

    def _show_info(self, info: dl.VideoInfo) -> None:
        self._info = info
        self._show_card()

        self._title_lbl.configure(text=info.title[:72])
        self._meta_lbl.configure(
            text=f"{info.uploader}  ·  {dl.fmt_duration(info.duration)}"
        )
        self._badge_lbl.configure(
            text=f"Max quality: {info.best_height}p" if info.best_height else ""
        )
        self._set_status(f"Loaded  ·  {info.title[:45]}")

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

    def _show_playlist_info(self, playlist_info: dl.PlaylistInfo) -> None:
        self._playlist_info = playlist_info
        self._show_playlist_card()

        self._playlist_title_lbl.configure(text=playlist_info.title[:72])
        dur_str = dl.fmt_duration(playlist_info.total_duration) if playlist_info.total_duration > 0 else ""
        meta = f"{playlist_info.uploader}  ·  {playlist_info.video_count} videos"
        if dur_str:
            meta += f"  ·  {dur_str}"
        self._playlist_meta_lbl.configure(text=meta)
        self._set_status(f"Loaded  ·  {playlist_info.title[:45]}")

        self._build_video_list(playlist_info.videos)

        def _load() -> None:
            if playlist_info.thumbnail:
                img = _load_thumb(playlist_info.thumbnail)
                if img:
                    self._playlist_thumb_img = img
                    self.after(
                        0, lambda i=img: self._playlist_thumb_lbl.configure(image=i),
                    )

        threading.Thread(target=_load, daemon=True).start()

    def _on_download(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            self._set_status("No URL entered.")
            return
        if self._active:
            self._set_status("A download is already in progress.")
            return

        out_str = self._folder_var.get().strip() or str(self.DEFAULT_DL)
        self._output_dir = Path(out_str)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._active = True
        self._dl_btn.configure(text="  Downloading…", state="disabled", fg_color=ACCENT_DIM)
        self._progress_var.set(0)
        self._progress_pct_lbl.configure(text="0%")
        self._set_status(f"Downloading  ·  {self._quality_var.get()}")

        task = dl.DownloadTask(
            url          = url,
            output_dir   = self._output_dir,
            quality      = self._quality_var.get(),
            audio_only   = self._audio_var.get(),
            subtitles    = self._subtitles_var.get(),
            cookies_file = self._cookies_var.get().strip(),
            on_progress  = self._on_progress,
            on_complete  = self._on_complete,
            on_error     = self._on_dl_error,
        )
        dl.download(task)

    def _on_playlist_download(self) -> None:
        if not self._playlist_info:
            self._set_status("No playlist loaded.")
            return
        if self._active:
            self._set_status("A download is already in progress.")
            return

        video_urls = [
            v.url for v in self._playlist_info.videos
            if self._video_checkboxes.get(v.index) and self._video_checkboxes[v.index].get()
        ]

        if not video_urls:
            self._set_status("No videos selected.")
            return

        out_str = self._folder_var.get().strip() or str(self.DEFAULT_DL)
        self._output_dir = Path(out_str)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._active = True
        self._playlist_dl_btn.configure(
            text="  Downloading…", state="disabled", fg_color=ACCENT_DIM,
        )
        self._progress_var.set(0)
        self._playlist_progress_pct_lbl.configure(text="0%")
        self._set_status(f"Downloading {len(video_urls)} videos…")

        task = dl.PlaylistDownloadTask(
            playlist_url      = self._url_var.get().strip(),
            output_dir        = self._output_dir,
            quality           = self._quality_var.get(),
            audio_only        = self._audio_var.get(),
            subtitles         = self._subtitles_var.get(),
            cookies_file      = self._cookies_var.get().strip(),
            video_urls        = video_urls,
            on_progress       = self._on_playlist_progress,
            on_video_complete = self._on_video_complete,
            on_complete       = self._on_playlist_complete,
            on_error          = self._on_dl_error,
        )
        dl.download_playlist(task)

    def _on_progress(self, pct: float, speed: float, eta: int, fname: str) -> None:
        self.after(0, self._update_progress, pct, speed, eta, fname)

    def _update_progress(self, pct: float, speed: float, eta: int, fname: str) -> None:
        self._progress_var.set(pct / 100)
        speed_s = dl.fmt_size(speed) if speed else ""
        eta_s = f"  |  {dl.fmt_time(eta)}" if eta else ""
        self._progress_lbl.configure(text=f"{speed_s}{eta_s}")
        self._progress_pct_lbl.configure(text=f"{pct:.0f}%")

    def _on_complete(self) -> None:
        self.after(0, self._finish_download, True)

    def _on_playlist_progress(self, current: int, total: int, title: str, url: str) -> None:
        self.after(0, self._update_playlist_progress, current, total, title)

    def _update_playlist_progress(self, current: int, total: int, title: str) -> None:
        pct = (current / total) * 100 if total else 0
        self._progress_var.set(pct / 100)
        self._playlist_progress_lbl.configure(
            text=f"Video {current} of {total}"
        )
        self._playlist_progress_pct_lbl.configure(text=f"{pct:.0f}%")

    def _on_video_complete(self, current: int, total: int, title: str) -> None:
        self.after(0, self._update_video_complete, current, total, title)

    def _update_video_complete(self, current: int, total: int, title: str) -> None:
        self._set_status(f"Completed {current} / {total}")

    def _on_playlist_complete(self) -> None:
        self.after(0, self._finish_playlist_download, True)

    def _finish_playlist_download(self, ok: bool) -> None:
        self._active = False
        self._playlist_dl_btn.configure(
            text="  Download Playlist", state="normal", fg_color=ACCENT,
        )
        if ok:
            self._progress_var.set(1.0)
            self._set_status("Playlist download complete — click the path to open folder", "success")
            self._playlist_progress_pct_lbl.configure(text="100%")
            self._playlist_progress_lbl.configure(
                text=f"Open folder: {self._output_dir}",
                text_color=ACCENT_GLOW, cursor="hand2",
            )
        else:
            self._progress_var.set(0)
            self._playlist_progress_lbl.configure(text="", text_color=TEXT_DIM, cursor="")
            self._set_status("Playlist download failed", "error")

    def _on_dl_error(self, msg: str) -> None:
        self.after(0, self._finish_download, False, msg)

    def _finish_download(self, ok: bool, error: str = "") -> None:
        self._active = False
        self._dl_btn.configure(
            text="  Download", state="normal", fg_color=ACCENT,
        )
        if ok:
            self._progress_var.set(1.0)
            self._progress_pct_lbl.configure(text="100%")
            self._set_status("Download complete — click the path to open folder", "success")
            self._progress_lbl.configure(
                text=f"Open folder: {self._output_dir}",
                text_color=ACCENT_GLOW, cursor="hand2",
            )
        else:
            self._progress_var.set(0)
            self._progress_pct_lbl.configure(text="")
            self._progress_lbl.configure(text="", text_color=TEXT_DIM, cursor="")
            if dl.is_age_error(error):
                self._set_status("Age-restricted — load a cookies.txt", "error")
            elif dl.is_bot_error(error):
                self._set_status("Bot check — load a cookies.txt", "error")
            else:
                self._set_status("Download failed", "error")

    def _set_status(self, msg: str, level: str = "info") -> None:
        colors = {
            "info":    TEXT_DIM,
            "success": SUCCESS,
            "error":   ERROR,
            "warn":    WARNING,
        }
        self._status_lbl.configure(text=msg, text_color=colors.get(level, TEXT_DIM))

    def _open_output_folder(self, _event=None) -> None:
        try:
            path = str(self._output_dir)
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = YtmaxApp()
    app.mainloop()
