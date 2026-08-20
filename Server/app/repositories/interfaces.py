"""Repository interfaces.

Future persistence ports must be defined here as vendor-neutral
protocols. Domain and engine code may depend on these interfaces.
They must not import Supabase clients, SQL dialects or HTTP models.

Adapters such as `app.repositories.supabase` implement the interfaces.
No interfaces are declared in this scaffold because the persistence
model is not approved yet.
"""
