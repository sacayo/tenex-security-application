"""Model integration: the only package that performs LLM I/O.

``client``   - OpenAI-compatible HTTP adapter and error types.
``generate`` - background job that builds facts, calls the model, validates,
and persists the narrative.

Prompt and validation logic stay pure in ``app.service.narrative``.
"""
