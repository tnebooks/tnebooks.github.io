# School Textbook Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a standalone agent that creates or repairs school textbook lessons in English or Tamil with source images, formulas, reviewed study aids, resumable runs, and usage reports.

**Architecture:** A local Python pipeline extracts and caches source evidence, sends bounded lesson/page inputs to the OpenAI Responses API, validates structured results, and applies passing changes through recoverable transactions. The model produces data; local components control paths, assets, budgets, and writes. Source generation and semantic review use separate contexts.

**Tech Stack:** Python 3.11+, OpenAI Python SDK, Pydantic 2, PyMuPDF, pdfplumber, Pillow, PyYAML, markdown-it-py, psutil, pytest; Node.js and KaTeX for math validation; optional Poppler and Hugo for alternate rendering and destination-site validation.

**Spec:** [Approved design](/Users/apple/explore/tnebooks.github.io/docs/superpowers/specs/2026-10-05-textbook-agent-design.md).

## Global Constraints

- "English output belongs in `content.en/docs/<lesson-slug>/_index.md`; Tamil output belongs in `content.ta/docs/<lesson-slug>/_index.md`."
- "Existing Hugo front matter, lesson paths, useful supplemental content, and presentation files must be preserved."
- "The user selected a standalone tool using an OpenAI API key."
- "Configure `OPENAI_API_KEY` locally and provide an explicit model identifier through the book configuration or `OPENAI_MODEL`."
- "The first version ships only the API backend."
- "Each medium needs its own official source for textbook verification."
- "Source images cannot be replaced by an AI illustration."
- "Equations use the existing site's supported inline `\(...\)` and block `\[...\]` syntax."
- "Repair a failed section at most twice."
- "Sequential lessons are the default; parallel review is not needed for the first release."
- "Use `store=false` for responses, without claiming that this disables all provider retention policies."
- "These tests make no paid API calls."
- "If credentials are unavailable, deliver the tested tool with the live pilot explicitly unverified."
- Product code belongs in `tools/textbook-agent`; do not alter the site's existing package dependencies or unrelated `package-lock.json` change.

## Review Focus

1. Printed page labels may restart between volumes or include Roman numerals: use explicit PDF page ranges, retain printed labels as strings, and test this in Task 1.
2. Two chapters may occupy the same physical PDF page: require separate page boundary boxes and test cropping/selection in Tasks 1 and 2.
3. A teacher may edit a lesson after preparation starts: recheck hashes and retain their edit; test this in Task 8.
4. A successful API response may be truncated or contain a refusal: checkpoint the error without applying partial content; test this in Task 3.
5. A textbook page may contain a malicious instruction or an image path outside the lesson: treat it as data and reject unsafe generated references; test this in Tasks 4 and 7.

---

## File map and shared contracts

All paths below are relative to `/Users/apple/explore/tnebooks.github.io/tools/textbook-agent`.

- `pyproject.toml`, `README.md`, `.env.example`: package entry point, dependencies, setup, and credential names without secrets.
- `src/textbook_agent/models.py`, `config.py`, `paths.py`: versioned Pydantic contracts, manifests, local configuration, and path enforcement.
- `src/textbook_agent/source.py`, `assets.py`: local extraction, renderer fallback, cache, crop creation, and visual checks.
- `src/textbook_agent/api.py`, `prompts.py`: structured model requests, bounded retry behavior, and source/review instructions.
- `src/textbook_agent/discovery.py`, `lessons.py`, `review.py`: chapter mapping, targeted lesson edits, study aids, and semantic review.
- `src/textbook_agent/validation.py`, `site.py`, `math_check.mjs`, `package.json`: Markdown/assets/math validation and temporary Hugo verification.
- `src/textbook_agent/state.py`, `apply.py`, `metrics.py`, `report.py`: checkpoints, cache keys, transactions, local sampling, usage, and reports.
- `src/textbook_agent/cli.py`, `pipeline.py`, `__main__.py`: user commands and sequential orchestration.
- `examples/class-10-science-ta-2024.json`, `tests/`: reusable source manifest and tests; fixtures contain no API key.

