# de-bess-optimiser: rules for Claude Code

This project is built with Claude Code. These rules apply to every session.

## Project

A day-ahead arbitrage optimiser for a battery in the German market (DE-LU),
then a solar plant with a battery. Prices come from ENTSO-E. The optimiser
is a linear programme in PuLP.

## Project rules

- Work in phases. One branch and one pull request per phase.
- Never hard-code assumptions. Battery assumptions live in config/battery.yaml and are labelled as assumptions.
- Write a test for every rule the model must respect (power limit, state of charge range, energy balance, cycle limit).
- Store timestamps in UTC. Convert to Europe/Berlin only for display.
- If a data source or market rule is uncertain, say so and say how to check it. Never invent numbers.

## Hard rules

- Never commit secrets (.env) or raw data (data/).
- Ask before adding any dependency.
- If something is unclear or a check fails, stop and ask. Do not guess.

## Coding guidelines

Source: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md
(MIT licence).

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
