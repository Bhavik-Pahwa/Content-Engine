# Vision

## Project Purpose

This project is a long-running content automation platform, initially focused on LinkedIn.

The first production version should discover technology topics, choose a strong topic, generate a LinkedIn-ready post, generate a matching image locally, maintain a queue of future posts, and publish one post per day using browser automation.

The system is intended to run continuously on a Linux laptop with modest hardware and minimal recurring cost.

## What We Are Building

We are building a local-first automation application for planning, generating, queuing, and publishing social content.

The initial product is a LinkedIn content engine. The long-term product is a multi-platform content operations system with pluggable providers for:

- Topic discovery
- Topic ranking
- Text generation
- Image generation
- Publishing
- Scheduling
- Observability

The application should favor reliability, recoverability, and understandable behavior over feature volume.

## Initial Scope

The first implementation should support:

- Discovering technology topics from low-cost or free sources.
- Ranking and selecting a topic suitable for LinkedIn.
- Generating a LinkedIn post draft.
- Generating a matching image locally.
- Storing generated posts in a durable queue.
- Publishing at most one approved or queued post per day.
- Using Playwright for LinkedIn publishing.
- Logging each important action and failure.
- Resuming safely after laptop restart, network outage, provider failure, or browser automation failure.

## Long-Term Goals

The architecture should make it straightforward to add:

- Instagram
- X
- Threads
- Blogs
- Additional AI providers
- Additional image-generation providers
- Additional topic sources
- Additional publishing platforms
- Human approval workflows
- Analytics and feedback loops
- Remote deployment targets
- A lightweight UI

## Non-Goals

The initial project should not attempt to be:

- A full marketing suite.
- A high-scale cloud SaaS product.
- A real-time trend-trading system.
- A spam automation tool.
- A platform for bypassing anti-automation systems.
- Dependent on expensive paid APIs.
- Dependent on a dedicated GPU.
- A complex distributed system.

The first version should not optimize for massive throughput. It should optimize for safe daily operation.

## Future Vision

Over time, the platform should evolve from a single-channel LinkedIn automation tool into a modular content pipeline:

1. Sources discover candidate ideas.
2. Ranking providers select the best ideas.
3. Generation providers create platform-specific content.
4. Media providers create or select supporting assets.
5. Review workflows approve, reject, or revise content.
6. Queue workers schedule and publish content.
7. Analytics providers measure performance.
8. Feedback loops improve future topic selection and writing style.

Each platform should be treated as a separate publishing target with its own constraints, formatting rules, media requirements, and failure modes.

## Success Criteria

The project is successful when:

- It can run unattended for days at a time on the target laptop.
- It publishes no more than the intended posting frequency.
- It does not lose queued posts after restart.
- It handles provider outages gracefully.
- It logs enough information to diagnose failures.
- It can generate acceptable LinkedIn posts without recurring paid services.
- It supports adding a new provider without rewriting the core pipeline.
- It supports adding a new publishing platform without changing unrelated modules.
- It remains understandable to a future maintainer after months of development.

