import logging

logger = logging.getLogger("codifylive")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s |X| %(levelname)s |X| %(name)s |X| %(message)s",
)
