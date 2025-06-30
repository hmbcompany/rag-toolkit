"""
Rate limiting middleware for RAG Toolkit.

Implements F-4.5: 200 req/s per tenant; 429 with "Retry-After".
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from uuid import UUID
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class RateLimitInfo:
    """Information about rate limiting for a tenant."""
    requests_per_second: int
    window_size: int = 60  # 1 minute window
    current_requests: int = 0
    reset_time: float = 0.0


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, rate: int, burst: int = None):
        """
        Initialize rate limiter.
        
        Args:
            rate: Requests per second
            burst: Burst capacity (defaults to rate)
        """
        self.rate = rate
        self.burst = burst or rate
        self.tokens = float(self.burst)
        self.last_update = time.time()
    
    def allow_request(self) -> Tuple[bool, float]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        time_passed = now - self.last_update
        
        # Add tokens based on elapsed time
        self.tokens = min(self.burst, self.tokens + time_passed * self.rate)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True, 0.0
        else:
            # Calculate retry after time
            retry_after = (1 - self.tokens) / self.rate
            return False, retry_after


class SlidingWindowRateLimiter:
    """Sliding window rate limiter implementation."""
    
    def __init__(self, rate: int, window_seconds: int = 60):
        """
        Initialize sliding window rate limiter.
        
        Args:
            rate: Maximum requests per window
            window_seconds: Window size in seconds
        """
        self.rate = rate
        self.window_seconds = window_seconds
        self.requests = deque()
    
    def allow_request(self) -> Tuple[bool, float]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Remove old requests outside the window
        while self.requests and self.requests[0] < window_start:
            self.requests.popleft()
        
        if len(self.requests) < self.rate:
            self.requests.append(now)
            return True, 0.0
        else:
            # Calculate retry after time
            oldest_request = self.requests[0]
            retry_after = oldest_request + self.window_seconds - now
            return False, max(0.0, retry_after)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting by tenant."""
    
    def __init__(self, app, default_rate: int = 200, default_burst: int = None, 
                 algorithm: str = "token_bucket"):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            default_rate: Default requests per second
            default_burst: Default burst capacity
            algorithm: "token_bucket" or "sliding_window"
        """
        super().__init__(app)
        self.default_rate = default_rate
        self.default_burst = default_burst or default_rate
        self.algorithm = algorithm
        
        # Store rate limiters per tenant
        self.tenant_limiters: Dict[str, object] = {}
        self.tenant_configs: Dict[str, RateLimitInfo] = {}
        
        # Global fallback for unknown tenants
        self.global_limiter = self._create_limiter(default_rate)
    
    def _create_limiter(self, rate: int, burst: int = None):
        """Create a rate limiter instance."""
        if self.algorithm == "token_bucket":
            return TokenBucketRateLimiter(rate, burst or rate)
        elif self.algorithm == "sliding_window":
            return SlidingWindowRateLimiter(rate)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
    
    def get_tenant_id_from_request(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        # Method 1: From subdomain (e.g., acme.ragtoolkit.app)
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain not in ["localhost", "127", "api", "www", "cloud"]:
                return subdomain
        
        # Method 2: From custom header
        tenant_header = request.headers.get("x-tenant-id")
        if tenant_header:
            return tenant_header
        
        # Method 3: From API key (would require database lookup)
        # This would be implemented in a real system
        
        return None
    
    def get_rate_limit_for_tenant(self, tenant_id: str) -> RateLimitInfo:
        """Get rate limit configuration for a tenant."""
        if tenant_id in self.tenant_configs:
            return self.tenant_configs[tenant_id]
        
        # In a real implementation, this would query the database
        # For now, return default configuration
        return RateLimitInfo(
            requests_per_second=self.default_rate,
            window_size=60,
            current_requests=0,
            reset_time=time.time() + 60
        )
    
    def get_limiter_for_tenant(self, tenant_id: str) -> object:
        """Get or create rate limiter for tenant."""
        if tenant_id not in self.tenant_limiters:
            config = self.get_rate_limit_for_tenant(tenant_id)
            self.tenant_limiters[tenant_id] = self._create_limiter(
                config.requests_per_second
            )
        
        return self.tenant_limiters[tenant_id]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for certain paths
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get tenant ID
        tenant_id = self.get_tenant_id_from_request(request)
        
        # Use appropriate limiter
        if tenant_id:
            limiter = self.get_limiter_for_tenant(tenant_id)
            limiter_name = f"tenant:{tenant_id}"
        else:
            limiter = self.global_limiter
            limiter_name = "global"
        
        # Check rate limit
        allowed, retry_after = limiter.allow_request()
        
        if not allowed:
            # Return 429 Too Many Requests with Retry-After header
            headers = {
                "Retry-After": str(int(retry_after) + 1),  # Round up
                "X-RateLimit-Limit": str(self.default_rate),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                "X-RateLimit-Scope": limiter_name
            }
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Try again in {retry_after:.1f} seconds.",
                    "retry_after": retry_after
                },
                headers=headers
            )
        
        # Add rate limit headers to successful responses
        response = await call_next(request)
        
        # Calculate remaining requests (approximation)
        if hasattr(limiter, 'tokens'):
            remaining = int(limiter.tokens)
        elif hasattr(limiter, 'requests'):
            config = self.get_rate_limit_for_tenant(tenant_id or "global")
            remaining = config.requests_per_second - len(limiter.requests)
        else:
            remaining = self.default_rate
        
        response.headers["X-RateLimit-Limit"] = str(self.default_rate)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
        response.headers["X-RateLimit-Scope"] = limiter_name
        
        return response


class TenantRateLimitConfig:
    """Configuration manager for tenant-specific rate limits."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.configs: Dict[str, RateLimitInfo] = {}
        self.default_config = RateLimitInfo(requests_per_second=200)
    
    def set_tenant_rate_limit(self, tenant_id: str, rate: int, burst: int = None):
        """Set rate limit for a specific tenant."""
        self.configs[tenant_id] = RateLimitInfo(
            requests_per_second=rate,
            window_size=60
        )
    
    def get_tenant_rate_limit(self, tenant_id: str) -> RateLimitInfo:
        """Get rate limit configuration for tenant."""
        return self.configs.get(tenant_id, self.default_config)
    
    def remove_tenant_rate_limit(self, tenant_id: str):
        """Remove custom rate limit for tenant (fall back to default)."""
        if tenant_id in self.configs:
            del self.configs[tenant_id]


