from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.universe import load_symbols_file, parse_nse_equity_csv, to_yahoo_symbol


class UniverseTests(unittest.TestCase):
    def test_parse_nse_equity_csv_returns_all_eq_symbols_for_yahoo(self) -> None:
        content = "\n".join(
            [
                "SYMBOL,NAME OF COMPANY,SERIES",
                "RELIANCE,Reliance Industries Limited,EQ",
                "TCS,Tata Consultancy Services Limited,EQ",
                "INFY,Infosys Limited,BE",
                "M&M,Mahindra and Mahindra Limited,EQ",
                "RELIANCE,Reliance Industries Limited,EQ",
            ]
        )

        symbols = parse_nse_equity_csv(content)

        self.assertEqual(symbols, ["RELIANCE.NS", "TCS.NS", "M&M.NS"])

    def test_symbols_file_accepts_commas_spaces_and_ns_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "symbols.txt"
            path.write_text("reliance, TCS.NS\n# comment\nm&m\n", encoding="utf-8")

            symbols = load_symbols_file(path)

        self.assertEqual(symbols, ["RELIANCE.NS", "TCS.NS", "M&M.NS"])

    def test_to_yahoo_symbol_normalizes_plain_symbol(self) -> None:
        self.assertEqual(to_yahoo_symbol(" heg "), "HEG.NS")


if __name__ == "__main__":
    unittest.main()

