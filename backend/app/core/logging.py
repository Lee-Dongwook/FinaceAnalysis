import logging
from os import getenv


def configure_logging() -> None:
    logging.basicConfig(
        level=getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
