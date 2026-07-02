import json
from pathlib import Path


ORDERS_FILE = Path('data/mock_orders.json')


def load_orders(file_path: Path = ORDERS_FILE) -> list[dict]:
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'错误，找不到文件')
        return []


def get_latest_order_by_user(user_id: str) -> dict | None:
    orders = load_orders()

    for order in orders:
        if order.get('user_id') == user_id:
            return order
        
    return None


def get_order_by_id(user_id: str, order_id: str) -> dict | None:
    # 根据订单号查询
    orders = load_orders()

    for order in orders:
        if order.get("user_id") == user_id and order.get("order_id") == order_id:
            return order
    
    return None
