import logging
import sys

from adapters.llm import OllamaAdapter
from models import SiemAlertState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("soc_agent.integration_test")


def main() -> None:
    logger.info("Starting real-world integration test for OllamaAdapter...")

    # Define a clean, standalone, realistic cyber event state for integration testing
    real_world_state: SiemAlertState = {
        "raw_alert": {
            "alert_id": "ALERT-404-BRUTE",
            "signature": "Multiple Failed RDP Login Attempts",
            "source_ip": "198.51.100.42",
            "target_host": "PROD-SQL-01",
            "user_targeted": "Administrator",
        },
        "correlated_logs": [
            {
                "timestamp": "2026-09-10T14:30:01Z",
                "event_id": 4625,
                "status": "Failure",
                "reason": "Unknown username or bad password",
            },
            {
                "timestamp": "2026-09-10T14:30:03Z",
                "event_id": 4625,
                "status": "Failure",
                "reason": "Unknown username or bad password",
            },
            {
                "timestamp": "2026-09-10T14:30:05Z",
                "event_id": 4624,
                "status": "Success",
                "reason": "Successful Logon after multiple failures",
            },
        ],
        "analysis": None,
        "metadata": {},
    }

    try:
        # Initialize the adapter with the exact model found by check_infra.py
        adapter = OllamaAdapter(
            model_name="llama3.1:latest", base_url="http://localhost:11434"
        )
        logger.info("OllamaAdapter successfully initialized with temperature 0.0.")

        logger.info(
            "Invoking LLM analysis. This might take a few seconds on the first run..."
        )
        analysis_result = adapter.analyze_event(real_world_state)

        # Display structured results if everything passed validation
        logger.info("--- ANALYSIS RESULTS RECEIVED AND VALIDATED ---")
        print(f"Is Threat Detected? : {analysis_result.is_threat}")
        print(f"Revised Severity    : {analysis_result.revised_severity}")
        print(f"Suggested Action    : {analysis_result.suggested_action}")
        print(f"Justification       : {analysis_result.justification}")

        print("\n--- MITRE ATT&CK CORRELATIONS ---")
        if not analysis_result.mitre_correlations:
            print("No MITRE technics correlated.")
        for correlation in analysis_result.mitre_correlations:
            print(
                f"- [{correlation.technic_id}] {correlation.technic_name} "
                f"(Tactic: {correlation.tactic}) | Confidence: {correlation.confidence_score}/5"
            )

    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
