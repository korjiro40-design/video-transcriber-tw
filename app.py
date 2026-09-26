import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FONT = ("Microsoft JhengHei UI", 10)
FONT_SMALL = ("Microsoft JhengHei UI", 9)
FONT_TITLE = ("Microsoft JhengHei UI", 20, "bold")


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


LOG_PATH = app_dir() / "error.log"


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_error(stage, exc):
    text = (
        f"影片逐字稿 TW 診斷記錄\n"
        f"時間：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"階段：{stage}\n"
        f"錯誤類型：{type(exc).__name__}\n"
        f"錯誤訊息：{exc}\n\n"
        f"完整 Traceback：\n{traceback.format_exc()}\n"
    )
    try:
        LOG_PATH.write_text(text, encoding="utf-8-sig")
    except Exception:
        pass
    return text


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("影片逐字稿 TW - 診斷版 V2")
        self.root.geometry("760x560")
        self.root.minsize(660, 500)
        self.files = []
        self.model = None

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="影片逐字稿", font=FONT_TITLE).pack(anchor="w")
        ttk.Label(frame, text="診斷版 V2：先用 CPU 確認整套流程正常，再啟用 GPU。", font=FONT).pack(anchor="w", pady=(4, 14))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="選取檔案", command=self.pick_files).pack(side="left")
        ttk.Button(buttons, text="清除", command=self.clear_files).pack(side="left", padx=8)
        self.start_btn = ttk.Button(buttons, text="開始生成逐字稿", command=self.start)
        self.start_btn.pack(side="right")

        self.listbox = tk.Listbox(frame, height=6, font=FONT)
        self.listbox.pack(fill="x", pady=12)
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="請先選取檔案")
        ttk.Label(frame, textvariable=self.status, font=FONT).pack(anchor="w", pady=(8, 5))

        ttk.Label(frame, text="執行記錄 / 錯誤診斷", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w", pady=(8, 4))
        self.logbox = tk.Text(frame, height=10, wrap="word", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True)
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text="複製記錄", command=self.copy_log).pack(side="left")
        ttk.Button(bottom, text="開啟 error.log", command=self.open_log).pack(side="left", padx=8)
        ttk.Label(bottom, text="本版固定 CPU 模式，避免 CUDA 先干擾診斷。", font=FONT_SMALL).pack(side="right")

    def log(self, text):
        def update():
            self.status.set(text)
            self.logbox.insert(tk.END, text + "\n")
            self.logbox.see(tk.END)
        self.root.after(0, update)

    def pick_files(self):
        paths = filedialog.askopenfilenames(title="選取影片或音訊", filetypes=[("影音檔案", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.wav *.flac *.aac"), ("所有檔案", "*.*")])
        if paths:
            self.files = [Path(p) for p in paths]
            self.listbox.delete(0, tk.END)
            for p in self.files:
                self.listbox.insert(tk.END, str(p))
            self.log(f"已選取 {len(self.files)} 個檔案")

    def clear_files(self):
        self.files = []
        self.listbox.delete(0, tk.END)
        self.log("已清除檔案")

    def copy_log(self):
        text = self.logbox.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        messagebox.showinfo("已複製", "執行記錄已複製到剪貼簿。")

    def open_log(self):
        if LOG_PATH.exists():
            os.startfile(LOG_PATH)
        else:
            messagebox.showinfo("尚無記錄", "目前還沒有 error.log。")

    def start(self):
        if not self.files:
            messagebox.showwarning("尚未選取檔案", "請先按『選取檔案』。")
            return
        self.start_btn.config(state="disabled")
        self.progress.start(10)
        self.logbox.delete("1.0", tk.END)
        threading.Thread(target=self.transcribe_all, daemon=True).start()

    def load_model(self):
        self.log("步驟 1/4：正在匯入 faster-whisper…")
        from faster_whisper import WhisperModel
        self.log("步驟 2/4：正在下載／載入 Whisper turbo 模型（第一次可能需數 GB）…")
        # 診斷版固定 CPU，確認 PyInstaller、模型下載與音訊解碼皆正常。
        self.model = WhisperModel("turbo", device="cpu", compute_type="int8")
        self.log("Whisper 模型載入成功（CPU int8）。")

    def transcribe_one(self, path, cc):
        self.log(f"步驟 3/4：開始辨識 {path.name}")
        segments, _ = self.model.transcribe(str(path), language="zh", vad_filter=True, beam_size=5)
        txt_path = path.with_name(path.stem + "_逐字稿.txt")
        srt_path = path.with_name(path.stem + "_字幕.srt")
        n = 0
        with txt_path.open("w", encoding="utf-8-sig") as txt, srt_path.open("w", encoding="utf-8-sig") as srt:
            for seg in segments:
                text = cc.convert(seg.text.strip())
                if not text:
                    continue
                n += 1
                txt.write(f"【{ts(seg.start)[:-4]}】\n{text}\n\n")
                srt.write(f"{n}\n{ts(seg.start)} --> {ts(seg.end)}\n{text}\n\n")
                if n % 25 == 0:
                    self.log(f"辨識中：已完成 {n} 段，音訊位置約 {ts(seg.end)[:-4]}")
        self.log(f"步驟 4/4：完成，共 {n} 段。")
        return txt_path

    def transcribe_all(self):
        stage = "初始化"
        try:
            stage = "載入 OpenCC"
            self.log("初始化：載入繁體中文轉換元件…")
            from opencc import OpenCC
            cc = OpenCC("s2twp")
            if self.model is None:
                stage = "載入 Whisper 模型"
                self.load_model()
            outputs = []
            for i, path in enumerate(self.files, 1):
                stage = f"轉錄檔案 {path.name}"
                self.log(f"[{i}/{len(self.files)}] 處理中…")
                outputs.append(self.transcribe_one(path, cc))
            self.log("全部完成！TXT 與 SRT 已存到原始檔案旁邊。")
            self.root.after(0, lambda: messagebox.showinfo("完成", "逐字稿已生成完成！\nTXT 與 SRT 已放在原始檔案旁邊。"))
            if outputs:
                try:
                    os.startfile(outputs[0])
                except Exception:
                    pass
        except Exception as e:
            detail = write_error(stage, e)
            self.log(f"錯誤階段：{stage}")
            self.log(f"{type(e).__name__}: {e}")
            self.log(f"完整錯誤已寫入：{LOG_PATH}")
            short = f"階段：{stage}\n\n{type(e).__name__}: {e}\n\n已建立 error.log。請按『複製記錄』或把 error.log 傳給我。"
            self.root.after(0, lambda msg=short: messagebox.showerror("處理失敗 - 診斷資訊", msg))
        finally:
            self.root.after(0, self.finish_ui)

    def finish_ui(self):
        self.progress.stop()
        self.start_btn.config(state="normal")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
