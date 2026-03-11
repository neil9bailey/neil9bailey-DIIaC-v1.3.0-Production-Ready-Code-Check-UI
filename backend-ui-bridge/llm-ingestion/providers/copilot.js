import crypto from "crypto";
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

const COPILOT_MODEL = process.env.COPILOT_MODEL || "gpt-4o";

const COPILOT_SYSTEM_PROMPT = `You are an adversarial red-team AI operating as a governance challenger.

Your role is to critically challenge and stress-test the strategy presented to you.

Return STRICT JSON only. The word JSON must appear in your output.

You MUST include these top-level sections:
challenge_summary, risk_flags, blind_spots, red_team_verdict

Each section must be a structured JSON object.

challenge_summary: A brief overview of the key weaknesses identified.
risk_flags: An array of objects with { risk, severity, rationale } for critical risks.
blind_spots: Areas the primary strategy failed to address adequately.
red_team_verdict: Overall assessment with { verdict, confidence, recommendation }.

Do NOT include markdown. Do NOT include commentary. Return a valid JSON object only.`;

export async function ingestCopilot(prompt, parameters = {}) {
  const model = parameters.model || COPILOT_MODEL;

  const response = await client.chat.completions.create({
    model,
    messages: [
      { role: "system", content: COPILOT_SYSTEM_PROMPT },
      { role: "user", content: prompt }
    ],
    temperature: parameters.temperature ?? 0.2,
    response_format: { type: "json_object" }
  });

  const content = response.choices[0].message.content;

  return {
    provider: "copilot",
    model: response.model,
    prompt_hash: crypto.createHash("sha256").update(prompt).digest("hex"),
    response_hash: crypto.createHash("sha256").update(content).digest("hex"),
    content
  };
}
