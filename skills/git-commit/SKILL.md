---
name: git-commit
description: Write a clear commit message from the staged changes and commit them. Use when the user asks to commit, or to write a commit message.
---

# Git commit

1. Run `git status` and `git diff --cached` with `bash`.
   - If nothing is staged, show the user the unstaged files and ask what to stage. Never run `git add -A` on your own.
2. Check the staged diff for secrets (API keys, tokens, passwords, `.env` files). If you find any, stop and tell the user. Do not commit.
3. Write the message:
   - Subject line: imperative mood, at most 72 characters, no trailing period, e.g. `Fix crash when skills folder is empty`.
   - Blank line, then a short body explaining *why* the change was made, if it is not obvious from the subject.
4. Show the message to the user and ask for confirmation before committing.
5. Commit with a quoted heredoc, so quotes in the message cannot break the shell command:
   ```
   git commit -F - <<'MSG'
   <subject>

   <body>
   MSG
   ```
6. Run `git log -1 --stat` and show the result.
