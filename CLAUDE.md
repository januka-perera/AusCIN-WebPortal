# AusCIN Coastal Media Portal

@AGENTS.md
@design_reference.md

## Claude Code instructions

- Use PowerShell commands because this project is developed natively on Windows.
- Do not assume WSL2 or Bash is available.
- Use the generated design references in `docs/design/references`.
- Before modifying code, inspect the relevant files and explain the proposed approach.
- Implement one coherent feature at a time.
- Run the relevant tests and linting after changes.
- Do not access production `/g/data/qu34`.
- Do not commit raw media, secrets, generated derivatives or local environment files.
- Do not introduce PostgreSQL, FastAPI, Redis or Docker while the task only concerns the frontend prototype.