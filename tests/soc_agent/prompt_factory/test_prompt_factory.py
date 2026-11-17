from src.soc_agent.prompt_factory.prompt_factory import PromptFactory
from src.soc_agent.threat_catalog import ThreatCatalog


def test_build_guard_layer_prompt_injects_platform_guideline_and_raw_log(
    mocker,
) -> None:
    """Verify build_guard_layer_prompt interpolates platform, guideline, and raw log into role tuples."""
    spy_guideline = mocker.patch.object(
        ThreatCatalog,
        "get_guideline",
        return_value="Focus on Sysmon Event ID 1 and PowerShell script blocks.",
    )

    messages = PromptFactory.build_guard_layer_prompt(
        platform="windows",
        raw_log="EventID=4688 NewProcessName=powershell.exe",
    )

    spy_guideline.assert_called_once_with("windows")
    assert len(messages) == 2

    system_role, system_content = messages[0]
    user_role, user_content = messages[1]

    assert system_role == "system"
    assert "- Platform: windows" in system_content
    assert (
        "Your summary must strictly reflect windows specific mechanisms."
        in system_content
    )
    assert (
        "- Platform Detection Guidelines: Focus on Sysmon Event ID 1 and PowerShell script blocks."
        in system_content
    )

    assert user_role == "user"
    assert (
        user_content == "Raw Security Log:\nEventID=4688 NewProcessName=powershell.exe"
    )
