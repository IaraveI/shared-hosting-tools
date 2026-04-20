# Repository Instructions

- Always use `python3` instead of `python` for shell commands.

## Checking Tool Releases

When asked whether any bundled command-line tools have a newer release:

1. Read the `README.md` "Tool releases" section first. Treat those links as the authoritative list of tools to check.
2. List local versioned binary directories in the repository root, for example `bat-0.26.1`, `jq-1.8.1`, or `wp-cli-2.12.0`.
3. Compare the local directory version with the latest upstream release from the README link.
4. Also note any versioned binary directory that is present locally but missing from the README release list, because it may need a tracking link added.
5. Run local `--version` checks where practical, but do not rely on them alone. Some tools may have incomplete or broken version output.
6. Report the result as a compact table with local version, latest upstream version, and recommended action.
7. If the latest upstream version could have changed since the model's knowledge cutoff, verify it online before answering.

