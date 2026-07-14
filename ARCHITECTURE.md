# Architecture Proposal

## Current Implementation Addendum

As of Sprint 10, the implemented pipeline is:

```text
Topic Discovery
  -> Knowledge Document
  -> Content Plan
  -> ContentItem lifecycle
  -> LinkedIn PostArtifact
  -> ImagePrompt
  -> ImageArtifact
  -> Experiment
  -> Lineage + Score + Metrics Placeholder
  -> PublicationArtifact
```

Important implemented components:

- `ContentItem` is the canonical lifecycle object.
- Knowledge, plan, post, and future media/publishing records are attached as artifacts.
- SQLite migrations are current through `010_linkedin_publisher`.
- Jobs are durable and dependency-aware.
- `WRITE_LINKEDIN_POST` generates a versioned LinkedIn draft from attached knowledge and plan artifacts.
- `GENERATE_IMAGE` creates a validated image artifact from attached knowledge, plan, and post artifacts.
- Writers consume lifecycle artifacts, not raw topics.
- Image generation consumes lifecycle artifacts, not raw topics or raw post text.
- Prompts are external markdown files under `prompts/` with version metadata.
- OpenRouter is implemented behind an LLM provider boundary.
- Deterministic humanization and validation run before a post artifact is persisted.
- The default image provider is `local_template`, a deterministic standard-library PNG renderer designed for the target laptop.
- Image prompts are persisted separately from image artifacts and cacheable by prompt hash.
- Content Intelligence records experiments, artifact lineage, deterministic content scores, and future metrics placeholders.
- CLI reporting commands expose assets, experiments, lineage, and statistics without requiring a dashboard.
- `PUBLISH_LINKEDIN` publishes one `READY_TO_PUBLISH` content item and records every attempt as a `PublicationArtifact`.
- `LinkedInPublisher` uses Playwright persistent context for real publishing; `MockPublisher` handles dry-run and tests.
- Publishing advances lifecycle to `PUBLISHED` only after a real success.
- `content-engine mark-ready` provides the minimal manual approval step from `IMAGE_READY` to `READY_TO_PUBLISH`.
- `content-engine demo` runs one manual vertical slice through the real services and prints a report, including the generated image path.

Next planned implementation step:

- Validate a real LinkedIn persistent session manually, then build scheduler and daily automation.

## Demo Mode Flow

```text
content-engine demo
  -> initialize application
  -> run health diagnostics
  -> discover topics
  -> filter and deduplicate topics
  -> rank accepted topics locally
  -> mark one topic selected
  -> create ContentItem
  -> build KnowledgeDocument
  -> attach knowledge artifact
  -> create ContentPlan
  -> attach plan artifact
  -> generate LinkedIn PostArtifact
  -> attach post artifact
  -> build ImagePrompt
  -> generate validated ImageArtifact
  -> attach image artifact
  -> record Experiment, lineage, score, and metrics placeholder
  -> print report
  -> exit
```

Demo Mode intentionally does not start the scheduler, enqueue background jobs, open Playwright, or publish content.

## Executive Summary

The recommended architecture is a local-first, queue-driven worker system backed by SQLite.

The system should be built as a small set of independent workers that communicate through durable database state rather than in-memory chains. Replaceable providers should handle topic discovery, text generation, image generation, and publishing.

This architecture fits the target machine, minimizes recurring cost, survives restarts, and gives the project a clean path to future platforms.

## Overall Architecture

High-level components:

- Scheduler: decides when recurring work should run.
- Topic discovery worker: collects candidate topics.
- Topic ranking worker: scores and selects topics.
- Draft generation worker: creates platform-specific text.
- Image generation worker: creates local media.
- Queue manager: maintains post states and scheduling.
- Publishing worker: publishes ready posts.
- Provider registry: loads configured providers.
- Persistence layer: stores content, jobs, provider results, and audit events.
- Logging layer: records structured operational events.

The first deployment can run as one long-lived process with multiple scheduled loops. It does not need a distributed task queue.

## High-Level Module Layout

Suggested future source layout:

```text
content_engine/
  app/
    startup
    runtime
    shutdown
  config/
    loading
    validation
    defaults
  db/
    connection
    migrations
    repositories
  domain/
    topics
    posts
    media
    publishing
    jobs
  providers/
    topics
    text
    image
    publishers
    notifications
  workers/
    discovery
    ranking
    drafting
    imaging
    publishing
    maintenance
  scheduling/
    clock
    daily_plan
    retry_policy
  observability/
    logging
    metrics
    audit
  tests/
```

This is a proposal only. Do not scaffold it until implementation begins.

## Data Flow

1. Scheduler triggers topic discovery.
2. Topic providers return candidate topics.
3. Candidates are stored with source metadata.
4. Ranking worker scores candidates.
5. The best topic is selected for a future post slot.
6. Draft worker generates LinkedIn text.
7. Image worker generates or attaches a matching local image.
8. Queue manager marks the post ready for publishing.
9. Publishing worker selects the next due ready post.
10. Playwright publisher opens LinkedIn and publishes the post.
11. Result is stored as published or failed with diagnostic context.

No important work should exist only in memory.

## Worker Design

Start with a single application process running scheduled workers.

Recommended workers:

