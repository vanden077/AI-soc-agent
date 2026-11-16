class ThreatCatalog:
    """
    Registry holding cyber detection guidelines mapped to MITRE ATT&CK Enterprise v19.2 platforms.
    Embeds canonical MITRE taxonomy terms to anchor downstream vector similarity search.
    """

    _GUIDELINES: dict[str, str] = {
        "windows": (
            "Focus on MITRE mechanisms: Command and Scripting Interpreter (PowerShell, CMD, WMI, Mshta), "
            "Process Injection, OS Credential Dumping (LSASS), Registry Run Keys persistence, "
            "Impair Defenses (disabling AV/EDR), and Scheduled Task creation."
        ),
        "macos": (
            "Focus on MITRE mechanisms: Unix Shell or AppleScript execution, Launch Agent or Launch Daemon "
            "persistence, TCC/Gatekeeper defense evasion, Keychain credential dumping, "
            "and malicious configuration profile installation."
        ),
        "linux": (
            "Focus on MITRE mechanisms: Unix Shell execution, Abuse Elevation Control Mechanism (sudo/SUID), "
            "Account Manipulation (/etc/passwd, /etc/shadow, SSH authorized_keys), Cron scheduled jobs, "
            "Web Shell deployment, and Indicator Removal on Host."
        ),
        "pre": (
            "Focus on MITRE mechanisms: Active Scanning, Gather Victim Identity or Org Information, "
            "Phishing for Information, Acquire Infrastructure (domains/certificates), "
            "and Compromise Accounts prior to initial access."
        ),
        "office suite": (
            "Focus on MITRE mechanisms: Email Collection via Email Forwarding Rule (inbox rules), "
            "Email Hiding Rules (deleting/moving messages), Steal Application Access Token (OAuth consent abuse), "
            "Malicious Office Macros/Add-ins, and Exfiltration Over Web Service."
        ),
        "identity provider": (
            "Focus on MITRE mechanisms: Steal Application Access Token, Use Alternate Authentication Material "
            "(OAuth tokens, session cookies), Modify Authentication Process, Multi-Factor Authentication "
            "Request Generation or Interception, and Valid Accounts directory manipulation."
        ),
        "saas": (
            "Focus on MITRE mechanisms: Steal Application Access Token (malicious OAuth application consent "
            "with high-privilege Mail/Directory permissions), Email Collection via Email Forwarding Rule "
            "(Exchange inbox rules), Email Hiding Rules, Valid Accounts impossible travel, "
            "and Exfiltration Over Web Service or Webhook."
        ),
        "iaas": (
            "Focus on MITRE mechanisms: Cloud Administration Command, Account Manipulation (IAM roles, "
            "access keys, federation), Impair Defenses (disabling CloudTrail/audit logs), "
            "Modify Cloud Compute Infrastructure, and Transfer Data to Cloud Account."
        ),
        "network devices": (
            "Focus on MITRE mechanisms: Network Boundary Bridging, Traffic Duplication or Routing Table "
            "modification, Modify System Image (firmware tampering), Valid Accounts privilege escalation, "
            "and Exfiltration Over Alternative Protocol."
        ),
        "containers": (
            "Focus on MITRE mechanisms: Escape to Host, Privileged Container execution, "
            "Deploy Container or malicious image modification, Kubernetes API/Docker socket abuse, "
            "and Container Administration Command."
        ),
        "esxi": (
            "Focus on MITRE mechanisms: Virtualization/Sandbox Evasion, Enable SSH on hypervisor, "
            "Data Encrypted for Impact (datastore ransomware), Snapshot deletion, "
            "and unauthorized VIB or hypervisor account manipulation."
        ),
    }

    @classmethod
    def get_guideline(cls, platform: str) -> str:
        """
        Retrieves the canonical MITRE guideline for a validated platform key.
        Fails fast with KeyError if an unvalidated platform string is passed.
        """
        return cls._GUIDELINES[platform]
