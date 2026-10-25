## 2024-05-18 - Memoizing AgentMessage and AgentMessagePart
**Learning:** During LLM streaming in chat interfaces, React re-renders the entire message list or all message parts within a message when new chunks stream in, causing significant reconciliation overhead.
**Action:** Use `React.memo()` on components that represent individual messages and message parts to prevent re-rendering when their props haven't changed during streaming.

## 2024-05-18 - Memoizing callbacks passed to Memoized components
**Learning:** Even if a component like `AgentMessage` is wrapped in `React.memo()`, passing an inline arrow function as a prop (like `onInputResponses={(inputResponses) => agent.send({ inputResponses })}`) creates a new function reference on every render. This invalidates the memoization and causes the child component to re-render unnecessarily. When `useEveAgent()` triggers a state update, all previously rendered `AgentMessage` components in the list will re-render.
**Action:** Always wrap callbacks passed to memoized child components in `useCallback()`, ensuring stable references. When the dependency is a method from a hook object (like `agent.send`), use the specific method in the dependency array (e.g., `[agent.send]`) rather than the whole object (`[agent]`) if the object itself is recreated on every render.

## 2026-10-25 - [ProcessPoolExecutor vs ThreadPoolExecutor]
**Learning:** For performance tasks in Python, CPU-bound tasks like regex parsing see substantial improvements from `ProcessPoolExecutor` compared to `ThreadPoolExecutor`, which is limited by the GIL. Using `min(32, os.cpu_count() + 4)` is for I/O bounds, whereas `os.cpu_count() or 1` is appropriate for ProcessPool workers. Also, ensure you gracefully handle and log exceptions rather than blindly swallowing them.
**Action:** When parallelizing a loop involving regex matching across multiple files, use `ProcessPoolExecutor` with max_workers based on `os.cpu_count()` and explicitly log any exceptions caught during future.result() extraction.
