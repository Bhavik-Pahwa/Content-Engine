# Project Context

This is a living document. Update it after every development sprint.

## Current Phase

Sprint 10 LinkedIn Publisher complete.

The project now has a runnable Python foundation, a generic job orchestration engine, a provider-driven topic discovery engine, a deterministic content planning engine, a local Knowledge Engine, a canonical `ContentItem` lifecycle, an AI Writing Engine for LinkedIn drafts, a local image generation engine, a Content Intelligence subsystem, a LinkedIn Publisher subsystem, and a manually triggered Demo Mode. It starts, validates configuration, initializes storage, configures structured logging, applies SQLite migrations, builds shared services, registers `DISCOVER_TOPICS`, `BUILD_KNOWLEDGE`, `PLAN_CONTENT`, `WRITE_LINKEDIN_POST`, `GENERATE_IMAGE`, and `PUBLISH_LINKEDIN`, runs diagnostics, starts a scheduler only for the normal runtime command, and can run manual content generation and publishing commands.

## Current Architecture

Implemented foundation architecture:

- Local-first application running on a Linux laptop.
- Single long-running process initially.
- Worker framework defined; no business workers implemented yet.
- SQLite as the durable store.
- Database-backed persistent job queue.
- Generic job execution engine with registered job handlers.
- Lightweight in-process scheduler with configurable concurrency.
- Configurable retry policy with exponential backoff.
- Stale running-job recovery on scheduler startup.
- Runtime metrics exposed through the scheduler service.
- Provider interfaces for replaceable capabilities.
- Topic discovery service as the single entry point for collecting candidate topics.
- Hacker News topic provider using the official Firebase API.
- Configurable keyword filtering for technology categories.
- Duplicate detection using normalized URL, exact normalized title, and near-title similarity.
- Content planning service between discovered topics and future generators.
- `ContentPlan` records as the platform-independent contract for future generation.
- Deterministic local planning for topic classification, keyword extraction, persona selection, hook selection, visual theme selection, and content intent.
- Planning history is preserved with versioned content plan records.
- Knowledge Engine converts topic source URLs into durable `KnowledgeDocument` records.
- Article fetching uses standard-library HTTP with redirects, timeouts, content-type checks, size limits, and retry behavior.
- Article extraction uses a conservative local HTML parser to remove common page chrome and extract title, body text, author, publication date, and canonical URL.
- Knowledge processing is deterministic and local: summary, keywords, entities, technology tags, companies, people, concepts, reading time, difficulty, audience, and category.
- Knowledge history is preserved with versioned records.
- `ContentItem` is the canonical lifecycle object for one idea moving through the system.
- Content lifecycle stages are enforced by a finite state machine: `DISCOVERED`, `KNOWLEDGE_READY`, `PLANNED`, `WRITING_READY`, `IMAGE_READY`, `READY_TO_PUBLISH`, `PUBLISHED`, `ARCHIVED`.
- Content artifacts link subsystem records to a content item without forcing every historical table to be redesigned at once.
- Stage transition history is persisted for auditability and recovery.
- Jobs support dependency IDs; the scheduler only claims jobs whose dependencies are complete.
- Pipeline coordinator creates content items, schedules dependent knowledge/planning jobs, records artifacts, advances lifecycle stages, and resumes interrupted pipelines without duplicating jobs.
- Writing Engine consumes planned content items through attached knowledge and plan artifacts; it does not read raw topics.
- Writer abstraction supports platform-specific writers; `LinkedInWriter` is implemented first.
- LLM provider abstraction supports OpenRouter initially and can be extended for OpenAI, Claude, Gemini, Ollama, or local providers.
- Prompt registry loads versioned prompt files from `prompts/` and renders placeholders at runtime.
- Generated LinkedIn drafts are stored as versioned `PostArtifact` records with generation metadata, provider metadata, hashtags, reading time, and status.
- Deterministic humanization runs before validation to clean formatting, remove configured cliches, and cap hashtags.
- Quality validation checks length, banned phrases, repeated phrases, duplicate drafts, and formatting before a draft is persisted.
- `WRITE_LINKEDIN_POST` integrates with the job engine and advances lifecycle to `WRITING_READY` only after a durable post artifact exists.
- Image generation consumes attached knowledge, plan, and post artifacts from a `ContentItem`.
- `ImagePromptBuilder` creates versioned positive/negative image prompts from knowledge and planning metadata without sending the LinkedIn post body directly to the image provider.
- `LocalTemplateImageProvider` is the default free local image provider and produces deterministic PNG images using the Python standard library.
- `ImagePrompt` and `ImageArtifact` records preserve prompt text, prompt hash, provider/model, dimensions, seed, file path, file hash, generation timing, and metadata.
- Image validation checks file existence, PNG readability, dimensions, final chunk integrity, file size, and SHA-256 hash.
- Image caching can reuse a valid artifact when the same prompt/provider/model/dimensions already produced an image.
- `GENERATE_IMAGE` integrates with the job engine and advances lifecycle from `WRITING_READY` to `IMAGE_READY`.
- Content Intelligence records reproducibility metadata after a post/image exists.
- `Experiment` records capture prompt versions, provider/model names, persona, hook, visual theme, image provider/model, generation timestamps, redacted configuration snapshots, optional git commit hash, and generation metadata.
- Artifact lineage records preserve the chain from topic to knowledge to plan to post to image.
- Content metrics placeholders reserve future LinkedIn analytics fields without collecting platform data yet.
- Deterministic content scores capture reading level, length score, hook quality, paragraph count, hashtag count, duplicate score, and prompt confidence.
- CLI reports are available for listing assets, showing the latest asset, showing an experiment, showing pipeline lineage, and showing statistics.
- Publishing uses a provider interface, with `LinkedInPublisher` implemented first and future publishers intended for Instagram, X, Threads, blogs, and newsletters.
- LinkedIn publishing uses a Playwright persistent browser context when real publishing is enabled.
- Dry-run publishing uses `MockPublisher` by default so tests and local previews do not require a LinkedIn account or Playwright.
- Publication attempts are persisted as `PublicationArtifact` records before browser automation starts.
- Publication records store platform, post/image artifact IDs, status, session path, URL when available, retry count, errors, screenshots, duration, and metadata.
- Publishing is idempotent: a content item/platform can have only one `published` publication record.
- `PUBLISH_LINKEDIN` integrates with the job engine and advances lifecycle from `READY_TO_PUBLISH` to `PUBLISHED` only after a real publish succeeds.
- `content-engine mark-ready` marks one `IMAGE_READY` content item as `READY_TO_PUBLISH`.
- `content-engine publish` publishes exactly one `READY_TO_PUBLISH` content item.
- Demo Mode is available through `content-engine demo`.
- Demo Mode executes one manual vertical slice: discover topics, locally rank and select one topic, build knowledge, create a content plan, generate one LinkedIn draft, generate a local LinkedIn image, record content intelligence, persist artifacts, and print a clean report.
- Demo Mode uses existing services and repositories; it does not schedule background jobs, publish, or use Playwright.
- Playwright publisher provider implemented; real account publishing requires optional Playwright installation, a persistent browser session, and `dry_run=false`.
- Local-first image generation implemented with a deterministic template provider; AI model-backed local/cloud image providers remain future extensions.
- Structured logging and durable audit events.
- `src/content_engine` package layout.
- Standard-library runtime foundation with no runtime third-party dependencies.
- `pip` plus `requirements-dev.txt` for development/test dependencies.

