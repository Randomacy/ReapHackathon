# BCI ownership

Work inside `bci-server/` only. This component owns Muse signal acquisition,
the experimental focus estimate, the simulator, and focus-event publishing.
It does not make purchase decisions or call Reap. Treat the repo's
`contracts/` folder as read-only if it is added by the integration team.
Keep the Muse SDK, local bridge binaries, raw recordings, and secrets out of Git.
