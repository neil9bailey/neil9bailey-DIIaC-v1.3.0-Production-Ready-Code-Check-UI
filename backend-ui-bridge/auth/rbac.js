// backend-ui-bridge/auth/rbac.js
// ESM-compatible RBAC middleware for DIIaC
//
// When Entra auth is active (req.entraAuth populated by entra.js middleware),
// the role is already bridged into x-role by the Entra middleware.
// This middleware validates that the resolved role is in the allowed set.

export function requireRole(allowedRoles = []) {
  return function (req, res, next) {
    const role =
      req.headers["x-role"] ||
      req.headers["X-Role"];

    if (!role) {
      return res.status(403).json({
        error: "Forbidden",
        reason: "No role provided",
      });
    }

    if (!allowedRoles.includes(role)) {
      return res.status(403).json({
        error: "Forbidden",
        reason: "Insufficient role permissions",
      });
    }

    // Attach actor lineage to the request for audit trail consumption
    if (req.entraAuth) {
      req.actor = {
        subject: req.entraAuth.subject,
        name: req.entraAuth.name,
        email: req.entraAuth.email,
        role: req.entraAuth.role,
        subroles: req.entraAuth.subroles || [],
        tenant_id: req.entraAuth.tenant_id,
        token_type: req.entraAuth.token_type,
        principal_id: req.entraAuth.principal_id,
      };
    } else {
      req.actor = {
        subject: "anonymous",
        name: "legacy-header-auth",
        email: null,
        role,
        subroles: [],
        tenant_id: null,
        token_type: "legacy_header",
        principal_id: null,
      };
    }

    next();
  };
}