## Completed Work

- Defined project vision.
- Defined engineering principles.
- Proposed high-level architecture.
- Proposed provider architecture.
- Proposed worker model.
- Proposed database design.
- Proposed queue strategy.
- Proposed failure recovery strategy.
- Proposed logging and configuration strategy.
- Recorded initial ADRs.
- Identified initial risks.
- Defined development roadmap.
- Created Sprint 1 application structure.
- Implemented centralized configuration loading from defaults, TOML file, and environment variables.
- Implemented structured console/file/error logging with rotation.
- Implemented SQLite connection management and SQL migration runner.
- Created initial future-facing schema.
- Implemented repository registry with health/settings repositories.
- Implemented dataclass domain models.
- Implemented provider and worker framework contracts.
- Implemented service container for explicit dependency wiring.
- Implemented storage directory initialization.
- Implemented startup diagnostics and health command.
- Implemented idle application runtime with signal-based shutdown.
- Added foundation tests.
- Implemented generic job model and lifecycle.
- Implemented persistent job repository.
- Implemented queue ordering by schedule, priority, and creation time.
- Implemented atomic job claiming.
- Implemented job execution engine.
- Implemented handler registry for future job types.
- Implemented retry policy with durable `RETRYING` state.
- Implemented lightweight scheduler with concurrency limits.
- Implemented stale running-job recovery.
- Implemented runtime metrics snapshots.
- Expanded health checks for queue, scheduler, and worker engine.
- Added orchestration tests.
- Implemented topic discovery configuration.
- Expanded topic domain model and database schema.
- Implemented topic repository.
- Implemented Hacker News provider.
- Implemented configurable topic filtering.
- Implemented duplicate detection.
- Implemented topic discovery service.
- Implemented `DISCOVER_TOPICS` job handler.
- Registered Hacker News provider and discovery job handler at startup.
- Added offline discovery tests using mocked provider/API responses.
- Implemented content planning configuration.
- Implemented `ContentPlan` domain model and repository.
- Added content planning database schema.
- Implemented deterministic topic classifier.
- Implemented content planning service.
- Implemented persona selection.
- Implemented hook style selection and rotation.
- Implemented visual theme selection.
- Implemented `PLAN_CONTENT` job handler.
- Registered content planner at startup.
- Added deterministic planning tests.
- Implemented knowledge configuration.
- Implemented `KnowledgeDocument` domain model and repository.
- Added Knowledge Engine database schema.
- Implemented article fetcher.
- Implemented local HTML article extractor.
- Implemented deterministic knowledge processor.
- Implemented Knowledge Engine service.
- Implemented `BUILD_KNOWLEDGE` job handler.
- Registered Knowledge Engine at startup.
- Added Knowledge Engine tests using mock HTML and fake fetchers.
- Implemented `ContentItem`, `ContentArtifact`, and `ContentStageTransition` domain models.
- Added content lifecycle database schema.
- Implemented content item repository, artifact attachment, lifecycle transition history, and lifecycle metrics.
- Implemented finite state machine validation for content item stages.
- Extended jobs with persisted dependency IDs exposed on the domain model.
- Updated job claiming so unmet dependencies block execution until dependency jobs complete.
- Added duplicate job lookup for pipeline scheduling.
- Implemented pipeline coordinator for content item creation, artifact recording, failure tracking, metrics, and recovery scheduling.
- Updated knowledge and planning job handlers to attach artifacts and advance lifecycle stages when pipeline payloads include `content_item_id`.
- Registered the pipeline coordinator in the service container.
- Added lifecycle, dependency, duplicate-prevention, and recovery tests.
- Implemented writing configuration.
- Implemented prompt registry and external prompt files.
- Implemented OpenRouter LLM provider support.
- Implemented `LinkedInWriter`.
- Implemented deterministic post humanizer.
- Implemented post quality validator.
- Implemented generated post parser.
- Implemented `PostArtifact` domain model and repository.
- Added Writing Engine database schema.
- Implemented Writing Service.
- Implemented `WRITE_LINKEDIN_POST` job handler.
- Registered Writing Engine, OpenRouter provider, and writing job handler at startup.
- Extended the pipeline coordinator so planned content items schedule LinkedIn writing.
- Added Writing Engine tests for prompt rendering, provider abstraction, validation, humanization, persistence, and job execution.
- Implemented manual Demo Mode command.
- Implemented local demo topic ranking.
- Persisted demo topic selection by marking the selected topic as `SELECTED`.
- Added demo stage logging for started, completed, duration, and failure events.
- Added clean demo completion and failure reports.
- Added offline Demo Mode integration tests with mocked external APIs.
- Implemented image generation configuration.
- Implemented `ImagePrompt` and `ImageArtifact` domain models.
- Added image prompt and image artifact database schema.
- Implemented image prompt/artifact repository and metrics.
- Implemented image provider interface.
- Implemented standard-library local template image provider.
- Implemented image prompt builder.
- Implemented image validation.
- Implemented image generation service with retries and cache reuse.
- Implemented `GENERATE_IMAGE` job handler.
- Registered local image provider and image job handler at startup.
- Extended pipeline scheduling from `WRITING_READY` to `GENERATE_IMAGE`.
- Extended Demo Mode to generate and report a local image artifact.
- Added image subsystem tests and updated demo tests.
- Implemented `Experiment`, `ArtifactLineage`, `ContentMetrics`, and `ContentScore` domain models.
- Added content intelligence database schema.
- Added image artifact versioning.
- Implemented content intelligence repository.
- Implemented deterministic content scoring.
- Implemented content intelligence service.
- Integrated content intelligence recording with `GENERATE_IMAGE` and Demo Mode.
- Added CLI report commands: `list-assets`, `show-latest-asset`, `show-experiment`, `show-pipeline`, and `show-statistics`.
- Added content intelligence and reporting tests.
- Implemented publishing configuration and storage directories for browser sessions and screenshots.
- Implemented `PublicationArtifact` domain model.
- Added publication artifact database schema.
- Implemented publication artifact repository and statistics.
- Implemented publisher interface, `LinkedInPublisher`, and `MockPublisher`.
- Implemented publishing service with attempt-first persistence, dry-run handling, failure recording, and idempotency.
- Implemented `PUBLISH_LINKEDIN` job handler.
- Registered publisher provider and publish job handler at startup.
- Added `content-engine mark-ready` CLI command.
- Added `content-engine publish` CLI command.
- Added publishing tests.

