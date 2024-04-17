import unittest

from src.util import greet


class UtilTest(unittest.TestCase):
    def test_greet(self):
        name = "Alice"
        expected_result = "Hello, Alice!"
        result = greet(name)
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()
