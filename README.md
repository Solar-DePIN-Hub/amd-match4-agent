# amd-match4-agent — AMD AI League, Match 4 (Intelligent Web Information Retrieval), v0

Agent receives a natural-language query (optionally a start URL), browses the web and returns **one exact value + source URL**,
or an empty answer when it cannot ground one. Built for the mandated base `rocm/pytorch:rocm10.0_ubuntu26.04_py3.14_pytorch_release_2.13.0`.

## Status (2026-10-18)
- Local CPU eval, rule-based mode (no LLM): **dev 32/32, holdout 7/8 (39/40)**, p50 0.4 s, max 11.1 s, whole 40-query run 74 s.
  The dev set was used for tuning, so dev accuracy is optimistic; the 8 holdout queries were written after tuning and the code was not changed afterwards.
  Holdout miss: `h08` (kernel.org start URL) returned `7.2` instead of `7.2.11`. See `tests/results.md`.
- **Not yet verified on an AMD GPU**: image build, py3.14 wheels for transformers/tokenizers, model load time, VRAM peak, LLM judge quality.

## Pipeline
1. **Classify** answer type: version / phone / email / date / year / price / number / text.
2. **Direct-source resolvers** (no search engine needed): PyPI, npm, crates.io, GitHub releases API, endoflife.date (latest / LTS / release date / EOL per cycle), Wikidata (CEO, founder, HQ, founded year, capital, director, phone, website, ...). If a registry is named explicitly and the package does not exist, the agent returns empty.
3. **Fetch + follow links**: start URL, or the official site from Wikidata (phones/emails), plus key-free search (Brave HTML → Bing → DuckDuckGo HTML). 5 seed pages + up to 4 followed links ranked by anchor text (contact/support/download/pricing...), parallel, 5 s per page.
4. **Typed candidates**: regex extractors plus `tel:`/`mailto:` links. Every candidate is a literal span of a fetched page. Scoring uses query keywords in the context and line, type labels, fax/TTY penalty, toll-free bonus, page relevance, cross-page consensus, and "newest version among strong candidates" for "latest".
5. **Judge**: the LLM (Qwen3-8B on GPU) only **picks a numbered candidate** or copies a span that is then verified to appear verbatim in the fetched text. Without an LLM, the rule-based top candidate is used when its score is ≥ 2.5. Otherwise the answer is empty.
6. **Timing**: the client writes a valid empty JSON immediately, then atomically overwrites it. The pipeline budget is 25 s (`AGENT_BUDGET_S`), under the 30 s hard limit. If the resident server is absent, the client answers in-process in rule mode and never loads a model per query.

## I/O contract (ASSUMED: inferred from the MC3 kit and the public Pinpoint/WebScout entries; the official Match 4 spec was not public)
- `python3 /app/app.py --query-id q01 --query "..." [--url https://...]`. Also accepted: a positional query, `--question/--task/--prompt`, `--id/--task-id`, `--start-url/--website/--site`, `--input tasks.json`, `--output-dir`, a no-op `--index`/`--corpus`. Unknown flags are ignored.
- Output `/app/output/<query-id>_output.json`:
  `{"answer": "...", "sources": [url], "citations": [url], "source_url": url, "confidence": x, "trace": {...}, "seconds": s}`.
  `sources` and `citations` hold the same single URL. `trace` and `seconds` are debug fields: drop them if the spec forbids extra keys (`write(..., extra=False)`).
- Container `CMD python3 /app/app.py --serve` loads the model once (startup) and serves a unix socket `/tmp/agent.sock`.
- Robust to likely harness variants:
  - `python3 /app/app.py --index [...]` or `--warmup` (MC3-style startup hook): starts the resident server if it is not running and **blocks until the model is loaded** (≤ `AGENT_INDEX_WAIT_S`, default 540 s), so model load is charged to startup, not to a query.
  - Harness overrides CMD (e.g. `sleep infinity`): the first query spawns the server in the background (that one query is answered in rule mode), later queries use the GPU model. A file lock guarantees one server per container.
  - Env-var input when no CLI query is given: `AGENT_QUERY`/`QUERY`, `AGENT_QUERY_ID`/`QUERY_ID`, `AGENT_URL`/`START_URL`/`URL`.
  - Batch file: `--input tasks.json` (list, or `{"tasks"|"queries": [...]}`; keys `id|query_id`, `query|question|task`, `url|start_url`). One output file per task.
  - `--output-dir DIR` or env `AGENT_OUTPUT` to redirect output.
- Formats (assumptions to revisit once real examples are seen): US phones `800-221-1212` (the grader keeps `( ) +`, so these are removed). Versions without `v`. API dates in ISO `YYYY-MM-DD`. Years as `YYYY`. Page-extracted values verbatim.
- Network: assumes outbound internet during grading (the general PDF says so). If only an allowlist is reachable (as reported for the notebook pod), search engines fail and the agent falls back to resolvers and the start URL.

## Layout
```
app/app.py              CLI client (tolerant args, atomic output, watchdog)
app/agent/agent.py      pipeline      app/agent/resolvers.py  PyPI/npm/crates/GitHub/endoflife/Wikidata
app/agent/extract.py    typed extractors   app/agent/search.py  Brave/Bing/DDG HTML
app/agent/net.py        stdlib HTTP + cache + HTML->text   app/agent/llm.py  Qwen judge (transformers, GPU)
app/agent/server.py     resident unix-socket server
Dockerfile, requirements-gpu.txt, scripts/fetch_model.sh, scripts/gpu_check.sh
tests/queries.json (40 verified queries), tests/run_eval.py, tests/results.md|json
```
Core agent = Python stdlib only (no pip deps). The GPU path adds transformers etc. with `--no-deps`, then checks that `torch.version.hip` is still set.

## Run locally (CPU)
```
python3 tests/run_eval.py            # all queries, fresh process each, 30 s kill, official normalisation
python3 app/app.py --query-id t --query "Who is the CEO of AMD?"   # AGENT_OUTPUT=/tmp/o to redirect output
```

## Published image
- `ghcr.io/solar-depin-hub/amd-match4-agent:v1`, assembled by `scripts/assemble.sh` in GitHub Actions (`.github/workflows/image.yml`, manual dispatch):
  the 11 unmodified base layers + a weights layer (`/models/qwen` = Qwen/Qwen3-4B-Instruct-2507, bf16, ~8 GB) + an app/deps layer (`/app`, `/opt/deps`).
  No docker pull of the 29 GiB base, no secrets (the workflow uses the ephemeral `GITHUB_TOKEN` only for the push).
- Python deps pinned in `app/requirements.txt`, verified on CPython 3.14 (transformers 5.20.0 loads and generates; numpy etc. come from the base venv).

## On the AMD notebook (TODO)
1. `scripts/fetch_model.sh Qwen/Qwen3-8B` (fallback `Qwen/Qwen3-4B-Instruct-2507`).
2. `docker build -t m4 .`, then check the size (≤ 60 GiB uncompressed) and that `torch.version.hip` survives.
3. `docker run -d --device=/dev/kfd --device=/dev/dri --group-add video --name m4 m4`, then `scripts/gpu_check.sh m4`. Measure startup (≤ 10 min), per-query time (≤ 30 s), VRAM peak (1–48 GiB), and whether the pod has network or only an allowlist.
4. Compare the LLM judge with rule mode on `tests/` and keep whichever scores better.
5. Image is published early (no official spec yet); re-tag after spec/GPU checks. Submission = public image link, never committed to a public repo.