## Pending Work

- Complete provider-event and audit repositories.
- Add additional topic providers.
- Benchmark local image-generation options on target hardware.
- Define backup procedure.
- Define operational commands.
- Expand operator tooling into a local approval/review dashboard.
- Add additional image providers after local template output is reviewed.
- Add prompt quality evaluation samples.
- Add optional backfill command for pre-Sprint-9 assets that were generated before Content Intelligence existed.
- Run a real LinkedIn manual-login dry run before enabling real publishing.
- Review generated demo text, image output, content intelligence reports, and dry-run publishing screenshots before investing further in scheduling.

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| LinkedIn UI changes break Playwright publishing | High | High | Isolate publishing behind provider interface, use screenshots on failure, add dry-run tests, pause after repeated failures. |
| Account restrictions from automation | Medium | High | Conservative daily frequency, avoid spam behavior, preserve manual control, use dry-run and approval modes. |
| Local image generation too slow on Intel i5 with 8 GB RAM | High | Medium | Benchmark early, support smaller models, use template-based fallback, generate images ahead of schedule. |
| Free topic sources become unavailable | Medium | Medium | Use multiple source providers, cache results, degrade gracefully. |
| AI provider APIs become unavailable or costly | Medium | Medium | Support local/free providers first, provider fallback, pause generation without breaking publishing queue. |
| Generated posts are low quality or repetitive | Medium | High | Store topic history, add duplicate detection, use style guidelines, introduce review workflow. |
| Queue state becomes inconsistent after crash | Medium | High | Use transactions, explicit states, stale lock recovery, idempotent workers. |
| Browser session expires | High | Medium | Detect login state, pause publishing, notify operator, avoid deleting queued posts. |
| Disk fills with generated images and logs | Medium | Medium | Define retention policy, compress or clean old artifacts, monitor disk usage. |
| SQLite database corruption or accidental deletion | Low | High | Enable backups, keep migrations, use safe shutdown, avoid manual mutation. |
| Too many responsibilities accumulate in one module | Medium | Medium | Maintain module boundaries, review architecture after each sprint. |
| Future platforms have incompatible content models | Medium | Medium | Store canonical post plus platform-specific publish targets and validations. |
| Timezone or schedule mistakes cause wrong publish time | Medium | Medium | Store timezone explicitly, test schedule calculations, log next publish time. |
| No alerting means failures go unnoticed | Medium | Medium | Add notification provider after basic pipeline, expose health status. |
| Dependency churn breaks unattended operation | Medium | Medium | Pin dependencies, update deliberately, keep integration tests. |
| Generic job engine grows business-specific branches | Medium | High | Keep scheduler business-neutral and require feature work to register handlers by job type. |
| Long-running jobs exceed stale timeout and get retried while still active | Low | Medium | Keep stale timeout conservative, make it configurable, and revisit when heavy workers are added. |
| Hacker News API is unavailable or rate-limited | Medium | Medium | Provider failures are isolated, logged, and retried through job orchestration; future providers can be added without changing discovery service. |
| Keyword filtering misses relevant topics | Medium | Medium | Keep categories configurable and improve topic quality through planning and future ranking. |
| Deterministic planning can feel repetitive | Medium | Medium | Rotate hooks, preserve plan history, and keep personas/themes configurable; consider LLM enrichment later only if needed. |
| Platform targets in plans could leak platform assumptions | Low | Medium | Keep plans limited to structured intent and leave platform-specific copy to future generators. |
| Local article extraction misses complex pages | Medium | Medium | Keep extractor isolated, preserve raw HTML when configured, and consider a dedicated extraction dependency if quality becomes a bottleneck. |
| Raw HTML storage can grow quickly | Medium | Medium | Make raw HTML storage configurable and define retention policy during operational hardening. |
| Knowledge processing may miss nuanced entities | Medium | Low | Store clean text and deterministic metadata now; add optional enrichment later if it clearly improves downstream quality. |
| OpenRouter API key is missing or provider is unavailable | Medium | Medium | Keep writing jobs retryable, fail clearly, preserve planned content items, and allow future provider fallback. |
| Prompt changes reduce post quality | Medium | Medium | Version prompts, persist prompt metadata with post artifacts, and keep validation tests around formatting and banned phrases. |

