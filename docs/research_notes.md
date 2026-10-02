# Phase 1 research record

This is the historical Phase 1 record. Current Phase 2 methodology, limitations,
and verified generation counts are documented in [phase2_research.md](phase2_research.md).

## Research question

Does adaptive evidence selection and evidence verification improve the reliability of GenAI-generated explanations of anomalies in structured data?

## Implemented

Python environment scaffold, settings validation, dependency health check, and setup tests. Dataset generation, anomaly injection, ML, evidence selection, verification, agents, GenAI, backend endpoints, dashboard, and evaluation are not implemented.

## Hypothesis, not a finding

Adaptive evidence selection and verification may improve supported-claim rate and evidence coverage relative to a dataset-to-LLM baseline. This remains untested. Phase 1 provides no evidence of novelty, patentability, causal effects, or statistical significance.

## Record for reproducibility

- Date, operating system, hardware, and exact Python version.
- Phase 1 dependency pins and the complete installed environment: `python -m pip freeze`.
- Git commit hash after creating a local commit: `git rev-parse HEAD`.
- Health-check output, test count, test outcome, and any setup deviations.
- Distinguish a conceptual test walkthrough from an actual terminal run.
- Record future experiment seeds, datasets, anomaly labels, prompts, model identifiers, tool traces, budgets, claim-scoring definitions, and run repetitions when implemented.

## Future evaluation plan only

Compare the baseline and proposed workflow using supported and unsupported claims, evidence coverage, factor identification, response time, and tool counts. Define these metrics and control inputs and model settings before running experiments. Future anomaly labels must be kept separate from agent-visible analysis inputs. Correlation must not be presented as causation.

## Current results

No research experiments have been performed in Phase 1. Passing environment tests verifies setup behavior only.

Actual development-environment verification on 2026-10-02 (Linux, Python 3.12.14): `pip check` reported no broken requirements; the health check passed; Pytest reported `9 passed in 0.02s`. Installed packages: python-dotenv 1.1.0, pytest 8.3.5, iniconfig 2.3.0, packaging 26.3, pluggy 1.6.0. Windows and macOS commands are provided but were not executed here. The first Git checkpoint includes the saved verification outputs in docs/phase1_checkpoint/. Use git log -1 to retrieve its commit identifier.
