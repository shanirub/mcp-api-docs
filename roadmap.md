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

## Phase 3 — Doc ingestion ✅
- [x] config.py (centralised DOCS_DIR, INDEX_DIR paths)
- [x] parsers/base.py (abstract base class — shared interface for all parsers)
- [x] parsers/doxygen.py (shared Doxygen XML parser, reused by FreeRTOS + ESP-IDF)
- [x] parsers/freertos.py (FreeRTOS-specific, delegates to doxygen.py)
- [x] parsers/INSTRUCTIONS.md (how to add a new parser)
- [x] downloaders/freertos.py (clones FreeRTOS-Kernel, generates Doxygen XML)
- [x] ingest.py (orchestrator: downloader → parser → JSON index)
- [x] FreeRTOS index live: 1272 symbols, V11.3.0
- [x] lookup_symbol wired to real index, verified end-to-end with xTaskCreate

## Phase 4 — Search quality (next)
- [ ] Fix empty `returns` field for some symbols (e.g. xTaskCreate)
- [ ] Fuzzy matching (tolerates typos and near-matches in symbol names)
- [ ] Multi-API search (query across all APIs at once via api="any")
- [ ] Version-aware lookup (flag if symbol exists in v1 but not v2)
- [ ] "Did you mean X?" suggestions for unknown symbols

## Phase 5 — More APIs
- [ ] ESP-IDF (Doxygen XML — doxygen.py already reusable)
- [ ] Arduino
- [ ] Raspberry Pi (raspi)
- [ ] C standard library
- [ ] C++ STL
- [ ] Python stdlib
- [ ] bash builtins

## Phase 6 — Maintenance
- [ ] Script to re-ingest docs on API updates
- [ ] Health endpoint for monitoring
- [ ] Rate limiting (cap requests per minute to prevent abuse)
- [ ] Auth token for claude.ai connector (if needed)

## Future ideas
- Semantic search layer (embedding-based) for conceptual queries
- Web UI for browsing the index
- CLI tool for local symbol lookup