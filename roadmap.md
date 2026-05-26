# Roadmap

## Phase 1 — Infrastructure ✅
- [x] Hetzner VPS provisioned (Ubuntu 24.04)
- [x] Tailscale SSH (port 22 closed publicly)
- [x] DNS: mcp.ministryofpa.ws
- [x] TLS: Let's Encrypt via certbot
- [x] nginx reverse proxy
- [x] Python MCP server (FastMCP, streamable HTTP)
- [x] End-to-end verified: claude.ai → nginx → MCP server

## Phase 2 — Systemd + Registration ✅
- [x] systemd service for MCP server (auto-start, auto-restart)
- [x] systemd service symlinked from repo (/opt/mcp-server/systemd/)
- [x] Register mcp.ministryofpa.ws in claude.ai Settings → Connectors
- [x] Verified Claude can call `lookup_symbol` tool end-to-end (stub response)

## Phase 3 — Doc ingestion (next)
- [ ] Create config.py (centralised DOCS_DIR, INDEX_DIR paths)
- [ ] Design and finalise JSON index schema
- [ ] Create parsers/base.py (abstract base class — shared interface for all parsers)
- [ ] Create parsers/doxygen.py (shared Doxygen XML parser for FreeRTOS + ESP-IDF)
- [ ] Create parsers/INSTRUCTIONS.md
- [ ] Create downloaders/freertos.py
- [ ] Create parsers/freertos.py
- [ ] Wire FreeRTOS index into lookup_symbol tool
- [ ] Repeat for ESP-IDF, Arduino, Raspberry Pi, C stdlib, C++ STL, Python stdlib, bash

## Phase 4 — Search quality
- [ ] Fuzzy matching (— tolerates typos and near-matches in symbol names)
- [ ] Multi-API search (query across all APIs at once)
- [ ] Version-aware lookup (flag if symbol exists in v1 but not v2)
- [ ] "Did you mean X?" suggestions for unknown symbols

## Phase 5 — Maintenance
- [ ] Script to re-ingest docs on API updates
- [ ] Health endpoint for monitoring
- [ ] Rate limiting (— cap requests per minute to prevent abuse)
- [ ] Auth token for claude.ai connector (if needed)

## Future ideas
- Semantic search layer (embedding-based) for conceptual queries
- Web UI for browsing the index
- CLI tool for local symbol lookup
