# LEGALII Enterprise

LEGALII is a local-first legal document workflow for law firms. It is designed to organize case packets, identify missing or inconsistent material and prepare structured next-step reports for professional review.

## Core workflow
- Ingest case documents and supporting files.
- Extract and normalize text.
- Identify missing documents and internal inconsistencies.
- Produce structured summaries and review tasks.
- Keep a human approval gate before consequential output.

## Architecture
This repository contains the LEGALII kit, enterprise deployment profiles, review/audit workflows and supporting product documentation. The exact implementation state is recorded in HANDOFF_STATUS.md and RELEASE_CHECKLIST.md; those files are operational records and may be older than the current branch.

## Safety and legal boundary
LEGALII is a document-workflow assistant, not a lawyer and not a source of legal advice. It must not independently determine legal strategy, submit filings, contact counterparties or calculate binding deadlines without qualified human verification. Client data must remain under the firm's approved retention, access-control and processing policies.

## Status
Engineering prototype / pre-release. The handoff notes list unfinished items including user management, complete review UI and hardened installer/deployment defaults. Do not describe this branch as production-ready until those gates are closed and tested.

## Development
Review the current branch and RELEASE_CHECKLIST.md before deployment. Use synthetic case packets for tests, keep API keys and client documents out of Git, and bind local services to loopback unless explicitly secured for a trusted network.

## License and notices
See LICENSE and NOTICE for upstream-derived components and attribution.

## Connections to the research network

LEGALII Enterprise and [LEGALAIR](https://github.com/Personaz1/LEGALAIR) explore adjacent legal-document workflows from separate repository histories. Their similarities are worth comparing; they should not be treated as one product unless their models, assumptions and intended users are deliberately reconciled.

Wider research connections:
- [decentralized-ai-child](https://github.com/Personaz1/decentralized-ai-child) and [TORI](https://github.com/Personaz1/TORI): orchestration, persistent case context, retrieval and multi-step reasoning.
- [ExploitIDE](https://github.com/Personaz1/ExploitIDE): structured evidence, source provenance and analysis workflows.
- [LongGapsBetweenPrimes](https://github.com/Personaz1/LongGapsBetweenPrimes): a useful contrast between formal proof and reasoning under ambiguous, incomplete real-world information.

The general research problem is not merely document summarization. It is maintaining a faithful chain from source material through extracted facts and competing interpretations to a human-reviewed decision.
