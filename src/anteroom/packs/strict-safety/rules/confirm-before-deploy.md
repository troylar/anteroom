# Confirm Before Deploy

Before running any deployment or release command, always:

1. Show a summary of what will be deployed (branch, version, target)
2. List any pending changes that haven't been committed
3. Confirm the user wants to proceed
4. Never auto-deploy without explicit user approval

This applies to: `npm publish`, `pip upload`, `docker push`, `kubectl apply`,
`terraform apply`, `aws deploy`, and similar commands.
