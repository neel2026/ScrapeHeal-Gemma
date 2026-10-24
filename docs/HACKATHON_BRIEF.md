# Hackathon Event Brief

**Event**: Hacktoberfest Hack Day Ahmedabad x Open Source Weekend  
**Date Checked**: October 22, 2026  
**Primary Source Listing**: [MLH Event Listing #15365](https://events.mlh.com/events/15365-hacktoberfest-hack-day-ahmedabad-x-open-source-weekend)  
**Secondary Challenge Sources**: [Major League Hacking (MLH)](https://mlh.com) & [Hacktoberfest](https://hacktoberfest.com)

---

## 1. Confirmed Event Facts

The following facts are verified directly from the official event listing:

- **Event Name**: Hacktoberfest Hack Day Ahmedabad x Open Source Weekend
- **Date**: Saturday, October 24, 2026
- **Time**: 9:30 AM – 6:00 PM IST
- **Venue**: Staunchsys IT Services, Aaron Spectra, Bodakdev, Ahmedabad, Gujarat, India
- **Event Nature**: In-person, one-day build-and-demo event centered on open-source AI and open-weight models.
- **Event Structure**: Features an opening kickoff, access to mentors throughout the day, project demos/presentations, and prizes.
- **Project Scope**: Participants are permitted to bring their own ideas.

---

## 2. Listed Challenge Categories & Verified Requirements

Requirements verified from official challenge announcements and MLH sponsor criteria:

### A. Best Open-Source AI Project
- **Core Requirement**: The project must be an original solution where open-source or open-weight AI constitutes a central, foundational capability.
- **Eligible Implementations**:
  - Utilizing open-weight large or small language models released under OSI-approved or recognized open licenses (e.g., Apache-2.0, MIT).
  - Developing custom, reusable agent skills adhering to open agent standards.
  - Designing or meaningfully extending model harnesses that handle context, memory, prompt routing, and tool calling.
- **Evaluation Emphasis**: Transparent architecture, open-source compliance, and tangible utility.

### B. Best Use of Gemma 4
- **Core Requirement**: The project must demonstrate genuine, central integration of Google DeepMind's Gemma open-weights model family (specifically referencing Gemma 4).
- **Eligible Implementations**:
  - Deploying Gemma 4 for on-device/edge inference or connecting to hosted endpoints for rapid prototyping.
  - Leveraging multimodal (text/vision) or agentic capabilities.
  - Solving focused problems in developer productivity, education, local utility, or accessibility.
- **Evaluation Emphasis**: Depth of model integration, effective prompt/context design, and end-to-end functionality.

---

## 3. Selected Foundation Model: Gemma 4

The foundational model for this project is confirmed: **Google Gemma 4**. This choice qualifies the project for both the *Best Use of Gemma 4* and *Best Open-Source AI Project* categories.

### Verified Model Limits & Operational Constraints
- **Daily Request Limit**: 14,000 requests per day (14k RPD).
- **Minute Request Limit**: 30 requests per minute (30 RPM).
- **Input Token Limit**: 16,000 input tokens per minute (16k TPM).

### Engineering Guardrails
1. **Request Throttling**: Maintain a conservative buffer below 30 RPM (e.g., max 20–25 RPM in practice).
2. **Input Budgeting**: Ensure input prompt payloads are kept lightweight to prevent breaching the 16,000 input tokens/minute cap.
3. **Caching**: Cache responses for repetitive user or system queries to minimize redundant API calls.
4. **Multi-Account API Key Rotation**: Support automatic failover between primary (`GEMINI_API_KEY_1`) and backup (`GEMINI_API_KEY_2`) keys to maximize quota resilience across two Google AI Studio accounts.
5. **Offline Demo Fallback**: Implement a robust mock mode (`MOCK_GEMMA=true` in [`.env`](file:///d:/events/Hacktoberfest%202026/.env)) that delivers predictable, realistic responses during the live demo, immune to event Wi-Fi drops or quota limits.
6. **Minimal Client Helper**: Provided in [`gemma_client.py`](file:///d:/events/Hacktoberfest%202026/gemma_client.py) with zero external dependencies, handling key rotation and mock fallback cleanly.

---

## 4. Unknowns & Unverified Details

To ensure no false assumptions are made, the following details are explicitly identified as **not confirmed in the official listing** as of October 22, 2026:

| Item | Status | Action / Note |
| :--- | :--- | :--- |
| **Team Size Limits** | *Not confirmed in the official listing* | Minimum and maximum team sizes have not been specified; clarify during kickoff. |
| **Solo Eligibility** | *Not confirmed in the official listing* | Whether individual participation is permitted without joining a team is unconfirmed. |
| **Exact Judging Rubric** | *Not confirmed in the official listing* | Official scoring weights (e.g., technical difficulty vs. design vs. presentation) are unpublished; treat internal criteria as preparation only. |
| **Submission Deadline & Platform** | *Not confirmed in the official listing* | Platform (e.g., Devpost, GitHub repository link, or live-only pitch) and hard code freeze cutoff are unconfirmed. |
| **Detailed Schedule / Agenda** | *Not confirmed in the official listing* | Specific times for kickoff conclusion, mentor check-in rounds, and demo slots remain unannounced (only total window 9:30 AM–6:00 PM IST is confirmed). |

---

## 5. Co-Pilot Preparation Checklist

When a project idea is chosen later, all work must align with these confirmed bounds:
1. **Timeframe**: Must be completely buildable and demonstrable within the 9:30 AM – 6:00 PM window.
2. **Category Alignment**: Double-check that the idea maximizes the use of Gemma 4's unique capabilities (multimodal, reasoning, or edge efficiency).
3. **Demo Resilience**: Build with mock/offline fallbacks to ensure live presentation reliability at the venue.
