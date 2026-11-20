from fastapi.openapi.models import Example

THREAT_ANALYZER_EXAMPLES: dict[str, Example] = {
    "hostile_oauth_inbox_rule": Example(
        summary="[Hostile] SaaS — Malicious OAuth Consent & Inbox Exfiltration",
        description="Tor exit node IP granting high-privilege Entra ID permissions followed by an Exchange forwarding/deletion rule.",
        value={
            "platform": "saas",
            "raw_log": (
                "Timestamp: 2026-11-10T11:14:22Z | EventSource: MicrosoftEntraID | "
                "EventID: ConsentToApplication | Actor: attacker_compromised_user@company.com | "
                "IPAddress: 185.220.101.5 (Tor Exit Node) | Operation: Consent to application | "
                "AppDisplayName: 'Enterprise IT Admin Assistant' | "
                "PermissionsRequested: ['User.Read', 'Mail.ReadWrite', 'Mail.Send', 'RoleManagement.ReadWrite.Directory'] | "
                "Status: Success || FollowUpEvent: ExchangeOnline | Operation: New-InboxRule | "
                "RuleName: 'Extract_Invoices' | Actions: ForwardTo 'j.doe@outlook.de', DeleteMessage"
            ),
        },
    ),
    "hostile_powershell_mimikatz": Example(
        summary="[Hostile] Windows — Hidden PowerShell Credential Dumping (Mimikatz)",
        description="ExecutionPolicy Bypass with hidden window running Invoke-Mimikatz -DumpCreds.",
        value={
            "platform": "windows",
            "raw_log": (
                "EventID: 4688 | Process Name: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe | "
                'Command Line: powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Invoke-Mimikatz -DumpCreds" | '
                "User: company\\compromised_admin"
            ),
        },
    ),
    "hostile_exchange_forwarding": Example(
        summary="[Hostile] Office Suite — External Invoice Forwarding Rule",
        description="Exchange Online inbox rule automatically exfiltrating invoice emails to an external Gmail address.",
        value={
            "platform": "office suite",
            "raw_log": (
                "Timestamp: 2026-11-10T14:32:00Z | Source: ExchangeOnline | Operation: New-InboxRule | "
                "RuleName: 'Forward invoices' | "
                "Parameters: { SubjectContainsWords: ['facture', 'invoice'], ForwardTo: 'exfil_data_collector@gmail.com' } | "
                "Status: Success"
            ),
        },
    ),
    "benign_windows_notepad": Example(
        summary="[Benign] Windows — Standard User Launching Notepad",
        description="Routine interactive user opening a local text document via Windows Explorer.",
        value={
            "platform": "windows",
            "raw_log": (
                "EventID: 4688 | New Process Name: C:\\Windows\\System32\\notepad.exe | "
                "Parent Process Name: C:\\Windows\\explorer.exe | "
                "Process Command Line: notepad.exe C:\\Users\\jdoe\\Documents\\notes.txt | "
                "Creator User Name: company\\jdoe"
            ),
        },
    ),
    "benign_windows_google_update": Example(
        summary="[Benign] Windows — Scheduled GoogleUpdate Background Task",
        description="Expected SYSTEM-level scheduled updater execution.",
        value={
            "platform": "windows",
            "raw_log": (
                "EventID: 4688 | Process Name: C:\\Program Files\\Google\\Update\\GoogleUpdate.exe | "
                'Command Line: "C:\\Program Files\\Google\\Update\\GoogleUpdate.exe" /ua /installsource scheduler | '
                "User: NT AUTHORITY\\SYSTEM"
            ),
        },
    ),
    "benign_entra_ad_connect": Example(
        summary="[Benign] SaaS — Automated Azure AD Connect Directory Sync",
        description="Routine automated directory synchronization updating user attributes.",
        value={
            "platform": "saas",
            "raw_log": (
                "Timestamp: 2026-11-10T08:00:15Z | Source: MicrosoftEntraID | Operation: Update user | "
                "Actor: AzureADConnect@://onmicrosoft.com | Target: Multiple Users | "
                "ModifiedProperties: ['AlternativeSignInId', 'AssignedPlans'] | Status: Success"
            ),
        },
    ),
}