Define these shared models once in Task 1. Later tasks import them rather than creating parallel contracts:

- `BookManifest`: schema version, book ID, PDF path/hash/page count, output path, medium, class, subject, edition, optional term/volume, model, lesson mappings, excluded sections.
- `LessonSpec`: stable ID, title, ASCII slug, weight, inclusive one-based PDF range, printed-page labels, per-page optional normalized boundary box.
- `RunLimits`: page window (default 2), request timeout (120 seconds), maximum output tokens (8192), maximum transient retries (2), maximum repair passes (2), optional recorded-token limit and run deadline, maximum calls per lesson (100).
- `SourcePage`: page number, dimensions, extracted text/layout, rendered image path, extraction warnings, checksum.
- `SourceItem`: stable ID, kind, page, bounding box, source text/caption, optional exercise ID, source-order index, uncertainty flags.
- `LessonEvidence`: manifest/lesson identity, source pages/items, source fingerprint.
- `ExistingLesson`: raw front matter, body, path, hashes of Markdown and referenced local assets, detected section anchors.
- `AssetSpec`/`AssetRecord`: source item/page, normalized crop box, caption; generated relative path, asset hash, dimensions, review flags.
- `LessonDraft`: structured section edits, source-item-to-section mappings, asset specifications, generated aids, change notes. New sections have stable anchors; edits name existing section anchors and expected section hashes.
- `ReviewResult`: source coverage, missing/incorrect items, visual/math findings, aid review results, unresolved issues, repairable section IDs.
- `ValidationResult`: errors, warnings, mechanical/site status; `passing` is derived from errors and required checks.
- `ApiUsage`: response/request ID, input/cached/output/reasoning tokens with nullable fields; `RunState`: run options, lesson stage/checkpoints, fingerprints, usage, events, application journals.

Use safe serializers for these models, strict schemas on model-generated data, and integer/float/string values only for persistent state. Secrets never enter these models.

### Task 1: Package, manifests, and safe paths

**Files:** Create `pyproject.toml`, `src/textbook_agent/{__init__,models,config,paths}.py`; tests `tests/test_config.py`, `tests/test_paths.py`.

**Interfaces:** Produce `load_manifest(path: Path) -> BookManifest`, `resolve_book(options: dict[str, object]) -> BookManifest`, `lesson_path(book: BookManifest, lesson: LessonSpec) -> Path`, `checked_path(root: Path, relative: str) -> Path`, and the shared models above.

- [ ] **Step 1:** Write failing tests for `en`/`ta` routing, invalid ranges, duplicate slugs, shared pages requiring disjoint boundary boxes, Roman/restarted printed labels, missing model, path traversal, and symlink escape. Pin routing with `assert lesson_path(tamil_book, lesson).relative_to(tamil_book.output).as_posix() == 'content.ta/docs/laws-of-motion/_index.md'`.
- [ ] **Step 2:** Run `pytest tests/test_config.py tests/test_paths.py -q`; expect failures because the package/contracts do not exist.
- [ ] **Step 3:** Implement the contracts and validation; require existing readable PDFs and safe destination roots. Keep printed-page labels as strings. Add installable `textbook-agent = textbook_agent.cli:main` entry point and a development test configuration; the CLI implementation comes in Task 10.
- [ ] **Step 4:** Install the package in an isolated environment and rerun these tests; expect all tests to pass without network/API access.
- [ ] **Step 5:** Commit only Task 1 package files and tests with `feat: add textbook manifests and safe paths`.

### Task 2: PDF evidence, rendering, and exact source assets

**Files:** Create `src/textbook_agent/{source,assets}.py`, `tests/test_source.py`, `tests/test_assets.py`, `tests/conftest.py`.

**Interfaces:** Consume Task 1 contracts. Produce `prepare_pages(book: BookManifest, lesson: LessonSpec, cache: Path) -> Iterator[SourcePage]`, `crop_assets(evidence: LessonEvidence, specs: list[AssetSpec], staging: Path) -> list[AssetRecord]`, `inspect_render(path: Path) -> list[str]`.

