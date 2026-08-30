"""Service layer.

Routers stay thin: they authenticate, validate the request shape and delegate.
All domain rules, transactions and audit writes live here.
"""
