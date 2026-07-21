"""PCB-CDSO domain layer package.

Holds command services that encode business invariants. The HTTP layer is a
thin adapter over these services; persistence uses SQLAlchemy 2.0 sync
sessions per ADR-0001.
"""
