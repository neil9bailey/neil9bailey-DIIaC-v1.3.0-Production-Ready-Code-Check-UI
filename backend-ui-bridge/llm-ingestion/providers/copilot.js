import crypto from "crypto";
import OpenAI from "openai";

const client = process.env.GITHUB_TOKEN
  ? new OpenAI({
      baseURL: "https://models.inference.ai.azure.com",
      apiKey: process.env.GITHUB_TOKEN,
    })
  : null;

export function isCopilotConfigured() {
  return Boolean(client);
}

export async function ingestCopilot(prompt, parameters = {}) {
  if (!client) {
    throw new Error("Copilot provider requires GITHUB_TOKEN to be set");
  }

  const model = parameters.model || process.env.COPILOT_MODEL || "gpt-4o";

  const response = await client.chat.completions.create({
    model,
    messages: [{ role: "user", content: prompt }],
    temperature: parameters.temperature ?? 0,
  });

  const content = response.choices[0].message.content;

  return {
    provider: "copilot",
    model: response.model,
    prompt_hash: crypto.createHash("sha256").update(prompt).digest("hex"),
    response_hash: crypto.createHash("sha256").update(content).digest("hex"),
    content,
  };
}
