import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FONT=("Microsoft JhengHei UI",10); FONT_SMALL=("Microsoft JhengHei UI",9); FONT_TITLE=("Microsoft JhengHei UI",20,"bold")
CHUNK_SECONDS=600

def app_dir():
    return Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent
LOG_PATH=app_dir()/"error.log"

def ts(sec):
    ms=int(round(sec*1000)); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_error(stage,exc):
    text=f"影片逐字稿 TW 診斷記錄\n時間：{datetime.now():%Y-%m-%d %H:%M:%S}\n階段：{stage}\n錯誤類型：{type(exc).__name__}\n錯誤訊息：{exc}\n\n完整 Traceback：\n{traceback.format_exc()}\n"
    try: LOG_PATH.write_text(text,encoding="utf-8-sig")
    except Exception: pass

def decode_audio_chunks(path):
    """用 PyAV 串流解碼，固定 16 kHz mono，每 10 分鐘 yield 一塊 float32，避免整部長音訊一次進 RAM。"""
    import av, numpy as np
    container=av.open(str(path))
    if not container.streams.audio:
        container.close(); raise RuntimeError("找不到音訊軌。")
    stream=container.streams.audio[0]
    resampler=av.audio.resampler.AudioResampler(format="s16",layout="mono",rate=16000)
    max_samples=CHUNK_SECONDS*16000; parts=[]; count=0
    try:
        for frame in container.decode(stream):
            frames=resampler.resample(frame)
            if frames is None: continue
            if not isinstance(frames,list): frames=[frames]
            for rf in frames:
                arr=rf.to_ndarray().reshape(-1)
                pos=0
                while pos<len(arr):
                    take=min(max_samples-count,len(arr)-pos)
                    parts.append(arr[pos:pos+take].copy()); count+=take; pos+=take
                    if count>=max_samples:
                        pcm=np.concatenate(parts).astype(np.float32)/32768.0
                        yield pcm; parts=[]; count=0
        tail=resampler.resample(None)
        if tail:
            if not isinstance(tail,list): tail=[tail]
            for rf in tail:
                arr=rf.to_ndarray().reshape(-1); parts.append(arr.copy()); count+=len(arr)
        if count:
            yield np.concatenate(parts).astype(np.float32)/32768.0
    finally: container.close()

