# Agent Tool Adapters

| Tool | Entry mechanism | Unified action |
|---|---|---|
| Codex | Automatically discovers `AGENTS.md` | Read full file, then task package and specs |
| Claude Code (CC) | Reads `CLAUDE.md` | `CLAUDE.md` redirects to `AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md` | Redirects to `AGENTS.md` |
| Coder/other Agent | Orchestrator-provided context | Attach `AGENTS.md` plus the standard YAML task package |

Tool adapters only locate the common rules. They must not duplicate product decisions, commands or acceptance criteria. If a tool requires a system prompt, use:

```text
Read AGENTS.md completely. Then read the task package, source milestone/spec,
linked ADRs, contracts, fixtures and tests. Do not edit outside allowed_paths.
If sources conflict or baseline verification fails, stop and report evidence.
Return the completed AGENT_HANDOFF_TEMPLATE.md with fresh command results.
```

## Orchestrator dispatch checklist

- Attach base SHA and repository-relative paths, never rely on prior chat context.
- Use one Agent as writer per leased path; use separate Agents for review/acceptance.
- Do not ask multiple tools to implement the same solution “for comparison” on shared paths.
- Compare outputs through PRs and tests, not by copying whole working directories.
- Expire sessions, not evidence: decisions and results move into GitHub/Git.

