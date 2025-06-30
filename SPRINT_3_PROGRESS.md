# Sprint 3: Cloud Multi-Tenant Alpha

## Objectives (from PRD)
**Sprint 3 - E-4 Cloud Multi-Tenant Alpha**

Exit criteria: Design-partner tenant live; Stripe test invoice generated

## Sprint 3 Tasks

### F-4.1: Tenant Isolation
- [ ] Postgres schema per tenant
- [ ] All rows tagged with tenant_id  
- [ ] Database migration for multi-tenancy
- [ ] API authentication updates for tenant context

### F-4.2: Sub-domain Routing  
- [ ] `{tenant}.ragtoolkit.app` via Traefik
- [ ] Fallback login at `cloud.ragtoolkit.app/login`
- [ ] DNS and certificate management

### F-4.3: Metering Service
- [ ] Cron job every 1 hour
- [ ] Aggregate `trace.count`, `seat.count` into usage table
- [ ] Usage API endpoints

### F-4.4: Stripe Integration (Test Mode)
- [ ] Create Customer functionality
- [ ] Attach Subscription capability  
- [ ] Store `stripe_customer_id`
- [ ] Generate test invoice

### F-4.5: Rate Limiting
- [ ] 200 req/s per tenant limit
- [ ] 429 responses with "Retry-After"
- [ ] Rate limiting middleware

## Progress Log

**Started**: $(date +"%Y-%m-%d %H:%M:%S")
**Branch**: sprint-3-cloud-multi-tenant
**Previous Sprint**: Sprint 2 completed - Integration Wizard fully functional

## Current Status
🎯 **Ready to start Sprint 3 development**

### Sprint 2 Completion Status:
- ✅ Integration Wizard (E-2) - Complete 
- ✅ SDK Connectors (E-3) - Complete
- ✅ Git repository clean and synchronized
- ✅ All systems operational (Docker, API, Database, Frontend)

### Next Steps:
1. Start with F-4.1 (Tenant Isolation) - Core database changes
2. Implement F-4.3 (Metering Service) - Usage tracking foundation  
3. Add F-4.4 (Stripe Integration) - Billing infrastructure
4. Deploy F-4.5 (Rate Limiting) - API protection
5. Complete F-4.2 (Sub-domain Routing) - Cloud deployment 