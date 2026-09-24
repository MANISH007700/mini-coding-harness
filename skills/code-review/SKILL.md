---
name: code-review
description: Review code or a diff for bugs, security issues and readability. Use when the user asks to review, check, or audit code.
---

# Code review

1. Work out what to review.
   - A file or folder named by the user: read it with `read_file`.
   - Nothing named: run `git diff HEAD` (fall back to `git diff --cached`) with `bash`.
2. Read enough surrounding code to understand how the changed code is called. Do not review lines in isolation.
3. Look for, in this order:
   - **Bugs**: wrong logic, off-by-one, unhandled `None`/empty input, broken error handling.
   - **Security**: secrets in code, shell or SQL injection, unsafe file paths.
   - **Readability**: unclear names, dead code, duplicated logic.
4. Report every finding as one line:
   `path:line - severity (high/medium/low) - what is wrong - how to fix it`
   Sort high severity first.
5. If nothing is wrong, say so plainly. Do not invent findings.
6. Do not edit any files unless the user asks you to apply the fixes.