class App:
    def __init__(self,root):
        self.root=root; root.title("影片逐字稿 TW - 長音訊修正版 V3"); root.geometry("760x560"); root.minsize(660,500); self.files=[]; self.model=None
        f=ttk.Frame(root,padding=20); f.pack(fill="both",expand=True)
        ttk.Label(f,text="影片逐字稿",font=FONT_TITLE).pack(anchor="w")
        ttk.Label(f,text="V3：長音訊每 10 分鐘分段處理，避免 3～4 小時課程耗盡記憶體。",font=FONT).pack(anchor="w",pady=(4,14))
        b=ttk.Frame(f); b.pack(fill="x"); ttk.Button(b,text="選取檔案",command=self.pick_files).pack(side="left"); ttk.Button(b,text="清除",command=self.clear_files).pack(side="left",padx=8); self.start_btn=ttk.Button(b,text="開始生成逐字稿",command=self.start); self.start_btn.pack(side="right")
        self.listbox=tk.Listbox(f,height=6,font=FONT); self.listbox.pack(fill="x",pady=12)
        self.progress=ttk.Progressbar(f,mode="indeterminate"); self.progress.pack(fill="x"); self.status=tk.StringVar(value="請先選取檔案"); ttk.Label(f,textvariable=self.status,font=FONT).pack(anchor="w",pady=(8,5))
        ttk.Label(f,text="執行記錄 / 錯誤診斷",font=("Microsoft JhengHei UI",11,"bold")).pack(anchor="w",pady=(8,4)); self.logbox=tk.Text(f,height=10,wrap="word",font=("Consolas",9)); self.logbox.pack(fill="both",expand=True)
        bot=ttk.Frame(f); bot.pack(fill="x",pady=(6,0)); ttk.Button(bot,text="複製記錄",command=self.copy_log).pack(side="left"); ttk.Button(bot,text="開啟 error.log",command=self.open_log).pack(side="left",padx=8); ttk.Label(bot,text="目前 CPU int8 穩定模式",font=FONT_SMALL).pack(side="right")
    def log(self,text):
        def u(): self.status.set(text); self.logbox.insert(tk.END,text+"\n"); self.logbox.see(tk.END)
        self.root.after(0,u)
    def pick_files(self):
        p=filedialog.askopenfilenames(title="選取影片或音訊",filetypes=[("影音檔案","*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.m4a *.wav *.flac *.aac"),("所有檔案","*.*")])
        if p:
            self.files=[Path(x) for x in p]; self.listbox.delete(0,tk.END)
            for x in self.files:self.listbox.insert(tk.END,str(x))
            self.log(f"已選取 {len(self.files)} 個檔案")
    def clear_files(self): self.files=[]; self.listbox.delete(0,tk.END); self.log("已清除檔案")
    def copy_log(self):
        x=self.logbox.get("1.0",tk.END).strip(); self.root.clipboard_clear(); self.root.clipboard_append(x); self.root.update(); messagebox.showinfo("已複製","執行記錄已複製。")
    def open_log(self):
        if LOG_PATH.exists(): os.startfile(LOG_PATH)
        else: messagebox.showinfo("尚無記錄","目前沒有 error.log。")
    def start(self):
        if not self.files: messagebox.showwarning("尚未選取檔案","請先選取檔案。"); return
        self.start_btn.config(state="disabled"); self.progress.start(10); self.logbox.delete("1.0",tk.END); threading.Thread(target=self.run,daemon=True).start()
    def load_model(self):
        self.log("正在載入 Whisper turbo（CPU int8）…"); from faster_whisper import WhisperModel; self.model=WhisperModel("turbo",device="cpu",compute_type="int8"); self.log("模型載入成功。")
    def transcribe_one(self,path,cc):
        txtp=path.with_name(path.stem+"_逐字稿.txt"); srtp=path.with_name(path.stem+"_字幕.srt"); n=0; offset=0.0; chunk_no=0
        with txtp.open("w",encoding="utf-8-sig") as txt,srtp.open("w",encoding="utf-8-sig") as srt:
            for audio in decode_audio_chunks(path):
                chunk_no+=1; duration=len(audio)/16000.0; self.log(f"正在辨識第 {chunk_no} 段：{ts(offset)[:-4]} ～ {ts(offset+duration)[:-4]}")
                segments,_=self.model.transcribe(audio,language="zh",vad_filter=True,beam_size=5)
                for seg in segments:
                    text=cc.convert(seg.text.strip())
                    if not text: continue
                    n+=1; start=offset+seg.start; end=offset+seg.end; txt.write(f"【{ts(start)[:-4]}】\n{text}\n\n"); srt.write(f"{n}\n{ts(start)} --> {ts(end)}\n{text}\n\n")
                txt.flush(); srt.flush(); offset+=duration; self.log(f"第 {chunk_no} 段完成；目前共 {n} 段文字。")
        self.log(f"完成：{path.name}，共 {n} 段。")
        return txtp
    def run(self):
        stage="初始化"
        try:
            stage="載入 OpenCC"; self.log("載入繁體中文轉換元件…"); from opencc import OpenCC; cc=OpenCC("s2twp")
            if self.model is None: stage="載入 Whisper 模型"; self.load_model()
            outs=[]
            for i,p in enumerate(self.files,1): stage=f"長音訊分段轉錄 {p.name}"; self.log(f"[{i}/{len(self.files)}] 開始處理 {p.name}"); outs.append(self.transcribe_one(p,cc))
            self.log("全部完成！"); self.root.after(0,lambda:messagebox.showinfo("完成","逐字稿已完成！TXT 與 SRT 在原檔案旁邊。"))
            if outs:
                try: os.startfile(outs[0])
                except Exception: pass
        except Exception as e:
            write_error(stage,e); self.log(f"錯誤階段：{stage}"); self.log(f"{type(e).__name__}: {e}"); self.log(f"完整錯誤：{LOG_PATH}"); msg=f"階段：{stage}\n\n{type(e).__name__}: {e}\n\n請把畫面記錄或 error.log 傳給我。"; self.root.after(0,lambda m=msg:messagebox.showerror("處理失敗",m))
        finally:self.root.after(0,self.finish)
    def finish(self):self.progress.stop(); self.start_btn.config(state="normal")

def main():
    root=tk.Tk(); App(root); root.mainloop()
if __name__=="__main__":main()
