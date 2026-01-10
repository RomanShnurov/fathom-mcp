# Security Guide

Comprehensive security guide for deploying Fathom MCP in different environments.

---

## Security Philosophy

Fathom MCP follows the principle of **separation of concerns**:

- **MCP Server** = Read-only access to local documents
- **Authentication** = External tools (reverse proxy, VPN, OAuth provider)
- **Cloud Sync** = External tools (rclone, desktop clients)

This architectural decision follows industry best practices:
- ✅ Don't roll your own auth/crypto
- ✅ Use well-tested, established libraries
- ✅ Single responsibility principle
- ✅ Defense in depth

---

## ⚠️ Important: No Built-In Authentication

**Fathom MCP does NOT include built-in authentication for HTTP transport.**

This is an intentional architectural decision:
- Authentication should be handled by dedicated, well-tested tools
- Most users run locally via stdio transport (no network access)
- Enterprise users have existing auth infrastructure (OAuth, SSO)
- Reduces attack surface and maintenance burden

**Never expose HTTP transport directly to the internet without protection.**

---

## Deployment Security Levels

### Level 1: Local Only (Recommended for Most Users) 🏠

Use **stdio transport** for local AI agents (Claude Desktop, custom clients).

**Configuration:**
```yaml
# config.yaml
transport:
  type: "stdio"  # Default - no network access
```

**Security:**
- ✅ No network exposure
- ✅ No authentication needed
- ✅ Process-level isolation
- ✅ OS-level permissions

**Use when:**
- Running Claude Desktop locally
- Personal knowledge base
- Development/testing

---

### Level 2: Network Isolated 🔒

Use **HTTP transport on localhost only**.

**Configuration:**
```yaml
# config.yaml
transport:
  type: "streamable-http"
  host: "127.0.0.1"  # Localhost only
  port: 8765
```

**Security:**
- ✅ No external network access
- ✅ Only same-machine clients
- ⚠️ No authentication (trust localhost)

**Use when:**
- Local web applications
- Same-machine AI agents
- Development environments

---

### Level 3: Reverse Proxy Authentication 🛡️

Use **reverse proxy** with authentication for remote access.

This is the **recommended approach** for production deployments.

#### Option A: Caddy (Easiest)

