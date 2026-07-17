# Contrato API

El endpoint de salud es `GET /health`. El chat compatible con OpenAI usa
`POST /v1/chat/completions`. El modo `knowledge` siempre consulta las fuentes
seleccionadas y debe abstenerse si no encuentra evidencia.

The administrative token is sent in the `X-Admin-Token` header. It is never
stored in indexed documents or returned in citations.
