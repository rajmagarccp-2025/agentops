from platform_api.mcp.audit import DatabaseAuditSink
from platform_api.mcp.mock_tools import default_tools
from platform_api.mcp.registry import ToolRegistry

audit_sink = DatabaseAuditSink()
tool_registry = ToolRegistry(default_tools(), audit_sink)
