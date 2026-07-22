import json
import tempfile
import unittest
from pathlib import Path

from scripts.convert_sing_box_rules import RuleFormatError, convert_file, parse_rules


class ParseRulesTest(unittest.TestCase):
    def test_parses_comments_and_removes_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.txt"
            source.write_text(
                "# comment\n"
                "DOMAIN,example.com\n"
                "DOMAIN-SUFFIX,example.org\n"
                "DOMAIN-KEYWORD,example\n"
                "DOMAIN,example.com\n",
                encoding="utf-8",
            )

            self.assertEqual(
                parse_rules(source),
                {
                    "domain": ["example.com"],
                    "domain_suffix": ["example.org"],
                    "domain_keyword": ["example"],
                },
            )

    def test_rejects_unsupported_rule_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.txt"
            source.write_text("IP-CIDR,192.0.2.0/24\n", encoding="utf-8")

            with self.assertRaisesRegex(RuleFormatError, "unsupported rule type"):
                parse_rules(source)

    def test_rejects_malformed_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.txt"
            source.write_text("DOMAIN\n", encoding="utf-8")

            with self.assertRaisesRegex(RuleFormatError, "expected RULE-TYPE,value"):
                parse_rules(source)


class ConvertFileTest(unittest.TestCase):
    def test_writes_sing_box_source_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "rules.txt"
            destination = root / "output" / "rules.json"
            source.write_text("DOMAIN-SUFFIX,example.com\n", encoding="utf-8")

            convert_file(source, destination)

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {
                    "version": 3,
                    "rules": [{"domain_suffix": ["example.com"]}],
                },
            )


if __name__ == "__main__":
    unittest.main()
