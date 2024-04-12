import unittest

from src.util import none_or_whitespace


class UtilTest(unittest.TestCase):
    def test_none_or_whitespace(self):
        true_cases = [None, "", " ", "\t", "\n", "\r\n"]
        false_cases = ["a", " a ", "hi..."]

        for case in true_cases:
            with self.subTest(case=case):
                self.assertTrue(none_or_whitespace(case))

        for case in false_cases:
            with self.subTest(case=case):
                self.assertFalse(none_or_whitespace(case))


if __name__ == "__main__":
    unittest.main()
