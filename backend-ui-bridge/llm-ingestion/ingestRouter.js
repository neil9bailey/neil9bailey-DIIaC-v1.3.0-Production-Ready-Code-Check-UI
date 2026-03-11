import express from "express";
import { ingestCopilot } from "./providers/copilot.js";
import { appendRecord } from "./store.js";

export const ingestRouter = express.Router();

ingestRouter.post("/llm", async (req, res) => {
  if (process.env.LLM_INGESTION_ENABLED !== "true") {
    return res.status(403).json({ error: "LLM ingestion disabled" });
  }

  const { provider, prompt, parameters } = req.body;

  let record;

  if (!provider || provider === "copilot") {
    record = await ingestCopilot(prompt, parameters);
  } else {
    return res.status(400).json({
      error: "provider_locked_to_copilot",
      provider_mode: "copilot_only",
      allowed_provider: "copilot",
    });
  }

  appendRecord(record);

  res.json({
    status: "captured",
    provider: record.provider,
    response_hash: record.response_hash
  });
});
