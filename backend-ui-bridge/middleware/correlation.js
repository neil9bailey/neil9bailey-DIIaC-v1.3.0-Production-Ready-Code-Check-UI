// backend-ui-bridge/middleware/correlation.js
// Assigns a unique X-Correlation-ID to every inbound request.
// Downstream code can read req.correlationId for tracing.

import crypto from "crypto";

export function correlationId() {
  return (req, _res, next) => {
    const id = req.headers["x-correlation-id"] || crypto.randomUUID();
    req.correlationId = id;
    _res.setHeader("X-Correlation-ID", id);
    next();
  };
}
