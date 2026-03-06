# No Destructive Commands

Never run commands that could cause irreversible damage without explicit user approval:

- No `rm -rf` on directories outside the current project
- No `git push --force` to shared branches
- No `git reset --hard` that would discard uncommitted work
- No `DROP TABLE`, `DELETE FROM` without a WHERE clause
- No `chmod 777` or overly permissive file permissions
- No killing processes by PID without confirming the process name

When in doubt, show the user what will happen and ask for confirmation.
