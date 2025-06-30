"""
Stripe integration service for RAG Toolkit.

Handles subscription management, billing, and usage tracking.
"""

import os
import stripe
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session
from .models import Tenant, UsageRecord
from .crud import TenantCRUD, UsageCRUD


# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Test mode for Sprint 3
STRIPE_TEST_MODE = os.getenv("STRIPE_TEST_MODE", "true").lower() == "true"

if STRIPE_TEST_MODE:
    print("🔧 Stripe running in TEST MODE")


class StripeService:
    """Service for Stripe billing integration."""
    
    @staticmethod
    def create_customer(email: str, name: str, metadata: Optional[Dict[str, str]] = None) -> stripe.Customer:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create Stripe customer: {e}")
    
    @staticmethod
    def create_subscription(customer_id: str, price_id: str, 
                          trial_days: Optional[int] = None) -> stripe.Subscription:
        """Create a subscription for a customer."""
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "payment_behavior": "default_incomplete" if not trial_days else "allow_incomplete",
                "payment_settings": {"save_default_payment_method": "on_subscription"},
                "expand": ["latest_invoice.payment_intent"],
            }
            
            if trial_days:
                subscription_params["trial_period_days"] = trial_days
            
            subscription = stripe.Subscription.create(**subscription_params)
            return subscription
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create subscription: {e}")
    
    @staticmethod
    def create_usage_based_subscription(customer_id: str, 
                                      metered_price_id: str) -> stripe.Subscription:
        """Create a usage-based subscription for metered billing."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[
                    {
                        "price": metered_price_id,
                    }
                ],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"],
            )
            return subscription
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create usage-based subscription: {e}")
    
    @staticmethod
    def report_usage(subscription_item_id: str, quantity: int, 
                    timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Report usage for metered billing."""
        try:
            usage_timestamp = timestamp or datetime.utcnow()
            
            usage_record = stripe.UsageRecord.create(
                subscription_item=subscription_item_id,
                quantity=quantity,
                timestamp=int(usage_timestamp.timestamp()),
                action="set"  # Replace the usage quantity for this timestamp
            )
            return usage_record
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to report usage: {e}")
    
    @staticmethod
    def create_test_invoice(customer_id: str, amount_cents: int, 
                           description: str) -> stripe.Invoice:
        """Create a test invoice for demonstration purposes."""
        try:
            # Create invoice item
            stripe.InvoiceItem.create(
                customer=customer_id,
                amount=amount_cents,
                currency="usd",
                description=description
            )
            
            # Create and finalize invoice
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=False,  # Don't auto-finalize
                collection_method="send_invoice",
                days_until_due=30
            )
            
            # Finalize the invoice
            finalized_invoice = stripe.Invoice.finalize_invoice(invoice.id)
            return finalized_invoice
            
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create test invoice: {e}")
    
    @staticmethod
    def get_customer(customer_id: str) -> stripe.Customer:
        """Retrieve a Stripe customer."""
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to retrieve customer: {e}")
    
    @staticmethod
    def get_subscription(subscription_id: str) -> stripe.Subscription:
        """Retrieve a Stripe subscription."""
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to retrieve subscription: {e}")
    
    @staticmethod
    def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> stripe.Subscription:
        """Cancel a subscription."""
        try:
            return stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=at_period_end
            )
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to cancel subscription: {e}")
    
    @staticmethod
    def list_invoices(customer_id: str, limit: int = 10) -> List[stripe.Invoice]:
        """List invoices for a customer."""
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit
            )
            return invoices.data
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to list invoices: {e}")


