# Product Vision Alignment

Before creating issues, planning features, or starting work, check that the proposed work aligns with the product vision in `VISION.md`.

## Quick Reference — Core Principles

1. **Deploy in minutes, not months** — `pip install` for solo, `docker run` for teams, K8s+Postgres+SSO for enterprise. Every feature must work at all three scales.
2. **Security is structural** — OWASP ASVS Level 2. Secure by default. Enterprise security teams should find nothing to object to.
3. **Maximum configurability** — every behavioral parameter should be a config knob with a sensible default. Zero config works. 50 knobs tuned to exact policy also works.
4. **Multiple interfaces, one engine** — web UI and CLI share the same core. Web UI is primary for most users. CLI is the developer power tool. Both are first-class.
5. **Self-managed, data-sovereign** — no phone-home, no telemetry. Deploy on-prem, cloud VPC, or bare metal. Nothing leaves your environment except what you send to your chosen LLM endpoint.
6. **Extensible through standards** — MCP, OpenAI-compatible APIs. Standard protocols, not proprietary plugins. In server mode, MCP configuration is admin-governed.
7. **Full enterprise governance, zero enterprise overhead** — SSO, RBAC, admin dashboard, audit trails, DLP, token budgets. Everything a regulated institution needs. A sysadmin sets it up in a day.

## What Anteroom Is Not (Negative Guardrails)

These are identity-level constraints. If a feature makes Anteroom more like any of these, flag it.

- **Not a ChatGPT clone** — the chat is the interaction layer, not the product. Features that just make it "more like ChatGPT" without serving core use cases don't belong
- **Not just a coding tool** — Anteroom serves the entire organization: document generation, data analysis, presentations, compliance research. Developers are the beachhead, not the boundary
- **Not a configuration burden — but a configuration powerhouse** — every behavioral parameter should be configurable. Zero configuration must always work, and every knob needs a sensible default
- **Not enterprise overhead** — Anteroom has enterprise features banks need, but deployment complexity scales with deployment *size*, not with Anteroom itself. Solo developers never think about Docker. Banks get SSO and K8s and still deploy in a day.
- **Not a model host** — Anteroom talks to models. It doesn't run, serve, quantize, or benchmark them

## Out of Scope (Hard No)

Do not build or propose features in these areas:
- Managed SaaS (self-managed only, for now)
- Model training or fine-tuning
- Mobile native apps
- Mandatory infrastructure dependencies (Docker/Postgres/K8s are supported but never required — core always runs with `pip install` + SQLite)
- Competing with IDEs (editor extensions connect to Anteroom, they don't recreate editor functionality)

## The Litmus Test

When evaluating a feature idea, ask:
1. Can someone in a locked-down enterprise use this?
2. Does it work at all three scales? Solo (`pip install`), team (`docker run`), enterprise (K8s+Postgres+SSO). Features should degrade gracefully, not break.
3. Would it pass a bank's architecture review?
4. Does it work in both interfaces (or have a clear reason not to)?
5. Would a product owner use it? If only a developer would, that's fine — but design for a broader audience when possible.
6. Would a CISO approve it? If it weakens security posture or creates audit gaps, it doesn't ship.
7. Is the enterprise feature as easy to deploy as the rest of Anteroom?

If the answer to any of these is "no," flag the concern before proceeding. Read `VISION.md` for the full product vision.

## When Ideas Don't Align

If a user proposes work that conflicts with the vision:
- Don't silently proceed — raise the concern directly
- Explain which principle it conflicts with
- Suggest an alternative approach that aligns, if one exists
- If the user wants to proceed despite the concern: go ahead, but:
  1. Add the `vision-review` label to the issue/PR
  2. Note the specific vision tension in the issue/PR description
  3. This ensures the project owner can batch-review vision-flagged work

## When Ideas Are Ambiguous

If alignment isn't clear:
- Ask the user how the feature relates to the core use cases (enterprise behind firewall, collaborative teams, power users)
- Check if the feature adds external dependencies or infrastructure requirements
- Consider whether it increases or decreases the "pip install to productive" time
