## 2024-10-23 - Dynamic ARIA labels for Copy buttons
**Learning:** Copy buttons in code blocks need dynamic ARIA labels that update to provide feedback to screen readers (e.g. "Copy code" -> "Copied"). Simply giving it a static ARIA label isn't enough when visual feedback (icon change) occurs.
**Action:** When adding ARIA labels to buttons that have interactive states with visual feedback, always link the `aria-label` to the state to ensure equivalent non-visual feedback.
## 2024-05-24 - Accessibility for Custom Collapsible Triggers
**Learning:** Found that custom `CollapsibleTrigger` components often lack semantic `aria-label` attributes to clarify their toggle action, especially when relying on generic icons or dynamic titles.
**Action:** When implementing collapsible UI elements, always ensure custom triggers have descriptive `aria-label`s, (e.g., `Toggle ${title} details`) to provide context for screen reader users.
