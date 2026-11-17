import logging
from collections.abc import Callable
from unittest.mock import MagicMock

from src.api.schemas import AvailablePlatforms
from src.soc_agent.agent import SocAgent
from src.soc_agent.schemas import GuardLayerVerdict, MitreTechnique
from src.workflow.workflow import SocAgentWorkflow


async def test_execute_skips_knn_when_verdict_is_benign(
    mocker,
    workflow_deps: tuple[MagicMock, MagicMock, MagicMock],
    caplog,
) -> None:
    """Short-circuit: benign verdict skips vectorization and similarity search."""
    with caplog.at_level(logging.INFO):
        llm_engine, embedding_engine, vector_engine = workflow_deps
        mocker.patch.object(
            SocAgent,
            "analyze_ingress_flow",
            return_value=GuardLayerVerdict(
                is_threat=False,
                confidence_score=0.95,
                semantic_summary=None,
            ),
        )

        workflow = SocAgentWorkflow(
            llm_engine=llm_engine,
            embedding_engine=embedding_engine,
            vector_engine=vector_engine,
        )
        report = await workflow.execute(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="Routine Windows Update service check.",
        )

        assert report.platform == AvailablePlatforms.WINDOWS
        assert report.is_threat is False
        assert report.confidence_score == 0.95
        assert report.semantic_summary is None
        assert report.matched_techniques == []
        embedding_engine.embed_query.assert_not_called()
        vector_engine.similarity_search.assert_not_called()
        assert "Benign activity confirmed for 'windows'. Skipping KNN." in caplog.text


async def test_execute_skips_knn_when_threat_has_no_semantic_summary(
    mocker,
    workflow_deps: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Short-circuit: missing semantic_summary forces safe benign fallback even if is_threat=True."""
    llm_engine, embedding_engine, vector_engine = workflow_deps
    mocker.patch.object(
        SocAgent,
        "analyze_ingress_flow",
        return_value=GuardLayerVerdict(
            is_threat=True,
            confidence_score=0.55,
            semantic_summary=None,
        ),
    )

    workflow = SocAgentWorkflow(
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_engine,
    )
    report = await workflow.execute(
        platform=AvailablePlatforms.LINUX,
        raw_log="Ambiguous cron entry",
    )

    assert report.is_threat is False
    assert report.semantic_summary is None
    assert report.matched_techniques == []
    embedding_engine.embed_query.assert_not_called()
    vector_engine.similarity_search.assert_not_called()


async def test_execute_runs_full_knn_pipeline_and_filters_clustered_matches(
    mocker,
    workflow_deps: tuple[MagicMock, MagicMock, MagicMock],
    mitre_technique_factory: Callable[[str, float], MitreTechnique],
    caplog,
) -> None:
    """Nominal threat: embeds summary, queries KNN with platform filter, sorts DESC, and keeps delta cluster."""
    with caplog.at_level(logging.INFO):
        llm_engine, embedding_engine, vector_engine = workflow_deps
        summary = "PowerShell encoded command invoking LSASS memory dump."
        mocker.patch.object(
            SocAgent,
            "analyze_ingress_flow",
            return_value=GuardLayerVerdict(
                is_threat=True,
                confidence_score=0.91,
                semantic_summary=summary,
            ),
        )
        embedding_engine.embed_query.return_value = [0.1, 0.2, 0.3]
        vector_engine.similarity_search.return_value = [
            mitre_technique_factory("T1059.001", 0.87),
            mitre_technique_factory("T1082", 0.85),
            mitre_technique_factory("T1003.001", 0.90),
        ]

        workflow = SocAgentWorkflow(
            llm_engine=llm_engine,
            embedding_engine=embedding_engine,
            vector_engine=vector_engine,
            knn_limit=4,
            min_similarity=0.45,
            similarity_delta=0.035,
        )
        report = await workflow.execute(
            platform=AvailablePlatforms.WINDOWS,
            raw_log="powershell.exe -enc ...",
        )

        embedding_engine.embed_query.assert_called_once_with(text=summary)
        vector_engine.similarity_search.assert_called_once_with(
            query_vector=[0.1, 0.2, 0.3],
            response_model=MitreTechnique,
            filter_expression={"platforms": "windows"},
            limit=4,
        )
        assert report.is_threat is True
        assert report.confidence_score == 0.91
        assert report.semantic_summary == summary
        assert [t.mitre_id for t in report.matched_techniques] == [
            "T1003.001",
            "T1059.001",
        ]
        assert (
            "Kept 2/3 MITRE techniques (top_score=0.900, cutoff=0.865)." in caplog.text
        )


async def test_execute_returns_empty_techniques_when_knn_returns_no_matches(
    mocker,
    workflow_deps: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Edge case: empty vector search result returns ThreatAnalysis with empty matched_techniques."""
    llm_engine, embedding_engine, vector_engine = workflow_deps
    mocker.patch.object(
        SocAgent,
        "analyze_ingress_flow",
        return_value=GuardLayerVerdict(
            is_threat=True,
            confidence_score=0.88,
            semantic_summary="Novel privilege escalation vector.",
        ),
    )
    embedding_engine.embed_query.return_value = [0.4, 0.5]
    vector_engine.similarity_search.return_value = []

    workflow = SocAgentWorkflow(
        llm_engine=llm_engine,
        embedding_engine=embedding_engine,
        vector_engine=vector_engine,
    )
    report = await workflow.execute(
        platform=AvailablePlatforms.MACOS,
        raw_log="sudo dylib hijack",
    )

    assert report.is_threat is True
    assert report.matched_techniques == []


async def test_execute_discards_all_matches_below_min_similarity_floor(
    mocker,
    workflow_deps: tuple[MagicMock, MagicMock, MagicMock],
    mitre_technique_factory: Callable[[str, float], MitreTechnique],
    caplog,
) -> None:
    """Edge case: discards weak matches and logs warning when top score < min_similarity."""
    with caplog.at_level(logging.WARNING):
        llm_engine, embedding_engine, vector_engine = workflow_deps
        mocker.patch.object(
            SocAgent,
            "analyze_ingress_flow",
            return_value=GuardLayerVerdict(
                is_threat=True,
                confidence_score=0.72,
                semantic_summary="Anomalous outbound connection.",
            ),
        )
        embedding_engine.embed_query.return_value = [0.9, 0.1]
        vector_engine.similarity_search.return_value = [
            mitre_technique_factory("T1071", 0.44),
            mitre_technique_factory("T1041", 0.30),
        ]

        workflow = SocAgentWorkflow(
            llm_engine=llm_engine,
            embedding_engine=embedding_engine,
            vector_engine=vector_engine,
            min_similarity=0.45,
        )
        report = await workflow.execute(
            platform=AvailablePlatforms.SAAS,
            raw_log="Unusual webhook egress",
        )

        assert report.is_threat is True
        assert report.matched_techniques == []
        assert (
            "Top MITRE match similarity (0.440) below floor threshold (0.45)."
            in caplog.text
        )
