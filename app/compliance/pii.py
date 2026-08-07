import re

# 可复用的个人信息（PII）脱敏工具。
# 输入侧（用户消息进入 LLM/记忆/日志之前）和输出侧（ComplianceAgent 审查回复）
# 共用同一套规则，保证前后端脱敏口径一致。

# 手机号：保留前 3 后 4，中间打码
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
# 身份证：18 位（17 位数字 + 校验位为数字或 X），保留前 6 后 4
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
# 银行卡：16-19 位连续数字，只保留后 4
_BANK_CARD_RE = re.compile(r"(?<!\d)\d{12,15}(\d{4})(?!\d)")
# 邮箱：保留首字符与域名
_EMAIL_RE = re.compile(r"([A-Za-z0-9])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def mask_phone(text: str) -> str:
    return _PHONE_RE.sub(r"\1****\2", text)


def mask_id_card(text: str) -> str:
    return _ID_CARD_RE.sub(r"\1********\2", text)


def mask_bank_card(text: str) -> str:
    return _BANK_CARD_RE.sub(r"****\1", text)


def mask_email(text: str) -> str:
    return _EMAIL_RE.sub(r"\1***\2", text)


def mask_pii(text: str) -> str:
    """对文本做 PII 脱敏。

    先处理身份证（18 位），避免其被更宽松的银行卡规则误伤；
    再依次处理银行卡、手机号、邮箱。手机号（11 位）短于银行卡最小长度，
    不会被银行卡规则匹配。
    """
    if not text:
        return text

    text = mask_id_card(text)
    text = mask_bank_card(text)
    text = mask_phone(text)
    text = mask_email(text)
    return text
