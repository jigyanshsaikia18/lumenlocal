"""Async job framework (P2A-1).

A thin layer over Celery that makes every tenant task retryable, idempotent,
per-tenant fair, and dead-letter-backed. See ``base.TenantTask`` for the
contract and ``example`` for a trivial registered task.
"""