- Discovery worker: runs periodically, stores candidate topics.
- Ranking worker: runs after discovery or when the queue is low.
- Draft worker: fills missing post drafts.
- Image worker: fills missing image assets.
- Publishing worker: runs daily and publishes only due posts.
- Maintenance worker: retries failed jobs, clears stale locks, performs health checks.

Each worker should:

- Claim work atomically.
- Persist state before doing slow operations.
- Use bounded retries.
- Record failures.
- Avoid duplicate output.
- Be safe to rerun after interruption.

## Provider System

Providers should be loaded through configuration and accessed through stable interfaces.

Provider categories:

- TopicSourceProvider
- TopicRankerProvider
- TextGeneratorProvider
- ImageGeneratorProvider
- PublisherProvider
- NotificationProvider

Provider metadata should include:

- Name
- Version
- Capability type
- Cost profile
- Online/offline requirement
- Rate limits if known
- Health status

Provider calls should return structured results, not raw strings only. For example, generated text should include prompt metadata, model/provider name, token or runtime estimate where available, and safety notes if applicable.

## Database Design

SQLite is recommended for the first version.

Suggested tables:

- topics: discovered topic candidates.
- topic_scores: ranking results and rationale.
- posts: canonical post records.
- post_versions: generated text revisions.
- media_assets: generated images and metadata.
- publish_targets: platform-specific publishing records.
- jobs: durable worker jobs and retry state.
- provider_events: provider calls, failures, and timings.
- audit_log: important state transitions.
- settings: local runtime flags such as pause state.

Important database requirements:

- Use migrations from the beginning.
- Use foreign keys.
- Use timestamps for creation and update.
- Use explicit status fields.
- Store error details separately from normal status.
- Avoid deleting operational history by default.

## Queue Strategy

Use the database as the initial queue.

Recommended queue behavior:

- Maintain multiple future ready posts.
- Separate generation queue from publishing queue.
- Publish only posts whose scheduled time is due.
- Enforce a daily publish limit.
- Lock or claim jobs before processing.
- Release stale claims after a timeout.
- Use exponential backoff for retryable failures.
- Mark permanent failures clearly.

Queue-first operation allows the system to continue generating future content even if publishing temporarily fails, and allows publishing to resume once the issue is fixed.

## Failure Recovery Strategy

Failure handling should be designed around recoverable state.

Recommended patterns:

- Retry transient provider failures with bounded backoff.
- Skip unavailable topic sources while preserving other sources.
- Pause publishing after repeated Playwright failures.
- Detect posts stuck in `publishing` after restart and move them to a review or retry state.
- Preserve failed drafts and images for inspection.
- Keep a manual pause flag for all publishing.
- Support dry-run mode before enabling real posting.

The system should never discard a queued post simply because one provider failed.

## Logging Strategy

Use structured logs from the beginning.

Log fields should include:

- timestamp
- level
- component
- worker
- provider
- post_id when applicable
- topic_id when applicable
- job_id when applicable
- status
- duration
- error type
- retry count

There should be separate concepts of:

- Application logs for debugging.
- Audit events for durable business history.
- Provider events for cost, latency, and reliability analysis.

## Configuration Strategy

Configuration should support local development and unattended production use.

Recommended configuration layers:

1. Built-in defaults.
2. Local configuration file.
3. Environment variables for secrets and deployment-specific values.
4. Runtime settings stored in the database for operational flags.

Configuration should control:

- Enabled providers.
- Provider priority.
- Posting schedule.
- Queue size target.
- Retry limits.
- Dry-run mode.
- Manual pause.
- Browser profile path.
- Generated media path.
- Logging level.

Invalid configuration should stop startup before any worker begins.

## Testing Strategy

Testing should start before adding many providers.

Recommended test categories:

- Unit tests for ranking, scheduling, state transitions, and retry policy.
- Repository tests against SQLite.
- Provider contract tests using fake providers.
- Worker tests with controlled queues.
- Playwright dry-run tests for browser flow where feasible.
- End-to-end local pipeline test that generates a queued post without publishing.

Publishing tests should avoid real accidental posts. Real publishing should require explicit configuration and manual confirmation during early development.

## Future Extensibility

The architecture should support future expansion by treating platforms and providers as plugins around a stable core.

Adding Instagram, X, Threads, or blogs should require:

- A platform-specific formatter.
- A platform-specific media requirement definition.
- A publisher provider.
- Platform-specific validation rules.
- Platform-specific scheduling constraints.

It should not require rewriting topic discovery, generic draft storage, job processing, or logging.

## Architectural Improvements To The Initial Idea

### Add Reviewability Even If Automation Is The Default

Fully automated publishing is risky. The architecture should include an optional approval state from the beginning, even if disabled by default.

### Separate Generation From Publishing

Generating and publishing in the same flow creates fragile behavior. Queue-first processing makes the system safer and easier to inspect.

### Treat Playwright Publishing As A Fragile Provider

Browser automation can break without warning. It should be isolated behind a publisher interface and surrounded by screenshots, logs, retries, and pause behavior.

### Prefer A Local Database Queue Before A Message Broker

A message broker would add operational burden without solving the first version's main problems. SQLite is enough for daily publishing and local generation.

### Design For Provider Failure As Normal

Free APIs, scraped sources, local models, and browser sessions will fail. Provider failure should be expected, measured, and recoverable.
