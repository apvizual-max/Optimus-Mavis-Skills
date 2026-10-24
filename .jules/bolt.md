## 2024-05-18 - Memoizing AgentMessage and AgentMessagePart
**Learning:** During LLM streaming in chat interfaces, React re-renders the entire message list or all message parts within a message when new chunks stream in, causing significant reconciliation overhead.
**Action:** Use `React.memo()` on components that represent individual messages and message parts to prevent re-rendering when their props haven't changed during streaming.

## 2024-05-18 - Memoizing callbacks passed to Memoized components
**Learning:** Even if a component like `AgentMessage` is wrapped in `React.memo()`, passing an inline arrow function as a prop (like `onInputResponses={(inputResponses) => agent.send({ inputResponses })}`) creates a new function reference on every render. This invalidates the memoization and causes the child component to re-render unnecessarily. When `useEveAgent()` triggers a state update, all previously rendered `AgentMessage` components in the list will re-render.
**Action:** Always wrap callbacks passed to memoized child components in `useCallback()`, ensuring stable references. When the dependency is a method from a hook object (like `agent.send`), use the specific method in the dependency array (e.g., `[agent.send]`) rather than the whole object (`[agent]`) if the object itself is recreated on every render.
