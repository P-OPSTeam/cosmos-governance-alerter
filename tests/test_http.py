"""Tests for governance API HTTP configuration."""
import unittest

from governance_vote import create_http_session, get_request_timeout


class HttpConfigurationTests(unittest.TestCase):
    """Verify connection pooling, retries, and timeout configuration."""

    def test_session_uses_configured_get_retries(self):
        session = create_http_session({
            'request_retries': 3,
            'request_backoff_factor': 0.25,
        })

        retry = session.get_adapter('http://').max_retries
        self.assertEqual(retry.total, 3)
        self.assertEqual(retry.connect, 3)
        self.assertEqual(retry.backoff_factor, 0.25)
        self.assertEqual(retry.allowed_methods, frozenset({'GET'}))
        session.close()

    def test_request_timeout_defaults(self):
        self.assertEqual(get_request_timeout({}), (5.0, 30.0))

    def test_request_timeout_is_configurable(self):
        self.assertEqual(
            get_request_timeout({
                'request_connect_timeout': 2,
                'request_read_timeout': 15,
            }),
            (2.0, 15.0),
        )


if __name__ == '__main__':
    unittest.main()
