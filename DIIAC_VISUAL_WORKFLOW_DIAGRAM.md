# DIIaC Visual Workflow Diagram (HITL + Deterministic Governance)

This diagram shows the **correct production sequence** for Human-In-The-Loop (HITL) operation where LLM assistance is combined with deterministic governed compile and verifiable artefacts.

```mermaid
sequenceDiagram
    autonumber
    actor U as Human Operator (Admin)
    participant UI as Frontend UI
    participant B as backend-ui-bridge
    participant L as LLM Provider / Stub
    participant R as DIIaC Runtime (Flask)
    participant S as Artefacts + Ledger + Exports

    U->>UI: 1) Enter Human Intent + Role Evidence
    UI->>B: 2) POST /api/human-input (optional inline)
    UI->>B: 3) POST /api/human-input/role
    B->>R: 4) Forward role evidence to runtime context
    R->>S: 5) Persist role input bundle

    U->>UI: 6) Select profile + schema + R/P
    U->>UI: 7) Run Governed Compile (Production)
    UI->>B: 8) POST /api/llm-governed-compile

    B->>L: 9) LLM synthesis from latest human intent
    L-->>B: 10) Structured synthesis output
    B->>B: 11) Hash LLM output + derive stable context linkage
    B->>R: 12) POST /api/human-input/role (LLM evidence role)
    B->>R: 13) POST /api/governed-compile (authoritative step)

    R->>R: 14) Validate profile/schema/RP + deterministic build
    R->>S: 15) Write board report + manifest + trace + scoring
    R->>S: 16) Append trust ledger + signatures + merkle root
    R-->>B: 17) Return execution_id + pack_hash + merkle_root
    B-->>UI: 18) Return compile + LLM metadata

    U->>UI: 19) Verify and export
    UI->>B: 20) /verify/execution, /verify/pack, /verify/replay
    UI->>B: 21) /decision-pack/<id>/export-signed
    B->>R: 22) Proxy verification/export
    R->>S: 23) Serve signed package + attestation artefacts
    R-->>UI: 24) Downloadable, auditable decision package
```

## Correct usage policy
- Use this production path for all final decisions.
- Keep `/govern/decision` only for exploratory drafts/demos.
- Treat deterministic compile output as the authoritative decision artefact.