## Technical Risks

### Browser Automation Fragility

LinkedIn publishing via Playwright is likely the most fragile component. It depends on UI structure, login state, network behavior, and platform anti-automation controls.

Mitigation: Treat it as an isolated provider, support dry-run mode, capture screenshots and HTML snapshots on failure, and pause after repeated failures.

### Provider Availability

Free sources and APIs can change, rate-limit, or disappear.

Mitigation: Use provider fallback, cache discovered topics, and avoid making any single provider mandatory.

### State Management Complexity

Queue-first design improves reliability but introduces state transitions that can be mishandled.

Mitigation: Define state machines clearly, test transitions, and use transactions for job claims.

## Performance Risks

### Image Generation Runtime

Local image generation may take minutes or be impractical depending on model choice.

Mitigation: Benchmark before committing, generate ahead of schedule, and include template-based image generation.

### Memory Pressure

8 GB RAM limits local model size and parallelism.

Mitigation: Run one heavy worker at a time, avoid loading multiple models simultaneously, and keep concurrency low.

### Long-Running Process Drift

Memory leaks or browser residue can accumulate in 24x7 operation.

Mitigation: Restart browser contexts, add health checks, and consider a supervised process restart schedule.

## Hardware Limitations

Target hardware:

- Linux laptop
- Intel i5
- Intel Iris Xe Graphics
- 8 GB RAM
- No dedicated GPU