- [ ] **Step 1:** Write failing fixture tests for multi-column text, vector diagrams with labels, garbled Tamil text, empty primary render with successful alternate renderer, an unreadable page, shared-page boundary boxes, invalid crops, and deterministic asset reuse. Assert out-of-range boxes raise a validation error and `assert first_asset.sha256 == repeated_asset.sha256`.
- [ ] **Step 2:** Run `pytest tests/test_source.py tests/test_assets.py -q`; expect missing-component failures.
- [ ] **Step 3:** Implement PyMuPDF extraction/rendering, pdfplumber alternative text evidence, optional Poppler rendering, and image diagnostics. Cache by source/page/boundary/extractor settings; render no more than the configured window in memory. Crop from a valid render with labels preserved; do not trust embedded-image extraction alone for vector diagrams.
- [ ] **Step 4:** Run the fixture tests and prepare selected real Tamil pages without API calls; verify page images are readable using visual inspection. Report pages needing semantic transcription rather than pretending local text is reliable.
- [ ] **Step 5:** Commit Task 2 files with `feat: prepare cached textbook evidence and figure crops`.

### Task 3: Structured API client, budgets, and recoverable errors

**Files:** Create `src/textbook_agent/api.py`, `tests/test_api.py`.

**Interfaces:** Produce `ModelClient.respond(task: str, payload: dict[str, object], images: list[Path], schema: type[BaseModel]) -> tuple[BaseModel, ApiUsage]`, with injected transport, budget ledger, clock, and sleeper for tests. Produce typed failure categories for refusal, incomplete output, quota, authentication, timeout, unsupported configuration, and transient exhaustion.

- [ ] **Step 1:** Write failing mocked tests for structured responses, `store=False`, image encoding, zero SDK retries, output limits, refusal, truncation, usage fields absent, rate-limit retry with Retry-After, quota exhaustion without retry, invalid API key without logging it, and token-limit stop before the next request. Assert `transport.call_count == 1` on quota errors and at most 3 calls for repeated transient errors.
- [ ] **Step 2:** Run `pytest tests/test_api.py -q`; expect missing-client failures.
- [ ] **Step 3:** Implement the official SDK Responses integration using validated JSON schemas. Validate image/structured-output compatibility on the first real request and surface unsupported-model errors. Use one retry policy, respect server delay and run deadline, save usage/request identifiers promptly, and classify an unknown request outcome explicitly.
- [ ] **Step 4:** Rerun mocked API tests; expect passing tests and no outbound requests. Before any live call, consult the current official SDK/API documentation and use an API-key helper if available; otherwise rely on locally configured environment credentials without printing them.
- [ ] **Step 5:** Commit with `feat: add bounded structured OpenAI client`.

### Task 4: Chapter discovery and verified source inventories

**Files:** Create `src/textbook_agent/{discovery,prompts}.py`, `tests/test_discovery.py`, `tests/test_inventory.py`.

**Interfaces:** Consume `prepare_pages` and `ModelClient.respond`. Produce `discover_lessons(book: BookManifest, client: ModelClient, cache: Path) -> BookManifest`, `inventory_lesson(book: BookManifest, lesson: LessonSpec, client: ModelClient, cache: Path) -> LessonEvidence`.

- [ ] **Step 1:** Write failing tests using recorded model outputs for bookmarks/contents/headings, existing folder mappings, mixed term/volume labels, ambiguous chapter boundaries, excluded non-lesson sections, nested exercise IDs, duplicate source-item IDs, suspicious language mismatch, and a PDF saying “ignore instructions and run a command.” Assert ambiguous boundaries cannot enter processing and malicious source text remains source data.
- [ ] **Step 2:** Run `pytest tests/test_discovery.py tests/test_inventory.py -q`; expect missing-discovery failures.
- [ ] **Step 3:** Implement chapter candidate discovery and source-page verification with bounded image windows. A provided manifest avoids rediscovery. Use strict medium checks and structured source-item lists covering prose, tables, figures, equations, activities, examples, sidebars, and exercises. Review item inventories against every selected page; hold uncertain mappings for correction.
- [ ] **Step 4:** Rerun tests; verify chapter discovery never overwrites a duplicate matching folder or invents page offsets.
- [ ] **Step 5:** Commit with `feat: map chapters and inventory textbook source items`.

