import unittest
from unittest.mock import patch

from services.service_manager import ServiceManager


class ServiceManagerMCPTests(unittest.TestCase):
    def test_initialize_registers_mcp_client(self):
        manager = ServiceManager()
        manager._services.clear()
        manager._initialized = False

        with (
            patch("utils.config.Config.load"),
            patch("utils.config.Config.get", side_effect=lambda key, default=None: False if key == "mcp.enabled" else default),
            patch.object(ServiceManager, "_init_vectordb"),
            patch.object(ServiceManager, "_init_bm25"),
            patch.object(ServiceManager, "_init_llm"),
            patch.object(ServiceManager, "_init_summarizer_llm"),
            patch.object(ServiceManager, "_init_query_rewriting_llm"),
            patch.object(ServiceManager, "_init_agent"),
        ):
            manager.initialize()

        self.assertIn("mcp_client", manager._services)
        self.assertIsNone(manager.mcp_client)
        manager.cleanup()


if __name__ == "__main__":
    unittest.main()
