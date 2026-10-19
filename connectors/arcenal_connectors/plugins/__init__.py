"""Registre fermé des plugins centraux livrés et autorisés."""

from .dolibarr import Dolibarr
from .nextcloud import Nextcloud
from .yunohost import YunoHost


def registry(network, helper):
    return {"dolibarr": Dolibarr(network), "nextcloud": Nextcloud(network), "yunohost": YunoHost(helper)}
