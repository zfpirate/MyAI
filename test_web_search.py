import unittest
from unittest.mock import patch

from internet.web_search import search_web


class WebSearchTests(unittest.TestCase):
    def test_rejects_invalid_queries_without_network_access(self):
        with patch("internet.web_search.DDGS") as ddgs:
            self.assertEqual(search_web(" "), {
                "status": "error",
                "message": "Longueur de recherche invalide.",
                "results": [],
            })
            ddgs.assert_not_called()

    def test_normalizes_and_limits_search_results(self):
        results = [
            {
                "title": f"Result {index}",
                "href": f"https://example.com/{index}",
                "body": "Summary",
            }
            for index in range(5)
        ]
        client = patch("internet.web_search.DDGS")
        with client as ddgs_type:
            ddgs_type.return_value.__enter__.return_value.text.return_value = (
                results
            )
            result = search_web("  Python   programming  ", max_results=3)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["query"], "Python programming")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["results"]), 3)

    def test_rejects_non_http_result_urls(self):
        with patch("internet.web_search.DDGS") as ddgs_type:
            ddgs_type.return_value.__enter__.return_value.text.return_value = [
                {"title": "Bad", "href": "javascript:alert(1)", "body": ""}
            ]
            result = search_web("valid query")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()
