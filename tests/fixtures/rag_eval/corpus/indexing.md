# Indexing semantics

`index add` preserves other registered roots. `index sync` mirrors one source
root and removes only documents that belong to that source. Index and manifest
are published as one recoverable generation after successful persistence.

Los archivos sin respuesta válida permanecen pendientes para reintento; no se
marcan como indexados correctamente.
