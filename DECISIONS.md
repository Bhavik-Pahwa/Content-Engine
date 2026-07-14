# Architectural Decision Records

This document records important engineering decisions.

Status values:

- Proposed: recommended but not yet validated in implementation.
- Accepted: approved for implementation.
- Superseded: replaced by a later decision.
- Rejected: considered and intentionally not chosen.

## ADR-001: Use SQLite As The Initial Database

Decision: Use SQLite for the first production version.

Context: The application runs on a single Linux laptop, has low write volume, and needs durable local state.

Options considered:

- SQLite
- PostgreSQL
- File-based JSON storage
- External hosted database

Final choice: SQLite.

Reasoning: SQLite is local, reliable, free, low maintenance, and sufficient for a single-machine daily publishing workflow.

Trade-offs: SQLite is not ideal for high concurrency, remote access, or multi-machine scale. The repository layer should avoid leaking SQLite-specific assumptions so PostgreSQL remains possible later.

Status: Accepted.

## ADR-002: Use A Queue-First Pipeline

Decision: Store intermediate work in durable queues and explicit states.

Context: The system must survive restarts, provider outages, and partial failures.

Options considered:

- Direct in-memory pipeline from topic discovery to publishing
- Filesystem-based handoff
- Database-backed queue
- External task queue

Final choice: Database-backed queue using SQLite.

Reasoning: A queue-first design prevents lost work, enables retries, supports inspection, and separates generation from publishing.

Trade-offs: This introduces more state management than a direct script. The complexity is justified by the need for 24x7 unattended operation.

Status: Accepted.

## ADR-003: Start With A Single Local Process And Worker Loops

Decision: Run workers inside one long-lived application process at first.

Context: The target machine is modest, and the workload is low frequency.

Options considered:

- One monolithic script
- One process with scheduled workers
- Multiple OS services
- Distributed task queue

Final choice: One process with scheduled workers.

Reasoning: This keeps deployment simple while preserving clean worker boundaries in the codebase.

Trade-offs: A single process can fail as a unit. The application must use durable state so restart recovery is reliable. Later versions can split workers into separate processes if needed.

Status: Accepted.

## ADR-004: Use Provider Interfaces For Replaceable Capabilities

Decision: Implement topic sources, generators, image providers, publishers, and notification systems behind provider interfaces.

Context: The project is expected to support additional AI providers, topic sources, and publishing platforms.

Options considered:

- Hardcoded integrations
- Provider interfaces
- Full plugin system from day one

Final choice: Provider interfaces now, plugin system later only if needed.

Reasoning: Interfaces provide extensibility without premature plugin infrastructure.

Trade-offs: Interfaces require discipline and contract tests. They may need refinement as real providers expose edge cases.

Status: Accepted.

## ADR-005: Generate Images Locally By Default

Decision: Prefer local image generation for the first version.

Context: The project should minimize recurring costs and run on hardware without a dedicated GPU.

Options considered:

- Paid image-generation APIs
- Local CPU image generation
- Lightweight local models optimized for modest hardware
- Template-based image generation
- Search/select existing public images

Final choice: Local-first image generation, with template-based fallback strongly considered.

Reasoning: Pure AI image generation on an Intel i5 with 8 GB RAM may be slow. A hybrid approach is safer: use local generation where practical, but keep a deterministic template/image composition provider available for reliable daily output.

Trade-offs: Local generation can be slow and lower quality. Template-based images may be less novel but are much more reliable on the target machine.

Status: Accepted.

## ADR-006: Use Playwright For LinkedIn Publishing

Decision: Use Playwright as the initial LinkedIn publishing mechanism.

Context: LinkedIn does not provide a simple low-cost public posting API path for this local automation use case.

Options considered:

- Playwright browser automation
- Official LinkedIn API
- Manual posting only
- Third-party social scheduling service

Final choice: Playwright behind a publisher provider.

Reasoning: Playwright is practical for local browser automation and avoids recurring scheduler costs.

Trade-offs: Browser automation is fragile, can break when the site changes, and must be conservative. Publishing should include dry-run mode, screenshots on failure, daily limits, and manual pause.

Status: Accepted.

## ADR-007: Keep Publishing Separate From Content Generation

Decision: Do not publish immediately after generating content.

Context: Generation and publishing have different failure modes and operational risk.

Options considered:

- Generate and publish immediately
- Generate into a queue, then publish when scheduled
- Require manual approval for every post

Final choice: Generate into a queue, then publish one due post per day. Keep optional approval support in the design.

Reasoning: This enables inspection, retry, scheduling, and future multi-platform support.

Trade-offs: Requires queue management and state transitions. Also means generated content can become stale, so future ranking should consider freshness.

Status: Accepted.

## ADR-008: Include Optional Human Approval State

Decision: Design the post lifecycle so manual approval can be enabled.

Context: Automated publishing carries reputational risk.

Options considered:

- Fully automatic only
- Approval required for all posts
- Optional approval state controlled by configuration

Final choice: Optional approval state.

Reasoning: This allows early safe operation and future workflow expansion without blocking automation experiments.

Trade-offs: Adds another state and user workflow. The first implementation can default to dry-run or automatic queueing while preserving the state model.

Status: Accepted.

## ADR-009: Use Structured Logging And Durable Audit Events

Decision: Separate application logs from durable audit history.

Context: Debugging browser automation and provider failures requires operational detail. Business events such as state changes should survive log rotation.

Options considered:

- Plain text logs only
- Structured logs only
- Structured logs plus database audit events

Final choice: Structured logs plus database audit events.

Reasoning: Logs help diagnose runtime problems. Audit events explain what happened to a topic, post, or publishing attempt over time.

