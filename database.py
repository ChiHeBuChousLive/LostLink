import sqlite3
from pathlib import Path


# Main database included in the GitHub repository.
DB_PATH = Path(__file__).resolve().parent / "data" / "lostlink.db"


def get_connection(db_path=None):
    """
    Create a SQLite connection.

    Args:
        db_path: Optional database file path.

    Returns:
        sqlite3.Connection: Database connection.
    """
    path = Path(db_path) if db_path else DB_PATH

    # Create the parent folder if necessary.
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    return connection


def init_db(db_path=None):
    """
    Create the items table.

    Args:
        db_path: Optional database file path.

    Returns:
        None
    """
    query = """
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        report_type TEXT NOT NULL
            CHECK (report_type IN ('lost', 'found')),

        raw_description TEXT NOT NULL,
        item_category TEXT NOT NULL,
        main_color TEXT,
        general_location TEXT NOT NULL,
        event_date TEXT,

        detailed_location TEXT,
        feature_description TEXT,
        hidden_feature TEXT,

        status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'matched', 'closed')),

        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """

    with get_connection(db_path) as connection:
        connection.execute(query)


def get_all_items(db_path=None):
    """
    Return all records in the database.

    Args:
        db_path: Optional database file path.

    Returns:
        list: All records as dictionaries.
    """
    query = """
    SELECT *
    FROM items
    ORDER BY created_at DESC, id DESC;
    """

    with get_connection(db_path) as connection:
        rows = connection.execute(query).fetchall()

    return [dict(row) for row in rows]


def insert_item(item, db_path=None):
    """
    Insert a lost or found report.

    Args:
        item: Dictionary containing the report information.

            Required fields:
                report_type
                raw_description
                item_category
                general_location

            Optional fields:
                main_color
                event_date
                detailed_location
                feature_description
                hidden_feature
                status (defaults to "open")

        db_path: Optional database file path.

    Returns:
        int: ID of the inserted record.
    """
    required_fields = (
        "report_type",
        "raw_description",
        "item_category",
        "general_location",
    )

    # Check required fields.
    for field in required_fields:
        if not item.get(field):
            raise ValueError(
                f"Missing required field: {field}"
            )

    if item["report_type"] not in ("lost", "found"):
        raise ValueError(
            "report_type must be 'lost' or 'found'"
        )

    status = item.get("status", "open")

    if status not in ("open", "matched", "closed"):
        raise ValueError(
            "status must be 'open', 'matched', or 'closed'"
        )

    query = """
    INSERT INTO items (
        report_type,
        raw_description,
        item_category,
        main_color,
        general_location,
        event_date,
        detailed_location,
        feature_description,
        hidden_feature,
        status
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    values = (
        item["report_type"],
        item["raw_description"],
        item["item_category"],
        item.get("main_color"),
        item["general_location"],
        item.get("event_date"),
        item.get("detailed_location"),
        item.get("feature_description"),
        item.get("hidden_feature"),
        status,
    )

    with get_connection(db_path) as connection:
        cursor = connection.execute(query, values)
        return cursor.lastrowid


def get_candidates(item, limit=10, db_path=None):
    """
    Find possible matching reports.

    Args:
        item: Dictionary containing the report information.
        limit: Maximum number of candidates to return.
        db_path: Optional database file path.

    Returns:
        list: Matching database records.
    """
    report_type = item.get("report_type")
    category = item.get("item_category")
    location = item.get("general_location")
    color = item.get("main_color")
    event_date = item.get("event_date")

    if report_type not in ("lost", "found"):
        raise ValueError(
            "report_type must be 'lost' or 'found'"
        )

    if not category:
        raise ValueError(
            "Missing required field: item_category"
        )

    if not location:
        raise ValueError(
            "Missing required field: general_location"
        )

    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(
            "limit must be a positive integer"
        )

    # Lost reports search found reports, and vice versa.
    opposite_type = (
        "found" if report_type == "lost" else "lost"
    )

    query = """
    SELECT *
    FROM items
    WHERE report_type = ?
      AND status = 'open'
      AND item_category = ?
      AND general_location = ?

      AND (
          ? IS NULL
          OR ? = 'unknown'
          OR main_color IS NULL
          OR main_color = 'unknown'
          OR main_color = ?
      )

      AND (
          ? IS NULL
          OR event_date IS NULL
          OR ABS(
              julianday(event_date) - julianday(?)
          ) <= 7
      )

    ORDER BY created_at DESC, id DESC
    LIMIT ?;
    """

    parameters = (
        opposite_type,
        category,
        location,
        color,
        color,
        color,
        event_date,
        event_date,
        limit,
    )

    with get_connection(db_path) as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    # Convert SQLite rows to normal dictionaries.
    return [dict(row) for row in rows]


def update_status(item_id, status, db_path=None):
    """
    Update the status of a report.

    Args:
        item_id: ID of the report.
        status: New status: open, matched, or closed.
        db_path: Optional database file path.

    Returns:
        bool: True if the report was updated, otherwise False.
    """
    if status not in ("open", "matched", "closed"):
        raise ValueError(
            "status must be 'open', 'matched', or 'closed'"
        )

    query = """
    UPDATE items
    SET
        status = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?;
    """

    with get_connection(db_path) as connection:
        cursor = connection.execute(
            query,
            (status, item_id),
        )

        return cursor.rowcount > 0


# Initialize the database when this file is run directly.
if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")