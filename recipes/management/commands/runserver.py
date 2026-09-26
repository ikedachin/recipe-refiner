"""Keep local startup independent of reverse DNS availability."""

from socketserver import TCPServer

from django.contrib.staticfiles.management.commands.runserver import Command as StaticRunserver
from django.core.servers.basehttp import WSGIServer


class LocalWSGIServer(WSGIServer):
    def server_bind(self) -> None:
        # HTTPServer.server_bind performs getfqdn(), which can stall offline.
        # WSGI only needs a server name; the explicit bound address is sufficient.
        TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]
        self.setup_environ()


class Command(StaticRunserver):
    server_cls = LocalWSGIServer
