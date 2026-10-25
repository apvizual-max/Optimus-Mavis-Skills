## 2024-10-25 - ThreadPoolExecutor for I/O bounds
**Learning:** In the Python Hermes-Antigravity bridge (`check_inbox.py`), file I/O operations block the main thread and can become a significant bottleneck if the inbox scales up or operates on slower filesystems.
**Action:** Use `concurrent.futures.ThreadPoolExecutor` when performing batch I/O operations (like reading or parsing multiple JSON files) to allow parallel I/O and speed up the processing pipeline.
