# Textbook agent acceptance report

Verified on 5 October 2026. Standalone implementation is complete on `codex/textbook-agent`; live model acceptance remains unverified. No paid OpenAI API calls were made.

## Verified results

- **53 offline tests passed**, including creation, targeted repair, Tamil/English output routing, unchanged-repeat zero model calls, resumability, lesson selection, bounded review repairs, missing credentials, source cache behavior, crop validation, formulas, transaction rollback, conflict detection, and reports.
- The real OpenAI SDK was exercised with offline HTTP responses for completed valid JSON, completed invalid JSON, and incomplete truncated JSON. Usage is saved before parsing and these failures interrupt safely.
- Teacher edits to generated aids remain intact and stop regeneration; audit includes the edited aids. Older managed aid blocks without provenance are also held for reconciliation.
- Forced runs refresh source inventories. Inventory identity now includes extracted text, warnings, image checksum, model, medium, lesson map and prompt version.
- The supplied Tamil PDF checksum and **360 physical pages / 23 mapped lessons** were verified. Post-lesson practicals and glossary are explicitly excluded by this lesson manifest.
- Real-source rendering checked **29 pages**, PDF 9–23 and 178–191. **26 exact diagram crops** were created using previously audited crop boxes, decoded successfully and inspected in a contact sheet. This verifies rendering/cropping, not AI discovery of crop coordinates.
- The existing science Hugo website built successfully in a temporary copy with both staged lessons. A localhost-only base URL override was used for browser inspection. Physics loaded **28 textbook images** and **297 KaTeX nodes**, biology loaded **24 textbook images** and **4 KaTeX nodes**, with no KaTeX error nodes. Tamil text and the momentum equation were visibly readable. These pages use existing previously audited lesson prose with additional new crop links; they are not newly AI-transcribed pilot outputs.
- CLI help, package installation and final whitespace checks passed. No original textbook content, website dependency changes or presentations were altered by acceptance checks.

## Measured offline time and resources

The first real-PDF extraction/crop/site check took **8.41 seconds**. Sandbox process inspection was unavailable for that first check, so memory/CPU are not reported for it. The repeated check with cached page renders took **3.60 seconds**, sampled at one-second intervals: **221.95 MiB peak local RSS**, **94.8% of one CPU core**, and **238.47 MiB working/acceptance disk data**. Five samples were collected. These are small offline checks, not estimates of a full AI conversion. RSS includes the local process and its live children and can include shared pages.

OpenAI API requests/tokens for all implementation acceptance checks: **0 / 0**. This excludes the Codex conversation used to develop the tool; its exact development token total is unavailable from the agent runtime. Model-server memory and CPU are unavailable. Future runs save their own stage durations, recorded API tokens, cached-token subsets, reasoning-token subsets, local resource samples and optional explicit-rate cost estimates.

## Live checks still required

`OPENAI_API_KEY` was not configured. Live model availability/schema compatibility, actual Tamil visual transcription, source-item completeness, semantic corrections, generated-answer quality, paid time/cost, and a two-lesson live create/repair/unchanged pilot have **not** been demonstrated. The official English PDF was not supplied; English routing passed fixtures, but official English textbook fidelity is unverified. The remaining real-book pages were not visually checked during this agent's acceptance run. Automated model review is not teacher approval.

After local setup in [README.md](README.md), set your API key and an image/structured-output capable API model, then run these individually on an isolated copy of the science repository:

```sh
textbook-agent run --manifest examples/class-10-science-ta-2024.json --output '/absolute/path/to/science-pilot-copy' --lesson laws-of-motion --max-calls-per-lesson 50 --token-limit 500000 --max-seconds 1800
textbook-agent run --manifest examples/class-10-science-ta-2024.json --output '/absolute/path/to/science-pilot-copy' --lesson plant-anatomy-and-plant-physiology --max-calls-per-lesson 50 --token-limit 500000 --max-seconds 1800
```

The numbers are ceilings for a pilot, not predicted usage. Start with one lesson. Run the same command again after it passes to inspect unchanged/zero-call behavior. For creation, use an empty destination with the required Hugo theme/config, or a generic Markdown destination. For repair, use a copy with deliberately incomplete lesson text. Inspect the run reports and staged review before student publication. `audit`, `resume`, and `status` are documented in the guide. Never put your key in source control or chat.

## Independent review and decisions

One fresh whole-branch reviewer identified three Important defects: premature parsing lost usage on truncation; teacher edits to managed aids could be overwritten; forced runs reused source inventories. All three were reproduced by failing offline regressions and fixed in one pass. The final suite passed 53/53. No second review was dispatched.

Rulings made, in order:

1. Treat the user's “create” after the plan handoff as approval of the recommended native execution. Cost if misunderstood: another execution-method clarification.
2. Deliver the implementation with live API/model, Tamil fidelity and paid-performance acceptance explicitly unverified, because credentials are unavailable. Cost if wrong: model/schema adjustments and a paid pilot may still be needed.
3. Verify English routing using fixtures and require the official English PDF for real fidelity acceptance. Cost if wrong: English-source corrections may be needed after that pilot.
4. Limit real-source visual acceptance to the 29-page/26-crop check and existing-site preview described above. Cost if wrong: defects on other pages or newly generated prose may remain until the full live audit.

Deferred minor findings:

- Receipt invalidation currently hashes Python code and root Hugo config files; directory-based Hugo config, theme changes and the JavaScript math validator are excluded. **Run `--force` after changing these** so current source/site/math checks run.
- Broader model tests still use simplified fixtures. Real SDK truncated/malformed/completed output is now covered, but the fixtures do not establish live educational accuracy or every real API response shape.

Machine-readable local acceptance measurements are in [acceptance-results.json](acceptance-results.json).
