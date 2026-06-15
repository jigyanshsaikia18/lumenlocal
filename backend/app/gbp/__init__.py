"""Google Business Profile integration seam (OAuth + locations).

The concrete Google HTTP calls live behind an abstract client so the connection
flow can be unit-tested without the network (mirrors ``app.sso`` and
``app.core.vault``). ``get_gbp_client`` returns the real client when Google
credentials are configured, otherwise the in-memory mock for local dev/tests.
"""
