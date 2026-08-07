from app.compliance.pii import mask_pii


def test_mask_phone_keeps_prefix_and_suffix():
    assert mask_pii("我的手机号是 13812345678") == "我的手机号是 138****5678"


def test_mask_id_card_18_digits():
    assert mask_pii("身份证 110101199003074321") == "身份证 110101********4321"


def test_mask_bank_card():
    assert mask_pii("卡号 6222021234567890123") == "卡号 ****0123"


def test_mask_email():
    assert mask_pii("邮箱 alice@example.com") == "邮箱 a***@example.com"


def test_mask_multiple_pii_in_one_text():
    masked = mask_pii("联系 13800001111，邮箱 bob@test.cn")
    assert "13800001111" not in masked
    assert "bob@test.cn" not in masked
    assert "138****1111" in masked
    assert "b***@test.cn" in masked


def test_non_pii_text_unchanged():
    # 订单号 A10001、金额 100 等非 PII 内容不应被误伤
    text = "订单 A10001 金额 100 元，预计 3 天到货"
    assert mask_pii(text) == text


def test_empty_text():
    assert mask_pii("") == ""
