# Environment Setup Guide

## Quick Start

### 1. Copy the unified environment file
```bash
cp .env.example .env
```

### 2. Generate secrets
```bash
# Generate all required secrets
export JWT_SECRET=$(openssl rand -base64 32)
export AES_KEY=$(openssl rand -base64 32)
export API_KEY=$(openssl rand -base64 32)
export NEXTAUTH_SECRET=$(openssl rand -base64 32)

# Update .env with generated values (Linux/macOS)
sed -i "s/generate_a_random_256_bit_string_here/$JWT_SECRET/" .env
sed -i "s/generate_a_random_256_bit_key_here/$AES_KEY/" .env
```

### 3. Component-specific env files

For development, you can use per-component env files:

| File | Scope | When to Use |
|------|-------|-------------|
| `.env` | All services | Docker Compose, full-stack development |
| `apps/web/.env.local` | Next.js only | Frontend-only development |
| `services/api/.env` | FastAPI only | API-only development |

### 4. Database Configuration

**Local Development (SQLite):**
```
DATABASE_URL=file:./dev.db
```

**Production (PostgreSQL):**
```
DATABASE_URL=postgresql://postgres:your_password@postgres:5432/omnimedical
```

> Note: The Prisma schema defaults to `provider = "sqlite"`. For PostgreSQL
> production deployments, change it to `provider = "postgresql"` in
> `prisma/schema.prisma`.

## Security Reminders

- Never commit `.env` files to version control
- Rotate secrets regularly
- Use different secrets for development and production
- Add `.env` and `.env.local` to your `.gitignore`
