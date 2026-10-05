# School textbook PDF-to-Markdown agent

Date: 5 October 2026
Status: Approved by the user on 5 October 2026; implementation has not started.

## Purpose and accepted requirements

Build a reusable local agent for school textbooks across classes, subjects, and editions. On each run it compares the supplied PDF with existing lesson Markdown, fixes missing or incorrect source content, and creates lessons that do not exist. The user selected complete textbook content plus verified study aids.

English output belongs in `content.en/docs/<lesson-slug>/_index.md`; Tamil output belongs in `content.ta/docs/<lesson-slug>/_index.md`. Images are local assets beside the lesson. Existing Hugo front matter, lesson paths, useful supplemental content, and presentation files must be preserved.

The initial delivery is a command-line agent, not a new website or hosted service. Its code lives under `tools/textbook-agent` in this repository; the destination textbook repository is a configurable path. It runs on the user's Mac and can later be used with other textbook repositories.

## Selected approach

Use a local Python pipeline for PDF extraction, rendering, caching, asset creation, validation, and file updates. Use the OpenAI Responses API through the official Python SDK for source interpretation, Tamil transcription repair, lesson comparison, study aids, and semantic review.

The user selected a standalone tool using an OpenAI API key. Configure `OPENAI_API_KEY` locally and provide an explicit model identifier through the book configuration or `OPENAI_MODEL`. The selected model must support image inputs and structured outputs; validate compatibility during preflight and report unavailable models clearly. Do not read or reuse Codex subscription credentials. The first version ships only the API backend.

Compared with a prompt-only skill, a pipeline provides durable checkpoints, repeatable validation, measurable usage, and controlled file updates. Compared with a hosted agent service, the selected local tool is simpler to run against existing repositories. API calls are billed separately from the user's Codex subscription.

## User workflow

The intended interface is a `textbook-agent` command with these actions:

- `run`: inspect the PDF, prepare source evidence, create or repair lessons, review them, validate results, and apply passing changes.
- `audit`: compare PDF and Markdown and produce a report without changing lesson files.
- `resume`: continue an interrupted run from its saved checkpoint.
- `status`: show completed lessons, failures, review flags, and recorded usage.

A run accepts the PDF path, destination repository, medium (`en` or `ta`), class, subject, edition, and optional term/volume and lesson selection. A saved book manifest allows subsequent runs to use one book identifier instead of repeating settings. The tool prints a short progress message for each lesson and ends with links to its report and modified files.

Example intended usage, after implementation:

```text
textbook-agent run --pdf <textbook.pdf> --output <subject-repository> --medium ta --class 10 --subject science --edition 2024
textbook-agent audit --book class-10-science-ta-2024
textbook-agent resume --run <run-id>
```

The medium is explicit. The tool checks for a likely mismatch but does not silently select another medium or translate a whole textbook into the other medium. Each medium needs its own official source for textbook verification.

## Book and lesson identity

A book manifest records class, subject, medium, edition, term/volume, PDF checksum, page count, and destination. Each lesson records its stable identifier, title, slug, weight, inclusive PDF page range, printed page labels, and optional section boundary boxes for pages shared with another lesson.

The agent proposes chapter boundaries from the table of contents, bookmarks, and visible chapter headings. It checks them against source pages before processing. Ambiguous boundaries or duplicate folder matches are reported as needing a manifest correction; the agent does not guess and overwrite an unrelated lesson.

Existing folder names are reused through manifest mappings. Newly created lessons use stable ASCII slugs. English and Tamil may share a topic identifier while retaining their own page ranges, wording, titles, and figures. No assumption is made that printed page number plus one fixed offset works for every book.

## Processing and component boundaries

1. **Inventory:** find existing lesson files and assets; read front matter; identify source language, chapter map, and current file hashes.
2. **Source preparation:** extract text and layout locally, render source pages, and cache results. Images, tables, activities, equations, examples, exercises, and sidebars are inventoried as source items with page references.
3. **Lesson preparation:** supply only the selected lesson's source evidence, existing Markdown, relevant terminology, and concise instructions to the API model. Large lessons are split along source sections, with a final lesson assembly and review pass. Attach a bounded window of locally rendered page images as image inputs alongside extracted text. Cache verified page transcriptions so later passes use compact structured evidence and only the images needed for visual checks.
4. **Repair or creation:** preserve source order and detail, correct demonstrable transcription errors, create missing content, and propose diagram crops and equation transcriptions. Changes are written to staging, not directly into the destination.
5. **Study aids:** add clearly separated explanations, summaries, bilingual terminology where useful, worked answers, and additional practice. Each aid records its source basis and review result.
6. **Independent review:** check staged lesson text against the source inventory and page images in a fresh context. Return item-level omissions, errors, and unresolved issues. A model's assertion that a lesson is complete is not sufficient evidence.
7. **Validation and application:** validate structured outputs, assets, math, coverage records, and site compatibility; repair a failed section at most twice. Apply passing lesson changes with backups and a recovery journal.
8. **Reporting:** save coverage, changes, source references, verification status, unresolved issues, time, token usage, and locally measured resource usage.

