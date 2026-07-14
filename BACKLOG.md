# Backlog

This backlog is the working queue for upcoming development. It should be updated after every sprint.

## Completed Sprints

### Sprint 1: Runtime Foundation

Objective: create a clean production foundation that starts, validates itself, initializes local resources, and remains idle without executing business logic.

Status: Complete.

Scope:

- Project structure.
- Dependency management.
- Centralized configuration.
- Structured logging.
- SQLite initialization and migrations.
- Initial schema for future phases.
- Core domain models.
- Storage directory initialization.
- Service container.
- Worker framework interfaces.
- Provider framework interfaces.
- Health checks.
- Main application startup flow.
- Foundation tests.

Out of scope:

- Topic discovery.
- Ranking logic.
- Text generation.
- Image generation.
- Publishing automation.
- Real provider implementations.
- UI.

Verification:

- Application starts with default configuration. Done.
- Application creates required local directories. Done.
- Application initializes SQLite. Done.
- Application applies migrations. Done.
- Application configures logs. Done.
- Application prints a concise startup report. Done.
- Application remains idle until stopped. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine` package.
- `pyproject.toml`.
- `requirements-dev.txt`.
- `config.example.toml`.
- SQLite migration `001_initial_schema`.
- Foundation test suite.

### Sprint 2: Job Orchestration Engine

Objective: implement the generic execution engine that coordinates all future work.

Status: Complete.

Scope:

- Generic job model.
- Persistent SQLite job queue.
- Job repository methods.
- Job lifecycle transitions.
- Worker execution framework.
- Handler registry for future job types.
- Configurable retry policy.
- Lightweight scheduler.
- Concurrency limit support.
- Stale running-job recovery.
- Graceful shutdown.
- Runtime metrics.
- Expanded health checks.
- Orchestration tests.

Out of scope:

- Hacker News.
- OpenRouter.
- Image generation.
- Playwright.
- LinkedIn.
- AI.
- Business-specific job handlers.

Verification:

- Jobs can be created and persisted. Done.
- Queue ordering respects schedule, priority, and creation time. Done.
- Registered handlers can execute jobs. Done.
- Exceptions produce retry or permanent failure states. Done.
- Scheduler dispatches pending jobs without duplicate execution. Done.
- Stale running jobs are recovered after restart. Done.
- Metrics report queue and execution state. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/db/jobs.py`.
- `src/content_engine/orchestration/`.
- SQLite migration `002_job_orchestration`.
- Expanded health diagnostics.
- Scheduler startup/shutdown wiring.
- Orchestration test suite.

### Sprint 3: Topic Discovery

Objective: discover and store candidate technology topics.

Status: Complete.

Scope:

- Topic provider contract tests.
- Hacker News topic provider.
- Discovery service.
- Configurable filtering.
- Topic deduplication.
- Topic persistence.
- `DISCOVER_TOPICS` job handler.
- Discovery metrics and logs.
- Error handling tests.

Out of scope:

- OpenRouter.
- Image generation.
- Playwright.
- LinkedIn.
- Publishing.
- Content generation.

Verification:

- Hacker News provider parses mocked API responses. Done.
- Filtering accepts relevant technology topics and rejects unrelated items. Done.
- Duplicate URLs, exact titles, and near-duplicate titles are handled. Done.
- Accepted topics persist across restarts. Done.
- `DISCOVER_TOPICS` executes through the generic job engine. Done.
- Provider failures are logged and surfaced through job failure/retry behavior. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/discovery/`.
- `src/content_engine/discovery/providers/hacker_news.py`.
- `src/content_engine/db/topics.py`.
- SQLite migration `003_topic_discovery`.
- `DISCOVER_TOPICS` job handler.
- Discovery test suite.

### Sprint 4: Content Planning Engine

Objective: transform discovered topics into structured, platform-independent content plans.

Status: Complete.

Scope:

- `ContentPlan` model.
- Content plan persistence and history.
- Deterministic local planner.
- Topic classification.
- Keyword extraction.
- Persona selection.
- Hook style selection.
- Visual theme selection.
- `PLAN_CONTENT` job handler.
- Planner configuration.
- Planner tests.

Out of scope:

- LLM text generation.
- LinkedIn text.
- Instagram captions.
- Tweets.
- Blog drafts.
- Image generation.
- Publishing.

Verification:

- Planner creates a reusable structured plan from a topic. Done.
- Persona selection is deterministic and configurable. Done.
- Hook style rotation avoids immediate repetition. Done.
- Visual theme selection is deterministic and configurable. Done.
- Topic classification and keyword extraction are tested. Done.
- Plans are persisted without overwriting history. Done.
- `PLAN_CONTENT` executes through the generic job engine. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/planning/`.
- `src/content_engine/db/content_plans.py`.
- SQLite migration `004_content_planning`.
- `ContentPlan` domain model.
- `PLAN_CONTENT` job handler.
- Planning test suite.

