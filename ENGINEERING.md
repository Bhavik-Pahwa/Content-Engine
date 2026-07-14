# Engineering Standards

## Core Principles

### Reliability Over Features

A small system that runs every day is more valuable than a broad system that fails unpredictably.

Every feature should define:

- What happens when it succeeds.
- What happens when it fails.
- Whether failure should retry, skip, pause, or alert.
- What state must be persisted before and after execution.

### Simplicity Over Cleverness

Prefer boring, local, understandable technology. This project should start with a simple process model and a durable local database before introducing external services, message brokers, or distributed infrastructure.

### Readability Over Micro-Optimization

The target workload is low volume. The bottlenecks will usually be provider latency, browser automation reliability, and local image-generation speed, not raw Python execution.

Code should be written for future maintainers first.

### Composition Over Inheritance

Business behavior should be assembled from small components:

- Sources
- Rankers
- Generators
- Media providers
- Publishers
- Workers
- Schedulers

Avoid deep class hierarchies. Prefer small interfaces and explicit dependencies.

### Configuration Over Hardcoding

Runtime behavior should be configured outside the source code where practical:

- Posting frequency
- Topic sources
- Enabled providers
- Provider priority
- Retry limits
- Output directories
- Browser profile paths
- Model names
- Prompt templates

Configuration should have validated defaults. Invalid configuration should fail loudly at startup.

### Interface-Driven Provider Architecture

External and replaceable capabilities should be represented behind stable interfaces.

Initial provider categories:

- Topic source provider
- Topic ranking provider
- Text-generation provider
- Image-generation provider
- Publishing provider
- Notification provider

Providers should be replaceable without changing the pipeline orchestration.

### Queue-First Processing

Generated content should move through durable states instead of being passed only in memory.

Queue-first design protects the system from:

- Laptop restarts
- Provider failures
- Partial generation
- Browser automation errors
- Duplicate publishing attempts

### Small Focused Modules

Each module should have one clear responsibility. Avoid "manager" modules that accumulate unrelated behavior.

Good module boundaries:

- Topic discovery
- Topic scoring
- Draft generation
- Media generation
- Queue persistence
- Publishing
- Scheduling
- Logging and observability
- Configuration

### Graceful Failure Handling

The system should degrade rather than collapse.

Examples:

- If one topic source fails, use other sources.
- If text generation fails, retry later.
- If local image generation fails, queue a text-only draft or mark the media step failed depending on platform requirements.
- If LinkedIn publishing fails, preserve the post and retry safely.
- If all AI providers fail, pause generation but keep the scheduler alive.

### Explicit State Transitions

Content should move through named states. State transitions should be deliberate and logged.

Example states:

- discovered
- selected
- draft_pending
- draft_ready
- image_pending
- ready_to_publish
- publishing
- published
- failed
- skipped

No worker should silently mutate important state.

### Idempotency

Workers must be safe to rerun after interruption.

For example:

- A generation worker should not create duplicate queue items for the same selected topic.
- A publisher should not publish the same post twice after restart.
- A failed image job should resume from the persisted job state.

### Observability From Day One

The system should log:

- Worker startup and shutdown
- Configuration summary
- Provider selection
- Topic discovery results
- Topic ranking decisions
- Queue state changes
- Generated content metadata
- Publishing attempts
- Retry attempts
- Exceptions with context

Logs should be structured enough to search and filter.

### Test Before Expansion

Each new provider or platform should include tests for:

- Configuration validation
- Success path
- Retryable failure
- Permanent failure
- State transitions
- Idempotency behavior

Do not add multiple platforms before the LinkedIn path has reliable tests and operational history.

## Architecture Standards

### Local-First by Default

The system should run on a single Linux laptop with no required cloud infrastructure.

SQLite is appropriate for the initial durable store. The design should avoid SQLite-specific assumptions that would block a later move to PostgreSQL.

### Minimal Dependencies

Each dependency should justify itself.

Prefer dependencies that are:

- Actively maintained
- Widely used
- Cross-platform where practical
- Easy to remove
- Suitable for offline or local operation

### Provider Fallbacks

Provider selection should support priority order and fallback behavior.

Example:

1. Try a local/free provider.
2. Fall back to another local/free provider.
3. Optionally use a paid API only if enabled by configuration.
4. If all providers fail, record the failure and retry later.

### Human Safety Controls

Even if the first version is automated, the architecture should support review and approval.

Recommended controls:

- Dry-run publishing mode.
- Daily publish limit.
- Manual pause flag.
- Content preview.
- Audit log.
- Optional approval-required queue state.

### Respect Platform Constraints

Browser automation is fragile and may violate platform expectations if abused.

The application should:

- Avoid aggressive automation.
- Use conservative posting frequency.
- Avoid scraping at high volume.
- Preserve manual account control.
- Surface failures instead of trying to bypass anti-automation mechanisms.

## Operational Standards

### Safe Startup

On startup the application should:

- Validate configuration.
- Check database connectivity.
- Verify required local directories.
- Load enabled providers.
- Detect incomplete jobs.
- Resume or repair safe states.
- Start workers only after readiness checks pass.

### Safe Shutdown

Workers should handle termination cleanly:

- Finish or checkpoint current work.
- Release browser sessions.
- Avoid leaving content permanently stuck in `publishing`.
- Persist useful failure context.

### Backups

The SQLite database and generated media directory should be easy to back up.

At minimum, the project should define a backup procedure before production use.

### Secrets Management

Secrets should not be committed to source control.

Examples:

- API keys
- Session tokens
- Browser profile credentials
- Account identifiers if sensitive

Use environment variables or local ignored configuration files.

## Documentation Standards

The planning documents are living documents.

Update them when:

- A major design decision changes.
- A new provider category is added.
- A new platform is added.
- A risk is discovered or retired.
- A sprint completes.
- Operational behavior changes.

