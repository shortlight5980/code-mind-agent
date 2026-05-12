import asyncio
import unittest
from unittest.mock import Mock, patch

import app


class AppHealthTests(unittest.TestCase):
    def test_health_includes_mcp_status(self):
        service_manager = Mock()
        service_manager.vectordb = object()
        service_manager.agent = object()
        mcp_client = Mock()
        mcp_client.is_initialized = True
        mcp_client.health_check.return_value = True
        service_manager.mcp_client = mcp_client

        with patch.object(app, "service_manager", service_manager):
            result = asyncio.run(app.health())

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["vectordb_initialized"])
        self.assertTrue(result["agent_initialized"])
        self.assertTrue(result["mcp_host_initialized"])
        self.assertTrue(result["mcp_client_initialized"])
        self.assertTrue(result["mcp_client_healthy"])


if __name__ == "__main__":
    unittest.main()
