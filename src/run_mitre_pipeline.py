import logging

from src.data_pipeline.mitre_pipeline import MitrePipeline

# Configure logging for visibility during injection
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """
    Main entry point to trigger the data pipeline.
    Initializes the MitrePipeline class and streams data into Redis.
    """
    logger.info("Initializing MITRE ATT&CK data injection pipeline...")
    mitre_pipeline = MitrePipeline()
    mitre_pipeline.start_pipeline()


if __name__ == "__main__":
    main()
