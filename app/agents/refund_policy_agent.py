from app.tools.kb_tools import load_refund_policy



class RefundPolicyAgent:
    def handle(self, message: str) -> str:
        policy_text = load_refund_policy()
        
        if not policy_text:
            return "暂时没有找到退款政策信息，请稍后转人工客服处理。"

        if self._contains_any(message, ["几天", "多久", "时效", "什么时候到账", "多久到账"]):
            return "退款会在仓库验收通过后 1-3 个工作日内原路退回。"

        if self._contains_any(message, ["不能退", "不支持", "哪些不能", "什么不能"]):
            return "生鲜、定制商品、虚拟商品、已拆封影响二次销售的商品，通常不支持无理由退货。"

        if self._contains_any(message, ["质量", "坏了", "破损", "瑕疵"]):
            return "如果商品存在质量问题，你可以申请售后，平台会根据检测结果处理退货、换货或维修。"

        return (
            "普通商品支持签收后 7 天内无理由退货；"
            "商品需要保持完好，不影响二次销售，并包含完整配件、包装和发票；"
            "退款会在仓库验收通过后 1-3 个工作日内原路退回。"
        )



    def _contains_any(self, message: str, keywords: list[str]) -> bool:
        return any(keyword in message for keyword in keywords)
