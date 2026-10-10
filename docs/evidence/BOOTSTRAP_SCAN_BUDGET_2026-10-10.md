# Bounded bootstrap scanning — 2026-10-10

The sensitive-pattern bootstrap scan now excludes generated pytest cache files and uses a token-start boundary for its email pattern. Previously a long nonmatching alphanumeric string caused repeated regex scans from every character. Large automatically generated test IDs made the application workflow stall after pytest passed.

Two regressions run the actual scanner as a subprocess with a 10-second deadline: a 1 MiB allowed synthetic address plus a 1 MiB generated cache must complete successfully, while a constructed synthetic token-shaped value must still fail without printing the token. Local proof passes in under one second per repo. This remains a heuristic scan, not proof that every secret or personal datum is absent.

AgentTest's large-output parametrizations also use short explicit case IDs. Automatic API-origin tests construct their synthetic URL credential separator to avoid a false positive from the heuristic email rule; request behavior and origin assertions are unchanged.
