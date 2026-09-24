class MitreDownloadError(Exception):
    """Error raised when CURL call to GitHub fails"""


class MitreJsonError(Exception):
    """Error raised when MITRE attack file is not JSON formatted"""
