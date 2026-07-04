import unittest

from app import app


class PortalTest(unittest.TestCase):
    def test_endpoints_dash_responden(self):
        cliente = app.server.test_client()
        self.assertEqual(cliente.get("/_dash-layout").status_code, 200)
        self.assertEqual(cliente.get("/_dash-dependencies").status_code, 200)


if __name__ == "__main__":
    unittest.main()
