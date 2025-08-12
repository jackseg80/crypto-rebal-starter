import os
from rq import Connection, Worker
from redis import Redis

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
conn = Redis.from_url(redis_url)

if __name__ == "__main__":
    with Connection(conn):
        w = Worker(['default'])
        print("Worker RQ démarré sur", redis_url)
        w.work(with_scheduler=True)