class TenantBillingService:
    """Service for managing tenant billing and subscriptions."""
    
    @staticmethod
    def setup_tenant_billing(db: Session, tenant_id: UUID, 
                           admin_email: str) -> Dict[str, Any]:
        """Set up billing for a new tenant."""
        tenant = TenantCRUD.get_tenant(db, tenant_id)
        if not tenant:
            raise Exception("Tenant not found")
        
        if tenant.stripe_customer_id:
            raise Exception("Billing already set up for this tenant")
        
        try:
            # Create Stripe customer
            customer = StripeService.create_customer(
                email=admin_email,
                name=tenant.name,
                metadata={
                    "tenant_id": str(tenant_id),
                    "tenant_slug": tenant.slug
                }
            )
            
            # Update tenant with Stripe customer ID
            TenantCRUD.update_tenant(
                db, 
                tenant_id, 
                stripe_customer_id=customer.id,
                subscription_status="trial"
            )
            
            return {
                "customer_id": customer.id,
                "tenant_id": str(tenant_id),
                "status": "billing_setup_complete"
            }
            
        except Exception as e:
            raise Exception(f"Failed to set up billing: {e}")
    
    @staticmethod
    def create_tenant_subscription(db: Session, tenant_id: UUID, 
                                 plan: str = "starter") -> Dict[str, Any]:
        """Create a subscription for a tenant."""
        tenant = TenantCRUD.get_tenant(db, tenant_id)
        if not tenant or not tenant.stripe_customer_id:
            raise Exception("Tenant not found or billing not set up")
        
        # Price IDs for different plans (these would be configured in Stripe)
        price_ids = {
            "starter": os.getenv("STRIPE_STARTER_PRICE_ID", "price_test_starter"),
            "pro": os.getenv("STRIPE_PRO_PRICE_ID", "price_test_pro"),
            "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "price_test_enterprise")
        }
        
        price_id = price_ids.get(plan)
        if not price_id:
            raise Exception(f"Unknown plan: {plan}")
        
        try:
            # Create subscription with 14-day trial
            subscription = StripeService.create_subscription(
                customer_id=tenant.stripe_customer_id,
                price_id=price_id,
                trial_days=14
            )
            
            # Update tenant subscription status
            TenantCRUD.update_tenant(
                db,
                tenant_id,
                subscription_plan=plan,
                subscription_status="trialing" if subscription.trial_end else "active"
            )
            
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "trial_end": subscription.trial_end,
                "plan": plan
            }
            
        except Exception as e:
            raise Exception(f"Failed to create subscription: {e}")
    
    @staticmethod
    def generate_usage_invoice(db: Session, tenant_id: UUID, 
                             period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate a usage-based invoice for a tenant."""
        tenant = TenantCRUD.get_tenant(db, tenant_id)
        if not tenant or not tenant.stripe_customer_id:
            raise Exception("Tenant not found or billing not set up")
        
        # Calculate usage for the period
        usage_data = UsageCRUD.calculate_current_usage(db, tenant_id)
        
        # Pricing tiers (example)
        trace_cost_per_thousand = 1.00  # $1 per 1000 traces
        seat_cost_per_month = 10.00     # $10 per seat per month
        
        # Calculate costs
        trace_cost_cents = int((usage_data["trace_count"] / 1000) * trace_cost_per_thousand * 100)
        seat_cost_cents = int(usage_data["seat_count"] * seat_cost_per_month * 100)
        total_cost_cents = trace_cost_cents + seat_cost_cents
        
        try:
            # Create test invoice
            invoice = StripeService.create_test_invoice(
                customer_id=tenant.stripe_customer_id,
                amount_cents=total_cost_cents,
                description=f"RAG Toolkit usage for {period_start.strftime('%B %Y')}\n" +
                           f"Traces: {usage_data['trace_count']:,}\n" +
                           f"Seats: {usage_data['seat_count']}"
            )
            
            return {
                "invoice_id": invoice.id,
                "amount_cents": total_cost_cents,
                "trace_count": usage_data["trace_count"],
                "seat_count": usage_data["seat_count"],
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "invoice_url": invoice.hosted_invoice_url
            }
            
        except Exception as e:
            raise Exception(f"Failed to generate usage invoice: {e}")
    
    @staticmethod
    def get_tenant_billing_info(db: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Get billing information for a tenant."""
        tenant = TenantCRUD.get_tenant(db, tenant_id)
        if not tenant:
            raise Exception("Tenant not found")
        
        billing_info = {
            "tenant_id": str(tenant_id),
            "subscription_status": tenant.subscription_status,
            "subscription_plan": tenant.subscription_plan,
            "stripe_customer_id": tenant.stripe_customer_id
        }
        
        if tenant.stripe_customer_id:
            try:
                # Get recent invoices
                invoices = StripeService.list_invoices(tenant.stripe_customer_id, limit=5)
                billing_info["recent_invoices"] = [
                    {
                        "id": inv.id,
                        "amount_paid": inv.amount_paid,
                        "status": inv.status,
                        "created": inv.created,
                        "invoice_url": inv.hosted_invoice_url
                    }
                    for inv in invoices
                ]
                
                # Get customer info
                customer = StripeService.get_customer(tenant.stripe_customer_id)
                billing_info["customer_email"] = customer.email
                
            except Exception as e:
                billing_info["error"] = f"Failed to fetch Stripe data: {e}"
        
        return billing_info


def create_test_products_and_prices():
    """Create test products and prices in Stripe for development."""
    if not STRIPE_TEST_MODE:
        print("⚠️  Not in test mode, skipping test product creation")
        return
    
    try:
        # Create RAG Toolkit product
        product = stripe.Product.create(
            name="RAG Toolkit",
            description="RAG observability and evaluation platform"
        )
        
        # Create prices for different plans
        starter_price = stripe.Price.create(
            product=product.id,
            unit_amount=2900,  # $29.00
            currency="usd",
            recurring={"interval": "month"},
            nickname="Starter Plan"
        )
        
        pro_price = stripe.Price.create(
            product=product.id,
            unit_amount=9900,  # $99.00
            currency="usd",
            recurring={"interval": "month"},
            nickname="Pro Plan"
        )
        
        # Usage-based price for traces
        usage_price = stripe.Price.create(
            product=product.id,
            unit_amount=100,  # $1.00 per unit
            currency="usd",
            recurring={
                "interval": "month",
                "usage_type": "metered"
            },
            billing_scheme="per_unit",
            nickname="Per-trace billing"
        )
        
        print(f"✅ Created test products and prices:")
        print(f"   Product ID: {product.id}")
        print(f"   Starter Price ID: {starter_price.id}")
        print(f"   Pro Price ID: {pro_price.id}")
        print(f"   Usage Price ID: {usage_price.id}")
        
        return {
            "product_id": product.id,
            "starter_price_id": starter_price.id,
            "pro_price_id": pro_price.id,
            "usage_price_id": usage_price.id
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Failed to create test products: {e}")
        return None


if __name__ == "__main__":
    # Create test products when running this file directly
    create_test_products_and_prices() 