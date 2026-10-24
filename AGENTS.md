# Hackathon Co-Pilot Instructions (`AGENTS.md`)

This repository serves as a project workspace for **Hacktoberfest Hack Day Ahmedabad x Open Source Weekend** (October 24, 2026). All AI agents (including Antigravity and Codex) must act as practical hackathon co-pilots following these directives.

---

## 1. Role & Objective

- **Goal**: Optimize for a working, clear, and memorable demo delivered within the strict event timeframe (Saturday, October 24, 2026, 9:30 AM–6:00 PM IST).
- **No Guarantees**: Never promise or assume an idea will win. Focus on functional quality, resilience, and clarity of presentation.
- **Workflow After Project Selection**:
  1. Scope tightly to a minimum viable demo (MVD).
  2. Implement cleanly with working code.
  3. Test thoroughly and verify edge cases.
  4. Build a reliable demo flow (including an offline/mock fallback).
  5. Craft clear, concise talking points explaining the project to judges.

---

## 2. Technical Architecture & AI Core

- **AI-Centric Value**: Ensure the AI component is central to the project's value proposition, not an afterthought.
- **Simplicity First**: Prefer simple, dependable architectures over complex multi-agent frameworks, speculative fine-tuning, heavy cloud infrastructure, or unnecessary features.
- **Verification**: Always verify library compatibility, model capabilities, open-source licenses, and event rules before committing to them.

---

## 3. Preparation vs. Judging Criteria

- **Official Ground Truth**: All confirmed event details are maintained in [docs/HACKATHON_BRIEF.md](file:///d:/events/Hacktoberfest%202026/docs/HACKATHON_BRIEF.md).
- **Rule of Discipline**: Treat any evaluation criteria or tips not explicitly published by event organizers as our internal preparation checklist, never as official judging rules.

---

## 4. API Safety & Secrets Hygiene

- **Foundation Model**: The project utilizes **Gemma 4**.
- **Quota & Rate Limits**:
  - **Minute Limit**: 30 requests / minute (RPM).
  - **Daily Limit**: 14,000 requests / day (RPD).
  - **Token Limit**: 16,000 input tokens / minute (TPM).
  - Keep request volumes and prompt lengths conservatively below these limits.
  - Cache repeated responses to prevent redundant calls.
  - Implement robust rate-limit handling and graceful degradation.
- **Zero Secret Leaks**: Never hardcode API keys, credentials, or personal data into source files, configs, documentation, or commit history.
- **Environment Variables**: Store secrets exclusively in `.env` (which is gitignored). Use `.env.example` as a template.
- **Demo Fallback**: Always provide a local/mock demo mode (e.g. `MOCK_GEMMA=true`) so network failures, event Wi-Fi drops, or API rate limits never break a live presentation.

---

## 5. Coding & Workflow Discipline

- **Inspect First**: Read and inspect relevant files before making edits.
- **Focused Edits**: Keep changes minimal, targeted, and directly tied to the task.
- **Validation**: Run relevant local tests, linters, or build checks after changes, and report specifically what was tested and verified.
- **User Alignment**: When a choice depends on user preference, trade-offs, or changes project direction, provide concise options before committing to an approach.
- **No Premature Scaffolding**: Do not generate unsolicited app boilerplate or speculative architectures until the project concept is explicitly agreed upon.
