from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "api-docs",
    transport_security=TransportSecuritySettings(
        allowed_hosts=["mcp.ministryofpa.ws"],
        allowed_origins=["https://mcp.ministryofpa.ws"],
    )
)

@mcp.tool()
def lookup_symbol(symbol: str) -> str:
    """Look up an API symbol, returning its signature and description."""
    return f"[STUB] Symbol '{symbol}' was queried. Index not built yet."

if __name__ == "__main__":
    import uvicorn
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)
