"""
SnapEdge Desktop Companion HUD - Floating Desktop Copilot Widget
Snapdragon® AI Lab Build & Present Challenge
Optimized for Snapdragon-Powered HP PCs (Qualcomm® Hexagon™ NPU 45 TOPS)

A native, lightweight floating desktop companion widget built with Python standard tkinter.
Can float over Microsoft Outlook, Word, Teams, or Excel.
"""

import json
import sys
import threading
import tkinter as tk
from tkinter import ttk
import urllib.request
import urllib.error

API_BASE = "http://127.0.0.1:8000"

class SnapEdgeDesktopWidget:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SnapEdge Copilot HUD")
        self.root.geometry("390x440+100+100")
        self.root.overrideredirect(True)  # Frameless floating HUD
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.95)  # Executive semi-transparency
        self.root.configure(bg="#0d1015")

        self.is_collapsed = False
        self.drag_x = 0
        self.drag_y = 0

        self.setup_ui()
        self.check_backend_status()

    def setup_ui(self):
        # 1. Custom Draggable Title Bar
        self.title_bar = tk.Frame(self.root, bg="#161a22", height=34, cursor="fleur")
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.bind("<Button-1>", self.start_drag)
        self.title_bar.bind("<B1-Motion>", self.do_drag)

        title_icon = tk.Label(self.title_bar, text=" Snapdragon®", fg="#e11425", bg="#161a22", font=("Segoe UI", 9, "bold"))
        title_icon.pack(side=tk.LEFT, padx=(8, 2))
        title_icon.bind("<Button-1>", self.start_drag)
        title_icon.bind("<B1-Motion>", self.do_drag)

        title_text = tk.Label(self.title_bar, text="| SnapEdge HUD", fg="#e6edf3", bg="#161a22", font=("Segoe UI", 9))
        title_text.pack(side=tk.LEFT)
        title_text.bind("<Button-1>", self.start_drag)
        title_text.bind("<B1-Motion>", self.do_drag)

        btn_close = tk.Label(self.title_bar, text="✕", fg="#8e9aab", bg="#161a22", font=("Segoe UI", 9), cursor="hand2")
        btn_close.pack(side=tk.RIGHT, padx=10)
        btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        self.btn_min = tk.Label(self.title_bar, text="—", fg="#8e9aab", bg="#161a22", font=("Segoe UI", 9), cursor="hand2")
        self.btn_min.pack(side=tk.RIGHT, padx=5)
        self.btn_min.bind("<Button-1>", lambda e: self.toggle_collapse())

        # 2. Main Body Container
        self.body_frame = tk.Frame(self.root, bg="#0d1015", padx=14, pady=10)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

        # Status Bar
        self.status_bar = tk.Frame(self.body_frame, bg="#1c2026", padx=8, pady=4)
        self.status_bar.pack(fill=tk.X, pady=(0, 10))

        self.status_dot = tk.Label(self.status_bar, text="●", fg="#20c997", bg="#1c2026", font=("Segoe UI", 8))
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))

        self.status_label = tk.Label(self.status_bar, text="Hexagon NPU Active (45 TOPS)", fg="#8e9aab", bg="#1c2026", font=("Segoe UI", 8))
        self.status_label.pack(side=tk.LEFT)

        self.gov_badge = tk.Label(self.status_bar, text="Eco-Governor", fg="#e11425", bg="#1c2026", font=("Segoe UI", 8, "bold"))
        self.gov_badge.pack(side=tk.RIGHT)

        # Quick Action Buttons
        btn_row = tk.Frame(self.body_frame, bg="#0d1015")
        btn_row.pack(fill=tk.X, pady=(0, 8))

        self.btn_clipboard = tk.Button(
            btn_row, text=" Copilot Clipboard (NPU)", bg="#e11425", fg="#ffffff",
            activebackground="#ff3344", activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), bd=0, relief=tk.FLAT, pady=6, cursor="hand2",
            command=self.run_clipboard_copilot
        )
        self.btn_clipboard.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_sim = tk.Button(
            btn_row, text="⚡ Sim Delay", bg="#282f3a", fg="#e6edf3",
            activebackground="#3b4453", activeforeground="#ffffff",
            font=("Segoe UI", 9), bd=0, relief=tk.FLAT, pady=6, cursor="hand2",
            command=self.quick_simulate_delay
        )
        self.btn_sim.pack(side=tk.LEFT, padx=(4, 0))

        # Output Area
        self.output_label = tk.Label(self.body_frame, text="AI Response / Simulation Trace:", fg="#8e9aab", bg="#0d1015", font=("Segoe UI", 8, "bold"))
        self.output_label.pack(anchor="w", pady=(2, 4))

        self.text_output = tk.Text(
            self.body_frame, bg="#161a22", fg="#e6edf3", insertbackground="#e6edf3",
            font=("Segoe UI", 9), bd=1, relief=tk.FLAT, wrap=tk.WORD, height=10
        )
        self.text_output.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.text_output.insert(tk.END, "Ready on Snapdragon-powered HP PC.\n\nClick 'Copilot Clipboard' to analyze copied text or emails, or 'Sim Delay' to test schedule ripple.")

        # Bottom Action Bar
        bottom_bar = tk.Frame(self.body_frame, bg="#0d1015")
        bottom_bar.pack(fill=tk.X)

        self.btn_copy = tk.Button(
            bottom_bar, text="Copy Response", bg="#1f242d", fg="#8e9aab",
            font=("Segoe UI", 8), bd=0, relief=tk.FLAT, pady=3, padx=8, cursor="hand2",
            command=self.copy_to_clipboard
        )
        self.btn_copy.pack(side=tk.LEFT)

        self.hotkey_info = tk.Label(bottom_bar, text="Press Esc to hide", fg="#6c798c", bg="#0d1015", font=("Segoe UI", 8))
        self.hotkey_info.pack(side=tk.RIGHT)

        # Global hotkey binding when widget is focused
        self.root.bind("<Escape>", lambda e: self.toggle_collapse())

    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_x)
        y = self.root.winfo_y() + (event.y - self.drag_y)
        self.root.geometry(f"+{x}+{y}")

    def toggle_collapse(self):
        if not self.is_collapsed:
            self.body_frame.pack_forget()
            self.root.geometry("220x34")
            self.btn_min.config(text="□")
            self.is_collapsed = True
        else:
            self.root.geometry("390x440")
            self.body_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_min.config(text="—")
            self.is_collapsed = False

    def copy_to_clipboard(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.btn_copy.config(text="Copied!", fg="#20c997")
            self.root.after(1500, lambda: self.btn_copy.config(text="Copy Response", fg="#8e9aab"))

    def check_backend_status(self):
        def worker():
            try:
                req = urllib.request.Request(f"{API_BASE}/api/status", headers={"User-Agent": "SnapEdgeHUD/1.0"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"{data.get('npu_hardware', 'Hexagon NPU')} | 100% Offline"
                        ))
            except Exception:
                self.root.after(0, lambda: self.status_label.config(
                    text="Server Offline (Launch with run.ps1)", fg="#e11425"
                ))
                self.root.after(0, lambda: self.status_dot.config(fg="#e11425"))
        threading.Thread(target=worker, daemon=True).start()

    def run_clipboard_copilot(self):
        try:
            clip_text = self.root.clipboard_get().strip()
        except tk.TclError:
            clip_text = ""

        if not clip_text:
            clip_text = "Review project milestones with client tomorrow and confirm delivery date."

        self.btn_clipboard.config(text="Processing on NPU...", state=tk.DISABLED)
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, f"Input: \"{clip_text[:80]}...\"\n\nExecuting Phi-3-mini INT4 on Hexagon NPU...")

        def worker():
            payload = json.dumps({"text": clip_text, "mode": "auto"}).encode("utf-8")
            req = urllib.request.Request(
                f"{API_BASE}/api/copilot",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    result = data.get("result_text", "No response.")
                    latency = data.get("latency_ms", 22)
                    model = data.get("model", "Phi-3-mini-4k-instruct-ONNX")

                    def update_ui():
                        self.text_output.delete("1.0", tk.END)
                        self.text_output.insert(tk.END, f"[{model} | {latency} ms]\n\n{result}")
                        self.btn_clipboard.config(text=" Copilot Clipboard (NPU)", state=tk.NORMAL)
                    self.root.after(0, update_ui)
            except Exception as e:
                def err_ui():
                    self.text_output.delete("1.0", tk.END)
                    self.text_output.insert(tk.END, f"Inference Error: {str(e)}\n\nEnsure SnapEdge server is running at {API_BASE}")
                    self.btn_clipboard.config(text=" Copilot Clipboard (NPU)", state=tk.NORMAL)
                self.root.after(0, err_ui)

        threading.Thread(target=worker, daemon=True).start()

    def quick_simulate_delay(self):
        prompt = "Delay meeting_001 by 45 minutes"
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, f"Simulating: \"{prompt}\" via AHEAD O(V+E) Engine...\n")

        def worker():
            payload = json.dumps({"prompt": prompt}).encode("utf-8")
            req = urllib.request.Request(
                f"{API_BASE}/api/simulate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    shifts = data.get("shifts", [])
                    out = f"Target: {data.get('target_event_id')} (+{data.get('total_shifts')} shifts)\n\n"
                    for s in shifts:
                        out += f"• [{s['event_id']}] ➔ {s['new_window']} (+{s['delay_mins']}m)\n  Cause: {s['message']}\n"
                    out += "\nVisit http://127.0.0.1:8000 to Auto-Resolve and sync calendar."

                    def update_ui():
                        self.text_output.delete("1.0", tk.END)
                        self.text_output.insert(tk.END, out)
                    self.root.after(0, update_ui)
            except Exception as e:
                def err_ui():
                    self.text_output.insert(tk.END, f"\nSimulation Error: {str(e)}")
                self.root.after(0, err_ui)

        threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    app = SnapEdgeDesktopWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