Trade-offs: More data is stored. Retention policy should be defined before long-term production use.

Status: Accepted.

## ADR-010: Avoid A Web UI In The First Implementation

Decision: Do not start with a web dashboard unless needed for verification.

Context: The first priority is reliable content pipeline behavior.

Options considered:

- CLI/status commands first
- Local web dashboard first
- Desktop app

Final choice: CLI/status output and logs first; web UI later.

Reasoning: A UI would slow down the initial reliability work. The data model should still allow a UI later.

Trade-offs: Manual review is less comfortable early on. A lightweight preview command or generated markdown report may be useful before a full UI.

Status: Accepted.

## ADR-011: Use pip With requirements-dev.txt For Sprint 1

Decision: Use standard `pip` installation with `requirements-dev.txt` for test dependencies.

Context: The target system should minimize dependency and tooling assumptions. `uv` is not currently installed in the development environment, and Sprint 1 needs no runtime third-party packages.

Options considered:

- uv
- Poetry
- pip with requirements files

Final choice: pip with `requirements-dev.txt`.

Reasoning: The runtime can use the Python standard library for configuration, logging, SQLite, domain models, and service wiring. Keeping runtime dependencies at zero reduces maintenance risk and makes the foundation easy to run on a modest Linux laptop.

Trade-offs: pip requirements files provide less workflow automation than uv or Poetry. The project can move to uv later if dependency management becomes more complex.

Status: Accepted.

## ADR-012: Use Standard-Library Dataclasses For Core Models

Decision: Use Python dataclasses and enums for Sprint 1 domain models and configuration models.

Context: The foundation needs typed, readable models without heavy validation requirements.

Options considered:

- Standard-library dataclasses
- Pydantic models
- SQLAlchemy ORM models
- Plain dictionaries

Final choice: Standard-library dataclasses and enums.

Reasoning: Dataclasses are simple, dependency-free, testable, and adequate for the current domain layer. Runtime validation is implemented explicitly in the configuration loader and database boundaries.

Trade-offs: Dataclasses do not provide automatic parsing and validation like Pydantic. If provider payloads become complex, a validation library can be reconsidered later.

Status: Accepted.

## ADR-013: Use A src Package Layout

Decision: Place application code under `src/content_engine`.

Context: The codebase is expected to grow and needs a layout that separates importable application code from tests, documentation, and local runtime files.

Options considered:

- Flat package in repository root
- `src/` package layout
- Deep layered folder hierarchy from day one

Final choice: `src/content_engine`.

Reasoning: A `src/` layout prevents tests from accidentally importing files from the repository root and keeps the project ready for packaging without adding unnecessary nesting.

Trade-offs: Running commands requires editable installation or setting `PYTHONPATH=src` when not installed.

Status: Accepted.

## ADR-014: Use SQL Migration Files Without An ORM For Sprint 1

Decision: Use raw SQL migration files and a small migration runner.

Context: The initial schema should be explicit and SQLite-focused while avoiding unnecessary runtime dependencies.

Options considered:

- Raw SQL migrations
- Alembic
- SQLAlchemy ORM metadata
- Manual schema creation in Python strings

Final choice: Raw SQL migration files executed by a migration runner.

Reasoning: SQL files keep the database contract visible and easy to review. The workload is simple enough that an ORM and migration framework would add more complexity than value in Sprint 1.

Trade-offs: Future complex migrations will need careful hand-written SQL. An ORM or migration tool can be adopted later if schema evolution becomes difficult.

Status: Accepted.

## ADR-015: Use A Service Container For Shared Dependencies

Decision: Initialize shared services once during startup and pass them through a service container.

Context: Future workers and providers will need configuration, logging, repositories, storage paths, and registries. Allowing modules to create these dependencies independently would make tests and long-term maintenance harder.

Options considered:

- Module-level global services
- Direct construction inside each worker
- Explicit service container
- Full dependency injection framework

Final choice: Explicit service container.

Reasoning: A small dataclass container keeps dependency flow visible without adding a framework. Tests can initialize the container with temporary paths and fake services.

Trade-offs: The container can become too broad if not curated. New services should be added only when multiple modules genuinely need them.

Status: Accepted.

## ADR-016: Use JSON Structured Logs With Rotating Files

Decision: Log to console, rotating application log, and rotating error log using JSON records.

Context: The application will run unattended and needs searchable diagnostics for startup, workers, providers, and browser publishing failures.

Options considered:

- Plain console logs only
- Plain file logs
- JSON structured logs with rotation
- External logging service

Final choice: JSON structured logs with local rotation.

Reasoning: Structured logs are easy to search and parse while keeping the deployment local-first and free.

Trade-offs: JSON logs are less pleasant for humans to skim than plain text. The startup summary remains human-readable to offset this.

Status: Accepted.

## ADR-017: Keep The Runtime Idle Until Workers Are Implemented

Decision: The Sprint 1 `run` command starts the foundation, performs diagnostics, and idles until shutdown without executing business logic.

Context: Sprint 1 is about production foundation, not content generation or publishing.

Options considered:

- Implement placeholder workers
- Run one-off diagnostics and exit
- Start and remain idle with no business workers

Final choice: Start and remain idle with no business workers.

Reasoning: This proves the long-running runtime behavior while avoiding misleading placeholder business logic.

Trade-offs: The app does no useful content work yet. Sprint 2 should add real queue behavior behind tests.

Status: Accepted.

## ADR-018: Represent All Executable Work As Jobs

Decision: Every future unit of executable work should enter the system as a persisted job.

