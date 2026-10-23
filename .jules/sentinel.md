## 2025-05-24 - [Command Injection]
**Vulnerability:** Command injection in `asyncio.create_subprocess_shell` where concatenated shell strings received CLI arguments in `dataplex_scanner.py`.
**Learning:** Shell strings using formatted literal quotes are a strong indicator of unsafe shell execution because they try to encapsulate user inputs instead of using safe execution primitives.
**Prevention:** Use `asyncio.create_subprocess_exec` and pass arguments as lists of strings instead of building shell commands. Avoid `shell=True` completely. When refactoring, remember to drop the literal quotes around arguments that were meant for shell parsing.