**Why Caddy:**
- Automatic HTTPS (Let's Encrypt)
- Built-in basic auth
- Simple configuration
- One binary, no dependencies

**Install:**
```bash
# macOS
brew install caddy

# Ubuntu/Debian
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

**Generate password hash:**
```bash
caddy hash-password
# Enter your password, get bcrypt hash
```

**Caddyfile:**
```caddyfile
# /etc/caddy/Caddyfile

mcp.yourdomain.com {
    # Basic authentication
    basicauth {
        alice $2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpBnZgr5k6V.vS5pLAiNYg6
        bob   $2a$14$Rlw1lVKi7D5XLIxZ.OQzMeJ0grRPV.8K6j3LVLhP2sC6Y9Gqo5xyO
    }

    # Reverse proxy to MCP server
    reverse_proxy localhost:8765 {
        # Health check
        health_uri /_health
        health_interval 30s
        health_timeout 5s
    }

    # Security headers (automatic)
    # - HTTPS redirect
    # - HSTS
    # - TLS 1.3
}
```

**Start Caddy:**
```bash
sudo systemctl enable caddy
sudo systemctl start caddy

# Check logs
sudo journalctl -u caddy -f
```

**Test:**
```bash
# Without auth - should fail
curl https://mcp.yourdomain.com/_health

# With auth - should work
curl -u alice:yourpassword https://mcp.yourdomain.com/_health
```

#### Option B: Nginx (Traditional)

**Why Nginx:**
- Industry standard
- High performance
- Extensive ecosystem
- Fine-grained control

**Install:**
```bash
# Ubuntu/Debian
sudo apt install nginx apache2-utils

# macOS
brew install nginx
```

**Generate password file:**
```bash
# Create password for user 'admin'
sudo htpasswd -c /etc/nginx/.htpasswd admin
# Enter password when prompted
```

**Nginx configuration:**
```nginx
# /etc/nginx/sites-available/fathom-mcp

upstream fathom_mcp {
    server localhost:8765;
    keepalive 32;
}

server {
    listen 80;
    server_name mcp.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;

    # SSL certificates (use certbot for Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Basic authentication
    auth_basic "MCP Server";
    auth_basic_user_file /etc/nginx/.htpasswd;

    # Health check (no auth required)
    location /_health {
        auth_basic off;
        proxy_pass http://fathom_mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # MCP endpoints (auth required)
    location / {
        proxy_pass http://fathom_mcp;
        proxy_http_version 1.1;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Buffering
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=mcp_limit:10m rate=10r/s;
    limit_req zone=mcp_limit burst=20 nodelay;

    # Logging
    access_log /var/log/nginx/fathom-mcp-access.log;
    error_log /var/log/nginx/fathom-mcp-error.log;
}
```

**Enable and test:**
```bash
# Test configuration
sudo nginx -t

# Enable site
sudo ln -s /etc/nginx/sites-available/fathom-mcp /etc/nginx/sites-enabled/

# Reload Nginx
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d mcp.yourdomain.com
```

#### Option C: Traefik (Docker-Native)

**Why Traefik:**
- Automatic service discovery
- Native Docker/Kubernetes support
- Automatic HTTPS
- Dynamic configuration

**docker-compose.yaml:**
```yaml
version: "3.8"

services:
  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your-email@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./letsencrypt:/letsencrypt"
    networks:
      - mcp

  fathom-mcp:
    build: .
    environment:
      FMCP_TRANSPORT__TYPE: "streamable-http"
      FMCP_TRANSPORT__HOST: "0.0.0.0"
      FMCP_TRANSPORT__PORT: "8765"
    volumes:
      - ./documents:/knowledge:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mcp.rule=Host(`mcp.yourdomain.com`)"
      - "traefik.http.routers.mcp.entrypoints=websecure"
      - "traefik.http.routers.mcp.tls.certresolver=letsencrypt"

      # Basic auth middleware
      - "traefik.http.middlewares.mcp-auth.basicauth.users=admin:$$apr1$$hash..."
      - "traefik.http.routers.mcp.middlewares=mcp-auth"

      # Service
      - "traefik.http.services.mcp.loadbalancer.server.port=8765"
    networks:
      - mcp

networks:
  mcp:
    driver: bridge
```

**Generate basic auth hash for Traefik:**
```bash
# Install htpasswd
sudo apt install apache2-utils

# Generate hash (escape $ as $$)
echo $(htpasswd -nb admin yourpassword) | sed 's/\$/\$$/g'
```

---

### Level 4: VPN Access 🌐

Use **VPN** for secure remote access without exposing ports.

This is the **best solution** for remote access to private servers.

#### Option A: Tailscale (Recommended)

**Why Tailscale:**
- Zero-config mesh VPN
- Automatic encryption (WireGuard)
- Per-device authentication
- Works through NAT/firewalls

**Install on server:**
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Get Tailscale IP
tailscale ip -4
# Example: 100.101.102.103
```

**Configure MCP server:**
```yaml
# config.yaml
transport:
  type: "streamable-http"
  host: "0.0.0.0"  # Listen on all interfaces (safe with Tailscale)
  port: 8765
```

**Start MCP server:**
```bash
fathom-mcp --config config.yaml
```

**Connect from client:**
```bash
# Install Tailscale on client device
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Access MCP server via Tailscale IP
curl http://100.101.102.103:8765/_health
```

**Claude Desktop config (on client):**
```json
{
  "mcpServers": {
    "knowledge": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "http://100.101.102.103:8765/mcp",
        "-H", "Content-Type: application/json"
      ]
    }
  }
}
```

**Security:**
- ✅ Encrypted tunnel (WireGuard)
- ✅ Device authentication
- ✅ No exposed ports
- ✅ Works through firewalls
- ✅ Access control via Tailscale admin

#### Option B: WireGuard (Advanced)

For self-hosted VPN with full control.

**Server setup:**
```bash
# Install WireGuard
sudo apt install wireguard

# Generate keys
wg genkey | tee privatekey | wg pubkey > publickey

# Configure
sudo nano /etc/wireguard/wg0.conf
```

**wg0.conf:**
```ini
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = <server-private-key>

# Client peer
[Peer]
PublicKey = <client-public-key>
AllowedIPs = 10.0.0.2/32
```

**Start WireGuard:**
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

**Configure MCP to listen on VPN interface:**
```yaml
transport:
  type: "streamable-http"
  host: "10.0.0.1"  # VPN IP
  port: 8765
```

---

### Level 5: OAuth 2.1 (Enterprise) 🏢

Use **OAuth 2.1** for enterprise environments with existing SSO/IdP.

Based on [MCP official authorization guide](https://modelcontextprotocol.io/docs/tutorials/security/authorization).

**When to use:**
- Multi-tenant deployments
- Enterprise SSO integration (Okta, Auth0, Azure AD)
- Audit requirements (who accessed what)
- Fine-grained permissions per user

**Implementation:**

Uses MCP SDK's built-in `TokenVerifier` (NOT custom implementation):

```python
# src/fathom_mcp/auth.py (example)
from mcp.server.auth.provider import TokenVerifier, AccessToken
from mcp.server.auth.settings import AuthSettings

class IntrospectionTokenVerifier(TokenVerifier):
    """Token verifier using OAuth 2.0 Token Introspection (RFC 7662)."""

    def __init__(self, introspection_endpoint: str, client_id: str, client_secret: str):
        self.introspection_endpoint = introspection_endpoint
        self.client_id = client_id
        self.client_secret = client_secret

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token via authorization server introspection."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.introspection_endpoint,
                data={
                    "token": token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get("active", False):
                return None

            return AccessToken(
                token=token,
                client_id=data.get("client_id", "unknown"),
                scopes=data.get("scope", "").split() if data.get("scope") else [],
                expires_at=data.get("exp"),
            )
```

**Configuration:**
```yaml
# config.yaml
auth:
  enabled: true
  provider: "oauth"
  issuer_url: "https://auth.yourcompany.com"
  client_id: "fathom-mcp"
  client_secret: "${OAUTH_CLIENT_SECRET}"  # From environment
  required_scopes: ["mcp:tools", "mcp:resources"]
```

**Supported providers:**
- Keycloak (open-source)
- Auth0
- Okta
- Azure AD / Entra ID
- Google Workspace
- Any OAuth 2.1 / OIDC compliant provider

**See:** [MCP Authorization Tutorial](https://modelcontextprotocol.io/docs/tutorials/security/authorization) for complete setup.

---

## Docker Deployment Examples

### Secure Docker Compose with Caddy

```yaml
# docker-compose.secure.yaml
version: "3.8"

services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - mcp
    restart: unless-stopped

  fathom-mcp:
    build: .
    environment:
      FMCP_TRANSPORT__TYPE: "streamable-http"
      FMCP_TRANSPORT__HOST: "0.0.0.0"
      FMCP_TRANSPORT__PORT: "8765"
      FMCP_KNOWLEDGE__ROOT: "/knowledge"
    volumes:
      - ./documents:/knowledge:ro
      - ./config.yaml:/app/config.yaml:ro
    # Don't expose ports externally - only via Caddy
    expose:
      - "8765"
    networks:
      - mcp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "/app/docker/healthcheck.py"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  mcp:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
```

**Caddyfile:**
```caddyfile
{
    # Global options
    email your-email@example.com
}

mcp.yourdomain.com {
    # Basic auth
    basicauth {
        admin $2a$14$hash...
    }

    # Reverse proxy
    reverse_proxy fathom-mcp:8765 {
        health_uri /_health
        health_interval 30s
    }

    # Rate limiting
    rate_limit {
        zone dynamic {
            key {remote_host}
            events 100
            window 1m
        }
    }
}
```

**Run:**
```bash
docker-compose -f docker-compose.secure.yaml up -d
```

---

## Security Best Practices

### 1. Never Expose Without Protection

❌ **DON'T:**
```yaml
transport:
  type: "streamable-http"
  host: "0.0.0.0"  # Exposed to internet
  port: 8765
  enable_cors: true
  allowed_origins: ["*"]  # Anyone can access!
```

✅ **DO:**
```yaml
# Option A: Local only
transport:
  type: "stdio"

# Option B: Localhost only
transport:
  type: "streamable-http"
  host: "127.0.0.1"

# Option C: Behind reverse proxy
transport:
  type: "streamable-http"
  host: "127.0.0.1"  # Nginx/Caddy on same machine

# Option D: VPN isolated
transport:
  type: "streamable-http"
  host: "10.0.0.1"  # VPN IP only
```

### 2. Use HTTPS in Production

Always terminate TLS at reverse proxy:
- Caddy: Automatic Let's Encrypt
- Nginx: Use `certbot --nginx`
- Traefik: Automatic ACME

### 3. Implement Rate Limiting

Protect against abuse:

```nginx
# Nginx
limit_req_zone $binary_remote_addr zone=mcp:10m rate=10r/s;
limit_req zone=mcp burst=20 nodelay;
```

```caddyfile
# Caddy
rate_limit {
    zone dynamic {
        key {remote_host}
        events 100
        window 1m
    }
}
```

### 4. Monitor Access Logs

```bash
# Nginx
tail -f /var/log/nginx/fathom-mcp-access.log

# Caddy
journalctl -u caddy -f

# Look for suspicious patterns
grep "401\|403\|500" /var/log/nginx/fathom-mcp-access.log
```

### 5. Keep Credentials Secure

```bash
# Use environment variables
export BASIC_AUTH_PASSWORD="strong-random-password"

# Or use secret management
# - HashiCorp Vault
# - AWS Secrets Manager
# - Docker Secrets

# Never commit credentials
echo ".htpasswd" >> .gitignore
echo "*.env" >> .gitignore
```

### 6. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Update Docker images
docker-compose pull
docker-compose up -d

# Update Fathom MCP
pip install --upgrade fathom-mcp
```

### 7. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Block direct access to MCP port
# (only allow via reverse proxy)
```

### 8. Principle of Least Privilege

```yaml
# Read-only document mounting
volumes:
  - ./documents:/knowledge:ro  # :ro = read-only
```

```bash
# Run as non-root user
docker run --user 1000:1000 fathom-mcp
```

---

## CORS Configuration

**CORS protects against browser-based attacks ONLY.**

It does NOT protect against:
- Direct HTTP requests (curl, wget, Python requests)
- Malicious servers
- API abuse

### Development (Local)

```yaml
# config.yaml
transport:
  enable_cors: true
  allowed_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
```

### Production (Specific Origins)

```yaml
transport:
  enable_cors: true
  allowed_origins:
    - "https://app.yourdomain.com"
    - "https://dashboard.yourdomain.com"
  # NEVER use "*" in production!
```

### Why CORS Alone Is Not Enough

```bash
# CORS only blocks browsers
# This bypasses CORS entirely:
curl -X POST http://your-server:8765/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "search_documents", ...}'
# ^ No browser, no CORS protection
```

**Solution:** Always use authentication (reverse proxy, VPN, OAuth).

---

## Troubleshooting

### Connection Refused

**Problem:**
```
Error: Connection refused to localhost:8765
```

**Solution:**
```bash
# Check if server is running
curl http://localhost:8765/_health

# Check if port is listening
netstat -tlnp | grep 8765

# Check server logs
journalctl -u fathom-mcp -f
```

### 401 Unauthorized

**Problem:**
```
HTTP/1.1 401 Unauthorized
```

**Solution:**
```bash
# Verify basic auth credentials
curl -u username:password http://localhost/_health

# Check .htpasswd file
cat /etc/nginx/.htpasswd

# Regenerate password
htpasswd -c /etc/nginx/.htpasswd username
```

### SSL Certificate Errors

**Problem:**
```
SSL certificate problem: unable to get local issuer certificate
```

**Solution:**
```bash
# Renew Let's Encrypt certificate
sudo certbot renew

# Check certificate expiry
openssl s_client -connect mcp.yourdomain.com:443 -servername mcp.yourdomain.com

# Force HTTPS redirect
# See Nginx/Caddy examples above
```

### Proxy Timeout

**Problem:**
```
504 Gateway Timeout
```

**Solution:**
```nginx
# Increase Nginx timeouts
proxy_connect_timeout 60s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

```yaml
# Increase MCP server timeout
search:
  timeout_seconds: 60
```

---

## Migration Path

### From Local to Production

**Step 1:** Start with stdio (development)
```yaml
transport:
  type: "stdio"
```

**Step 2:** Test with HTTP localhost
```yaml
transport:
  type: "streamable-http"
  host: "127.0.0.1"
```

**Step 3:** Add reverse proxy
```bash
# Install Caddy
sudo apt install caddy

# Configure basic auth
# See examples above
```

**Step 4:** Get SSL certificate
```bash
# Automatic with Caddy
# Just update Caddyfile domain
```

**Step 5:** Monitor and harden
```bash
# Set up monitoring
# Configure rate limits
# Review access logs
```

---

## Related Documentation

- [Integration Guide](integration.md) - Client setup and configuration
- [Configuration Reference](configuration.md) - All configuration options
- [Cloud Sync Guide](cloud-sync-guide.md) - External sync strategies
- [MCP Authorization Tutorial](https://modelcontextprotocol.io/docs/tutorials/security/authorization) - OAuth 2.1 setup

---

## Summary

| Use Case | Recommended Solution | Security Level |
|----------|---------------------|----------------|
| Local development | stdio transport | 🟢 High |
| Same-machine access | HTTP on 127.0.0.1 | 🟢 High |
| Remote personal use | VPN (Tailscale) | 🟢 High |
| Team deployment | Reverse proxy + basic auth | 🟡 Medium-High |
| Enterprise deployment | OAuth 2.1 with SSO | 🟢 High |
| Public API (not recommended) | OAuth + rate limiting + WAF | 🟡 Medium |

**Key principle:** Authentication is NOT the MCP server's responsibility. Use external, proven tools.
