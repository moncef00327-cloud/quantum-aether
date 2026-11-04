import unittest

import uptime_check as u


class UptimeDecisionTests(unittest.TestCase):
    def test_healthy_stays_quiet(self):
        state, actions = u.decide({"fails": 0, "down_since": None, "alerted": False}, True, True, "t0")
        self.assertEqual(actions, [])
        self.assertEqual(state["fails"], 0)

    def test_single_blip_is_ignored(self):
        state, actions = u.decide({"fails": 0}, False, False, "t0")
        self.assertEqual(actions, [])
        self.assertEqual(state["fails"], 1)

    def test_app_down_twice_restarts_app_and_alerts_once(self):
        s, a = u.decide({"fails": 0}, False, False, "t0")
        s, a = u.decide(s, False, False, "t1")
        self.assertEqual(a, ["restart:quantum_saas", "alert_down"])
        self.assertEqual(s["down_since"], "t0")
        s, a = u.decide(s, False, False, "t2")
        self.assertEqual(a, [])                       # لا رسالة ثانية ولا إعادة تشغيل كل 5 دقائق
        s, a = u.decide(s, False, False, "t3")
        s, a = u.decide(s, False, False, "t4")
        self.assertEqual(a, ["restart:quantum_saas"])  # محاولة ثانية واحدة فقط
        for t in range(10):
            s, a = u.decide(s, False, False, f"x{t}")
            self.assertNotIn("restart:quantum_saas", a)
        s, a = u.decide(s, True, True, "t9")
        self.assertEqual(a, ["alert_up"])
        self.assertEqual(s, {"fails": 0, "down_since": None, "alerted": False})

    def test_proxy_down_restarts_caddy(self):
        s, _ = u.decide({"fails": 0}, True, False, "t0")
        _, a = u.decide(s, True, False, "t1")
        self.assertIn("restart:caddy", a)


if __name__ == "__main__":
    unittest.main()
