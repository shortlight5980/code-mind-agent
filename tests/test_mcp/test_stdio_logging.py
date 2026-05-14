import importlib
import logging
import os
import sys
import unittest
from unittest.mock import patch


class StdioLoggingTests(unittest.TestCase):
    def test_logger_defaults_to_stderr_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CODEMIND_LOG_STDERR", None)
            import utils.logger as logger_module

            logger_module._logger_instances.clear()
            importlib.reload(logger_module)
            logger = logger_module.get_logger("test.stderr.default")

        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        self.assertTrue(stream_handlers)
        self.assertIs(stream_handlers[0].stream, sys.stderr)


if __name__ == "__main__":
    unittest.main()
