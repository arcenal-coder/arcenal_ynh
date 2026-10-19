"""HTTPS épinglé à une IP résolue/validée ; aucun proxy ni redirection."""

import ipaddress
import http.client
import json
import socket
import ssl
import time
from urllib.parse import quote, urlsplit

from .contracts import Denied, require


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        self.tls_context = ssl.create_default_context()
        super().__init__(hostname, port=443, timeout=10, context=self.tls_context)
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            # Connexion à l'IP autorisée, mais certificat vérifié pour le vrai nom.
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class Network:
    def __init__(self, networks=()):
        self.networks = tuple(ipaddress.ip_network(value) for value in networks)

    def request(self, config, method, suffix, headers=None, body=None):
        base = urlsplit(config["url"])
        try:
            addresses = {str(item[4][0]) for item in socket.getaddrinfo(base.hostname, 443, type=socket.SOCK_STREAM)}
            require(addresses, "connexion_impossible")
            for address in addresses:
                ip = ipaddress.ip_address(address)
                require(ip.is_global or any(ip in network for network in self.networks), "destination_non_autorisee")
            hostname = base.hostname.encode("idna").decode("ascii")
            request_headers = dict(headers or {}, Host=hostname)
            client = PinnedHTTPS(hostname, sorted(addresses)[0])
            try:
                deadline = time.monotonic() + 20
                client.request(method, quote(base.path, safe="/") + suffix, body=body, headers=request_headers)
                response = client.getresponse()
                require(200 <= response.status < 300, "connexion_ou_action_refusee")
                content = bytearray()
                while True:
                    require(time.monotonic() <= deadline, "delai_connexion_depasse")
                    chunk = response.read1(4096)
                    if not chunk:
                        break
                    content.extend(chunk)
                    require(len(content) <= 65536, "reponse_distante_invalide")
                return bytes(content)
            finally:
                client.close()
        except Denied:
            raise
        except (OSError, ValueError, http.client.HTTPException):
            raise Denied("connexion_impossible") from None


def object_response(content):
    try:
        value = json.loads(content)
        require(isinstance(value, dict), "reponse_distante_invalide")
        return value
    except (ValueError, UnicodeError):
        raise Denied("reponse_distante_invalide") from None
