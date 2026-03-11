# DIIaC v1.2.0 — Getting Started Guide
### From zero to your first governed compile in under 90 minutes

**Who this guide is for:** Anyone who wants to deploy and demonstrate DIIaC locally.
No deep technical expertise required — just follow each step in order.

---

## What is DIIaC?

DIIaC (Deterministic Infrastructure Intelligence as Code) is a **governance platform** that helps organisations make infrastructure and technology decisions in a structured, auditable, and cryptographically verifiable way.

Instead of decisions being made in emails or spreadsheets with no audit trail, DIIaC:

- Captures stakeholder inputs (CTO, CISO, Architect, etc.) in a structured format
- Compiles them into a **governed decision pack** — a scored, ranked set of recommendations
- Signs every output with a cryptographic signature so it can never be tampered with
- Keeps a tamper-evident audit log of every decision ever made

Every decision is **deterministic** — the same inputs always produce the same output, every single time.

---

## What you will have running at the end of this guide

```
Your laptop
├── Governance Runtime    http://localhost:8000   (the decision engine)
├── Backend Bridge        http://localhost:3001   (the API gateway)
└── Web Interface         http://localhost:5173   (the UI you'll use)
        │
        Secrets pulled from ──► Azure Key Vault
        Login via ────────────► Vendorlogic Entra ID (Microsoft SSO)
```

---

## Before you start — checklist

Make sure you have all of the following before beginning.