Implications:

- Avoid GPU-dependent generation.
- Avoid large local language models unless benchmarked.
- Keep worker concurrency low.
- Prefer ahead-of-time generation over just-in-time generation.
- Prefer SQLite and local files over heavier services.

## Maintenance Concerns

- Playwright selectors will need maintenance.
- Prompt quality will need iteration.
- Topic sources will need replacement over time.
- Generated media storage will need cleanup.
- Logs and audit tables will need retention policy.
- Documentation must stay current with architecture changes.

## Potential Bottlenecks

- Image generation speed.
- Browser automation failures.
- Text generation provider latency.
- Queue stuck states.
- Manual review overhead if approval becomes required.

## Future Scaling Challenges

If the platform grows beyond one local account and one daily post, likely pressure points will be:

- SQLite concurrency.
- Multi-account credential isolation.
- Per-platform rate limits.
- Provider cost tracking.
- Browser session management.
- Need for a web UI.
- Need for notifications and observability.
- Migration to PostgreSQL or a hosted deployment.

## Startup Instructions

Create and prepare the local environment:

```text
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
```

Run diagnostics:

```text
.venv/bin/content-engine health
```

Run the idle application:

```text
.venv/bin/content-engine run
```

Stop the running application with `Ctrl+C` or `SIGTERM`.

