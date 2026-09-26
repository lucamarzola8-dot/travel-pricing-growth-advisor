# Kiro Feature Coverage

How this project demonstrates each Kiro University Challenge lesson, and where to
find it in the repository.

| Lesson | Feature | Where it lives |
|--------|---------|----------------|
| 1 | **Spec-driven development** | `.kiro/specs/travel-pricing-growth-advisor/` — `requirements.md` (EARS), `design.md`, `tasks.md` |
| 2 | **Steering documents** | `.kiro/steering/` — `product.md`, `tech.md`, `structure.md` |
| 3 | **Hooks** | `.kiro/hooks/` — pytest-on-backend-save, tsc-on-frontend-save, cdk-synth-on-infra-save |
| 4 | **Property-based testing** | `backend/tests/properties/` — pricing P1–P5, growth G1–G5 (hypothesis) |
| 5 | **Powers (usage)** | `power/` toolkit + `power/README.md` install/use notes |
| 6 | **MCP** | `.kiro/settings/mcp.json` — optional `fetch` event-enrichment server (off by default) |
| 7 | **Custom agents** | `.kiro/agents/` — `travel-data-analyst.json`, `aws-infra-reviewer.json` |
| Bonus 2 | **Package a Power** | `power/` — `plugin.json`, `skills/setup/SKILL.md`, `mcp.json` |

## Notes

- **Property-based testing** is the highest-value technical feature here: the
  pricing and growth logic have natural invariants (price bounds, monotonicity,
  exact budget sums) that are checked over hundreds of generated inputs. Run them
  with `pytest` from `backend/`.
- **Hooks** keep the three layers honest: saving backend Python runs the tests,
  saving frontend source type-checks it, and saving the CDK stack re-synthesizes
  the template.
- **Custom agents** are scoped and safe by construction: the infra reviewer is
  synth-only and denied any deploy/AWS CLI command; the data analyst is denied
  destructive shell and `git push`.
- **MCP and the Power** stay off the critical path: event enrichment is optional
  and disabled by default so the product always runs offline.
- **Bonus 1 (Kiro Web / cloud sessions)** is optional and not required for the
  completion award; it can be exercised by running a cloud session against this
  repo without any code change.