Context: The platform will eventually perform topic fetching, ranking, generation, imaging, publishing, archival, maintenance, and health checks. These tasks need a shared orchestration model.

Options considered:

- Separate bespoke loops per feature
- A generic job engine with job types
- External task queue

Final choice: A generic SQLite-backed job engine with string job types and registered handlers.

Reasoning: A single orchestration model makes retries, metrics, visibility, restart recovery, and scheduling consistent across future features.

Trade-offs: Every future feature must fit the job contract. The engine must stay generic and avoid accumulating business-specific behavior.

Status: Accepted.

## ADR-019: Use Explicit RETRYING State Before Requeueing Failed Jobs

Decision: Use `RETRYING` as a durable status for failed jobs that will be attempted again.

Context: Failed work should remain visible, but retryable jobs also need to be excluded from immediate execution until their backoff time arrives.

Options considered:

- Keep retryable jobs as `PENDING` with delayed `run_after`
- Use a separate `RETRYING` state with delayed `run_after`
- Create a new job for every retry attempt

Final choice: Use `RETRYING` with `run_after`, then make the queue eligible for both `PENDING` and due `RETRYING` jobs.

Reasoning: `RETRYING` makes operational state clearer while preserving a single historical job record.

Trade-offs: Queue queries must include both pending and due retrying jobs. The additional state is worth the visibility.

Status: Accepted.

## ADR-020: Use In-Process Scheduler With Thread-Based Concurrency

Decision: Implement a lightweight in-process scheduler using a thread pool.

Context: The application runs on a single laptop, and Sprint 2 needs orchestration without external infrastructure.

Options considered:

- Synchronous single-job polling
- In-process scheduler with thread pool
- Multiprocessing
- External queue and worker service

Final choice: In-process scheduler with configurable thread-based concurrency.

Reasoning: Threaded execution is simple, sufficient for IO-heavy future tasks, and keeps deployment local-first. The default concurrency is low to respect the target hardware.

Trade-offs: CPU-bound work will not scale well in threads. Heavy local image generation should later be isolated or constrained to one worker at a time.

Status: Accepted.

## ADR-021: Recover Stale RUNNING Jobs On Startup

Decision: On scheduler startup, move stale `RUNNING` jobs back into retry or failed states according to retry policy.

Context: A laptop restart or process crash can leave jobs marked running even though no worker is alive.

Options considered:

- Leave stale running jobs untouched
- Mark all running jobs failed on startup
- Recover stale running jobs using lock age and retry policy

Final choice: Recover stale running jobs using a configurable stale timeout and the normal retry policy.

Reasoning: This provides restart safety without discarding work that may be safe to retry.

Trade-offs: A long-running legitimate job could be recovered if the timeout is too low. Defaults should be conservative and configurable.

Status: Accepted.

## ADR-022: Keep Scheduler Handlers Business-Neutral

Decision: The scheduler executes registered handlers by job type but does not know what those job types mean.

Context: Sprint 2 must not implement topic sources, AI, image generation, Playwright, LinkedIn, or any other business-specific behavior.

Options considered:

- Hardcode future job types in scheduler
- Use a generic handler registry
- Use plugin discovery immediately

Final choice: Generic handler registry.

Reasoning: This keeps the execution engine stable as hundreds of future job types are added.

Trade-offs: Unregistered job types must fail clearly or remain pending depending on policy. Sprint 2 chooses clear failure because silent pending jobs are harder to diagnose.

Status: Accepted.

## ADR-023: Use Provider-Driven Topic Discovery

Decision: Topic discovery should run through a discovery service that calls configured topic providers.

Context: Hacker News is the first source, but future sources include RSS feeds, Google News RSS, GitHub Trending, Dev.to, Product Hunt, and other APIs.

Options considered:

- Hardcode Hacker News in the job handler
- Provider-driven discovery service
- Full plugin system

Final choice: Provider-driven discovery service with explicit provider registration.

Reasoning: The job handler remains small and stable, while new providers can be added by implementing the topic provider contract and registering them.

Trade-offs: The service introduces a little orchestration code now, but it prevents the first provider from becoming a special case.

Status: Accepted.

## ADR-024: Use Standard-Library HTTP For Hacker News Initially

Decision: Use `urllib.request` for the Hacker News Firebase API in Sprint 3.

Context: Runtime dependencies are intentionally minimal, and Hacker News requires only simple GET requests with timeouts.

Options considered:

- Standard-library `urllib.request`
- `requests`
- `httpx`
- Async HTTP client

Final choice: Standard-library `urllib.request`.

Reasoning: It avoids adding a runtime dependency for a small API integration. Provider tests can inject a fake client, so the implementation remains testable.

Trade-offs: `urllib` is less ergonomic than `requests` or `httpx`. If future providers require richer HTTP behavior, a maintained HTTP client can be introduced deliberately.

Status: Accepted.

## ADR-025: Start Filtering With Configurable Keyword Categories

Decision: Use configurable keyword categories for initial topic filtering.

Context: The system needs to reject unrelated stories without introducing AI or complex classification in this sprint.

Options considered:

- Accept all Hacker News stories
- Hardcoded keyword list
- Configurable keyword categories
- AI classifier

Final choice: Configurable keyword categories.

Reasoning: Keyword filtering is simple, deterministic, cheap, and easy to test. It can be replaced or supplemented by ranking/classification later.

Trade-offs: Keyword filtering will miss some relevant stories and accept some weak matches. Planning and future ranking can improve topic quality.

Status: Accepted.

## ADR-026: Use URL, Normalized Title, And Fuzzy Title Duplicate Detection

Decision: Detect duplicate topics using normalized URLs, normalized titles, and a configurable near-title similarity threshold.

