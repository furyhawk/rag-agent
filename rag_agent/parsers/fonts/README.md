# Vendored fonts

This directory vendors fonts required by the `marker-pdf` library so PDF
conversion works in offline / air-gapped containers.

## Why this is here

`marker` downloads `GoNotoCurrent-Regular.ttf` from
`https://models.datalab.to/artifacts` on first use (in `marker/util.py`,
`download_font()`), storing it next to the installed package. When that host
is unreachable (DNS/egress blocked), every `PdfConverter(...)` construction
raises `NameResolutionError` and the document ingest job fails.

`rag_agent/parsers/pdf.py` sets the `FONT_PATH` env var to this vendored file
before `marker` is imported, so `download_font()` finds the font already
present and never performs a network request.

## Files

- `GoNotoCurrent-Regular.ttf` — 14.7 MB, sha256
  `882afbab965608c2d2bc627fd8016b962aa5a6be2d358f9de24a7b5967c5632e`.
  Downloaded from `https://models.datalab.to/artifacts/GoNotoCurrent-Regular.ttf`
  on 2026-08-18.

## License

`GoNotoCurrent` is a merge of Noto fonts (SIL Open Font License 1.1). Redistribution
is permitted; see the SIL OFL 1.1 terms for details.
