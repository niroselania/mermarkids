import json
import os
import sqlite3
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "mermarkids.sqlite3"
PORT = int(os.environ.get("PORT", "80"))


def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_number INTEGER NOT NULL UNIQUE,
              date TEXT NOT NULL,
              customer TEXT NOT NULL,
              phone TEXT NOT NULL DEFAULT '',
              product TEXT NOT NULL,
              quantity REAL NOT NULL DEFAULT 0,
              unit_price REAL NOT NULL DEFAULT 0,
              total REAL NOT NULL DEFAULT 0,
              deposit REAL NOT NULL DEFAULT 0,
              account TEXT NOT NULL,
              pending REAL NOT NULL DEFAULT 0,
              paid_status TEXT NOT NULL DEFAULT 'partial',
              order_status TEXT NOT NULL DEFAULT 'PENDIENTE DE ENTREGA',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expenses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              date TEXT NOT NULL,
              concept TEXT NOT NULL,
              cash REAL NOT NULL DEFAULT 0,
              mp REAL NOT NULL DEFAULT 0,
              account TEXT NOT NULL,
              mer REAL NOT NULL DEFAULT 0,
              marian REAL NOT NULL DEFAULT 0,
              total REAL NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            """
        )


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_order(payload, existing=None):
    quantity = as_float(payload.get("quantity"))
    unit_price = as_float(payload.get("unitPrice", payload.get("unit_price")))
    total = round(quantity * unit_price, 2)
    paid_status = payload.get("paidStatus", payload.get("paid_status", "partial"))
    deposit = as_float(payload.get("deposit"))
    if paid_status == "paid":
        deposit = total
    if paid_status == "pending":
        deposit = 0
    deposit = min(max(deposit, 0), total)
    pending = round(max(total - deposit, 0), 2)
    if pending <= 0:
        paid_status = "paid"

    order_number = payload.get("orderNumber", payload.get("order_number"))
    if not order_number and existing:
        order_number = existing["order_number"]

    return {
        "order_number": int(order_number),
        "date": payload.get("date") or payload.get("orderDate") or date.today().isoformat(),
        "customer": (payload.get("customer") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "product": (payload.get("product") or "").strip(),
        "quantity": quantity,
        "unit_price": unit_price,
        "total": total,
        "deposit": deposit,
        "account": payload.get("account") or "MARIAN MP",
        "pending": pending,
        "paid_status": paid_status,
        "order_status": payload.get("orderStatus", payload.get("order_status", "PENDIENTE DE ENTREGA")),
    }


def normalize_expense(payload):
    cash = as_float(payload.get("cash"))
    mp = as_float(payload.get("mp"))
    total = round(cash + mp, 2)
    account = payload.get("account") or "MER"
    mer = total if account == "MER" else total / 2 if account == "COMPARTIDO" else 0
    marian = total if account == "MARIAN" else total / 2 if account == "COMPARTIDO" else 0
    return {
        "date": payload.get("date") or date.today().isoformat(),
        "concept": (payload.get("concept") or "").strip(),
        "cash": cash,
        "mp": mp,
        "account": account,
        "mer": round(mer, 2),
        "marian": round(marian, 2),
        "total": total,
    }


def order_row(row):
    item = dict(row)
    item["orderNumber"] = item.pop("order_number")
    item["unitPrice"] = item.pop("unit_price")
    item["paidStatus"] = item.pop("paid_status")
    item["orderStatus"] = item.pop("order_status")
    return item


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/data":
            with db() as conn:
                orders = [order_row(row) for row in conn.execute("SELECT * FROM orders ORDER BY order_number DESC")]
                expenses = [dict(row) for row in conn.execute("SELECT * FROM expenses ORDER BY id DESC")]
            self.send_json({"orders": orders, "expenses": expenses})
            return

        if parsed.path == "/api/orders/next":
            with db() as conn:
                value = conn.execute("SELECT COALESCE(MAX(order_number), 56788) + 1 AS next FROM orders").fetchone()["next"]
            self.send_json({"next": value})
            return

        if parsed.path == "/api/orders/find":
            params = parse_qs(parsed.query)
            order_number = params.get("orderNumber", [""])[0]
            with db() as conn:
                row = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
            if not row:
                self.send_json({"error": "Pedido no encontrado"}, 404)
                return
            self.send_json(order_row(row))
            return

        super().do_GET()

    def do_POST(self):
        if self.path == "/api/orders":
            payload = normalize_order(self.read_json())
            stamp = now_iso()
            try:
                with db() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO orders (
                          order_number, date, customer, phone, product, quantity, unit_price, total,
                          deposit, account, pending, paid_status, order_status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["order_number"], payload["date"], payload["customer"], payload["phone"],
                            payload["product"], payload["quantity"], payload["unit_price"], payload["total"],
                            payload["deposit"], payload["account"], payload["pending"], payload["paid_status"],
                            payload["order_status"], stamp, stamp,
                        ),
                    )
                    row = conn.execute("SELECT * FROM orders WHERE id = ?", (cur.lastrowid,)).fetchone()
                self.send_json(order_row(row), 201)
            except sqlite3.IntegrityError:
                self.send_json({"error": "Ya existe un pedido con ese numero"}, 409)
            return

        if self.path == "/api/expenses":
            payload = normalize_expense(self.read_json())
            with db() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO expenses (date, concept, cash, mp, account, mer, marian, total, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["date"], payload["concept"], payload["cash"], payload["mp"], payload["account"],
                        payload["mer"], payload["marian"], payload["total"], now_iso(),
                    ),
                )
                row = conn.execute("SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)).fetchone()
            self.send_json(dict(row), 201)
            return

        self.send_json({"error": "Ruta no encontrada"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/orders/"):
            order_id = parsed.path.rsplit("/", 1)[-1]
            with db() as conn:
                existing = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
                if not existing:
                    self.send_json({"error": "Pedido no encontrado"}, 404)
                    return
                payload = normalize_order(self.read_json(), existing)
                conn.execute(
                    """
                    UPDATE orders
                    SET order_number = ?, date = ?, customer = ?, phone = ?, product = ?, quantity = ?,
                        unit_price = ?, total = ?, deposit = ?, account = ?, pending = ?, paid_status = ?,
                        order_status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["order_number"], payload["date"], payload["customer"], payload["phone"],
                        payload["product"], payload["quantity"], payload["unit_price"], payload["total"],
                        payload["deposit"], payload["account"], payload["pending"], payload["paid_status"],
                        payload["order_status"], now_iso(), order_id,
                    ),
                )
                row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            self.send_json(order_row(row))
            return

        self.send_json({"error": "Ruta no encontrada"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/orders/"):
            order_id = parsed.path.rsplit("/", 1)[-1]
            with db() as conn:
                conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            self.send_json({"ok": True})
            return

        if parsed.path.startswith("/api/expenses/"):
            expense_id = parsed.path.rsplit("/", 1)[-1]
            with db() as conn:
                conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            self.send_json({"ok": True})
            return

        self.send_json({"error": "Ruta no encontrada"}, 404)


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MerMarKids escuchando en puerto {PORT}")
    server.serve_forever()
