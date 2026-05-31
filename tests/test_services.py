import tempfile
import unittest
from pathlib import Path

from inf_hub.errors import ValidationError
from inf_hub.services import pair_updates, parse_env_file, write_env_file


class ServicesTests(unittest.TestCase):
    def test_pair_updates_requires_matching_pairs(self):
        with self.assertRaises(ValidationError):
            pair_updates(["A"], ["1", "2"])

    def test_parse_env_file_supports_export_and_comments(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text("# comment\nexport A=1\nB=2\n")
            updates = parse_env_file(str(p))
            self.assertEqual([(u.key, u.value) for u in updates], [("A", "1"), ("B", "2")])

    def test_write_env_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            write_env_file(str(p), [{"secretKey": "A", "secretValue": "1"}, {"secretKey": "B", "secretValue": "2"}])
            self.assertEqual(p.read_text(), "A=1\nB=2\n")


if __name__ == "__main__":
    unittest.main()
