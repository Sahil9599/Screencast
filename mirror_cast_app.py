"""
Mirror Cast - Screen Mirroring Application
Mirrors Android phone screen to PC over Hotspot using scrcpy + ADB WiFi.
No internet required. Beautiful tkinter GUI.

Usage:
    python mirror_cast_app.py

Requirements:
    - Python 3.8+
    - Android phone with USB Debugging enabled
    - One-time USB connection to authorize ADB
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import socket
import zipfile
import urllib.request
import shutil
import re
import time
import json
import datetime

# ─── Config ───────────────────────────────────────────────────────────

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(APP_DIR, 'tools')
SCRCPY_DIR = os.path.join(TOOLS_DIR, 'scrcpy')
ADB_PATH = os.path.join(SCRCPY_DIR, 'adb.exe')
SCRCPY_PATH = os.path.join(SCRCPY_DIR, 'scrcpy.exe')
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

SCRCPY_URL = "https://github.com/Genymobile/scrcpy/releases/download/v3.2/scrcpy-win64-v3.2.zip"
SCRCPY_ZIP = os.path.join(TOOLS_DIR, 'scrcpy.zip')

ADB_PORT = 5555

# ─── Helpers ──────────────────────────────────────────────────────────

def get_local_ip():
    """Get local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def load_config():
    """Load saved configuration."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save configuration."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def run_cmd(cmd, timeout=30):
    """Run a command and return output."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return '', 'Timeout', 1
    except FileNotFoundError:
        return '', 'Command not found', 1


# ─── Main Application ────────────────────────────────────────────────

class MirrorCastApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mirror Cast - Screen Mirroring")
        self.root.geometry("540x680")
        self.root.minsize(460, 480)
        self.root.resizable(True, True)
        self.root.configure(bg='#0d0d1a')

        self.config = load_config()
        self.phone_ip = self.config.get('phone_ip', '')
        self.mirror_process = None
        self.is_mirroring = False
        self.current_recording = None

        self._setup_styles()
        self._build_ui()
        self._check_tools()

    def _setup_styles(self):
        """Configure ttk styles for dark theme."""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Colors
        self.BG = '#0d0d1a'
        self.BG_CARD = '#16162e'
        self.BG_INPUT = '#1e1e3a'
        self.FG = '#e0e0f0'
        self.FG_DIM = '#7777aa'
        self.ACCENT = '#4f8cff'
        self.GREEN = '#22c55e'
        self.RED = '#ef4444'
        self.ORANGE = '#f59e0b'

        self.style.configure('Card.TFrame', background=self.BG_CARD)
        self.style.configure('App.TFrame', background=self.BG)
        self.style.configure('Title.TLabel', background=self.BG, foreground=self.ACCENT,
                           font=('Segoe UI', 22, 'bold'))
        self.style.configure('Subtitle.TLabel', background=self.BG, foreground=self.FG_DIM,
                           font=('Segoe UI', 10))
        self.style.configure('Card.TLabel', background=self.BG_CARD, foreground=self.FG,
                           font=('Segoe UI', 10))
        self.style.configure('CardTitle.TLabel', background=self.BG_CARD, foreground=self.FG,
                           font=('Segoe UI', 12, 'bold'))
        self.style.configure('Status.TLabel', background=self.BG_CARD, foreground=self.FG_DIM,
                           font=('Segoe UI', 10))
        self.style.configure('Accent.TButton', font=('Segoe UI', 11, 'bold'), padding=(20, 12))
        self.style.configure('Small.TButton', font=('Segoe UI', 9), padding=(12, 6))

    def _build_ui(self):
        """Build the complete UI with scrollable content and sticky bottom action bar."""
        # ── 1. Top Fixed Header & Status ──
        top_frame = tk.Frame(self.root, bg=self.BG)
        top_frame.pack(side='top', fill='x', padx=16, pady=(8, 4))

        header_row = tk.Frame(top_frame, bg=self.BG)
        header_row.pack(fill='x')
        tk.Label(header_row, text="📱 Mirror Cast 📺", bg=self.BG, fg=self.ACCENT,
                 font=('Segoe UI', 16, 'bold')).pack(side='left')
        tk.Label(header_row, text="120 FPS • Zero-Lag", bg=self.BG, fg=self.FG_DIM,
                 font=('Segoe UI', 9)).pack(side='right', pady=4)

        # Status Card (Compact)
        status_frame = tk.Frame(top_frame, bg=self.BG_CARD, highlightbackground='#2a2a4a',
                               highlightthickness=1, padx=12, pady=8)
        status_frame.pack(fill='x', pady=(6, 4))

        self.status_dot = tk.Canvas(status_frame, width=10, height=10, bg=self.BG_CARD,
                                   highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 8))
        self._set_dot(self.ORANGE)

        self.status_label = tk.Label(status_frame, text="Checking tools...",
                                    bg=self.BG_CARD, fg=self.FG, font=('Segoe UI', 9))
        self.status_label.pack(side='left')

        # Tools status (Compact badge)
        self.tools_status = tk.Label(status_frame, text="Tools ready", bg=self.BG_CARD, fg=self.GREEN,
                                    font=('Segoe UI', 8, 'bold'))
        self.tools_status.pack(side='right')

        # Hidden download button ref (tools are pre-installed)
        self.btn_download = tk.Button(self.root)

        # ── 2. Bottom Sticky Action Bar (Always Visible!) ──
        bottom_bar = tk.Frame(self.root, bg=self.BG)
        bottom_bar.pack(side='bottom', fill='x', padx=16, pady=(4, 10))

        # Start/Stop button
        self.btn_mirror = tk.Button(bottom_bar, text="🚀  Start Mirroring",
                                   command=self._toggle_mirror,
                                   bg='#4f8cff', fg='white', font=('Segoe UI', 12, 'bold'),
                                   relief='flat', padx=20, pady=10, cursor='hand2',
                                   activebackground='#3a7aee', state='disabled')
        self.btn_mirror.pack(fill='x', pady=(2, 4))

        # Footer
        tk.Label(bottom_bar, text=f"PC IP: {get_local_ip()} • Scroll with mouse wheel if needed",
                 bg=self.BG, fg=self.FG_DIM, font=('Segoe UI', 8)).pack()

        # ── 3. Middle Scrollable Content Container ──
        middle_container = tk.Frame(self.root, bg=self.BG)
        middle_container.pack(side='top', fill='both', expand=True, padx=12, pady=(0, 2))

        self.canvas = tk.Canvas(middle_container, bg=self.BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(middle_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self.canvas, bg=self.BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        def _on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_configure(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        self.scroll_frame.bind("<Configure>", _on_frame_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        content = self.scroll_frame

        # ── Step 1: Connection Mode ──
        self._make_section(content, "1. Connection Mode",
            "Direct USB cable se <15ms latency milti hai, ya Hotspot se wireless cast karo.")

        mode_frame = tk.Frame(content, bg=self.BG)
        mode_frame.pack(fill='x', pady=(2, 4))

        self.conn_mode_var = tk.StringVar(value='wireless')
        tk.Radiobutton(mode_frame, text="🔌 USB Cable (Fastest ~15ms)", variable=self.conn_mode_var,
                       value='usb', command=self._on_mode_change,
                       bg=self.BG, fg=self.ACCENT, selectcolor=self.BG_INPUT,
                       activebackground=self.BG, activeforeground=self.ACCENT,
                       font=('Segoe UI', 9, 'bold')).pack(side='left', padx=4)

        tk.Radiobutton(mode_frame, text="📶 Wireless (Hotspot)", variable=self.conn_mode_var,
                       value='wireless', command=self._on_mode_change,
                       bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                       activebackground=self.BG, activeforeground=self.ACCENT,
                       font=('Segoe UI', 9)).pack(side='left', padx=10)

        # Container for wireless controls
        self.wireless_container = tk.Frame(content, bg=self.BG)
        self.wireless_container.pack(fill='x', pady=(0, 2))

        ip_frame = tk.Frame(self.wireless_container, bg=self.BG)
        ip_frame.pack(fill='x', pady=(2, 4))

        tk.Label(ip_frame, text="Phone IP:", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 6))

        self.ip_entry = tk.Entry(ip_frame, bg=self.BG_INPUT, fg=self.FG,
                                insertbackground=self.FG, font=('Consolas', 10),
                                relief='flat', width=16)
        self.ip_entry.pack(side='left', padx=(0, 6), ipady=3)
        if self.phone_ip:
            self.ip_entry.insert(0, self.phone_ip)

        self.btn_connect_wifi = tk.Button(ip_frame, text="📶 Connect IP",
                                         command=self._connect_wifi,
                                         bg='#1e3a5f', fg='white', font=('Segoe UI', 9, 'bold'),
                                         relief='flat', padx=10, pady=3, cursor='hand2',
                                         activebackground='#2e4a6f')
        self.btn_connect_wifi.pack(side='left')

        # Setup buttons row
        setup_btn_row = tk.Frame(self.wireless_container, bg=self.BG)
        setup_btn_row.pack(fill='x', pady=(2, 4))

        self.btn_usb_setup = tk.Button(setup_btn_row, text="🔌 Setup via USB",
                                      command=self._setup_adb_wifi,
                                      bg='#2a2a4a', fg=self.FG, font=('Segoe UI', 9),
                                      relief='flat', padx=10, pady=4, cursor='hand2',
                                      activebackground='#3a3a5a')
        self.btn_usb_setup.pack(side='left', fill='x', expand=True, padx=(0, 4))

        self.btn_pair_wireless = tk.Button(setup_btn_row, text="📲 Pair Wireless (Android 11+)",
                                          command=self._pair_wireless_dialog,
                                          bg='#2a2a4a', fg=self.FG, font=('Segoe UI', 9),
                                          relief='flat', padx=10, pady=4, cursor='hand2',
                                          activebackground='#3a3a5a')
        self.btn_pair_wireless.pack(side='right', fill='x', expand=True)

        # USB help label (shown when USB mode is selected)
        self.usb_help_label = tk.Label(content, text="⚡ USB Mode: Phone ko USB cable se lagao (Debugging ON) aur Start Mirroring dabao!",
                                       bg='#12233c', fg='#7ec8e3', font=('Segoe UI', 9), padx=10, pady=8,
                                       relief='flat')

        # Step 3 Marker (for dynamic packing)
        self.step3_marker = tk.Frame(content, bg=self.BG, height=1)
        self.step3_marker.pack(fill='x', pady=0)

        # ── Step 2: Settings ──
        self._make_section(content, "2. Performance & Display Settings",
            "FPS aur Resolution choose karein.")

        # Frame Rate (FPS) options
        fps_frame = tk.Frame(content, bg=self.BG)
        fps_frame.pack(fill='x', pady=(2, 3))

        tk.Label(fps_frame, text="⚡ FPS:", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 6))

        self.fps_var = tk.StringVar(value='60')
        for val, label in [('60', '60 FPS'), ('90', '90 FPS'), ('120', '120 FPS'), ('max', 'Auto/Max')]:
            tk.Radiobutton(fps_frame, text=label, variable=self.fps_var, value=val,
                          bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                          activebackground=self.BG, activeforeground=self.ACCENT,
                          font=('Segoe UI', 9)).pack(side='left', padx=4)

        # Resolution options
        res_frame = tk.Frame(content, bg=self.BG)
        res_frame.pack(fill='x', pady=(2, 3))

        tk.Label(res_frame, text="📐 Res:", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 8))

        self.res_var = tk.StringVar(value='1080')
        for val, label in [('720', '720p'), ('1080', '1080p FHD'), ('native', 'Native')]:
            tk.Radiobutton(res_frame, text=label, variable=self.res_var, value=val,
                          bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                          activebackground=self.BG, activeforeground=self.ACCENT,
                          font=('Segoe UI', 9)).pack(side='left', padx=5)

        # Codec options
        codec_frame = tk.Frame(content, bg=self.BG)
        codec_frame.pack(fill='x', pady=(2, 4))

        tk.Label(codec_frame, text="🎬 Codec:", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 4))

        self.codec_var = tk.StringVar(value='h265')
        for val, label in [('h265', 'H.265 / HEVC (Zero-Lag)'), ('h264', 'H.264')]:
            tk.Radiobutton(codec_frame, text=label, variable=self.codec_var, value=val,
                          bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                          activebackground=self.BG, activeforeground=self.ACCENT,
                          font=('Segoe UI', 9)).pack(side='left', padx=4)

        # Options checkbuttons
        opt_frame2 = tk.Frame(content, bg=self.BG)
        opt_frame2.pack(fill='x', pady=(2, 4))

        self.zero_lag_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame2, text="🚀 Zero-Lag", variable=self.zero_lag_var,
                      bg=self.BG, fg=self.ACCENT, selectcolor=self.BG_INPUT,
                      activebackground=self.BG, font=('Segoe UI', 9, 'bold')).pack(side='left', padx=3)

        self.fullscreen_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt_frame2, text="Fullscreen", variable=self.fullscreen_var,
                      bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                      activebackground=self.BG, font=('Segoe UI', 9)).pack(side='left', padx=3)

        self.stay_awake_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame2, text="Stay Awake", variable=self.stay_awake_var,
                      bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                      activebackground=self.BG, font=('Segoe UI', 9)).pack(side='left', padx=3)

        self.show_fps_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame2, text="Show FPS", variable=self.show_fps_var,
                      bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                      activebackground=self.BG, font=('Segoe UI', 9)).pack(side='left', padx=3)

        self.no_audio_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt_frame2, text="No Audio", variable=self.no_audio_var,
                      bg=self.BG, fg=self.FG, selectcolor=self.BG_INPUT,
                      activebackground=self.BG, font=('Segoe UI', 9)).pack(side='left', padx=3)

        # ── Step 3: Screen Recording ──
        rec_frame = tk.Frame(content, bg=self.BG_CARD, highlightbackground='#3a1e28', highlightthickness=1, padx=8, pady=5)
        rec_frame.pack(fill='x', pady=(4, 6))

        self.record_var = tk.BooleanVar(value=False)
        tk.Checkbutton(rec_frame, text="🔴 Record Screen (Real-Time FPS: 60/90/120)",
                       variable=self.record_var,
                       bg=self.BG_CARD, fg='#ff6b6b', selectcolor=self.BG_INPUT,
                       activebackground=self.BG_CARD, activeforeground='#ff8b8b',
                       font=('Segoe UI', 9, 'bold')).pack(side='left', padx=2)

        tk.Button(rec_frame, text="📁 Open Recordings", command=self._open_recordings_folder,
                  bg='#2a1e28', fg='#ffb3ba', font=('Segoe UI', 8, 'bold'),
                  relief='flat', padx=8, pady=2, cursor='hand2',
                  activebackground='#3a2835').pack(side='right', padx=2)

        # ── Log Section ──
        log_frame = tk.Frame(content, bg=self.BG_CARD, highlightbackground='#2a2a4a',
                            highlightthickness=1)
        log_frame.pack(fill='x', pady=(4, 4))

        tk.Label(log_frame, text="System Log", bg=self.BG_CARD, fg=self.FG_DIM,
                font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=8, pady=(4, 1))

        self.log_text = tk.Text(log_frame, bg='#0a0a16', fg='#8888bb',
                               font=('Consolas', 8), height=3, relief='flat',
                               insertbackground=self.FG, wrap='word', state='disabled')
        self.log_text.pack(fill='x', padx=6, pady=(0, 4))

    def _make_section(self, parent, title, desc):
        """Create a section header."""
        tk.Label(parent, text=title, bg=self.BG, fg=self.FG,
                font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=4, pady=(6, 0))
        tk.Label(parent, text=desc, bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 8)).pack(anchor='w', padx=4, pady=(0, 2))

    def _set_dot(self, color):
        """Set status dot color."""
        self.status_dot.delete('all')
        self.status_dot.create_oval(1, 1, 11, 11, fill=color, outline=color)

    def _set_status(self, text, color=None):
        """Update status bar."""
        self.status_label.config(text=text)
        if color:
            self._set_dot(color)

    def _log(self, msg):
        """Append to log."""
        self.log_text.config(state='normal')
        self.log_text.insert('end', f"{msg}\n")
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def _on_mode_change(self):
        """Handle switching between USB and Wireless connection modes."""
        mode = self.conn_mode_var.get()
        if mode == 'usb':
            self.wireless_container.pack_forget()
            self.usb_help_label.pack(fill='x', pady=(4, 6), before=self.step3_marker)
            self._set_status("USB Mode: Connect phone via USB & start", self.GREEN)
            self.btn_mirror.config(state='normal')
            self._log("[MODE] Switched to Direct USB Cable Mode (Ultra-Low Latency <15ms).")
        else:
            self.usb_help_label.pack_forget()
            self.wireless_container.pack(fill='x', pady=(0, 4), before=self.step3_marker)
            self._log("[MODE] Switched to Wireless Hotspot Mode.")
            self._auto_detect_connected_device()

    def _open_recordings_folder(self):
        """Open recordings folder in Windows Explorer."""
        rec_dir = os.path.join(APP_DIR, 'recordings')
        os.makedirs(rec_dir, exist_ok=True)
        try:
            os.startfile(rec_dir)
        except Exception:
            messagebox.showinfo("Recordings", f"Recordings folder:\n{rec_dir}")

    # ─── Tools Download ────────────────────────────────────────────────

    def _check_tools(self):
        """Check if scrcpy and ADB are available and auto-detect connected phone."""
        if os.path.exists(SCRCPY_PATH) and os.path.exists(ADB_PATH):
            self.tools_status.config(text="✅ Tools installed", fg=self.GREEN)
            self.btn_download.config(text="✅ Tools Ready", state='disabled', bg='#1a3a1a')
            self._log("[OK] scrcpy and ADB found.")
            self._auto_detect_connected_device()
        else:
            self.tools_status.config(text="❌ Tools not found - download required", fg=self.RED)
            self._set_status("Download tools first (Step 1)", self.RED)
            self._log("[!] scrcpy not found. Click 'Download Tools'.")

    def _auto_detect_connected_device(self):
        """Check adb devices and auto-select active connection."""
        try:
            out, _, _ = run_cmd([ADB_PATH, 'devices'])
            lines = [l.strip() for l in out.split('\n') if l.strip() and 'List of devices' not in l]
            devices = [l.split()[0] for l in lines if '\tdevice' in l]

            # Look for wireless IP connection first
            wireless = [d for d in devices if ':' in d]
            if wireless:
                ip_part = wireless[0].split(':')[0]
                self.phone_ip = ip_part
                self.ip_entry.delete(0, 'end')
                self.ip_entry.insert(0, ip_part)
                self._set_status(f"Connected wirelessly: {ip_part}!", self.GREEN)
                self._log(f"[OK] Phone detected wirelessly: {wireless[0]}")
                self.btn_mirror.config(state='normal')
                return

            # If USB device found
            if devices:
                self._set_status("Phone connected via USB! Ready to mirror.", self.GREEN)
                self._log(f"[OK] USB device detected: {devices[0]}")
                self.btn_mirror.config(state='normal')
                return

            if self.phone_ip:
                self.ip_entry.delete(0, 'end')
                self.ip_entry.insert(0, self.phone_ip)
                self._set_status("Click 'Connect to Phone IP'", self.ORANGE)
            else:
                self._set_status("Connect phone via Hotspot or USB", self.ORANGE)
        except Exception as e:
            self._set_status("Tools ready. Setup phone connection.", self.ORANGE)

    def _download_tools(self):
        """Download scrcpy in background thread."""
        self.btn_download.config(text="⏳ Downloading...", state='disabled', bg='#3a3a5a')
        self._set_status("Downloading scrcpy...", self.ORANGE)
        self._log("[...] Downloading scrcpy from GitHub...")
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        """Background worker for downloading scrcpy."""
        try:
            os.makedirs(TOOLS_DIR, exist_ok=True)

            # Download
            self._log(f"[...] URL: {SCRCPY_URL}")
            urllib.request.urlretrieve(SCRCPY_URL, SCRCPY_ZIP, self._download_progress)

            # Extract
            self._log("[...] Extracting...")
            self.root.after(0, lambda: self._set_status("Extracting...", self.ORANGE))

            with zipfile.ZipFile(SCRCPY_ZIP, 'r') as z:
                z.extractall(TOOLS_DIR)

            # Find the extracted folder (usually scrcpy-win64-vX.X)
            extracted_dirs = [d for d in os.listdir(TOOLS_DIR)
                            if os.path.isdir(os.path.join(TOOLS_DIR, d)) and 'scrcpy' in d.lower()]

            if extracted_dirs and not os.path.exists(SCRCPY_DIR):
                src = os.path.join(TOOLS_DIR, extracted_dirs[0])
                shutil.move(src, SCRCPY_DIR)
            elif extracted_dirs and os.path.exists(SCRCPY_DIR):
                # Already exists, copy contents
                src = os.path.join(TOOLS_DIR, extracted_dirs[0])
                for item in os.listdir(src):
                    s = os.path.join(src, item)
                    d = os.path.join(SCRCPY_DIR, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                shutil.rmtree(src)

            # Cleanup zip
            if os.path.exists(SCRCPY_ZIP):
                os.remove(SCRCPY_ZIP)

            self._log("[OK] scrcpy downloaded and extracted!")
            self.root.after(0, self._check_tools)

        except Exception as e:
            self._log(f"[ERROR] Download failed: {e}")
            self.root.after(0, lambda: self._set_status(f"Download failed: {e}", self.RED))
            self.root.after(0, lambda: self.btn_download.config(
                text="🔄 Retry Download", state='normal', bg=self.ACCENT))

    def _download_progress(self, block_num, block_size, total_size):
        """Update download progress."""
        if total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            self.root.after(0, lambda p=percent: self.btn_download.config(
                text=f"⏳ Downloading... {p}%"))

    # ─── ADB Setup ─────────────────────────────────────────────────────

    def _setup_adb_wifi(self):
        """Setup ADB over WiFi using USB connection."""
        if not os.path.exists(ADB_PATH):
            messagebox.showerror("Error", "ADB not found! Download tools first (Step 1).")
            return

        self._set_status("Setting up ADB WiFi...", self.ORANGE)
        self._log("[...] Setting up ADB over WiFi...")
        threading.Thread(target=self._setup_adb_worker, daemon=True).start()

    def _setup_adb_worker(self):
        """Background worker for ADB WiFi setup."""
        # Check USB connection
        out, err, code = run_cmd([ADB_PATH, 'devices'])
        self._log(f"[ADB] devices: {out}")

        lines = [l.strip() for l in out.split('\n') if l.strip() and 'List' not in l]
        usb_devices = [l for l in lines if not l.startswith('*') and '\t' in l]

        if not usb_devices:
            self._log("[!] No USB device found. Connect phone via USB and enable USB Debugging!")
            self.root.after(0, lambda: messagebox.showwarning("No Device",
                "Phone USB se connect karo!\n\n"
                "Steps:\n"
                "1. Settings → About Phone → Build Number 7 times tap\n"
                "2. Settings → Developer Options → USB Debugging ON\n"
                "3. Phone ko USB cable se PC se connect karo\n"
                "4. Phone pe 'Allow USB Debugging' permission do"))
            self.root.after(0, lambda: self._set_status("Connect phone via USB first", self.RED))
            return

        # Get phone IP
        ip_out, _, _ = run_cmd([ADB_PATH, 'shell', 'ip', 'route'])
        self._log(f"[ADB] ip route: {ip_out}")

        phone_ip = None
        # Try to find IP from ip route
        for line in ip_out.split('\n'):
            match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', line)
            if match:
                ip = match.group(1)
                if not ip.startswith('127.'):
                    phone_ip = ip
                    break

        if not phone_ip:
            # Try wlan0
            ip_out2, _, _ = run_cmd([ADB_PATH, 'shell', 'ip', 'addr', 'show', 'wlan0'])
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ip_out2)
            if match:
                phone_ip = match.group(1)

        if not phone_ip:
            # Fallback: try ifconfig
            ip_out3, _, _ = run_cmd([ADB_PATH, 'shell', 'ifconfig', 'wlan0'])
            match = re.search(r'inet addr:(\d+\.\d+\.\d+\.\d+)', ip_out3)
            if match:
                phone_ip = match.group(1)

        if phone_ip:
            self._log(f"[OK] Phone IP found: {phone_ip}")
            self.root.after(0, lambda: self.ip_entry.delete(0, 'end'))
            self.root.after(0, lambda: self.ip_entry.insert(0, phone_ip))
            self.phone_ip = phone_ip
            self.config['phone_ip'] = phone_ip
            save_config(self.config)
        else:
            self._log("[!] Could not auto-detect phone IP. Enter manually.")

        # Enable ADB TCP mode
        self._log("[...] Enabling ADB TCP mode on port 5555...")
        out, err, code = run_cmd([ADB_PATH, 'tcpip', str(ADB_PORT)])
        self._log(f"[ADB] tcpip: {out} {err}")

        time.sleep(2)

        if phone_ip:
            # Connect wirelessly
            self._log(f"[...] Connecting to {phone_ip}:{ADB_PORT}...")
            out, err, code = run_cmd([ADB_PATH, 'connect', f'{phone_ip}:{ADB_PORT}'])
            self._log(f"[ADB] connect: {out} {err}")

            if 'connected' in out.lower():
                self._log("[OK] ADB WiFi connected! Ab USB nikal sakte ho.")
                self.root.after(0, lambda: self._set_status(
                    f"Connected to {phone_ip}! Ready to mirror.", self.GREEN))
                self.root.after(0, lambda: self.btn_mirror.config(state='normal'))
            else:
                self._log("[!] Connection failed. Check if phone is on same network.")
                self.root.after(0, lambda: self._set_status("WiFi connection failed", self.RED))
        else:
            self._log("[!] Enter phone IP manually and click 'Connect via WiFi'")
            self.root.after(0, lambda: self._set_status("Enter phone IP manually", self.ORANGE))

    def _pair_wireless_dialog(self):
        """Open Wireless Debugging Pairing Dialog for Android 11+."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Android 11+ Wireless Pairing")
        dlg.geometry("420x360")
        dlg.configure(bg=self.BG_CARD)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="📲 Wireless Pairing (No USB)", bg=self.BG_CARD, fg=self.ACCENT,
                 font=('Segoe UI', 13, 'bold')).pack(pady=(12, 4))
        tk.Label(dlg, text="Phone Settings → Developer Options → Wireless Debugging ON\nTap 'Pair device with pairing code'",
                 bg=self.BG_CARD, fg=self.FG_DIM, font=('Segoe UI', 9), justify='center').pack(pady=(0, 10))

        form = tk.Frame(dlg, bg=self.BG_CARD)
        form.pack(fill='x', padx=24)

        tk.Label(form, text="Pairing IP & Port (e.g. 192.168.1.13:37123):", bg=self.BG_CARD, fg=self.FG,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 2))
        entry_pair_addr = tk.Entry(form, bg=self.BG_INPUT, fg=self.FG, font=('Consolas', 10), relief='flat')
        entry_pair_addr.pack(fill='x', ipady=4, pady=(0, 8))
        if self.phone_ip:
            entry_pair_addr.insert(0, f"{self.phone_ip}:")

        tk.Label(form, text="6-Digit Pairing Code:", bg=self.BG_CARD, fg=self.FG,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 2))
        entry_code = tk.Entry(form, bg=self.BG_INPUT, fg=self.FG, font=('Consolas', 10), relief='flat')
        entry_code.pack(fill='x', ipady=4, pady=(0, 8))

        tk.Label(form, text="Main Wireless Debugging IP & Port (Shown on main screen):", bg=self.BG_CARD, fg=self.FG,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 2))
        entry_conn_addr = tk.Entry(form, bg=self.BG_INPUT, fg=self.FG, font=('Consolas', 10), relief='flat')
        entry_conn_addr.pack(fill='x', ipady=4, pady=(0, 14))

        def do_pair():
            pair_addr = entry_pair_addr.get().strip()
            code = entry_code.get().strip()
            conn_addr = entry_conn_addr.get().strip()
            if not pair_addr or not code:
                messagebox.showwarning("Incomplete", "Pairing IP:Port aur Code dono enter karo!", parent=dlg)
                return
            dlg.destroy()
            self._pair_worker(pair_addr, code, conn_addr)

        tk.Button(dlg, text="⚡ Pair & Connect", command=do_pair,
                  bg=self.ACCENT, fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', pady=8, cursor='hand2').pack(fill='x', padx=24)

    def _pair_worker(self, pair_addr, code, conn_addr):
        def run():
            self._set_status(f"Pairing with {pair_addr}...", self.ORANGE)
            self._log(f"[ADB] pairing: adb pair {pair_addr} {code}")
            out, err, _ = run_cmd([ADB_PATH, 'pair', pair_addr, code])
            self._log(f"[ADB] pair result: {out} {err}")

            if "successfully paired" in out.lower():
                self._log("[OK] Device paired successfully!")
                target_to_connect = conn_addr if conn_addr else pair_addr.split(':')[0] + f":{ADB_PORT}"
                self._log(f"[ADB] connecting to: {target_to_connect}")
                out_c, err_c, _ = run_cmd([ADB_PATH, 'connect', target_to_connect])
                self._log(f"[ADB] connect result: {out_c} {err_c}")
                if "connected" in out_c.lower():
                    self.phone_ip = target_to_connect.split(':')[0]
                    self.config['phone_ip'] = self.phone_ip
                    save_config(self.config)
                    self.root.after(0, lambda: self.ip_entry.delete(0, 'end'))
                    self.root.after(0, lambda: self.ip_entry.insert(0, self.phone_ip))
                    self.root.after(0, lambda: self._set_status(f"Connected to {self.phone_ip}!", self.GREEN))
                    self.root.after(0, lambda: self.btn_mirror.config(state='normal'))
                else:
                    self.root.after(0, lambda: self._set_status("Paired! Enter connect port above", self.ORANGE))
            else:
                self.root.after(0, lambda: self._set_status("Pairing failed! Check code.", self.RED))

        threading.Thread(target=run, daemon=True).start()

    def _connect_wifi(self):
        """Connect to phone via WiFi (no USB needed if already set up)."""
        phone_ip = self.ip_entry.get().strip()
        if not phone_ip:
            messagebox.showwarning("IP Required",
                "Phone ka IP address enter karo!\n\n"
                "Phone pe check karo:\n"
                "Settings → WiFi → Connected network → IP Address")
            return

        if not os.path.exists(ADB_PATH):
            messagebox.showerror("Error", "ADB not found! Download tools first (Step 1).")
            return

        self.phone_ip = phone_ip
        self.config['phone_ip'] = phone_ip
        save_config(self.config)

        self._set_status(f"Connecting to {phone_ip}...", self.ORANGE)
        self._log(f"[...] Connecting to {phone_ip}:{ADB_PORT}...")
        threading.Thread(target=self._connect_wifi_worker, daemon=True).start()

    def _connect_wifi_worker(self):
        """Background worker for WiFi connection."""
        phone_ip = self.phone_ip
        out, err, code = run_cmd([ADB_PATH, 'connect', f'{phone_ip}:{ADB_PORT}'])
        self._log(f"[ADB] connect: {out} {err}")

        if 'connected' in out.lower() or 'already' in out.lower():
            self._log(f"[OK] Connected to {phone_ip}!")
            self.root.after(0, lambda: self._set_status(
                f"Connected to {phone_ip}! Ready to mirror.", self.GREEN))
            self.root.after(0, lambda: self.btn_mirror.config(state='normal'))
        else:
            self._log(f"[!] Failed: {out} {err}")
            self._log("[!] Make sure:")
            self._log("    - Phone is connected to PC's hotspot")
            self._log("    - USB Debugging was enabled before")
            self._log("    - ADB WiFi was set up via USB (Step 2)")
            self.root.after(0, lambda: self._set_status("Connection failed", self.RED))

    # ─── Mirroring ─────────────────────────────────────────────────────

    def _toggle_mirror(self):
        """Start or stop mirroring."""
        if self.is_mirroring:
            self._stop_mirror()
        else:
            self._start_mirror()

    def _start_mirror(self):
        """Start screen mirroring with scrcpy."""
        if not os.path.exists(SCRCPY_PATH):
            messagebox.showerror("Error", "scrcpy not found! Download tools first.")
            return

        # Build scrcpy command
        cmd = [SCRCPY_PATH]

        # Device and connection mode
        is_usb = (self.conn_mode_var.get() == 'usb')
        if is_usb:
            cmd.append('-d')  # Strictly use USB connected device
            self._log("[START] Mode: Direct USB Cable (Fastest, ~15ms latency)")
        else:
            phone_ip = self.ip_entry.get().strip() or self.phone_ip
            if phone_ip:
                target = f"{phone_ip}:{ADB_PORT}" if ":" not in phone_ip else phone_ip
                cmd.extend(['-s', target])
                self._log(f"[START] Mode: Wireless Hotspot ({target})")
            else:
                cmd.append('-e')
                self._log("[START] Mode: Wireless Hotspot (TCP/IP)")

        # Codec selection
        codec = self.codec_var.get()
        cmd.extend(['--video-codec', codec])

        # Zero-Lag / Low Latency optimizations
        if self.zero_lag_var.get():
            cmd.extend([
                '--video-buffer=0',          # Drop delayed frames immediately (no latency buildup)
                '--audio-buffer=20',         # Minimal 20ms audio buffer
                '--render-driver=direct3d',  # Hardware-accelerated Direct3D renderer for Windows
            ])

        # FPS and Bitrate settings (USB gets high 24M bitrate, Wi-Fi tuned to 12M)
        fps = self.fps_var.get()
        bitrate_120 = '24M' if is_usb else '12M'
        bitrate_90  = '18M' if is_usb else '10M'
        bitrate_60  = '12M' if is_usb else '8M'
        bitrate_max = '24M' if is_usb else '14M'

        if fps == '60':
            cmd.extend(['--max-fps', '60', '--video-bit-rate', bitrate_60])
        elif fps == '90':
            cmd.extend(['--max-fps', '90', '--video-bit-rate', bitrate_90])
        elif fps == '120':
            cmd.extend(['--max-fps', '120', '--video-bit-rate', bitrate_120])
        elif fps == 'max':
            cmd.extend(['--video-bit-rate', bitrate_max])

        # Resolution settings
        res = self.res_var.get()
        if res == '720':
            cmd.extend(['--max-size', '1280'])
        elif res == '1080':
            cmd.extend(['--max-size', '1920'])
        # 'native' leaves full resolution without --max-size

        # Show FPS counter
        if self.show_fps_var.get():
            cmd.append('--print-fps')

        # Options
        if self.fullscreen_var.get():
            cmd.append('--fullscreen')
        if self.stay_awake_var.get():
            cmd.append('--stay-awake')
        if self.no_audio_var.get():
            cmd.append('--no-audio')

        # Screen Recording
        if self.record_var.get():
            rec_dir = os.path.join(APP_DIR, 'recordings')
            os.makedirs(rec_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fps_tag = f"{fps}fps" if fps != 'max' else 'maxfps'
            rec_file = os.path.join(rec_dir, f"recording_{timestamp}_{fps_tag}.mp4")
            cmd.extend(['--record', rec_file, '--record-format', 'mp4'])
            self.current_recording = rec_file
            self._log(f"[REC] 🔴 Recording at real-time {fps_tag}: {os.path.basename(rec_file)}")
        else:
            self.current_recording = None

        # Window title
        cmd.extend(['--window-title', 'Mirror Cast - Phone Screen'])

        self._log(f"[...] Starting: {' '.join(cmd)}")
        self._set_status("Starting screen mirror...", self.ORANGE)

        try:
            # Set scrcpy directory as working dir so it finds adb
            self.mirror_process = subprocess.Popen(
                cmd, cwd=SCRCPY_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            self.is_mirroring = True
            self.btn_mirror.config(text="⏹  Stop Mirroring", bg=self.RED,
                                  activebackground='#cc3333')
            self._set_status("Mirroring active!", self.GREEN)
            self._log("[OK] Screen mirroring started!")

            # Monitor process in background
            threading.Thread(target=self._monitor_mirror, daemon=True).start()

        except Exception as e:
            self._log(f"[ERROR] Failed to start: {e}")
            self._set_status(f"Error: {e}", self.RED)

    def _stop_mirror(self):
        """Stop screen mirroring."""
        if self.mirror_process:
            try:
                self.mirror_process.terminate()
                self.mirror_process.wait(timeout=5)
            except Exception:
                try:
                    self.mirror_process.kill()
                except Exception:
                    pass
            self.mirror_process = None

        self.is_mirroring = False
        self.btn_mirror.config(text="🚀  Start Mirroring", bg=self.ACCENT,
                              activebackground='#3a7aee')
        self._set_status("Mirroring stopped.", self.ORANGE)
        self._log("[OK] Mirroring stopped.")
        if self.current_recording:
            rec_name = os.path.basename(self.current_recording)
            self._log(f"[REC] ✅ Saved: recordings/{rec_name}")
            self.current_recording = None

    def _monitor_mirror(self):
        """Monitor the scrcpy process."""
        if self.mirror_process:
            stdout, stderr = self.mirror_process.communicate()
            if stdout:
                self._log(f"[scrcpy] {stdout.decode(errors='replace').strip()}")
            if stderr:
                self._log(f"[scrcpy] {stderr.decode(errors='replace').strip()}")

            exit_code = self.mirror_process.returncode
            if exit_code != 0 and self.is_mirroring:
                self._log(f"[!] scrcpy exited with code {exit_code}")
                self.root.after(0, self._stop_mirror)

    # ─── Run ───────────────────────────────────────────────────────────

    def run(self):
        """Start the application."""
        self.root.mainloop()


# ─── Entry Point ──────────────────────────────────────────────────────

if __name__ == '__main__':
    app = MirrorCastApp()
    app.run()