## Test Instructions

Run the foundation test suite:

```text
.venv/bin/python -m pytest
```

Current verification result:

- `71 passed`
- `.venv/bin/python -m compileall -q src tests` passed.
- `.venv/bin/content-engine health` passed and should report migrations through `010_linkedin_publisher`.
- `.venv/bin/content-engine --help` passed and reports `demo`, `mark-ready`, `publish`, and reporting commands.
- `.venv/bin/content-engine mark-ready` passed against the local image-ready asset.
- `.venv/bin/content-engine publish` passed in dry-run mode and recorded a skipped publication attempt.
- Idle runtime starts the scheduler, reports healthy diagnostics, handles `SIGTERM`, stops the scheduler, and exits with code 0.
- Health check reports `DISCOVER_TOPICS`, `BUILD_KNOWLEDGE`, `PLAN_CONTENT`, `WRITE_LINKEDIN_POST`, `GENERATE_IMAGE`, and `PUBLISH_LINKEDIN` registered, with Hacker News, OpenRouter, local template image, and publishing providers configured.

## Next Milestone

Next milestone: real LinkedIn session validation, then scheduler and daily automation.

The next step should be to install the optional Playwright extra, open a persistent LinkedIn browser session, log in manually once, and run `content-engine publish` against a `READY_TO_PUBLISH` item first in dry-run/simulated mode and then with `dry_run=false` only when ready. Scheduling should remain out of scope until manual publishing behavior is trusted.

## Demo Instructions

Run one manual end-to-end demo:

```text
OPENROUTER_API_KEY=... .venv/bin/content-engine demo
```

Optional configuration:

```text
.venv/bin/content-engine demo --config config.toml
```

The number of topics fetched is controlled by existing discovery configuration, especially `discovery.hacker_news_fetch_limit`. Demo Mode now persists topic, knowledge, plan, draft, and image artifacts, and prints the generated image path.

## Publishing Instructions

Dry-run/simulated publishing uses the built-in mock publisher when `runtime.dry_run = true`:

```text
.venv/bin/content-engine mark-ready
.venv/bin/content-engine publish
```

`mark-ready` marks one `IMAGE_READY` item as `READY_TO_PUBLISH`. `publish` publishes exactly one `READY_TO_PUBLISH` item. In dry-run mode it records a skipped publication attempt and does not advance lifecycle.

Real LinkedIn publishing requires the optional Playwright dependency:

```text
.venv/bin/python -m pip install -e '.[publish]'
.venv/bin/python -m playwright install chromium
```

Use a local ignored config file with:

```toml
[runtime]
dry_run = false

[publishing]
provider = "linkedin"
linkedin_session_dir = "storage/browser/linkedin"
screenshot_dir = "storage/screenshots"
simulate = false
```

Run publish once to open the persistent browser context. If LinkedIn asks for login, log in manually in that browser window, close it, and rerun the command. Do not store LinkedIn passwords in code or configuration.

## Development Roadmap

### Sprint 1: Runtime Foundation

Objective: Create a runnable application foundation.

Status: Complete.

Produces runnable software:

