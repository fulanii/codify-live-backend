import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s |X| %(levelname)s |X| %(name)s |X| %(message)s",
)


logger = logging.getLogger("codifylive")