Context: Topic sources can report the same story under slightly different titles or URLs.

Options considered:

- Database unique URL only
- Exact title matching only
- URL plus title normalization
- URL plus title normalization plus fuzzy title comparison

Final choice: URL, normalized title, and fuzzy title comparison.

Reasoning: This balances correctness and simplicity for the expected low topic volume.

Trade-offs: Fuzzy comparison can occasionally reject distinct but similarly worded topics. The threshold is configurable.

Status: Accepted.

## ADR-027: Introduce ContentPlan As The Contract Between Topics And Generators

Decision: Future content generators should consume `ContentPlan` records rather than raw topics.

Context: The platform needs consistent, reusable intent before any platform-specific text generation happens. A topic alone does not define angle, audience, persona, hook, visual direction, or call to action.

Options considered:

- Let each platform generator decide planning independently
- Store platform-specific drafts directly from topics
- Introduce platform-independent content plans

Final choice: Introduce platform-independent `ContentPlan` records.

Reasoning: Plans make generation more controllable, reusable, auditable, and consistent across LinkedIn, Instagram, X, blogs, newsletters, and future channels.

Trade-offs: The pipeline gains an extra step before text generation. The extra structure is useful because it prevents future generators from duplicating strategy logic.

Status: Accepted.

## ADR-028: Use Deterministic Local Planning Before LLM Planning

Decision: Sprint 4 planning should be deterministic and local.

Context: The project should minimize recurring costs and avoid using an LLM where simple classification and rotation logic is enough.

Options considered:

- Fully LLM-based planning
- Deterministic local planning
- Hybrid local planning plus optional LLM enrichment

Final choice: Deterministic local planning for Sprint 4.

Reasoning: Topic classification, keyword extraction, persona selection, hook selection, and visual theme selection can be implemented cheaply and tested predictably. LLM enrichment can be added later if it clearly improves quality.

Trade-offs: Deterministic planning may be less nuanced than LLM reasoning. The design leaves metadata space and service boundaries for future enrichment.

Status: Accepted.

## ADR-029: Keep Content Plans Platform-Independent

Decision: The planner must not generate platform-specific copy.

Context: The same plan should be reusable by LinkedIn, Instagram, X, blogs, newsletters, and other future generators.

Options considered:

- Planner emits platform-specific drafts
- Planner emits reusable intent only
- Planner emits both intent and drafts

Final choice: Planner emits reusable structured intent only.

Reasoning: Platform formatters and generators should own platform-specific text, while the planner owns content strategy.

Trade-offs: A later generator step is required before anything publishable exists.

Status: Accepted.

## ADR-030: Preserve Planning History Instead Of Overwriting Plans

Decision: Store every generated content plan as a separate immutable history record.

Context: Planning logic will evolve, and the application needs auditability and comparison across versions.

Options considered:

- One mutable plan per topic
- Versioned plan table
- Separate content plan records with version numbers

Final choice: Separate content plan records with per-topic version numbers.

Reasoning: This preserves history while keeping queries straightforward.

Trade-offs: Multiple plans can exist for one topic. Later workflow code must choose the active or latest plan explicitly.

Status: Accepted.

## ADR-031: Introduce KnowledgeDocument As Long-Term Memory

Decision: Store extracted and processed source material as `KnowledgeDocument` records.

Context: Future planners, writers, image generators, and AI systems need a canonical source of facts and context rather than repeatedly reading raw topic URLs.

Options considered:

- Let generators read raw topic URLs directly
- Store only summaries on topics
- Introduce versioned knowledge documents

Final choice: Introduce versioned `KnowledgeDocument` records.

Reasoning: Knowledge documents create durable, reusable, auditable memory that can feed multiple future capabilities.

Trade-offs: The pipeline gains another step before generation. The added structure reduces repeated fetching and keeps raw internet content separate from planned or generated content.

Status: Accepted.

## ADR-032: Use Local Deterministic Knowledge Processing First

Decision: Use deterministic local processing for summaries, keywords, tags, entities, reading time, and audience estimates in Sprint 5.

Context: The project should minimize recurring cost and avoid unnecessary LLM usage.

Options considered:

- LLM-based extraction and summarization
- Local deterministic processing
- Hybrid deterministic processing plus optional LLM enrichment

Final choice: Local deterministic processing.

Reasoning: Basic extraction, summary generation, keyword extraction, and technology tagging can be useful without token spend and can be tested predictably.

Trade-offs: Local summaries are less nuanced than LLM summaries. The schema preserves clean text and metadata so future LLM enrichment can be added later.

Status: Accepted.

## ADR-033: Use Standard-Library Fetching And HTML Extraction Initially

Decision: Implement article fetching and extraction with the Python standard library in Sprint 5.

Context: The current runtime has no third-party dependencies, and the initial source is ordinary article URLs from Hacker News topics.

Options considered:

- Standard-library `urllib` plus `html.parser`
- `requests` plus BeautifulSoup
- `trafilatura`
- `readability-lxml`

Final choice: Standard-library `urllib` and a conservative HTML parser/extractor.

Reasoning: This keeps the runtime small and dependency-free while still supporting redirects, timeouts, content-type checks, metadata extraction, and main-text extraction for typical articles.

Trade-offs: Dedicated article extraction libraries handle messy web pages better. If extraction quality becomes a bottleneck, a focused dependency such as `trafilatura` can be adopted deliberately.

Status: Accepted.

## ADR-034: Preserve Knowledge History Instead Of Overwriting Documents

Decision: Store every generated knowledge document as a separate versioned record.

