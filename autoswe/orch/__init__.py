"""Orchestrator package — pure decision logic, no I/O.

Three layers:
  A. decide(World) -> Action       — state machine
  B. run(Action, World) -> Result  — Claude runner wrapper
  C. emit(Action, Result, World) -> Effects  — writes
"""
