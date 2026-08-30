# Versioning and Change Control

Architecture changes follow:

`Architecture Proposal → Contract Update → Tests → Implementation → Review → Commit/PR → Version Update → Freeze`

The architecture specification lives in this folder. Chat-only instructions do
not change architecture. A change that affects architecture must update these
documents, contract tests, implementation mapping, and version metadata before
freeze. Product branding (`NSE Stock Manager v2.1`) and architecture version
(`v2.2-hardened`) are distinct. Immutable records retain their exact schema,
engine/configuration, and provenance versions; new records never overwrite old
ones.
