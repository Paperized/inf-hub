import unittest

from inf_hub.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_register_token_command_exists(self):
        parser = build_parser()
        args = parser.parse_args(["register", "token", "--token-id", "t1", "--token", "abc", "--yes"])
        self.assertEqual(args.command, "register")
        self.assertEqual(args.register_object, "token")
        self.assertEqual(args.token_id, "t1")

    def test_unregister_token_command_exists(self):
        parser = build_parser()
        args = parser.parse_args(["unregister", "token", "--token-id", "t1", "--yes"])
        self.assertEqual(args.command, "unregister")
        self.assertEqual(args.unregister_object, "token")

    def test_init_token_removed(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["init", "token"])

    def test_update_command_exists(self):
        parser = build_parser()
        args = parser.parse_args(["update", "-k", "A", "-v", "1", "-f", ".env.local"])
        self.assertEqual(args.command, "update")
        self.assertEqual(args.k, ["A"])
        self.assertEqual(args.v, ["1"])
        self.assertEqual(args.file, ".env.local")


if __name__ == "__main__":
    unittest.main()
