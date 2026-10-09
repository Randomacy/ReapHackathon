# Agent server ownership

Keep agent implementation, tests, dependencies, and local data inside
`agent-server/`. The agent receives aggregate BCI events, owns purchasing
mandates and order state, and is the only component allowed to call Reap.
Never commit API keys, test card data, SQLite files, or raw EEG. Keep Reap
credentials server-side and send card entry to Reap's hosted enrollment page.
