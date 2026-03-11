import { useState } from "react";
import { createHumanInput } from "./api";

interface Props {
  onIntentSaved?: () => void;
}

const EXAMPLE_INTENT =
  `Example: "Evaluate the strategic case for migrating our on-premises data centre to Azure Government Cloud. ` +
  `Key constraints: data sovereignty requirements under UK GDPR, a 24-month runway, and a £4M capex ceiling. ` +
  `Assess vendor lock-in risk, resilience SLAs, and regulatory compliance posture against NCSC guidance."`;

export default function HumanInputPanel({ onIntentSaved }: Props) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!text.trim()) { setStatus("Input required — enter your strategic objective before submitting."); return; }
    try {
      setSaving(true);
      setStatus("Saving intent…");
      await createHumanInput({ raw_text: text.trim() });
      setStatus("✔ Intent saved successfully. You can now run the governance decision draft.");
      setText("");
      if (onIntentSaved) onIntentSaved();
    } catch (err: unknown) {
      console.error(err);
      setStatus("Error saving intent. Verify the bridge service is running.");
    }
    setSaving(false);
  }

  return (
    <div className="panel">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: "0 0 3px" }}>Step 1 — Submit Human Intent</h2>
          <p className="muted-text" style={{ margin: 0 }}>
            Provide a strategic objective, board directive, or decision context. This becomes the governance anchor
            for all subsequent AI-assisted analysis.
          </p>
        </div>
        <span style={{ background: "var(--blue-50)", color: "var(--blue-600)", border: "1px solid var(--blue-100)", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, flexShrink: 0, marginLeft: 16 }}>
          Required
        </span>
      </div>

      <div className="form-section">
        <div className="form-section-header">
          <div className="form-section-number">1</div>
          <span className="form-section-title">Strategic Objective</span>
          <span className="form-section-desc">{text.length}/2000 chars</span>
        </div>
        <div className="form-section-body">
          <div className="form-field">
            <label>Human Intent</label>
            <textarea
              rows={7}
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={2000}
              placeholder="Enter a strategic objective, board directive, or decision context…&#10;&#10;Be specific about: the decision domain, key constraints, success criteria, regulatory context, and expected outcomes."
              style={{ width: "100%", fontFamily: "var(--font-sans)" }}
            />
            <div className="field-hint">
              Be specific. Include domain, constraints, regulatory context, and desired outcomes for best governance results.
            </div>
            <div className="field-example">{EXAMPLE_INTENT}</div>
          </div>
        </div>
      </div>

      <div className="button-row">
        <button className="btn-primary" onClick={() => void submit()} disabled={saving || !text.trim()}>
          {saving ? "Saving…" : "Submit Intent"}
        </button>
        {text.trim() && (
          <button className="btn-ghost" onClick={() => setText("")}>Clear</button>
        )}
      </div>

      {status && (
        <div
          className="status"
          style={status.startsWith("✔") ? { background: "var(--green-50)", color: "var(--green-700)", borderLeftColor: "var(--green-600)" } : {}}
        >
          {status}
        </div>
      )}
    </div>
  );
}
