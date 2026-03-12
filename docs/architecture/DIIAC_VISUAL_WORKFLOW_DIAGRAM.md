# Visual Workflow Diagram (v1.3.0-ui)

```mermaid
flowchart LR
  A[User on UI] --> B[Entra Sign-In]
  B --> C[Frontend Dashboard]
  C --> D[Bridge API]
  D --> E[Auth and RBAC Validation]
  E --> F[Governance Runtime]
  F --> G[Decision Artifacts]
  F --> H[Trust Ledger and Merkle]
  G --> I[Decision Pack Export]
  H --> I
  I --> J[Offline/Independent Verification]
```

## Notes

- UI is externally accessible at `diiacui.vendorlogic.io`.
- Bridge enforces auth and orchestrates runtime operations.
- Runtime produces deterministic outputs and trust evidence.
