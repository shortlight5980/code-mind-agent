import unittest
from unittest.mock import patch

from agent.mcp_host import MCPHostError
from services.service_manager import ServiceManager


class ServiceManagerMCPTests(unittest.TestCase):
    def test_initialize_registers_mcp_client(self):
        manager = ServiceManager()
        manager._services.clear()
        manager._initialized = False

        with (
            patch("utils.config.Config.load"),
            patch.object(ServiceManager, "_init_vectordb"),
            patch.object(ServiceManager, "_init_bm25"),
            patch.object(ServiceManager, "_init_llm"),
            patch.object(ServiceManager, "_init_summarizer_llm"),
            patch.object(ServiceManager, "_init_query_rewriting_llm"),
            patch.object(ServiceManager, "_init_agent"),
            patch("services.service_manager.MCPClient") as mcp_client_cls,
        ):
            mcp_client = mcp_client_cls.return_value
            manager.initialize()

        self.assertIn("mcp_client", manager._services)
        self.assertIs(manager.mcp_client, mcp_client)
        mcp_client.initialize.assert_called_once_with()
        manager.cleanup()

    def test_initialize_fails_when_mcp_client_init_fails(self):
        manager = ServiceManager()
        manager._services.clear()
        manager._initialized = False

        with (
            patch("utils.config.Config.load"),
            patch.object(ServiceManager, "_init_vectordb"),
            patch.object(ServiceManager, "_init_bm25"),
            patch.object(ServiceManager, "_init_llm"),
            patch.object(ServiceManager, "_init_summarizer_llm"),
            patch.object(ServiceManager, "_init_query_rewriting_llm"),
            patch.object(ServiceManager, "_init_agent"),
            patch("services.service_manager.MCPClient") as mcp_client_cls,
        ):
            mcp_client_cls.return_value.initialize.side_effect = MCPHostError("boom")
            with self.assertRaises(MCPHostError):
                manager.initialize()

        self.assertFalse(manager.is_initialized)
        manager.cleanup()


if __name__ == "__main__":
    unittest.main()