Context: Source pages can change, extraction logic can improve, and future AI systems need traceable historical context.

Options considered:

- Mutate one knowledge row per topic
- Store only latest extraction
- Store versioned knowledge documents

Final choice: Store versioned knowledge documents.

Reasoning: Versioning preserves history and makes reprocessing safe.

Trade-offs: Storage grows over time. Retention and archival policy should be defined during operational hardening.

Status: Accepted.

## ADR-035: Introduce ContentItem As The Canonical Lifecycle Object

Decision: Introduce `ContentItem` as the canonical record for one idea moving through the content pipeline.

Context: Topics, knowledge documents, content plans, future drafts, images, publishing records, and analytics should not behave like disconnected islands.

Options considered:

- Keep connecting subsystem records by convention
- Add foreign keys from every artifact table to a content item
- Add a canonical content item plus artifact attachment table

Final choice: Add `ContentItem` plus a generic artifact attachment table.

Reasoning: This creates a central lifecycle spine without rewriting every existing table in one sprint. Future artifact tables can add direct `content_item_id` columns when useful, while the attachment table keeps the lifecycle coherent now.

Trade-offs: Artifact lookup requires a join table. This is acceptable for the current low-volume local system and avoids a risky migration of existing subsystem tables.

Status: Accepted.

## ADR-036: Use A Finite State Machine For Content Lifecycle Stages

Decision: Represent lifecycle progress as explicit stages with validated transitions.

Context: The app must always know where a content item is and prevent invalid movement such as publishing before writing or planning before knowledge exists.

Options considered:

- Free-form status strings
- Stage enum without validation
- Explicit finite state machine

Final choice: Explicit finite state machine.

Reasoning: The pipeline will become more complex as writing, image generation, publishing, and analytics are added. Validated transitions keep state understandable and recoverable.

Trade-offs: Exceptional workflows require deliberate transition support instead of ad hoc updates.

Status: Accepted.

## ADR-037: Use Job Dependencies For Pipeline Ordering

Decision: Extend jobs so the scheduler only claims jobs whose dependency jobs have completed.

Context: Future jobs must run in order: knowledge before planning, planning before writing, writing before image generation, image before publishing.

Options considered:

- Enforce ordering inside handlers
- Poll lifecycle stage only
- Use job dependencies
- External workflow engine

Final choice: Use SQLite-backed job dependencies in the existing job engine.

Reasoning: Dependencies fit the current local queue and avoid introducing a workflow engine. Lifecycle stage and dependencies serve different purposes: lifecycle tracks content state, dependencies order execution.

Trade-offs: Dependency graphs can become hard to inspect without operator tooling. CLI inspection should follow soon.

Status: Accepted.

## ADR-038: Preserve Stage Transition History

Decision: Store every content item stage transition in an append-only history table.

Context: The application needs auditability, recovery, and visibility for long-running unattended operation.

Options considered:

- Only store current stage
- Store current stage plus application logs
- Store current stage plus durable transition history

Final choice: Store current stage and durable transition history.

Reasoning: Current stage supports fast health/status queries. History explains how an item reached that stage.

Trade-offs: History grows over time and needs retention/archival policy later.

Status: Accepted.

## ADR-039: Keep Pipeline Jobs Backward Compatible

Decision: Pipeline-aware jobs carry both the existing subsystem identifier, such as `topic_id`, and the new `content_item_id`.

Context: `BUILD_KNOWLEDGE` and `PLAN_CONTENT` already existed and were tested as standalone jobs. Sprint 6 needed to unify them under `ContentItem` without breaking direct job execution.

Options considered:

- Replace all job payloads with `content_item_id` only
- Keep old payloads and ignore lifecycle integration
- Carry both `topic_id` and `content_item_id` for pipeline jobs

Final choice: Carry both identifiers for pipeline jobs.

Reasoning: Existing handlers can continue to load their current source records while the lifecycle coordinator can attach resulting artifacts to the canonical content item.

Trade-offs: Payloads contain some duplication. This is acceptable because it preserves backward compatibility and makes job logs easier to inspect.

Status: Accepted.

## ADR-040: Record Lifecycle Artifacts From Existing Job Handlers

Decision: Existing knowledge and planning job handlers record lifecycle artifacts only when their job payload includes `content_item_id`.

Context: The project needs content item stage advancement after durable knowledge and plan records are created, but standalone jobs should remain valid.

Options considered:

- Move artifact recording into the generic job engine
- Require every handler to become lifecycle-only
- Let lifecycle-aware handlers optionally record artifacts

Final choice: Let handlers optionally record artifacts when pipeline context is present.

Reasoning: Artifact recording is business workflow behavior, not generic job engine behavior. Keeping it in the handlers via the coordinator avoids coupling the scheduler to content-specific concepts.

Trade-offs: Handlers know about lifecycle artifacts. This should be kept thin and delegated to the pipeline coordinator.

Status: Accepted.

## ADR-041: Schedule Current Pipeline Steps As A Dependent Chain

Decision: Creating a content item for a topic schedules `BUILD_KNOWLEDGE` and `PLAN_CONTENT`, with planning dependent on knowledge completion.

Context: Sprint 6 introduced dependency-aware jobs and a pipeline coordinator. The next step should be visible and durable immediately, but the scheduler must not execute it early.

Options considered:

- Schedule only the next job at each stage
- Schedule the known current chain with dependencies
- Wait for a separate daily automation scheduler

Final choice: Schedule the known current chain with dependencies.

Reasoning: This makes restart behavior straightforward because the queued pipeline is durable. Dependency checks prevent premature execution.

