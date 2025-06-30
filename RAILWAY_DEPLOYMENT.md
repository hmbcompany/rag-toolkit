# Railway Deployment Guide

## Overview
This guide walks through deploying the RAG Toolkit multi-tenant application to Railway with full subdomain support.

## Prerequisites
1. Railway account (free tier is sufficient for testing)
2. Custom domain or Railway-provided domain
3. Environment variables configured

## Required Environment Variables

### Database
- `DATABASE_URL` - PostgreSQL connection string (Railway will provide this)

### API Configuration
- `RAGTOOLKIT_API_KEY` - Legacy API key for backward compatibility
- `PORT` - Port to run on (Railway will set this automatically)

### Stripe Configuration (for billing)
- `STRIPE_SECRET_KEY` - Stripe secret key (test mode recommended)
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret
- `STRIPE_TEST_MODE` - Set to "true" for test mode (default: "true")
- `STRIPE_STARTER_PRICE_ID` - Stripe price ID for starter plan
- `STRIPE_PRO_PRICE_ID` - Stripe price ID for pro plan
- `STRIPE_ENTERPRISE_PRICE_ID` - Stripe price ID for enterprise plan

### Optional LLM API Keys
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GOOGLE_API_KEY` - Google API key

## Deployment Steps

### 1. Create Railway Project
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project
railway new
```

### 2. Add PostgreSQL Database
1. Go to your Railway project dashboard
2. Click "Add Service" → "Database" → "PostgreSQL"
3. Railway will automatically set `DATABASE_URL` environment variable

### 3. Deploy Application
```bash
# Link to your Railway project
railway link

# Set environment variables (replace with your values)
railway variables set RAGTOOLKIT_API_KEY=your_api_key_here
railway variables set STRIPE_SECRET_KEY=sk_test_your_stripe_key
railway variables set STRIPE_TEST_MODE=true

# Deploy
railway up
```

### 4. Configure Custom Domain (for subdomain testing)

#### Option A: Use Railway Subdomain
Railway will provide a URL like: `https://your-project.railway.app`

#### Option B: Configure Custom Domain
1. Go to Railway dashboard → Settings → Domains
2. Add your custom domain (e.g., `ragtoolkit.app`)
3. Add wildcard subdomain: `*.ragtoolkit.app`
4. Update DNS records as instructed by Railway

### 5. Test Multi-Tenant Functionality

Once deployed, test the subdomain routing:

```bash
# Create a tenant
curl -X POST https://your-app.railway.app/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Company",
    "slug": "test-company"
  }'

# Test subdomain access (if using custom domain)
curl https://test-company.ragtoolkit.app/health
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `RAGTOOLKIT_API_KEY` | No | - | Legacy API key |
| `STRIPE_SECRET_KEY` | No | - | Stripe secret key |
| `STRIPE_TEST_MODE` | No | `true` | Enable Stripe test mode |
| `PORT` | No | `8000` | Port to run on |

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL service is running in Railway
- Check `DATABASE_URL` environment variable is set

### Subdomain Routing Issues
- Verify wildcard DNS is configured: `*.yourdomain.com`
- Test with Railway's provided domain first

### Rate Limiting
- Default: 200 requests/second per tenant
- No Redis required (in-memory rate limiting)

## Production Considerations

1. **Database**: Use Railway's PostgreSQL Pro for production
2. **Environment**: Set `STRIPE_TEST_MODE=false` for live billing
3. **Monitoring**: Enable Railway's built-in monitoring
4. **Scaling**: Adjust replicas in railway.json if needed

## Support

For issues specific to Railway deployment, check:
- Railway documentation: https://docs.railway.app
- Railway Discord: https://discord.gg/railway 