- Startup and shutdown flow.
- Configuration loading and validation.
- SQLite connection and migration system.
- Structured logging.
- Basic health/status command.

Verification:

- App starts with valid configuration.
- App fails clearly with invalid configuration.
- Database is created and migrated.
- Logs are written.
- Tests cover configuration and database startup.

### Sprint 2: Job Orchestration Engine

Objective: Implement the generic job orchestration engine.

Status: Complete.

Produces runnable software:

- Persistent job queue.
- Job repository layer.
- Job claiming and retry policy.
- Stale job recovery.
- Generic handler registry.
- Worker execution engine.
- Lightweight scheduler.
- Runtime metrics.
- Expanded health checks.

Verification:

- Jobs can be created, claimed, completed, failed, and retried.
- Restart does not lose queued work.
- Tests cover state transitions and idempotency.

### Sprint 3: Topic Discovery

Objective: Discover and store candidate technology topics.

Status: Complete.

Produces runnable software:

- Topic source provider interface.
- At least one free initial topic source.
- `DISCOVER_TOPICS` job handler.
- Topic deduplication.
- Topic filtering.
- Topic persistence.

Verification:

- Worker stores discovered topics.
- Failed source does not stop all discovery.
- Duplicate topics are handled.
- Tests use fake providers.

### Sprint 4: Content Planning Engine

Objective: Transform discovered topics into reusable, platform-independent content plans.

Status: Complete.

Produces runnable software:

- `ContentPlan` model.
- Content plan persistence.
- Deterministic planner service.
- Persona, hook, and visual theme selection.
- `PLAN_CONTENT` job handler.

Verification:

- Planner creates structured plans from topics.
- Plans remain platform-independent.
- Planning history is preserved.
- Tests cover classifier, personas, hooks, visual themes, persistence, and job execution.

### Sprint 5: Knowledge Engine

Objective: Build the Knowledge Engine.

Status: Complete.

Produces runnable software:

- `KnowledgeDocument` model.
- Knowledge document persistence.
- Article fetching.
- HTML content extraction.
- Deterministic knowledge processing.
- `BUILD_KNOWLEDGE` job handler.

Verification:

- Fetching, extraction, processing, persistence, and job execution are tested.
- Knowledge history is preserved.
- Tests use mock HTML and fake fetchers.

### Sprint 6: Content Lifecycle

Objective: Establish `ContentItem` as the canonical lifecycle object for one idea moving through the system.

Status: Complete.

Produces runnable software:

- Content item repository and schema.
- Artifact attachment model.
- Lifecycle finite state machine.
- Stage transition history.
- Dependency-aware job claiming.
- Pipeline coordinator.
- Lifecycle metrics.

Verification:

- Invalid transitions are rejected.
- Valid transitions are persisted.
- Jobs with unmet dependencies are not claimed.
- Pipeline scheduling avoids duplicate content items and duplicate jobs.
- Pipeline recovery schedules the next available stage.

### Sprint 7: Writing Engine

Objective: Generate versioned text drafts using OpenRouter.

Status: Complete.

Produces runnable software:

- LLM provider interface.
- OpenRouter provider.
- Prompt registry and prompt versioning.
- Draft/post repository.
- `WRITE_LINKEDIN_POST` job.
- Post artifact attached to `ContentItem`.
- Deterministic humanization and validation.

Verification:

- Drafts are generated from content item, knowledge, and plan records.
- Provider failures retry cleanly.
- Draft versions are preserved.
- Lifecycle advances only after a durable draft artifact exists.
- Tests cover prompt rendering, validation, humanization, persistence, and job execution.

### Sprint 8: Local Image Generation

Objective: Generate or compose matching local images.

Status: Complete.

Produces runnable software:

- Image provider interface.
- Local template image provider.
- Image prompt builder.
- Image prompt and artifact persistence.
- Image validation and cache reuse.
- `GENERATE_IMAGE` job.
- Pipeline integration from `WRITING_READY` to `IMAGE_READY`.
- Demo Mode image output.

Verification:

