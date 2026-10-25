## 2024-05-19 - Fast scan_crushers performance optimization
**Learning:** ProcessPoolExecutor outperforms regex checking in python loops when batch parsing many files for many regex patterns.
**Action:** When asked to optimize tight nested loops over directory trees and regex parsing, use `concurrent.futures.ProcessPoolExecutor` with `chunksize=100` before pursuing hand-written `FAST_STRINGS` lists.
