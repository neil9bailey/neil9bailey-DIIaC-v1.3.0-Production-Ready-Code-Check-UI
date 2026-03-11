// backend-ui-bridge/lib/logger.js
// Structured JSON logger for the Node.js bridge.
// Outputs one JSON line per log event for machine-parseable log aggregation.

const LOG_LEVEL_MAP = { debug: 10, info: 20, warn: 30, error: 40 };
const CURRENT_LEVEL = LOG_LEVEL_MAP[
  (process.env.LOG_LEVEL || "info").toLowerCase()
] || 20;

function emit(level, msg, extra = {}) {
  if ((LOG_LEVEL_MAP[level] || 20) < CURRENT_LEVEL) return;
  const entry = {
    ts: new Date().toISOString(),
    level,
    msg,
    ...extra,
  };
  const out = level === "error" ? process.stderr : process.stdout;
  out.write(JSON.stringify(entry) + "\n");
}

export const log = {
  debug: (msg, extra) => emit("debug", msg, extra),
  info:  (msg, extra) => emit("info", msg, extra),
  warn:  (msg, extra) => emit("warn", msg, extra),
  error: (msg, extra) => emit("error", msg, extra),
};
