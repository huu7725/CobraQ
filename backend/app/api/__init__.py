"""Load the complete router only when requested, avoiding database startup on utility imports."""


def __getattr__(name):
    if name == "api_router":
        from .router import api_router
        return api_router
    raise AttributeError(name)
