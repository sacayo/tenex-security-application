"""LLM integration: the only package that talks to the model server.

    client.py    -> OpenAI-compatible HTTP adapter (httpx) + error types
    generate.py  -> background job that builds facts, calls the model,
                    validates, and persists the narrative

Pure prompt/validation logic lives in `app.service.narrative`; this package
is the impure edge around it.
"""
