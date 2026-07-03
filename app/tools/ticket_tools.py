import json
from pathlib import Path


TICKETS_FILE = Path("data/mock_tickets.json")


def load_tickets(file_path: Path = TICKETS_FILE) -> list[dict]:
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_tickets(tickets: list[dict], file_path: Path = TICKETS_FILE) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def create_ticket(user_id: str, content: str, file_path: Path = TICKETS_FILE) -> dict:
    tickets = load_tickets(file_path)
    ticket_id = f"T{10001 + len(tickets)}"

    ticket = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "content": content,
        "status": "pending",
    }

    tickets.append(ticket)
    save_tickets(tickets, file_path)

    return ticket


def get_latest_ticket_by_user(user_id: str, file_path: Path = TICKETS_FILE) -> dict | None:
    tickets = load_tickets(file_path)

    for ticket in reversed(tickets):
        if ticket.get("user_id") == user_id:
            return ticket

    return None