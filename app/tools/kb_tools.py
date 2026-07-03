from pathlib import Path



REFUND_POLICY_FILE = Path("data/knowledge_base/refund_policy.md")


def load_refund_policy(file_path: Path = REFUND_POLICY_FILE) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""