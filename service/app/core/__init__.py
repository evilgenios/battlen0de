"""Warpath protocol engine: wire format, per-account credentials, the TCP
game-server client, and the Lilith account-linking HTTP client.

Nothing in this package reads Discord, FastAPI, or any other control-surface
state. It only knows about one thing: speaking the Warpath protocol on
behalf of whatever WarpathCredentials it is given.
"""