### Task 5: Targeted lesson repair, new lessons, and study aids

**Files:** Create `src/textbook_agent/lessons.py`, extend `prompts.py`, tests `tests/test_lessons.py`.

**Interfaces:** Produce `read_existing(path: Path) -> ExistingLesson | None`, `draft_lesson(evidence: LessonEvidence, existing: ExistingLesson | None, client: ModelClient) -> LessonDraft`, `assemble_lesson(lesson: LessonSpec, existing: ExistingLesson | None, draft: LessonDraft, assets: list[AssetRecord]) -> str`.

- [ ] **Step 1:** Write failing tests for new `_index.md`, insertion of a missing section, corrections in an existing section, source-order assembly, preservation of raw front matter/video references/supplements/presentations, stale section hashes, source-linked formulas/captions, labeled summaries/answers/practice, and labeled source-error corrections. Assert an unrelated supplementary section is byte-for-byte preserved after a targeted repair.
- [ ] **Step 2:** Run `pytest tests/test_lessons.py -q`; expect missing-lesson failures.
- [ ] **Step 3:** Implement section anchors and hash-checked edits instead of unconditional body replacement. For large lessons, draft individual source sections and assemble in source order. Preserve complete source material separately from generated aids; use exact diagram crops and supported math delimiters. Do not apply draft content here.
- [ ] **Step 4:** Rerun tests and inspect assembled fixture Markdown for both media; expect preserved metadata and no source-item loss.
- [ ] **Step 5:** Commit with `feat: create and repair source-grounded lessons`.

### Task 6: Semantic review and bounded section repair

**Files:** Create `src/textbook_agent/review.py`, extend `prompts.py`, tests `tests/test_review.py`.

**Interfaces:** Produce `review_lesson(evidence: LessonEvidence, markdown: str, assets: list[AssetRecord], client: ModelClient) -> ReviewResult`, `repair_sections(evidence: LessonEvidence, draft: LessonDraft, review: ReviewResult, client: ModelClient) -> LessonDraft`.

- [ ] **Step 1:** Write failing tests for omitted visible items, missing subquestions, incorrect signs/units, clipped diagram labels, Tamil terminology inconsistency, generated answers lacking support, textbook errors needing notes, and a repair loop that continues to fail. Assert at most 2 repair passes and that an unresolved source omission blocks application while an unverified aid can remain staged separately.
- [ ] **Step 2:** Run `pytest tests/test_review.py -q`; expect missing-review failures.
- [ ] **Step 3:** Implement a fresh-context review using source evidence, staged content, and relevant images. Check inventory completeness independently from draft claims. Repair only named sections; keep source fidelity, aid review, mechanical validation, and teacher approval distinct. Never execute generated math/code; use safe numeric parsing for checkable arithmetic.
- [ ] **Step 4:** Rerun tests; expect deterministic repair bounds and honest unresolved-status reporting.
- [ ] **Step 5:** Commit with `feat: review source fidelity and repair failed sections`.

### Task 7: Markdown, assets, math, and destination-site validation

**Files:** Create `src/textbook_agent/{validation,site}.py`, `math_check.mjs`, `package.json`; tests `tests/test_validation.py`, `tests/test_site.py`.

**Interfaces:** Produce `validate_lesson(markdown: str, lesson: LessonSpec, evidence: LessonEvidence, assets: list[AssetRecord], staging: Path) -> ValidationResult`, `validate_site(book: BookManifest, staged_lessons: dict[str, Path], work: Path) -> ValidationResult`.

