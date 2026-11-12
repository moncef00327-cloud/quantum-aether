"""Result page: grade A shows the badge and free alert before the paid report; other grades show the fix first."""
import copy
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app
from tests.test_app import RESULT


def render(grade):
    result = copy.deepcopy(RESULT)
    result["grade"] = grade
    if grade == "A":
        result["key_exchange"].update(group="X25519MLKEM768", pq=True)
    tmp = tempfile.TemporaryDirectory()
    app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
                                       "HASH_SALT": "s", "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": ""},
                                      scanner=Mock(return_value=result))
    client = app.test_client()
    response = client.post("/scan?lang=en", data={"domain": "example.com"})
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    tmp.cleanup()
    return page


class ResultOrderTests(unittest.TestCase):
    def positions(self, page):
        return {name: page.index(marker) for name, marker in
                (("buy", 'id="buy"'), ("alert", 'id="alert"'), ("badge", 'data-copy="#badge-html"'))}

    def test_grade_a_shows_badge_and_alert_first(self):
        p = self.positions(render("A"))
        self.assertLess(p["badge"], p["alert"])
        self.assertLess(p["alert"], p["buy"])

    def test_other_grades_show_the_fix_first(self):
        for grade in ("B", "C", "F"):
            with self.subTest(grade=grade):
                p = self.positions(render(grade))
                self.assertLess(p["buy"], p["alert"])
                self.assertLess(p["alert"], p["badge"])

    def test_each_card_appears_once(self):
        for grade in ("A", "B"):
            page = render(grade)
            for marker in ('id="buy"', 'id="alert"', 'data-copy="#badge-html"'):
                self.assertEqual(page.count(marker), 1, (grade, marker))

    def test_grade_a_highlights_subdomain_bypass_risk(self):
        page_a = render("A")
        page_b = render("B")
        self.assertIn("bypass the CDN", page_a)
        self.assertNotIn("bypass the CDN", page_b)
        self.assertIn("is rarely the only host", page_b)



if __name__ == "__main__":
    unittest.main()
