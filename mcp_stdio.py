"""Compatibility entry point for the documented root-level MCP stdio command."""
import runpy
import sys
import backend  # noqa: F401 -- registers the reorganized application modules

if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    runpy.run_module('backend.api.mcp_stdio', run_name='__main__')
