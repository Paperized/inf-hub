import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inf_hub.runtime import effective_local_value, parse_id


class RuntimeTests(unittest.TestCase):
    def test_parse_id(self):
        self.assertEqual(parse_id("Name | abc"), "abc")
        self.assertIsNone(parse_id(None))

    def test_effective_local_value_reads_inf(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("inf_hub.config.LOCAL_INF_FILE", Path(td) / ".inf"):
                inf = Path(td) / ".inf"
                inf.write_text("tokenId: token-main\nprojectId: proj-1\nenvironment: dev\n")
                self.assertEqual(effective_local_value("tokenId"), "token-main")


if __name__ == "__main__":
    unittest.main()