Trade-offs: If knowledge succeeds at the job level but artifact recording fails, the dependent job may become eligible while lifecycle state is stale. Current handlers record artifacts before returning success, and later operational tooling should surface any mismatch.

Status: Accepted.

## ADR-042: Keep Prompts Outside Python Source

Decision: Store writing prompts as versioned markdown files under `prompts/`.

Context: Prompt wording will change frequently as quality improves. Hardcoded prompts make iteration risky and hide an important product artifact inside implementation code.

Options considered:

- Hardcode prompt strings in writer classes
- Store prompts in configuration values
- Store prompt files in a prompt registry

Final choice: Store prompt files in a prompt registry.

Reasoning: Prompt files are easy to review, version, test, and tune without changing writer logic. The registry renders placeholders at runtime and records prompt versions in post metadata.

Trade-offs: Missing prompt files become runtime configuration failures. Health or operational checks should later validate required prompts explicitly.

Status: Accepted.

## ADR-043: Introduce A Writing Engine With Platform Writers

Decision: Implement a generic Writing Engine with platform-specific writer implementations, starting with `LinkedInWriter`.

Context: LinkedIn is the first target, but future output formats include Instagram captions, X posts, blogs, and newsletters.

Options considered:

- One generic writer with platform conditionals
- Separate platform writers behind a shared writer contract
- One-off LinkedIn generation script

Final choice: Separate platform writers behind a shared writer contract.

Reasoning: Each platform has different length, tone, structure, and validation rules. A writer contract keeps the pipeline stable while allowing platform-specific behavior to live in focused classes.

Trade-offs: Some prompt assembly and validation logic may be duplicated across future writers. Shared helpers should be extracted only when a second platform proves the common shape.

Status: Accepted.

## ADR-044: Use OpenRouter Behind An LLM Provider Boundary

Decision: Add OpenRouter as the initial LLM provider behind a text-generation provider interface.

Context: The project needs AI-assisted LinkedIn drafts but should support future providers such as OpenAI, Claude, Gemini, and Ollama without changing writer logic.

Options considered:

- Call OpenRouter directly from `LinkedInWriter`
- Add a provider interface and OpenRouter implementation
- Delay provider implementation and use only fakes

Final choice: Add a provider interface and OpenRouter implementation.

Reasoning: Provider boundaries preserve extensibility and make tests cheap with fake providers. OpenRouter support is available when `OPENROUTER_API_KEY` is configured, while tests avoid live API calls.

Trade-offs: The first live generation path still depends on a network API and may incur cost. The system must fail gracefully when the API key is missing or the provider is unavailable.

Status: Accepted.

## ADR-045: Store Generated Drafts As Versioned Post Artifacts

Decision: Persist each generated platform draft as an immutable `PostArtifact` version linked to a `ContentItem`.

Context: Draft quality will improve over time, and the system must preserve generation history, provider metadata, prompt versions, and retry context.

Options considered:

- Store latest draft directly on content items
- Store one mutable post row per content item/platform
- Store versioned post artifacts

Final choice: Store versioned post artifacts.

Reasoning: Versioning keeps retries and improvements auditable. Linking artifacts to content items keeps the lifecycle canonical without making posts the root object.

Trade-offs: Future publishing code must choose the latest approved or draft version explicitly.

Status: Accepted.

## ADR-046: Validate And Humanize Drafts Deterministically Before Retrying

Decision: Run deterministic humanization and validation before requesting another LLM generation attempt.

Context: Many quality issues are mechanical: spacing, repeated phrases, too many hashtags, banned cliches, or excessive length.

Options considered:

- Accept provider output directly
- Ask the LLM to fix every issue
- Apply deterministic cleanup and validate before retrying

Final choice: Apply deterministic cleanup and validate before retrying.

Reasoning: Deterministic transforms are cheaper, testable, and predictable. LLM retries should be reserved for content that still fails validation after cleanup.

Trade-offs: Deterministic cleanup is less nuanced than a human editor. Future review tooling should allow manual edits before publishing.

Status: Accepted.

## ADR-047: Writers Consume Lifecycle Artifacts, Not Raw Topics

Decision: Writers load `KnowledgeDocument` and `ContentPlan` artifacts attached to a `ContentItem`; they do not read raw `Topic` records.

Context: Sprint 6 established `ContentItem` as the canonical lifecycle object, and Sprint 5/4 created knowledge and planning artifacts as the prepared inputs for generation.

Options considered:

- Let writers read topics directly
- Pass raw topic, knowledge, and plan objects ad hoc
- Build writer context from attached lifecycle artifacts

Final choice: Build writer context from attached lifecycle artifacts.

Reasoning: This keeps generation based on processed knowledge and structured intent, not raw discovery data. It also makes future platforms consume the same canonical context.

Trade-offs: Writing cannot proceed if artifacts are missing or lifecycle state is stale. That is intentional and should surface as a recoverable job failure.

Status: Accepted.

## ADR-048: Add Demo Mode As A Manual Vertical Slice

Decision: Add a manually triggered `content-engine demo` command that runs one end-to-end pipeline from discovery through LinkedIn draft generation.

Context: Before investing in image generation, publishing, scheduling, or dashboards, the project needs a practical way to evaluate content quality using the real architecture.

Options considered:

- Wait for full automation before testing output quality
- Build a separate demo script outside the application
- Add a CLI command that uses existing application services once

Final choice: Add a CLI command that uses existing application services once.

Reasoning: Demo Mode validates the real system without adding scheduling or publishing behavior. It exercises discovery, ranking, knowledge, planning, lifecycle artifacts, prompt rendering, LLM generation, post persistence, and reporting in one run.

