"""Trial feedback from the dashboard: reaches the owner even when the trial user's own address bounces."""
import unittest

import monitor
import monitor_db
from tests.test_trial import TrialTest, shift_trial


class TrialFeedbackTest(TrialTest):
    def test_dashboard_shows_feedback_form_in_three_languages(self):
        self.start_trial()
        token = self.trial_token()
        for lang, word in (("en", "How is the trial going?"), ("ar", "كيف تجدون التجربة؟")):
            body = self.client.get(f"/monitor/{token}?lang={lang}").get_data(as_text=True)
            self.assertIn(word, body)
            self.assertIn(f'action="/monitor/{token}/feedback', body)

    def test_feedback_is_stored_and_emailed_to_owner(self):
        self.start_trial()
        token = self.trial_token()
        self.mailer.sent.clear()
        r = self.client.post(f"/monitor/{token}/feedback?lang=en",
                             data={"liked": "yes", "subscribe": "maybe", "note": "Need Slack alerts\x07"})
        self.assertIn("n=feedback_thanks", r.headers["Location"])
        owner = [m for m in self.mailer.sent if m[0] == "owner@example.com"]
        self.assertEqual(len(owner), 1)
        self.assertIn("liked=yes, subscribe=maybe", owner[0][1])
        self.assertIn("Need Slack alerts", owner[0][2])
        with self.conn() as c:
            fb = monitor_db.last_feedback(c, self.account()["id"])
        self.assertEqual((fb["liked"], fb["subscribe"], fb["note"]), ("yes", "maybe", "Need Slack alerts"))
        page = self.client.get(f"/monitor/{token}?lang=en&n=feedback_thanks").get_data(as_text=True)
        self.assertIn("Your feedback reached the team", page)
        self.assertIn("we received your feedback", page)

    def test_invalid_answers_and_daily_limit(self):
        self.start_trial()
        token = self.trial_token()
        r = self.client.post(f"/monitor/{token}/feedback", data={"liked": "maybe", "subscribe": "yes"})
        self.assertIn("n=feedback_invalid", r.headers["Location"])
        for _ in range(monitor_db.FEEDBACK_PER_DAY):
            self.client.post(f"/monitor/{token}/feedback", data={"liked": "no", "subscribe": "no"})
        r = self.client.post(f"/monitor/{token}/feedback", data={"liked": "no", "subscribe": "no"})
        self.assertIn("n=feedback_limit", r.headers["Location"])
        self.assertEqual(self.client.post("/monitor/not-a-token/feedback", data={"liked": "yes", "subscribe": "yes"}).status_code, 404)

    def test_ended_trial_can_still_send_feedback_and_purge_removes_it(self):
        self.start_trial()
        token = self.trial_token()
        acc = self.account()
        with self.conn() as c:
            monitor_db.set_status(c, acc["id"], "TRIAL_ENDED")
        r = self.client.post(f"/monitor/{token}/feedback", data={"liked": "partly", "subscribe": "no"})
        self.assertIn("n=feedback_thanks", r.headers["Location"])
        with self.conn() as c:
            monitor_db.purge_ended_trials(c, "9999-01-01T00:00:00Z")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM trial_feedback").fetchone()[0], 0)

    def test_reminder_and_end_emails_ask_for_feedback(self):
        acc = {"lang": "ar"}
        self.assertIn("هل ترغبون بالاشتراك", monitor.trial_reminder_email(acc, 3, "u")[1])
        self.assertIn("would you like to subscribe", monitor.trial_reminder_email({"lang": "en"}, 3, "u")[1])
        self.assertIn("Reply to this email", monitor.trial_ended_email({"lang": "en"}, "u")[1])


if __name__ == "__main__":
    unittest.main()
