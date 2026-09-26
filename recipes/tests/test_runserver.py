from unittest.mock import MagicMock, patch

from django.core.management import get_commands

from recipes.management.commands.runserver import LocalWSGIServer

from .helpers import OfflineSimpleTestCase


class RunserverTests(OfflineSimpleTestCase):
    def test_local_command_overrides_staticfiles_command(self):
        self.assertEqual(get_commands()["runserver"], "recipes")

    def test_binding_does_not_require_reverse_dns(self):
        server = MagicMock()
        server.server_address = ("127.0.0.1", 8123)
        with patch("recipes.management.commands.runserver.TCPServer.server_bind") as bind:
            with patch("socket.getfqdn", side_effect=AssertionError("Unexpected DNS lookup")):
                LocalWSGIServer.server_bind(server)
        bind.assert_called_once_with(server)
        self.assertEqual(server.server_name, "127.0.0.1")
        self.assertEqual(server.server_port, 8123)
        server.setup_environ.assert_called_once()