Trade-offs: Demo Mode still depends on live external providers unless tests inject fakes. It is intentionally not a replacement for durable scheduled automation.

Status: Accepted.

## ADR-049: Keep Demo Mode Job-Free And Scheduler-Free

Decision: Demo Mode directly orchestrates existing services and lifecycle artifact recording without starting the scheduler or enqueueing background jobs.

Context: The demo should execute once from start to finish and stop. The existing pipeline coordinator normally schedules next jobs when artifacts are recorded.

Options considered:

- Start the scheduler and let jobs execute normally
- Create jobs and manually claim them
- Call services directly and record artifacts through the lifecycle coordinator with scheduling disabled

Final choice: Call services directly and record artifacts through the lifecycle coordinator with scheduling disabled.

Reasoning: This proves the production service boundaries while avoiding background automation, timing flakiness, and leftover queued work. Completed artifacts are still persisted exactly as normal domain records.

Trade-offs: Demo Mode does not exercise job claiming or retry behavior. Those are already covered by the orchestration tests and normal worker path.

Status: Accepted.

## ADR-050: Rank Demo Topics Locally

Decision: Demo Mode ranks accepted discovered topics with a deterministic local score and selects one topic.

Context: The project does not yet have a dedicated ranking engine, but the demo needs to choose one topic after discovery.

Options considered:

- Use the first discovered topic
- Ask an LLM to rank topics
- Use a deterministic local ranking score

Final choice: Use a deterministic local ranking score based on source score and filtering metadata.

Reasoning: Local ranking is simple, free, testable, and sufficient for a demo. A dedicated ranking subsystem can be added later if content quality review shows topic choice is weak.

Trade-offs: The ranking heuristic is basic and may not choose the most nuanced topic. The demo report makes this visible for review.

Status: Accepted.

## ADR-051: Use A Deterministic Local Template Provider As The Default Image Provider

Decision: Implement `local_template` as the default image provider for Sprint 8.

Context: The target laptop has an Intel i5, Intel Iris Xe graphics, 8 GB RAM, and no dedicated GPU. Full local diffusion models may be slow, fragile to install, or memory-heavy.

Options considered:

- Stable Diffusion through a local Python stack
- SD.cpp or ComfyUI
- Cloud image APIs
- Deterministic local PNG composition

Final choice: Deterministic local PNG composition behind the image provider interface.

Reasoning: The default path must be free, reliable, testable, and able to run unattended on modest hardware. A template provider gives professional-enough LinkedIn visuals now while preserving the provider boundary for SD.cpp, ComfyUI, FLUX, fal.ai, Replicate, or OpenAI Images later.

Trade-offs: Template images are less novel and less photorealistic than AI-generated images. This is acceptable for the baseline because reliability is more important than maximum realism.

Status: Accepted.

## ADR-052: Persist Image Prompts Separately From Image Artifacts

Decision: Store generated image prompts in `image_prompts` and generated files in `image_artifacts`.

Context: Prompt generation is its own meaningful output. Future provider comparisons, prompt revisions, and image regeneration need prompt history even when a cached image is reused.

Options considered:

- Store prompt text only inside image artifact metadata
- Store prompt files on disk only
- Store a separate prompt table linked to image artifacts

Final choice: Store a separate prompt record with prompt version, positive prompt, negative prompt, style metadata, and prompt hash.

Reasoning: Separate prompt records preserve auditability and make cache lookup by prompt hash straightforward.

Trade-offs: The schema has one more table and an extra lookup. The volume is low, so the clarity is worth it.

Status: Accepted.

## ADR-053: Cache Images By Prompt Hash, Provider, Model, And Dimensions

Decision: Reuse a valid image when the same prompt/provider/model/dimensions combination already produced one.

Context: Image generation should avoid duplicate work, especially once heavier local or cloud providers are added.

Options considered:

- Always regenerate images
- Cache by content item only
- Cache by prompt hash and generation settings

Final choice: Cache by prompt hash, provider, model, width, and height, with validation before reuse.

Reasoning: Prompt-level caching is deterministic and avoids coupling reuse to one content item. Validation prevents stale or missing files from being silently reused.

Trade-offs: If the same prompt deserves visual variety, an operator must change prompt inputs, seed policy, or disable cache reuse.

Status: Accepted.

## ADR-054: Extend Demo Mode Through Image Generation

Decision: Demo Mode now generates and records an image artifact after the LinkedIn draft.

Context: Sprint 8's purpose is to prove that completed content assets can receive validated images without introducing scheduling, publishing, or Playwright.

Options considered:

- Leave Demo Mode ending at draft generation
- Require the scheduler to execute `GENERATE_IMAGE`
- Directly call the image service in Demo Mode and record the artifact with scheduling disabled

Final choice: Directly call the image service in Demo Mode and record the artifact through the lifecycle coordinator with scheduling disabled.

Reasoning: This keeps the manual evaluation path useful while preserving the production artifact and lifecycle model.

Trade-offs: Demo Mode still does not exercise scheduler claiming for image jobs. The job handler is covered by focused tests.

Status: Accepted.

## ADR-055: Introduce Experiment Records For Reproducibility

Decision: Persist an `Experiment` record for generated content once post and image artifacts exist.

Context: Future learning requires knowing which prompt versions, providers, models, persona, hook, visual theme, and configuration produced each asset.

Options considered:

- Keep metadata only inside artifact JSON fields
- Add one experiment record per content item
- Add experiment records linked to the exact artifact versions used

Final choice: Add experiment records linked to content item, knowledge, plan, post, and image artifact IDs.

Reasoning: Artifact-level experiment records make generated assets reproducible and comparable without mutating historical artifacts.