| # | What you need | How to check | Install link |
|---|--------------|-------------|-------------|
| 1 | **Docker Desktop** running | Open Docker Desktop — the whale icon should show green | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| 2 | **Git** | Open a terminal, type `git --version` | [git-scm.com](https://git-scm.com) |
| 3 | **Azure CLI** | Open a terminal, type `az --version` | [learn.microsoft.com/cli/azure/install-azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) |
| 4 | **Access to the Vendorlogic Azure tenant** | Ask your Azure admin to confirm you have access | — |
| 5 | **Access to Key Vault `kv-diiac-vendorlogic`** | Your admin should have granted you `Key Vault Secrets User` | — |

> **Windows users:** All commands in this guide work in either **PowerShell** or
> **Git Bash**. For the pull script specifically, use PowerShell.

---

---

# PART 1 — Get the code

**Time: ~5 minutes**

---

## Step 1 — Open a terminal

- **Windows:** Press `Win + X` → select **Windows Terminal** or **PowerShell**
- **Mac:** Press `Cmd + Space` → type **Terminal** → press Enter
- **Linux:** Right-click desktop → Open Terminal

---

## Step 2 — Choose where to put the project

Navigate to a folder where you want the project to live.

```bash
# Example — put it in your Documents folder:
cd ~/Documents

# Or on Windows:
cd C:\Users\YourName\Documents
```

---

## Step 3 — Clone the repository

```bash
git clone https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git diiac
cd diiac
```

✅ **You should see:** A folder called `diiac` has been created. Your terminal is now inside it.

---

## Step 4 — Switch to the locked release version

```bash
git checkout v1.2.0
```

✅ **You should see:** A message like `HEAD is now at ... v1.2.0`

> This pins you to the exact v1.2.0 release. Nothing will change unexpectedly.

---

---

# PART 2 — Connect to Azure

**Time: ~10 minutes**

---

## Step 5 — Log in to Azure

```bash
az login
```

✅ **What happens:** A browser window opens asking you to sign in with your Microsoft account.
Sign in with your **Vendorlogic work account** (the one that has access to the Azure tenant).

After signing in, return to your terminal. You should see your account details printed.

```
✅ You should see something like:
[
  {
    "name": "Vendorlogic Production",
    "user": { "name": "you@vendorlogic.com" }
  }
]
```

> **Already logged in?** If you've used Azure CLI before, this step may complete instantly.

---

## Step 6 — Confirm you have access to the Key Vault

```bash
az keyvault secret list --vault-name kv-diiac-vendorlogic -o table
```

✅ **You should see:** A table listing secrets like `diiac-admin-api-token`, `diiac-signing-private-key-pem`, etc.

> **If you see an error like "does not have secrets list permission":**
> Ask your Azure admin to grant you the `Key Vault Secrets User` role on `kv-diiac-vendorlogic`.

---

---

# PART 3 — Pull your secrets

**Time: ~2 minutes**

The DIIaC platform needs several secrets to run (admin password, signing key, OpenAI API key).
These are securely stored in Azure Key Vault. The pull script fetches them automatically.

---

## Step 7 — Run the secret pull script

**Mac / Linux / Git Bash:**
```bash
bash scripts/pull-keyvault-secrets.sh
```

**Windows PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\pull-keyvault-secrets.ps1
```

✅ **You should see:**
```
DIIaC v1.2.0 — Key Vault secret pull
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Logged in as: you@vendorlogic.com
✓ Key Vault found: kv-diiac-vendorlogic
✓ Signing key → .secrets/signing_key.pem
✓ ADMIN_API_TOKEN retrieved (64 chars)
✓ OPENAI_API_KEY retrieved
✓ .env written

Next step:
  docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

**What just happened?**
- A file called `.env` was created in your project folder containing the secrets
- The Ed25519 signing key was saved to `.secrets/signing_key.pem`
- Neither of these files will ever be committed to Git — they only live on your machine

---

---

# PART 4 — Start DIIaC

**Time: ~5–15 minutes (first run downloads Docker images)**

---

## Step 8 — Start the full stack

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

> **First time only:** Docker needs to build the images. This downloads Node.js,
> Python, and installs all dependencies inside containers. It takes 5–15 minutes
> depending on your internet speed. **Subsequent starts take about 30 seconds.**

---

## Step 9 — Wait for all three services to be ready

Watch the log output in your terminal. Wait until you see **all three** of these lines:

```
governance-runtime  | * Running on http://0.0.0.0:8000
backend-ui-bridge   | DIIaC Bridge listening on port 3001
frontend            | ➜  Local:   http://localhost:5173/
```

This usually takes 60–90 seconds after the build completes.

> **💡 Tip:** Want to run it in the background? Press `Ctrl+C` to stop the log view
> (this does NOT stop DIIaC), then use:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
> ```
> To follow logs later: `docker compose logs -f`

---

## Step 10 — Quick health check

Open a **new** terminal tab, navigate back to the `diiac` folder, and run:

```bash
curl http://localhost:8000/health
```

✅ **You should see:**
```json
{
  "status": "OK",
  "readiness": {
    "overall_ready": true,
    "storage": true,
    "contracts": true,
    "database": true
  }
}
```

If `status` is `OK` and `overall_ready` is `true` — **DIIaC is running correctly.**

---

---

# PART 5 — Open the web interface

**Time: ~5 minutes**

---

## Step 11 — Open your browser

Go to: **http://localhost:5173**

You will be redirected to a **Microsoft sign-in page**.

---

## Step 12 — Sign in with your Vendorlogic account

Sign in using your normal Vendorlogic work email and password.

> If you see a permissions prompt asking to grant access to "DIIaC-UI-Vendorlogic" — click **Accept**.
> This only needs to happen once per account.

✅ **You should see:** The DIIaC dashboard loads, showing panels for:
- Human Input
- Governed Compile
- Trust Dashboard
- Admin Console (admin users only)

---

---

# PART 6 — Your first governed compile

**Time: ~10 minutes**

This is the core DIIaC workflow. We're going to simulate a CTO making an infrastructure decision for Vendorlogic.

---

## Step 13 — Open the Human Input panel

In the DIIaC interface, click **"Human Input"** in the navigation.

This is where you capture what the stakeholder needs and believes.

---

## Step 14 — Fill in the role input form

Complete the form with the following example values (or use real Vendorlogic context):

| Field | Example value |
|-------|--------------|
| **Execution Context ID** | `vendorlogic-cloud-2026-q1` |
| **Role** | `CTO` |
| **Domain** | `Cloud Infrastructure Procurement` |
| **Assertions** | `Azure-primary multi-cloud strategy` / `Zero-trust security required` / `UK data residency mandatory` |
| **Non-Negotiables** | `Microsoft Entra ID integration` / `ISO 27001 compliance` |
| **Risk Flags** | `Single-vendor lock-in` / `Shadow IT proliferation` |
| **Evidence References** | `REF-001: Board technology mandate Q1 2026` |

Click **Submit Role Input**.

✅ **You should see:** A confirmation that the role input has been stored.

---

## Step 15 — Open the Governed Compile panel

Click **"Governed Compile"** in the navigation.

---

## Step 16 — Configure and run the compile

Fill in the compile form:

| Field | Value |
|-------|-------|
| **Execution Context ID** | `vendorlogic-cloud-2026-q1` *(same as above)* |
| **Schema ID** | `it_enterprise_governance_v1` |
| **Profile** | `IT Enterprise` |
| **Reasoning Level** | `strategic` |
| **Policy Level** | `board` |
| **Governance Modes** | `strict`, `hitl` |

Click **Run Governed Compile**.

> **This takes a few seconds.** The platform is analysing your role inputs,
> scoring vendor options against the IT Enterprise sector profile, building
> a Merkle tree, signing the output with Ed25519, and recording everything
> in the trust ledger.

✅ **You should see:** A compiled decision pack appear, containing:
- An **Execution ID** (unique identifier for this decision)
- A **Merkle Root** (cryptographic fingerprint of all outputs)
- A **Signature** (Ed25519 cryptographic signature)
- **Vendor scoring** — ranked recommendations with scores
- **Board report** — a readable governance summary

---

## Step 17 — Verify the output

Click on the **Trust Dashboard** panel.

You should see:
- **Ledger Records:** at least 1 (each compile adds records to the chain)
- **Latest Record Hash:** a long hex string — this proves your decision is in the chain

Click **"Verify Execution"** and paste in your Execution ID.

✅ **You should see:** `"status": "VERIFIABLE"` and `"ledger_match": true`

This means: the decision was recorded, signed, and is tamper-evident.

---

## Step 18 — Export the signed decision pack

In the Governed Compile panel, click **"Export Signed Pack"**.

✅ **You should see:**
- `signature_alg: "Ed25519"` — the algorithm used
- `signing_key_id` — identifies which key signed it
- `zip_sha256` — the fingerprint of the exported file
- `merkle_root` — matches what you saw in the Trust Dashboard

This ZIP file is the **portable governance artefact** — it can be shared with auditors, regulators, or customers as cryptographic proof of the decision.

---

---

# PART 7 — Admin Console (for admin users)

**Time: ~5 minutes**

If you are in the `DIIaC-Admins` Entra group, you have access to the Admin Console.

---

## Step 19 — Open the Admin Console

Click **"Admin Console"** in the navigation.

Here you can see:

| Panel | What it shows |
|-------|--------------|
| **Health** | Real-time readiness of storage, contracts, and database |
| **Metrics** | Total executions, signed percentage, ledger record count |
| **Logs** | Structured backend logs with event IDs |
| **Executions** | All compiled decision packs |
| **Audit Export** | Generate a tamper-evident audit bundle for any set of executions |

---

## Step 20 — Generate an audit export

In the Admin Console, click **"Generate Audit Export"**.

Leave the execution IDs blank to include all executions, then click **Export**.

✅ **You should see:** An audit bundle created with a download URL.

This is what you would send to an auditor or regulator — a complete, cryptographically bound record of all governance decisions.

---

---

# PART 8 — Stopping and restarting

---

## Stopping DIIaC

```bash
# Stop everything (keeps your data)
docker compose -f docker-compose.yml -f docker-compose.staging.yml down
```

## Starting again (fast — no rebuild needed)

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

## Full clean restart (deletes all data — fresh state)

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml down -v
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

---

---

# PART 9 — Demo talking points

Use these when showing DIIaC to stakeholders.

---

### What to say when opening the UI

> *"This is DIIaC — every decision made in here is cryptographically signed and
> tamper-evident. Nothing can be changed after the fact without it being detectable."*

---

### What to say when submitting role input

> *"This is where we capture what the stakeholder — in this case the CTO — actually
> believes and needs. Instead of those requirements living in an email or a PowerPoint,
> they're ingested into the governance engine and become part of the permanent record."*

---

### What to say when running the compile

> *"Watch this — every time we submit the same inputs, we get the exact same Execution ID
> and the same scores. That's deterministic governance. It's not an AI black box — it's
> reproducible, auditable, and you can prove it to a regulator."*

---

### What to say when showing the signature

> *"This Ed25519 signature means this decision pack was signed by this specific key,
> at this specific time. If anyone alters even a single byte in the output, the
> signature breaks. You can verify this offline with just the public key."*

---

### What to say when showing the Merkle tree

> *"The Merkle root binds every individual artefact in the decision pack together.
> If the board report changes, or the vendor scoring changes, the Merkle root changes.
> Nothing can be silently edited."*

---

### What to say when showing the audit export

> *"This is what you hand to your auditor. It contains the complete chain of
> governance decisions, the cryptographic proofs, and the full log of who
> accessed what and when. One click — full audit trail."*

---

---

# PART 10 — Common issues and fixes

---

### "Docker Desktop is not running"

Open Docker Desktop from your Applications or Start Menu. Wait for the whale icon to show green, then try again.

---

### The pull script says "does not have secrets list permission"

Your Azure account needs the `Key Vault Secrets User` role on `kv-diiac-vendorlogic`. Ask your Azure administrator to assign it via:
```bash
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee your.email@vendorlogic.com \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-diiac-prod/providers/Microsoft.KeyVault/vaults/kv-diiac-vendorlogic
```

---

### Health check shows `"overall_ready": false`

```bash
# See which check is failing:
curl http://localhost:8000/health
```

Check the `readiness` section. If `storage: false`, the Docker volumes may not have been created — try a full restart:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml down -v
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

---

### Admin health shows `"key_mode": "ephemeral"`

The signing key wasn't loaded. Re-run the pull script and restart:
```bash
bash scripts/pull-keyvault-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.staging.yml restart governance-runtime
```

---

### The browser shows a blank page or "Cannot connect"

Check that the frontend container is running:
```bash
docker compose ps
```

All three services (governance-runtime, backend-ui-bridge, frontend) should show `running`. If any show `exited`, check logs:
```bash
docker compose logs frontend
docker compose logs backend-ui-bridge
docker compose logs governance-runtime
```

---

### Microsoft sign-in loop — keeps redirecting back to login

1. Check that `http://localhost:5173/auth/callback` is added as a redirect URI in the DIIaC-UI-Vendorlogic Entra app registration.
2. Try clearing your browser cache or opening a private/incognito window.

---

### Port already in use (error: address already in use)

Another service is using port 8000, 3001, or 5173. Edit your `.env` file to change the ports:
```
RUNTIME_HOST_PORT=8001
BRIDGE_HOST_PORT=3002
FRONTEND_HOST_PORT=5174
```
Then restart the stack.

---

---

# Reference — at a glance

| URL | What it is | Auth needed? |
|-----|-----------|-------------|
| http://localhost:5173 | Web interface | Entra login |
| http://localhost:8000/health | Runtime health | None |
| http://localhost:8000/api/business-profiles | List sector profiles | None |
| http://localhost:8000/admin/health | Admin health detail | Admin token |
| http://localhost:8000/admin/metrics | Operational metrics | Admin token |

| Command | What it does |
|---------|-------------|
| `docker compose ... up --build` | Start DIIaC (build images) |
| `docker compose ... up -d` | Start DIIaC in background |
| `docker compose ... down` | Stop DIIaC (keep data) |
| `docker compose ... down -v` | Stop DIIaC and wipe data |
| `docker compose logs -f` | Follow live logs |
| `bash scripts/pull-keyvault-secrets.sh` | Refresh secrets from Azure |

---

*DIIaC v1.2.0 — Vendorlogic Customer Instance*
*For technical issues, raise a GitHub issue or contact the platform team.*
