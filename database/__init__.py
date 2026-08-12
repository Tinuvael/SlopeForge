"""Active PostgreSQL persistence package.

The concrete modules remain here temporarily because moving the shared ORM graph,
Alembic metadata, repositories, and startup code together would create high-risk
churn. New infrastructure adapters belong under :mod:`infrastructure.db`.
"""
