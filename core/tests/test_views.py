from django.test import TestCase


class CoreViewsTests(TestCase):
    def test_home_view_renders_template(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dbablo")

    def test_healthcheck_view_returns_ok(self) -> None:
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
