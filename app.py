import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("影片逐字稿 TW")
        self.root.geometry("700x430")
        self.root.minsize(620, 390)
        self.files = []
        self.model = None
        self.gpu = False

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="影片逐字稿", font=("Microsoft JhengHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text="選取影片或音訊，按一下即可產生繁體中文 TXT 與 SRT。", font=("Microsoft JhengHei UI", 10)).pack(anchor="w", pady=(4, 16))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="選取檔案", command=self.pick_files).pack(side="left")
        ttk.Button(buttons, text="清除", command=self.clear_files).pack(side="left", padx=8)
        self.start_btn = ttk.Button(buttons, text="開始生成逐字稿", command=self.start)
        self.start_btn.pack(side="right")

        self.listbox = tk.Listbox(frame, height=8, font=("Microsoft JhengHei UI", 10))
        self.listbox.pack(fill="both", expand=True, pady=12)

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="請先選取檔案")
        ttk.Label(frame, textvariable=self.status, font=("Microsoft JhengHei UI", 10)).pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, text="第一次使用會下載 Whisper turbo 模型；NVIDIA GPU 優先，失敗會自動改用 CPU。", font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(8, 0))

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="選取影片或音訊",
            filetypes=[
                ("影音檔案", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.wav *.flac *.aac"),
                ("所有檔案", "*.*"),
            ],
        )
        if paths:
            self.files = [Path(p) for p in paths]
            self.refresh_list()
            self.status.set(f"已選取 {len(self.files)} 個檔案")

    def clear_files(self):
        self.files = []
        self.refresh_list()
        self.status.set("請先選取檔案")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.files:
            self.listbox.insert(tk.END, str(p))

    def start(self):
        if not self.files:
            messagebox.showwarning("尚未選取檔案", "請先按『選取檔案』。")
            return
        self.start_btn.config(state="disabled")
        self.progress.start(10)
        threading.Thread(target=self.transcribe_all, daemon=True).start()

    def set_status(self, text):
        self.root.after(0, lambda: self.status.set(text))

    def load_model(self):
        from faster_whisper import WhisperModel
        self.set_status("正在載入 Whisper turbo 模型…第一次使用可能需要下載數 GB。")
        try:
            self.model = WhisperModel("turbo", device="cuda", compute_type="float16")
            self.gpu = True
        except Exception:
            self.model = WhisperModel("turbo", device="cpu", compute_type="int8")
            self.gpu = False

    def transcribe_one(self, path, cc):
        try:
            segments, _ = self.model.transcribe(str(path), language="zh", vad_filter=True, beam_size=5)
            segments = list(segments)
        except Exception:
            if not self.gpu:
                raise
            from faster_whisper import WhisperModel
            self.set_status("GPU 執行環境不可用，改用 CPU 重試…")
            self.model = WhisperModel("turbo", device="cpu", compute_type="int8")
            self.gpu = False
            segments, _ = self.model.transcribe(str(path), language="zh", vad_filter=True, beam_size=5)
            segments = list(segments)

        txt_path = path.with_name(path.stem + "_逐字稿.txt")
        srt_path = path.with_name(path.stem + "_字幕.srt")
        with txt_path.open("w", encoding="utf-8-sig") as txt, srt_path.open("w", encoding="utf-8-sig") as srt:
            n = 0
            for seg in segments:
                text = cc.convert(seg.text.strip())
                if not text:
                    continue
                n += 1
                txt.write(f"【{ts(seg.start)[:-4]}】\n{text}\n\n")
                srt.write(f"{n}\n{ts(seg.start)} --> {ts(seg.end)}\n{text}\n\n")
        return txt_path

    def transcribe_all(self):
        try:
            from opencc import OpenCC
            cc = OpenCC("s2twp")
            if self.model is None:
                self.load_model()
            outputs = []
            for i, path in enumerate(self.files, 1):
                self.set_status(f"[{i}/{len(self.files)}] 正在辨識：{path.name}")
                outputs.append(self.transcribe_one(path, cc))
            self.set_status("全部完成！逐字稿已存到原始檔案旁邊。")
            self.root.after(0, lambda: messagebox.showinfo("完成", "逐字稿已生成完成！\n\nTXT 與 SRT 會放在原始影片／音訊旁邊。"))
            if outputs:
                try:
                    os.startfile(outputs[0])
                except Exception:
                    pass
        except Exception as e:
            self.set_status("發生錯誤")
            self.root.after(0, lambda: messagebox.showerror("處理失敗", str(e)))
        finally:
            self.root.after(0, self.finish_ui)

    def finish_ui(self):
        self.progress.stop()
        self.start_btn.config(state="normal")


def main():
    root = tk.Tk()
    try:
        root.option_add("*Font", "Microsoft JhengHei UI 10")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