- [ ] **Step 1:** Write failing tests for UTF-8/YAML, weights, duplicate/missing coverage IDs, nested exercises, missing/bad assets, source crop failures, Markdown/HTML image links, traversal and symlink links, balanced but invalid LaTeX, KaTeX rejection, generic Markdown destinations, missing Hugo theme/tools, and failed Hugo build. Assert unavailable required site/math tools leave results staged.
- [ ] **Step 2:** Run `pytest tests/test_validation.py tests/test_site.py -q`; expect missing-validation failures.
- [ ] **Step 3:** Implement Markdown parsing and path checks; use a fixed local Node helper with KaTeX strict error reporting, never model-supplied executable code. Build a temporary destination copy using its actual content/config/theme arrangement. Verify emitted images/formulas and produce a visual QA checklist for representative Tamil text, diagrams, and tables. Keep validation dependencies confined to this package.
- [ ] **Step 4:** Install only the package-local KaTeX dependency and rerun tests plus a fixture site build; inspect representative rendered output. A successful build alone cannot certify visual/source accuracy.
- [ ] **Step 5:** Commit with `feat: validate lesson assets formulas and Hugo output`.

### Task 8: Checkpoints, unchanged-run skips, and recoverable application

**Files:** Create `src/textbook_agent/{state,apply}.py`, `tests/test_state.py`, `tests/test_apply.py`.

**Interfaces:** Produce `fingerprint(book: BookManifest, lesson: LessonSpec, existing: ExistingLesson | None, versions: dict[str, str]) -> str`, `save_state(root: Path, state: RunState) -> None`, `load_state(root: Path, run_id: str) -> RunState`, `apply_lesson(book: BookManifest, lesson: LessonSpec, staged: Path, expected: ExistingLesson | None) -> list[Path]`, `recover_transaction(journal: Path) -> None`.

- [ ] **Step 1:** Write failing tests for initial-existing-content audit, validated unchanged skip, source/asset/Markdown/instruction/model/glossary invalidation, crash between file replacements, new-lesson rollback, teacher edits during a run, lock contention, interrupted resume, and preservation of old user assets. Assert a changed destination produces a conflict without overwriting the teacher's edit.
- [ ] **Step 2:** Run `pytest tests/test_state.py tests/test_apply.py -q`; expect missing-state failures.
- [ ] **Step 3:** Implement atomic state writes, per-book lock, durable staged evidence, fingerprinted validation receipts, backup/journal/replace/recovery transactions, and rechecked destination hashes. Store agent files under destination `.textbook-agent`, outside generated content. Clean only owned temporary files, never unreferenced user assets.
- [ ] **Step 4:** Rerun tests with injected failures at each application boundary; expect exact prior-file recovery and reliable resume.
- [ ] **Step 5:** Commit with `feat: add resumable runs and recoverable lesson updates`.

### Task 9: Time, token, resource, and coverage reports

**Files:** Create `src/textbook_agent/{metrics,report}.py`, `tests/test_metrics.py`, `tests/test_report.py`.

**Interfaces:** Produce `ResourceSampler.start()/stop() -> dict[str, object]`, `write_report(book: BookManifest, state: RunState, report_dir: Path) -> tuple[Path, Path]`. Sampler uses a 1-second default interval and an injectable clock/process reader.

- [ ] **Step 1:** Write failing tests for elapsed stage/lesson times, missing token fields, cached/reasoning subsets, deduplicated response IDs, unknown request outcomes, nullable cost estimates, explicit dated prices, sampled CPU/RSS peaks, source exclusions, failures/conflicts, teacher approval absence, and secret/log redaction. Assert cached tokens are not added again to input totals.
- [ ] **Step 2:** Run `pytest tests/test_metrics.py tests/test_report.py -q`; expect missing-report failures.
- [ ] **Step 3:** Implement readable Markdown plus JSON reports, per-stage/request usage, source-to-section coverage, change lists, and local process resource sampling. Label measurements and estimates accurately; never claim model-server memory or perfect content.
- [ ] **Step 4:** Rerun tests; inspect one fixture report for readable English/Tamil titles and actionable unresolved issues.
- [ ] **Step 5:** Commit with `feat: report textbook coverage usage and runtime`.

### Task 10: End-to-end commands, documentation, and real-source pilot preparation

**Files:** Create `src/textbook_agent/{cli,pipeline,__main__}.py`, `README.md`, `.env.example`, `examples/class-10-science-ta-2024.json`, `tests/test_pipeline.py`, `tests/test_cli.py`.

