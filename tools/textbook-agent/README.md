# School textbook agent

Create or repair complete English/Tamil school lessons from a source PDF. The tool preserves existing lesson metadata and supplements, crops textbook diagrams, transcribes formulas, adds separately reviewed study aids, and leaves uncertain work in staging with a report.

English lessons go to `content.en/docs/<lesson>/_index.md`; Tamil lessons go to `content.ta/docs/<lesson>/_index.md`. Run each medium with its own textbook PDF. The tool uses your OpenAI API account, independently of a Codex subscription.

## Setup on your Mac

Open a terminal in this directory. Python 3.11 or newer and Node.js are required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
npm --prefix src/textbook_agent ci
```

Set your API key locally and choose an API model that supports image inputs and structured outputs:

```sh
export OPENAI_API_KEY='YOUR_LOCAL_API_KEY'
export OPENAI_MODEL='YOUR_API_MODEL_ID'
```

Do not send the key in chat or commit it. `.env.example` lists the settings; `.env` files are not automatically loaded. The model identifier is checked by the API on the first real request; an unsupported or unavailable model produces a clear error.

Hugo and the destination's theme are required when the destination is a Hugo website. If the primary PDF renderer fails, the agent uses Poppler when installed, or the alternate renderer included with pdfplumber. On macOS, `brew install hugo poppler` supplies optional external tools. Extraction is local; selected source text and page images are sent to OpenAI for model processing.

## Start with your Tamil Science textbook

The example manifest already maps all 23 lessons in the supplied 2024 Class 10 Tamil Science PDF. It records the exact PDF checksum and page count. It targets `/Users/apple/explore/10th-science`, so a passing run updates that repository. To experiment first, copy that repository to a separate directory and pass `--output` with the copy's absolute path.

Start with one physics lesson:

```sh
textbook-agent run \
  --manifest examples/class-10-science-ta-2024.json \
  --lesson laws-of-motion \
  --max-calls-per-lesson 50 \
  --token-limit 500000 \
  --max-seconds 1800
```

The call/token/time numbers above are example pilot limits, not expected consumption. Recorded-token limits stop between requests and may be exceeded by an in-flight response. Image inputs and generated output incur API charges. Uncertain request outcomes can incur charges even when usage is unavailable.

Process all lessons by omitting `--lesson`. Select another lesson with its ID or folder slug. Use `--force` to re-review selected lessons even when a validation receipt exists.

## Other classes and subjects

```sh
textbook-agent run \
  --pdf '/absolute/path/to/english-textbook.pdf' \
  --output '/absolute/path/to/class-subject-repository' \
  --medium en --class 9 --subject maths --edition 2024