class AdvancedRateLimiter:
    """Advanced rate limiter with multiple algorithms and tenant-specific configs."""
    
    def __init__(self, config_manager: TenantRateLimitConfig = None):
        """Initialize advanced rate limiter."""
        self.config_manager = config_manager or TenantRateLimitConfig()
        self.limiters: Dict[str, Dict[str, object]] = defaultdict(dict)
    
    def _get_limiter_key(self, tenant_id: str, endpoint: str = "default") -> str:
        """Generate limiter key for tenant and endpoint."""
        return f"{tenant_id}:{endpoint}"
    
    def get_limiter(self, tenant_id: str, endpoint: str = "default") -> object:
        """Get or create rate limiter for tenant and endpoint."""
        key = self._get_limiter_key(tenant_id, endpoint)
        
        if key not in self.limiters[tenant_id]:
            config = self.config_manager.get_tenant_rate_limit(tenant_id)
            self.limiters[tenant_id][endpoint] = TokenBucketRateLimiter(
                rate=config.requests_per_second,
                burst=config.requests_per_second * 2  # Allow 2x burst
            )
        
        return self.limiters[tenant_id][endpoint]
    
    async def check_rate_limit(self, tenant_id: str, endpoint: str = "default") -> Tuple[bool, float]:
        """Check if request is within rate limit."""
        limiter = self.get_limiter(tenant_id, endpoint)
        return limiter.allow_request()
    
    def reset_tenant_limits(self, tenant_id: str):
        """Reset all rate limiters for a tenant."""
        if tenant_id in self.limiters:
            del self.limiters[tenant_id]


# Utility functions for testing and monitoring
def create_rate_limit_response(retry_after: float, limit: int, scope: str) -> JSONResponse:
    """Create a standardized 429 response."""
    headers = {
        "Retry-After": str(int(retry_after) + 1),
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(int(time.time() + retry_after)),
        "X-RateLimit-Scope": scope
    }
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded. Try again in {retry_after:.1f} seconds.",
            "retry_after": retry_after,
            "limit": limit,
            "scope": scope
        },
        headers=headers
    )


async def test_rate_limiter():
    """Test rate limiter functionality."""
    limiter = TokenBucketRateLimiter(rate=5, burst=10)  # 5 req/s, burst of 10
    
    print("Testing rate limiter...")
    
    # Test burst
    for i in range(15):
        allowed, retry_after = limiter.allow_request()
        print(f"Request {i+1}: {'✅ Allowed' if allowed else f'❌ Rate limited (retry in {retry_after:.2f}s)'}")
        
        if not allowed:
            break
    
    print("\nWaiting 2 seconds for token refill...")
    await asyncio.sleep(2)
    
    # Test after refill
    for i in range(5):
        allowed, retry_after = limiter.allow_request()
        print(f"After wait {i+1}: {'✅ Allowed' if allowed else f'❌ Rate limited (retry in {retry_after:.2f}s)'}")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_rate_limiter()) 