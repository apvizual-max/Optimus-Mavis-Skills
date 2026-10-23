## 2024-05-18 - Memoizing AgentMessage and AgentMessagePart
**Learning:** During LLM streaming in chat interfaces, React re-renders the entire message list or all message parts within a message when new chunks stream in, causing significant reconciliation overhead.
**Action:** Use `React.memo()` on components that represent individual messages and message parts to prevent re-rendering when their props haven't changed during streaming.
