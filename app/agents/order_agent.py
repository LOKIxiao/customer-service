from app.tools.order_tools import get_latest_order_by_user, get_order_by_id




class OrderAgent:
    def handle(self, user_id: str, slots: dict[str, str]) -> str:
        order_id = slots.get('order_id')
        
        if order_id:
            order = get_order_by_id(user_id=user_id, order_id=order_id)
        else:
            order = get_latest_order_by_user(user_id=user_id)
        
        if order is None:
            return '没有查询到你的订单信息，请确认订单号是否正确，或稍后转人工客服处理。'

        return self._build_order_reply(order)
    

    def _build_order_reply(self, order: dict) ->str:
        order_id = order.get('order_id', '未知订单')
        status = order.get('status', 'unknown')
        item_name = order.get('item_name', '商品')
        estimated_delivery = order.get('estimated_delivery', '暂未提供预计送达时间')

        status_text = self._translate_status(status)
        return (
            f'你的订单{order_id} ({item_name}) 当前状态是{status_text},'
            f'预计送达时间为{estimated_delivery}'
        )



    def _translate_status(self, status: str) -> str:
        status_map = {
            'shipped': '已发货',
            'processing': '处理中',
            'delivered': '已送达',
            'cancelled': '已取消',
        }

        return status_map.get(status, '未知状态')
