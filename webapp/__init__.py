"""Thin clinician-facing demo UI for EPL-CDS.

Two panels mirror the architectural firewall: the LLM proposes Facts
(`/api/extract`, optional, needs a provider), a human verifies/edits them, and
the deterministic engine renders the determination (`/api/evaluate`, always
available offline). This is a research demo — decision support, never a
diagnosis or a medical device.
"""

from webapp.app import create_app

__all__ = ["create_app"]