```

For Tamil, use `--medium ta` and the official Tamil source. Optional `--term` and `--volume` distinguish books. The agent proposes chapter mappings from contents/bookmarks/headings and checks boundary pages. Ambiguous mappings stop for a corrected manifest rather than guessing. A table of contents extending beyond the first 12 PDF pages needs an explicit manifest.

For repeated use, save a JSON manifest modeled on the example. Required book fields are `book_id`, `pdf`, `output`, `medium`, `class_name`, `subject`, and `edition`; `model` may be omitted when `OPENAI_MODEL` is set. Lessons contain `id`, `title`, `slug`, `weight`, `pdf_start`, and `pdf_end`. PDF pages are one-based and inclusive. Printed page labels are separate strings; never assume the offset is the same for every book. Shared chapter pages require disjoint normalized `boundaries` boxes. A book without a lesson list uses chapter discovery.

When changing the source PDF intentionally, update its edition/book ID and checksum in the manifest. A supplied checksum mismatch is an error, not an automatic source replacement.

## Audit, resume, and status

Audit compares without changing lesson Markdown or its assets:

```sh
textbook-agent audit --manifest examples/class-10-science-ta-2024.json --lesson optics
textbook-agent status --output '/Users/apple/explore/10th-science'
textbook-agent resume --output '/Users/apple/explore/10th-science' --run RUN_ID
```

A run prints its run ID and report path. Resume retains selected lessons, recorded usage, cached responses, and saved work. Fix the key/quota or reported problem, then resume. If a saved token/time limit has already been reached, explicitly raise it with `resume --token-limit NUMBER --max-seconds NUMBER`.

Books are registered locally after discovery. From the destination directory, use `textbook-agent run --book class-10-science-ta-2024`; from elsewhere add `--output` pointing to that destination. `--manifest` is the most portable choice.

Exit code 0 means the selected work completed; 1 means a preflight/runtime interruption; 2 means lesson issues need review. Status can be read without an API key or access to the original PDF.

## What a passing run checks

- Complete source items, including exercise subquestions, figures, tables, activities and sidebars, are inventoried and reviewed against page images.
- Textbook diagrams use exact source crops with source page, bounding box, caption and checksum.
- Inline `\(...\)` and block `\[...\]` formulas are checked through KaTeX. Complex notation that cannot be represented reliably is held for review rather than approximated.
- Independent model review checks wording, labels, units and answers. A narrow safe arithmetic checker verifies explicit numeric arithmetic where available; this is not a general symbolic proof engine.
- Metadata, local image files, source mappings, paths and executable HTML are checked. Hugo destinations are built in a temporary copy before application.
- Unverified generated aids remain in staging; they do not replace complete textbook source content. Model review does not mean teacher approval. A teacher should review generated answers and unresolved source errors before student publication.

The source PDF is the authority for transcription. Errors in the textbook require a labeled correction note. Official English and Tamil PDFs are verified separately; a translated supplement is not represented as an official textbook passage.

## Caching, backups, and reports

The destination's `.textbook-agent` directory stores book manifests, source renders/transcriptions, exact-input successful API responses, staged content, reports, validation receipts, and transaction backups. It sits outside `content.en`/`content.ta` and is excluded from the temporary site build. Add `.textbook-agent/` to the destination's Git ignore file if you do not want this working data in source control.

An unchanged, previously validated lesson can skip API work only when its PDF, lesson mapping, tool/instruction version, model, glossary, Markdown, root Hugo configuration files and image hashes match. Existing Markdown encountered for the first time always gets a source audit. Cached responses help resume interrupted sections without buying identical successful responses again.

Changes use a destination lock, original-file hashes and recoverable transactions. If a teacher edits a file during a run, the agent holds the lesson rather than overwriting the edit. It does not delete old user assets, edit presentations, commit textbook changes, or publish the site.

Reports include source coverage, modified files, unresolved findings, staged study aids, stage time, recorded tokens and local resource measurements. Cached input is part of input usage; reasoning is part of output usage. Measurements cover the local agent and its child processes, not model-server memory. CPU percentage is relative to one core; summed process RSS can include shared pages.

Optionally add a `prices` object to the book manifest with `effective_date`, `currency`, `input_per_million`, `cached_per_million`, and `output_per_million`. Supply your own current rates; the agent does not invent prices. Estimated cost uses recorded usage and is not the final API bill.

## Validation and current limits

```sh
python -m pytest -q
textbook-agent --help
```

Tests use fixture PDFs and simulated API responses and make no paid calls. The implementation's live AI pilot requires your locally configured API key. The official English source has not been supplied for the real Class 10 Science pilot. See the acceptance report for what was actually verified.

This first release is a local command-line tool with sequential lessons. Automatic publication, schedules, a graphical interface, cloud hosting, general symbolic mathematics, and AI-generated textbook illustrations are outside its scope. Keep backups and review held lessons; automated checks cannot guarantee perfect educational content.

Teacher changes inside a generated study-aid block are protected by its embedded content checksum. A changed block (or an older block without a checksum) stops regeneration for that lesson and leaves the file intact. Audit still reviews the current aids. To reconcile, move the corrected text into a teacher supplement outside the managed block and remove the old managed block before running again. `--force` also refreshes source inventories, rather than only the later drafts.

Validation receipts currently exclude directory-based Hugo configuration, theme files and the JavaScript math validator. Run `--force` after changing any of these so the source/site/math checks are refreshed. See [ACCEPTANCE_REPORT.md](ACCEPTANCE_REPORT.md) for measured acceptance results and the live checks still required.