Trade-offs: Some metadata is duplicated from artifact tables into the experiment for easier reporting. This is acceptable because experiments are audit records.

Status: Accepted.

## ADR-056: Persist Artifact Lineage Explicitly

Decision: Store lineage edges in `artifact_lineage`.

Context: The system needs to answer how a post or image was produced: topic to knowledge to plan to post to image.

Options considered:

- Infer lineage from content item artifact order
- Store lineage only in logs
- Persist explicit lineage edges

Final choice: Persist explicit lineage edges.

Reasoning: Explicit lineage is easier to inspect, test, and extend when future artifacts such as video, publishing records, and analytics are added.

Trade-offs: Lineage can duplicate information implied by the content item artifact list. The explicit graph is worth it for long-term auditability.

Status: Accepted.

## ADR-057: Create Metrics Placeholders Before Analytics Collection

Decision: Add `content_metrics` rows with empty engagement fields before LinkedIn analytics collection exists.

Context: Publishing and analytics will arrive later, but content assets should already have a stable destination for future impressions, likes, comments, shares, bookmarks, click-through rate, and engagement rate.

Options considered:

- Wait until LinkedIn analytics is implemented
- Store future metrics in experiment metadata
- Add a dedicated metrics placeholder table now

Final choice: Add a dedicated metrics placeholder table.

Reasoning: This avoids a future schema scramble when publishing begins and makes the intended learning loop visible today.

Trade-offs: The table contains empty fields for now. That is intentional and documented.

Status: Accepted.

## ADR-058: Start With Deterministic Content Scores

Decision: Calculate internal quality scores deterministically from generated post structure and metadata.

Context: The system needs early quality signals but should not add another LLM call or external analytics dependency in this sprint.

Options considered:

- No scoring until real analytics exist
- LLM-based quality scoring
- Deterministic scoring from text and metadata

Final choice: Deterministic scoring from reading level, length, hook quality, paragraph count, hashtag count, duplicate score, and prompt confidence.

Reasoning: Deterministic scoring is cheap, testable, and useful enough for comparing drafts before real engagement metrics exist.

Trade-offs: The score is not a prediction of LinkedIn performance. It is an internal quality heuristic and should later be compared against real metrics.

Status: Accepted.

## ADR-059: Add CLI Reports Before Building A Dashboard

Decision: Add report commands for assets, experiments, lineage, and statistics before implementing a dashboard.

Context: Operators need to inspect generated assets and intelligence records, but a web dashboard is still out of scope.

Options considered:

- Query SQLite manually
- Build a dashboard now
- Add focused CLI report commands

Final choice: Add focused CLI report commands.

Reasoning: CLI reports are fast to implement, testable, and sufficient for Sprint 9 validation. They also clarify what a future dashboard should show.

Trade-offs: CLI output is less interactive than a dashboard. A dashboard remains a future sprint once the core pipeline is more stable.

Status: Accepted.

## ADR-060: Use Playwright Persistent Context For LinkedIn Publishing

Decision: Implement LinkedIn publishing with Playwright persistent browser context.

Context: LinkedIn publishing needs a logged-in browser session, but passwords must not be stored in code or configuration.

Options considered:

- Store LinkedIn credentials and log in automatically
- Use Playwright persistent context and manual login once
- Use a third-party social scheduler
- Delay publishing until an official API path exists

Final choice: Use Playwright persistent context and require manual login once.

Reasoning: Persistent context preserves local session cookies without storing passwords. It fits the local-first model and keeps account control with the operator.

Trade-offs: Browser automation is fragile and may require selector maintenance. If the session expires, publishing pauses and asks for manual login.

Status: Accepted.

## ADR-061: Persist Publication Attempts Before Browser Automation

Decision: Create a `PublicationArtifact` attempt before opening LinkedIn.

Context: Publishing can fail due to network issues, expired sessions, Playwright crashes, page changes, image upload failures, or uncertain browser state.

Options considered:

- Persist only successful publications
- Persist after browser automation finishes
- Persist attempt first, then update status

Final choice: Persist attempt first.

Reasoning: Attempt-first persistence makes failures visible and recoverable. It prevents a crash from erasing evidence that publishing was attempted.

Trade-offs: Failed and dry-run attempts accumulate. This is useful operational history and should later get retention policy.

Status: Accepted.

## ADR-062: Enforce Publishing Idempotency With A Database Guard

Decision: Add a partial unique index that allows only one `published` publication artifact per content item/platform.

Context: The system must never accidentally publish the same content item twice.

Options considered:

- Rely on service checks only
- Rely on lifecycle stage only
- Add service checks plus database uniqueness

Final choice: Add service checks plus database uniqueness.

Reasoning: The service returns an existing published record without calling the provider again, and the database prevents duplicate published records if a future bug bypasses the service.

Trade-offs: Manual correction is needed if a publication is incorrectly marked as published. That is preferable to duplicate LinkedIn posts.

Status: Accepted.

## ADR-063: Use MockPublisher For Dry-Run And Tests

Decision: Use `MockPublisher` whenever runtime dry-run is enabled or publishing simulation is configured.

Context: Tests and local previews should not require a real LinkedIn account, a browser install, or network access.

Options considered:

- Always launch Playwright in dry-run mode
- Skip publishing tests
- Use a mock publisher behind the same interface

Final choice: Use a mock publisher behind the same interface.

Reasoning: The mock exercises the service, persistence, idempotency, and lifecycle behavior without risking real posts.

Trade-offs: MockPublisher does not validate LinkedIn selectors or authentication. Real session validation remains a manual operational step.

Status: Accepted.
