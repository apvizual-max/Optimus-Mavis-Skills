## 2024-10-26 - Express CORS Security Configuration
**Learning:** Example standalone typescript files using Express might default to `app.use(cors())`, exposing an overly permissive CORS policy.
**Action:** When creating or reviewing Express examples, ensure `cors` is initialized with a specific configuration object (e.g., pulling from `process.env.ALLOWED_ORIGINS` with a restrictive fallback like localhost) to prevent unauthorized cross-origin access.
