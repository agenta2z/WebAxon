# Browser-Use vs WebAxon: Comprehensive Comparison

**Date:** 2026-03-12  
**Author:** Rovo Dev (automated analysis)

This directory contains a thorough architectural comparison between [browser-use](https://github.com/browser-use/browser-use) (open-source LLM browser automation framework) and WebAxon (internal Atlassian web automation framework).

## Report Index

| # | Report | Focus Area |
|---|--------|------------|
| 1 | [Executive Summary](./01-executive-summary.md) | High-level comparison, key strengths/weaknesses, bottom line |
| 2 | [Architecture Comparison](./02-architecture-comparison.md) | System architecture, control flow, data flow, dependencies, error handling, configuration |
| 3 | [DOM and Element Handling](./03-dom-and-element-handling.md) | DOM extraction, serialization, element identification, incremental change detection |
| 4 | [Agent Loop and LLM Integration](./04-agent-loop-and-llm-integration.md) | Agent loop design, LLM providers, prompt engineering, state management |
| 5 | [Browser Automation Layer](./05-browser-automation-layer.md) | Browser connection, action execution, watchdog system, vision capabilities |
| 6 | [Extensibility and Ecosystem](./06-extensibility-and-ecosystem.md) | Plugin systems, skills, MCP, code generation, event bus, developer experience |
| 7 | [Recommendations](./07-recommendations.md) | Prioritized adoption recommendations for WebAxon, integration strategy |

## Quick Summary

- **Browser-Use** excels at: vision/screenshots, resilience (watchdogs), LLM ecosystem breadth, cloud browsers, extensibility
- **WebAxon** excels at: HTML processing precision, stable element identification (XPaths), multi-agent pipeline, meta-agent synthesis, action memory

The two systems are **complementary** — see [Recommendations](./07-recommendations.md) for a proposed integration strategy.
