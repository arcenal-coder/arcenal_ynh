from arcenal_connectors.edge import register as register_connector


def register(ctx):
    register_connector(ctx, "dolibarr")
