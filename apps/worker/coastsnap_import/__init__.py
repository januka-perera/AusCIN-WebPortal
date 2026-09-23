"""Single-site CoastSnap ingestion proof of concept.

Pipeline: Spotteron API -> Level 0 original -> Level 1 copy with
embedded metadata -> JSON manifest -> SFTP transfer to a Gadi test
directory. See apps/worker/coastsnap_import/cli.py for the entry point.

This package is intentionally independent of apps/web: it defines its
own ingestion-shaped models (product level, storage path, parent
media, checksums, processing details, transfer status) rather than
reusing the frontend's CoastSnapObservation type, which was never
meant to describe pipeline state.
"""

__version__ = "0.1.0"
