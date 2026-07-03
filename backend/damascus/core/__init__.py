"""
Damascus Core
=============
The central coordination system of the platform.
Provides: Orchestration Runtime, State Manager, Event Bus,
Scheduler, Registry Layer, Lifecycle Manager, Observability Layer.

The Core does NOT own:
- long-term memory
- tool implementations
- model implementations
- security policies
- agent reasoning
- evolution decisions

Those belong to their respective dedicated subsystems.
"""