**Interfaces:** Consume all earlier interfaces. Produce `run_book(book: BookManifest, limits: RunLimits, mode: str, run_id: str | None = None, force: bool = False) -> RunState`, `main(argv: list[str] | None = None) -> int`. Modes are `run` and `audit`; `resume` reloads saved mode/options; `status` reads saved state without API access.

- [ ] **Step 1:** Write failing integration tests for empty English/Tamil destinations, targeted existing repair, missing credentials before requests, partial lesson failures, audit with zero lesson mutations, quota interruption/resume, CLI book registry resolution, medium mismatch, unchanged repeat run with zero model calls, and exit codes (0 completed, 1 preflight/runtime failure, 2 unresolved lesson issues).
- [ ] **Step 2:** Run `pytest tests/test_pipeline.py tests/test_cli.py -q`; expect missing-orchestrator failures.
- [ ] **Step 3:** Implement one-lesson-at-a-time stage transitions, budget checks, progress output, selected lessons, force behavior, and report links. Initialize registry files in the dedicated destination workspace; resolve `--book` from the current destination's registry or an explicit `--output` path. Build the 23-lesson example manifest from the existing audited chapter mapping, checking the real PDF hash/page count and listing excluded practical/glossary/appendix ranges.
- [ ] **Step 4:** Document installation, model/key environment setup, a complete Tamil example, an English example requiring its own source, audit/resume/status, limits, teacher review, and live-verification boundaries. Run `pytest -q` and CLI help/example-manifest validation; expect all offline tests to pass and no secrets in repository files.
- [ ] **Step 5:** Commit with `feat: deliver standalone textbook agent commands and guide`.

### Task 11: Acceptance, independent review, and delivery

**Files:** Save final validation and pilot reports under the tool's documented output location; revise only files implicated by failures/review findings.

**Interfaces:** Use the installed `textbook-agent` commands against an isolated copy, never the user's actual textbook files for a deliberately destructive test.

- [ ] **Step 1:** Run the full offline test suite and fixture Markdown/Hugo/math checks. Record results and inspect the final fixture report; fix actual failures using the owning component's regression test.
- [ ] **Step 2:** Check only whether API credentials are available without displaying them. When available, run the approved two-lesson Tamil pilot (laws of motion and plant anatomy/physiology) under explicit request/token/time limits. Prepare empty and deliberately incomplete isolated destination copies, then demonstrate creation, repair, coverage review, valid assets/formulas, and unchanged-run zero-call behavior.
- [ ] **Step 3:** Record actual live time/usage/resource samples and visually inspect source/staged/rendered pages. If the key/quota or official English source is unavailable, record the exact unverified acceptance checks and provide runnable instructions; do not fabricate success.
- [ ] **Step 4:** Obtain a fresh whole-change code review under the user's chosen execution workflow. Resolve concrete findings and run only relevant follow-up checks after changes. Check the final diff for unrelated website/dependency/textbook modifications.
- [ ] **Step 5:** Deliver links to the tool guide and validation/pilot reports, the exact run command, and material limitations. Keep publishing and textbook commits outside scope; present branch integration choices under the applicable finishing workflow.

## Self-review record

- Source routing, mapping, extraction, visual fallback, source completeness, equations, aids, review bounds, and site validation map to Tasks 1-7.
- Preservation, invalidation, locking, conflict detection, staging, backup/recovery, and resumability map to Tasks 5 and 8.
- API/schema/security/budget boundaries map to Tasks 1, 3, 4, 7, and 10; reporting and honest quality claims map to Tasks 9 and 11.
- All five Review Focus cases have explicit tests in their owning tasks. Shared interfaces use the same contract names throughout.
- No paid API call is needed to install, build, or run the offline suite. Live acceptance depends on local credentials and account quota.

## Execution choice for user review

Recommend **Native** execution: implement this plan in the current chat, task by task, then obtain one fresh final review. This avoids the repeated implementation/reviewer contexts per task and fits the user's token-efficiency priority.

Alternatively, **Subagent-driven** execution assigns a fresh implementer and reviewer to each task. It adds independent checks at each boundary but uses more contexts and tokens. The user must review this written plan and choose the execution method before implementation starts.
