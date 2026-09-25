import os
import sys
import subprocess
from pathlib import Path


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    if len(sys.argv) < 2:
        print("請把影片/音訊檔拖到『影片逐字稿.exe』上。")
        input("按 Enter 關閉...")
        return

    from faster_whisper import WhisperModel
    from opencc import OpenCC

    cc = OpenCC("s2twp")
    files = [Path(x) for x in sys.argv[1:] if Path(x).is_file()]
    if not files:
        print("找不到有效檔案。")
        input("按 Enter 關閉...")
        return

    # RTX 顯卡優先；若 CUDA 執行失敗，會自動改 CPU。
    try:
        print("載入 Whisper large-v3-turbo（NVIDIA GPU）...")
        model = WhisperModel("turbo", device="cuda", compute_type="float16")
        # 先真正跑模型時才可能發現 CUDA DLL 問題，下面每檔有 fallback。
        gpu = True
    except Exception as e:
        print(f"GPU 載入失敗，改用 CPU：{e}")
        model = WhisperModel("turbo", device="cpu", compute_type="int8")
        gpu = False

    for idx, path in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] 開始：{path.name}")
        try:
            try:
                segments, info = model.transcribe(str(path), language="zh", vad_filter=True, beam_size=5)
                segments = list(segments)
            except Exception as e:
                if not gpu:
                    raise
                print(f"GPU 辨識失敗，改用 CPU 重試：{e}")
                model = WhisperModel("turbo", device="cpu", compute_type="int8")
                gpu = False
                segments, info = model.transcribe(str(path), language="zh", vad_filter=True, beam_size=5)
                segments = list(segments)

            txt_path = path.with_name(path.stem + "_逐字稿.txt")
            srt_path = path.with_name(path.stem + "_字幕.srt")

            with txt_path.open("w", encoding="utf-8-sig") as txt, srt_path.open("w", encoding="utf-8-sig") as srt:
                for n, seg in enumerate(segments, 1):
                    text = cc.convert(seg.text.strip())
                    if not text:
                        continue
                    txt.write(f"【{ts(seg.start)[:-4]}】\n{text}\n\n")
                    srt.write(f"{n}\n{ts(seg.start)} --> {ts(seg.end)}\n{text}\n\n")

            print(f"完成：{txt_path.name}")
            print(f"字幕：{srt_path.name}")
            try:
                os.startfile(txt_path)
            except Exception:
                pass
        except Exception as e:
            print(f"處理失敗：{path.name}\n{e}")

    input("\n全部完成。按 Enter 關閉...")


if __name__ == "__main__":
    main()