Each component consumes and produces versioned JSON or files through documented interfaces. The model runner returns structured source items and review results; it does not choose arbitrary destination paths. The source preparer and validator work without model access and can be tested independently.

## Source accuracy and visual handling

All source prose, exercises, activities, tables, examples, sidebars, captions, and relevant diagrams within the selected lesson are included. Front matter, practicals, glossary, and appendices remain separately identified source sections; they are not silently folded into unrelated lessons. A run selecting all lessons reports excluded non-lesson sections explicitly.

Extracted text is evidence, not the final authority. Garbled Tamil, suspiciously empty pages, unusual text order, tables, and dense notation require rendered-page review. If one renderer produces a suspicious page, try the alternate renderer. If the source remains unreadable, record the page and hold the affected lesson for review rather than inventing text.

Textbook diagrams are extracted or cropped from the PDF with captions and labels preserved. Figure placement follows its source context. Crops use validated page coordinates and are checked for clipping, readability, and nonblank pixels. Every figure has a source page, bounding box, asset checksum, caption, and linked source-item identifier.

Vector figures and diagrams made of multiple embedded objects use a rendered crop when direct extraction would lose labels. Filenames are stable and content-aware so repeated runs reuse the same assets. Source images cannot be replaced by an AI illustration. Optional additional schematic diagrams may use SVG or Mermaid and must be labeled as study aids; new photorealistic or generative illustrations are outside the first version.

Equations use the existing site's supported inline `\(...\)` and block `\[...\]` syntax, with variables, signs, units, fractions, subscripts, and superscripts checked against the source. Validate rendering with KaTeX, and independently calculate numeric worked examples where possible. Complex notation that cannot be transcribed reliably is preserved as a source crop with a review flag, not silently omitted or approximated.

Textbook mistakes are preserved in the source representation with a clearly labeled correction note where evidence supports it. They are never silently rewritten as if the PDF contained the correction. Generated answers cannot be called teacher approved without actual teacher approval.

## Existing content and repeat runs

Do not regenerate a whole existing lesson merely because a small section is missing. Use semantic source comparisons and targeted updates. Preserve unrelated front matter, references, videos, supplements, and presentation files. Suspected errors in existing supplemental material appear in the report or an explicit labeled correction.

Cache keys include PDF checksum, page/range identity, extraction version, manifest mapping, instruction version, configured model, glossary version, and relevant existing-content hashes. A change invalidates only affected work where possible.

An unchanged, previously validated lesson can skip model work only when its source, Markdown, asset, and verification hashes still match. An initial encounter with existing content always requires source audit; the mere existence of `_index.md` never establishes completeness. A force option reruns selected lessons.

Keep source extracts, checkpoints, staged files, backups, and reports in a dedicated `.textbook-agent` directory under the destination, excluded from site output. Store reports as JSON plus readable Markdown. Do not delete older unreferenced user assets automatically.

Before applying, recheck destination hashes to detect edits made during a run. Conflicts hold that lesson for review. Application uses a per-lesson journal and temporary files with atomic replacements; a crash must be recoverable to the prior lesson and assets. Concurrent writers to the same book are prevented by a lock. Completed lessons remain usable if another lesson fails.

## Validation and quality status

Machine checks cover UTF-8, YAML/front matter, safe paths, valid page ranges and crop coordinates, local asset existence/decoding, Markdown structure, math rendering, duplicate source-item identifiers, and source-inventory coverage. Tables and diagrams require visual/semantic review in addition to syntax checks.

Every source item is linked to its Markdown section or asset and records source evidence. The reviewer checks the inventory itself for omitted visible items. All exercise groups and question identifiers must be represented, including nested subquestions. Coverage counts are evidence to inspect, not a mathematical guarantee of correctness.

If the destination has a Hugo configuration and the required build tools/theme are available, build a temporary copy and inspect representative pages for Tamil text, images, tables, and formulas. Build failures block affected changes; unavailable build dependencies are reported and leave results staged until site validation can run. Generic Markdown destinations use the Markdown/math validation path.

The agent reports separate statuses for source fidelity, mechanical validation, generated-aid review, and teacher approval. It may describe material as model reviewed or mechanically validated. It must not claim that automated checks prove perfect content or imply teacher approval.