### Sprint 5: Knowledge Engine

Objective: convert raw internet content into structured knowledge documents for future planners, writers, image generators, and AI systems.

Status: Complete.

Scope:

- `KnowledgeDocument` model.
- Knowledge document persistence and history.
- Article fetching from topic source URLs.
- HTML content extraction.
- Deterministic knowledge processing.
- Concise local summarization.
- Keyword extraction.
- Technology, company, people, and concept detection.
- `BUILD_KNOWLEDGE` job handler.
- Knowledge tests using mock HTML.

Out of scope:

- LinkedIn post generation.
- Image generation.
- Publishing.
- OpenRouter or other LLM calls.
- Browser automation.

Verification:

- Fetching handles successful HTML and failures. Done.
- Extraction removes navigation/scripts/footers enough for clean article text. Done.
- Processing creates summary, keywords, tags, entities, reading time, and audience metadata. Done.
- Knowledge documents persist without overwriting history. Done.
- `BUILD_KNOWLEDGE` executes through the generic job engine. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/knowledge/`.
- `src/content_engine/db/knowledge.py`.
- SQLite migration `005_knowledge_engine`.
- `KnowledgeDocument` domain model.
- `BUILD_KNOWLEDGE` job handler.
- Knowledge Engine test suite.

### Sprint 6: Content Lifecycle

Objective: establish `ContentItem` as the canonical lifecycle object for one idea moving through the system.

Status: Complete.

Scope:

- `ContentItem` model.
- Finite state machine for lifecycle stages.
- Content item persistence.
- Stage transition history.
- Artifact attachment model.
- Job dependency execution support.
- Pipeline coordinator.
- Pipeline metrics.
- Lifecycle, dependency, recovery, and duplicate-prevention tests.

Out of scope:

- Writing.
- Image generation.
- Publishing.
- Dashboard.
- Instagram.

Verification:

- Invalid lifecycle transitions are rejected. Done.
- Valid lifecycle transitions are persisted. Done.
- Artifacts attach to content items. Done.
- Jobs with unmet dependencies do not execute. Done.
- Pipeline resumes without duplicating completed work. Done.
- Failed content items are visible. Done.
- Duplicate content items for the same topic are prevented. Done.
- Tests pass. Done.

Completed artifacts:

- `ContentItem`, `ContentArtifact`, and `ContentStageTransition` domain models.
- SQLite migration `006_content_lifecycle`.
- `ContentItemRepository`.
- Finite state machine for lifecycle transitions.
- Dependency-aware job claiming.
- Pipeline coordinator.
- Pipeline metrics.
- Lifecycle-aware knowledge and planning job handler integration.
- Content lifecycle test suite.

### Sprint 7: AI Writing Engine

Objective: generate high-quality LinkedIn drafts from planned content items using a provider-driven Writing Engine.

Status: Complete.

Scope:

- Writer abstraction.
- `LinkedInWriter`.
- LLM provider abstraction.
- OpenRouter provider.
- External prompt registry.
- Prompt versioning.
- Prompt placeholder rendering.
- `PostArtifact` model and persistence.
- Draft version history.
- Deterministic humanization.
- Quality validation.
- `WRITE_LINKEDIN_POST` job handler.
- Pipeline integration from `PLANNED` to `WRITING_READY`.
- Writing tests.

Out of scope:

- Image generation.
- Publishing.
- Playwright.
- Instagram.
- X.
- Blog generation.
- Newsletter generation.

Verification:

- Prompt rendering works with versions and variables. Done.
- Provider abstraction works with fake providers and OpenRouter implementation. Done.
- Humanizer removes configured cliches and normalizes hashtags. Done.
- Validator rejects low-quality drafts. Done.
- Post artifacts persist with version history. Done.
- `WRITE_LINKEDIN_POST` creates a post artifact and advances lifecycle. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/writing/`.
- `src/content_engine/db/posts.py`.
- SQLite migration `007_writing_engine`.
- `PostArtifact` domain model.
- `prompts/system.md`.
- `prompts/linkedin.md`.
- `WRITE_LINKEDIN_POST` job handler.
- Writing Engine test suite.

### Vertical Slice: Demo Mode

Objective: prove the existing architecture can produce one complete LinkedIn draft from discovery through writing.

Status: Complete.

Scope:

- Manual `content-engine demo` command.
- One-time execution only.
- Topic discovery through existing provider/filter/dedup service.
- Local ranking and single-topic selection.
- Persist selected topic decision.
- Knowledge artifact generation.
- Content plan generation.
- LinkedIn draft generation through existing Writing Engine and OpenRouter provider.
- Artifact persistence through normal repositories and lifecycle coordinator.
- Clean human-readable report.
- Stage logging with started, completed, duration, and failures.
- Offline integration tests with mocked external APIs.

Out of scope:

- Scheduling.
- Playwright.
- Publishing.
- Dashboard.
- Automatic daily automation.

Verification:

- Demo pipeline persists topic, content item, knowledge, plan, draft, and image artifacts. Done.
- Demo pipeline advances lifecycle to `IMAGE_READY`. Done.
- Demo pipeline leaves no scheduled background jobs in tests. Done.
- Demo report prints selected topic, source, knowledge summary, persona, hook, draft, image path, artifacts, and duration. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/app/demo.py`.
- `content-engine demo` CLI command.
- Demo integration tests.

## Upcoming Sprints

### Sprint 8: Local Image Generation

Objective: generate or compose matching local images.

Status: Complete.

Scope:

- Image provider implementation.
- Deterministic template fallback.
- Media asset persistence.
- Image prompt builder.
- Image prompt and artifact persistence.
- Image validation.
- Image cache reuse.
- `GENERATE_IMAGE` job handler.
- Pipeline integration from `WRITING_READY` to `IMAGE_READY`.
- Demo Mode image generation.
- Image tests.

Out of scope:

- Stable Diffusion or ComfyUI model setup.
- Cloud image providers.
- Image publishing.
- Image approval workflow.

Verification:

- Image prompt builder uses knowledge and planning artifacts. Done.
- Local template provider creates valid PNG files. Done.
- Image artifacts persist with file metadata and hashes. Done.
- Cache reuse avoids unnecessary regeneration for the same prompt. Done.
- `GENERATE_IMAGE` creates an image artifact and advances lifecycle. Done.
- Demo Mode produces an image artifact without scheduling or publishing. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/images/`.
- `src/content_engine/db/images.py`.
- SQLite migration `008_image_generation`.
- `ImagePrompt` and `ImageArtifact` domain models.
- `GENERATE_IMAGE` job handler.
- Image Engine test suite.

### Sprint 9: Content Intelligence

Objective: preserve reproducibility metadata, lineage, placeholder metrics, and deterministic content scoring for every generated content asset.

Status: Complete.

Scope:

- Experiment model.
- Artifact lineage graph.
- Metrics placeholder model.
- Deterministic content score.
- Image artifact versioning.
- Content intelligence service.
- CLI reporting commands.
- Demo and image job integration.
- Intelligence tests.

Out of scope:

- LinkedIn analytics collection.
- Playwright.
- Publishing.
- Dashboard.
- AI-based scoring.

Verification:

- Experiments persist generation settings and artifact metadata. Done.
- Lineage records topic to knowledge to plan to post to image. Done.
- Metrics placeholders exist without collecting platform data. Done.
- Content scores are deterministic. Done.
- CLI reports render assets, experiments, pipeline lineage, and statistics. Done.
- Re-recording intelligence for the same artifacts is idempotent. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/intelligence/`.
- `src/content_engine/db/intelligence.py`.
- SQLite migration `009_content_intelligence`.
- CLI report commands.
- Content Intelligence test suite.

### Sprint 10: Playwright Publisher

Objective: validate and implement LinkedIn publishing through Playwright.

Status: Complete.

Scope:

- Publisher interface.
- `LinkedInPublisher`.
- Mock publisher for dry-run/testing.
- Playwright publisher shell.
- Browser profile configuration.
- Dry-run composer flow.
- Failure screenshots.
- Real publish opt-in.
- Publication artifact persistence.
- `mark-ready` CLI command.
- `PUBLISH_LINKEDIN` job handler.
- `content-engine publish` CLI command.

Out of scope:

- Daily automation.
- LinkedIn analytics collection.
- Multi-platform publishing.
- Dashboard approval workflow.

Verification:

- Dry-run publishing records a skipped attempt and does not advance lifecycle. Done.
- Successful publishing records a publication artifact and advances lifecycle. Done.
- Already-published content is not published twice. Done.
- Failed publishing preserves `READY_TO_PUBLISH` state. Done.
- Tests pass. Done.

Completed artifacts:

- `src/content_engine/publishing/`.
- `src/content_engine/db/publications.py`.
- SQLite migration `010_linkedin_publisher`.
- `PublicationArtifact` domain model.
- `content-engine mark-ready` CLI command.
- `PUBLISH_LINKEDIN` job handler.
- Publishing test suite.

### Sprint 11: Scheduler And Daily Automation

Objective: run the daily content pipeline safely.

Planned work:

- Daily scheduler.
- Publish limit enforcement.
- Queue fill policy.
- Pause/resume controls.

### Sprint 12: Dashboard

Objective: provide local visibility and approval workflow.

Planned work:

- Local status dashboard.
- Content preview.
- Approval/rejection controls.
- Operational health view.

### Sprint 13: Instagram

Objective: add the first non-LinkedIn publishing target.

Planned work:

- Instagram platform rules.
- Instagram formatter.
- Instagram media requirements.
- Instagram publisher design.
