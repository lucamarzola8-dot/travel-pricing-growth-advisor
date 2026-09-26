# travel-growth-toolkit (Kiro Power)

A packaged Kiro Power that bundles the conventions, agent skill, and optional MCP
server for building **event-driven travel pricing and international growth** features.
It encodes the same rules this project follows so they can be reused in any workspace.

## What it contains

```
power/
  plugin.json          # Power manifest (name, version, skills, mcp)
  skills/
    setup/
      SKILL.md          # Agent skill: pricing/growth conventions + testing rules
  mcp.json              # Optional fetch MCP server (event enrichment, off by default)
```

## What it gives you

- **Skill** — loads travel pricing/growth best practices on demand when you mention
  matching keywords (dynamic fare, revenue management, growth opportunity, etc.):
  explainable rule-based pricing, monotonic opportunity scoring, budget allocation
  that sums exactly, offline-first data, and the property-based tests to prove it.
- **MCP** — an optional `fetch` server for enriching the events dataset from public
  web pages. Disabled by default so the pricing path stays offline.

## Using the power

Powers can be shared as public GitHub repositories and installed into a Kiro
workspace, after which Kiro loads the skill and tools on demand. Install a power
only from a source you trust and review its contents first.

1. Point Kiro at this power directory (or its published GitHub repo).
2. The skill activates automatically when your request matches its keywords.
3. To enable event enrichment, set `"disabled": false` on the `fetch` server in
   `mcp.json` (requires `uv`/`uvx`).

> Third-party powers may be subject to separate terms. This power is authored for
> the Travel Pricing & Growth Advisor project.