- Image asset is generated and linked to a content item.
- Failure preserves the draft.
- Cache reuse avoids unnecessary regeneration.
- Tests cover prompt building, provider output, validation, persistence, caching, and job execution.

### Sprint 9: Content Intelligence

Objective: Preserve reproducibility metadata, lineage, placeholder metrics, and deterministic scoring for generated assets.

Status: Complete.

Produces runnable software:

- Experiment records.
- Artifact lineage records.
- Metrics placeholders.
- Deterministic content scores.
- CLI reporting commands.
- Demo and image job intelligence recording.

Verification:

- Experiments persist generation settings and artifact metadata.
- Lineage records topic to knowledge to plan to post to image.
- Metrics placeholders exist without collecting platform data.
- Content scores are deterministic.
- CLI reports render assets, experiments, pipeline lineage, and statistics.

### Sprint 10: Playwright Publisher

Objective: Publish one `READY_TO_PUBLISH` content item to LinkedIn through a provider-driven publisher.

Status: Complete.

Produces runnable software:

- Publisher provider interface.
- LinkedIn publisher with Playwright persistent context.
- Mock publisher for dry-runs and tests.
- Publication artifact persistence.
- Attempt-first failure recovery.
- Idempotent publish guard.
- `PUBLISH_LINKEDIN` job.
- `content-engine publish` CLI command.
- Screenshot capture on failure.

Verification:

- Dry-run records a skipped publication attempt without advancing lifecycle.
- Successful publish records a publication artifact and advances lifecycle to `PUBLISHED`.
- Repeated publish after success does not call the provider again.
- Failed publish records the error and preserves `READY_TO_PUBLISH`.
- Tests cover mock publisher, service behavior, job integration, and idempotency.

### Sprint 11: Scheduler And Daily Automation

Objective: Run the daily content pipeline safely.

Produces runnable software:

- Daily scheduler.
- Queue fill policy.
- Publish limit enforcement.
- Pause/resume controls.

Verification:

- Only due content items are selected.
- Daily limit prevents duplicate publishing.
- Manual pause prevents publishing.
- Restart recovery works.

### Sprint 12: Dashboard

Objective: Provide local visibility and approval workflow.

Produces runnable software:

- Local status dashboard.
- Content item and artifact inspection.
- Content preview.
- Approval/rejection controls.
- Operational health view.

Verification:

- Operator can inspect lifecycle state.
- Operator can see failures and retries.
- Approval state affects publishing eligibility.

### Sprint 12: Instagram

Objective: Add the first non-LinkedIn publishing target.

Produces runnable software:

- Instagram platform rules.
- Instagram formatter.
- Instagram media requirements.
- Instagram publisher design.

Verification:

- Instagram can consume the same `ContentItem` artifacts.
- LinkedIn behavior remains unchanged.
- Provider tests verify interface compatibility.

### Later: Operational Hardening

Objective: Make the system suitable for unattended use.

Produces runnable software:

- Pause/resume controls.
- Backup procedure.
- Log retention policy.
- Basic notifications or status reporting.
- Recovery for stuck states.

Verification:

- Restart recovery works.
- Manual pause prevents publishing.
- Backups can be restored.
- Health report identifies failures.

### Current Utility: Autonomous Autopost Loop

`content-engine autopost` runs the real pipeline repeatedly:

Discovery -> Knowledge -> Planning -> Writing -> Image -> Publishing

Behavior:

- Publishes one content item per iteration.
- Persists all intermediate artifacts and publication attempts.
- Uses the configured image provider and publisher.
- Stops on quota, payment, rate-limit, authentication, or checkpoint errors.
- Stops after a configurable number of consecutive non-terminal failures.
- Supports `--max-posts` for bounded test runs.
- Supports `--delay-seconds` for pacing between successful publishes.

Recommended command for unattended local operation:

```bash
CONTENT_ENGINE_DRY_RUN=false CONTENT_ENGINE_PUBLISHING_SIMULATE=false .venv/bin/content-engine autopost --delay-seconds 900
```
