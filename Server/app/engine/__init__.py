"""Deterministic assessment work.

The engine applies domain rules to evidence. It must not talk to HTTP
clients or Supabase directly. Persistence is reached through
repository interfaces, and API routes only invoke services that call
into the engine.
"""
