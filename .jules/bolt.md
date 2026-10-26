## 2024-10-26 - [Avoid Private Attributes in Python concurrency]
**Learning:** [Relying on internal or private attributes like `_max_workers` in `ThreadPoolExecutor` or `ProcessPoolExecutor` is fragile and can lead to bugs across Python versions.]
**Action:** [Next time I use `concurrent.futures`, I will avoid accessing private properties or use documented public APIs to handle chunking, or let the executor manage defaults.]

## 2024-10-26 - [ThreadPoolExecutor vs ProcessPoolExecutor]
**Learning:** [For operations strictly defined as I/O-bound (like reading files), `ThreadPoolExecutor` is significantly more efficient because it avoids the overhead of inter-process communication and object pickling required by `ProcessPoolExecutor`.]
**Action:** [Next time I need to optimize a blocking loop, I will carefully choose between threads (for I/O) and processes (for CPU) to minimize overhead.]
## 2026-10-26 - [File I/O Optimization in Loops]
**Learning:** Overwriting `.gitignore` using `>` instead of appending `>>` caused a severe side-effect that blocked the patch. `os.scandir` is highly effective for reducing stat overhead in file traversal compared to `os.listdir()` and `os.path.isfile()`.
**Action:** Always use `>>` when modifying `.gitignore`. Pre-compile regexes outside loops, and always clean up test artifacts thoroughly before committing.