Unresolved source errors and aids requiring teacher review are listed prominently. The source lesson may pass while questionable generated aids remain in staging. Failed source transcription, missing figures, malformed equations, conflicts, and unsafe paths prevent application of that lesson.

## Runtime, usage, and instruction boundaries

Default to one active lesson and a small bounded page-image window, appropriate for the user's 16 GB Mac. Render pages on demand, release image buffers, and cache locally. Sequential lessons are the default; parallel review is not needed for the first release.

Reuse short stable instructions, limit each model context to relevant source material, and retry only failed sections. Enforce configurable maximum model calls per lesson, request timeout, output-token limit, and maximum run duration. Track actual usage after each request and stop before launching another request once a configured recorded-token limit is reached. This is a between-request limit, not a guaranteed cap on an in-flight request. Disable hidden SDK retries and use a single bounded exponential-backoff policy for transient rate limits and server/network failures. Quota exhaustion and authentication failures stop immediately with a resumable checkpoint. An uncertain request outcome is recorded because retrying can incur another charge.

Record wall time per stage and lesson, API request identifiers, input tokens, cached-input tokens, output tokens, and available reasoning-token fields. Cached input is a subset of input; reasoning output is a subset of output. Missing usage fields remain unknown. Optional estimated cost uses explicit user-supplied per-model prices and their effective date; no price is invented or hardcoded as current. Recorded usage and estimated cost are not the final API bill.

Sample local process CPU, resident memory, and disk cache size during the run. Report sampling interval, measured peaks, and scope. Local process memory does not include model-server memory; an app-wide memory reading is not attributed exclusively to the job.

PDF contents are untrusted textbook data. Instructions embedded in PDFs, OCR text, metadata, or image labels cannot override the user request or agent instructions. Do not execute commands suggested by documents. The model returns data under a strict JSON schema and is not given a general shell or unrestricted filesystem tool. Only intended destination lesson files and the agent's own workspace may be mutated. Read the API key from the local environment; never write it to manifests, reports, logs, source control, or prompts. Send the selected source text and page images to OpenAI over the SDK; local extraction does not mean model processing is offline. Use `store=false` for responses, without claiming that this disables all provider retention policies.

## Errors and recovery

Missing PDFs, dependencies, API key, inaccessible destinations, malformed manifests, and unsupported model configurations fail early with a clear action. Network interruption, quota exhaustion, timeout, or invalid model output preserves a checkpoint and allows resume. Explicitly handle model refusal and incomplete responses before parsing structured content. No placeholder lesson is applied as completed content.

Structured model outputs must pass schema validation before use. Reject absolute model-proposed asset paths, path traversal, symlink escapes, out-of-range source pages, and impossible crop coordinates. Log compact operational results, not credentials or private model reasoning.

## Acceptance and pilot

Automated tests use small fixture PDFs and recorded/mock model results to cover a complete new lesson, a partially missing existing lesson, Tamil extraction failure, vector diagrams, equations, shared chapter pages, repeat-run skipping, interrupted application, stale destination edits, invalid paths, malformed output, API refusal, and bounded retry behavior. These tests make no paid API calls.

Live acceptance uses the supplied Class 10 Tamil Science PDF with one physics and one biology lesson in an isolated destination copy, when the user's API key and account quota are available. Demonstrate creation from empty folders, targeted repair of a deliberately incomplete copy, readable diagram crops, correctly rendered formulas, source coverage evidence, and an unchanged repeat run with no new model calls. Record pilot time and usage. A full 23-lesson rerun is not required to validate the agent implementation. If credentials are unavailable, deliver the tested tool with the live pilot explicitly unverified; do not fabricate a successful live report.

English source fidelity is tested with an English fixture and then a matching official English textbook when supplied. Existing English Markdown cannot be certified against the Tamil source. The report must distinguish fixture tests from real-book verification.

Deliverables are the agent package, dependency specification, runnable instructions, example book manifest for the supplied Tamil PDF, focused tests, and pilot audit/usage reports. Automatic publishing, committing textbook changes, cloud deployment, scheduled runs, a graphical interface, and a general school platform are outside this release.

## Official documentation consulted

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): schema-constrained model responses and explicit handling of refusal or incomplete output.
- [OpenAI images and vision](https://developers.openai.com/api/docs/guides/images-vision): supplying rendered source pages as image inputs.
- [OpenAI error codes](https://developers.openai.com/api/docs/guides/error-codes): distinguishing transient rate limits from exhausted quota and authentication failures.
- [Codex authentication](https://learn.chatgpt.com/docs/auth): ChatGPT subscription sign-in and API-key usage are distinct access methods.
