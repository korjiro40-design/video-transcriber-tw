# 影片逐字稿 TW

Windows 本機影片／音訊逐字稿工具。把檔案拖到 `影片逐字稿.exe`（或 `影片逐字稿.bat`）即可開始。

## 功能
- 支援 MP4 / MKV / MOV / MP3 / M4A 等常見影音格式
- faster-whisper `turbo` 模型
- NVIDIA CUDA 優先，失敗時自動改用 CPU
- 中文語音辨識
- 簡體自動轉台灣繁體
- 同時輸出 `_逐字稿.txt` 與 `_字幕.srt`
- 一次可拖入多個檔案
- 完成後自動開啟 TXT

## 第一次使用
第一次轉錄時會從 Hugging Face 下載 Whisper `turbo` 模型，因此需要網路，模型約數 GB。之後模型留在本機快取，可離線使用。

> 注意：GitHub Actions 編譯出的 EXE 不會把 Whisper 模型塞進 ZIP，因此下載檔不會大到數 GB。

## Windows 可攜版
到 GitHub 的 **Actions → Build Windows Portable → 最新成功的執行 → Artifacts**，下載 `影片逐字稿-Windows-x64`，解壓縮即可。

## 使用方式
1. 解壓縮 ZIP。
2. 把影片或音訊直接拖到 `影片逐字稿.exe`。
3. 等待辨識完成。
4. 原影片旁會出現：
   - `檔名_逐字稿.txt`
   - `檔名_字幕.srt`

## GPU 說明
程式優先嘗試 NVIDIA CUDA。若電腦缺少相容 CUDA 執行環境，會自動退回 CPU，不會因此完全無法使用。RTX 顯卡建議更新 NVIDIA 驅動程式。
