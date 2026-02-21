from fastapi import FastAPI, Body
from datetime import datetime, timedelta, time
import pymysql

app = FastAPI()

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="password",
        database="meetingroom",
        cursorclass=pymysql.cursors.DictCursor
    )

def convert_to_time(value):
    # TIME型（datetime.time）
    if isinstance(value, time):
        return value

    # 文字列（"09:00:00"）
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M:%S").time()

    # timedelta（MySQL TIME がこうなる場合あり）
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return time(hours, minutes)

    raise ValueError("Unsupported time format")

def generate_times(start_time, end_time):
    start_time = convert_to_time(start_time)
    end_time = convert_to_time(end_time)

    times = []

    current = datetime.combine(datetime.today(), start_time)
    end = datetime.combine(datetime.today(), end_time)

    while current <= end:
        times.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)

    return times


@app.get("/init-data")
def get_init_data():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            # 部屋取得
            cursor.execute("SELECT roomId, roomName FROM m_meetingroom")
            rooms = cursor.fetchall()

            # 営業時間取得
            cursor.execute("SELECT start_time, end_time FROM m_reservation_time LIMIT 1")
            time_range = cursor.fetchone()

        times = generate_times(
            time_range["start_time"],
            time_range["end_time"]
        )

        return {
            "meetingRooms": [
                {
                    "roomId": str(room["roomId"]),
                    "roomName": room["roomName"]
                }
                for room in rooms
            ],
            "times": times
        }

    finally:
        connection.close()

@app.get("/reservations/get")
def get_reservations(date: str):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    A.reserveId,
                    A.roomId,
                    B.roomName,
                    A.meetingName,
                    A.date,
                    A.reserver,
                    A.start_time,
                    A.end_time
                FROM t_reservation A, m_meetingroom B
                WHERE A.date = %s
                AND A.roomId = B.roomId
                AND A.deleteFlg = 0
            """
            cursor.execute(sql, (date,))
            rows = cursor.fetchall()

        result = []

        for row in rows:
            start = datetime.strptime(str(row["start_time"]), "%H:%M:%S")
            end = datetime.strptime(str(row["end_time"]), "%H:%M:%S")

            times = []
            current = start
            while current < end:
                times.append(current.strftime("%H:%M"))
                current += timedelta(minutes=30)

            result.append({
                "reservationId": row["reserveId"],
                "roomId": row["roomId"],
                "roomName": row["roomName"],
                "meetingName": row["meetingName"],
                "date": row["date"].strftime("%Y-%m-%d"),
                "reserver": row["reserver"],
                "start_time": convert_to_time(row["start_time"]).strftime("%H:%M"),
                "end_time": convert_to_time(row["end_time"]).strftime("%H:%M"),
                "time": times
            })

        return result

    finally:
        connection.close()

@app.post("/reservations/add")
def test_insert_reservation(payload: dict = Body(...)):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO t_reservation (
                    roomId,
                    meetingName,
                    date,
                    reserver,
                    start_time,
                    end_time
                ) VALUES (
                   %s, %s, %s, %s, %s, %s
                )
            """
            cursor.execute(sql,
                (
                    payload["roomId"],
                    payload["meetingName"],
                    payload["date"],
                    payload["reserver"],
                    payload["start_time"],
                    payload["end_time"],
                )
            )

        connection.commit()

    finally:
        connection.close()

@app.delete("/reservations/delete/{reserveId}")
def test_delete_reservation(reserveId: int):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                UPDATE
                    meetingroom.t_reservation
                SET deleteFlg = 1,
                updateTime = NOW()
                WHERE reserveId = %s
            """ 
            cursor.execute(sql, (reserveId))

        connection.commit()

    finally:
        connection.close()