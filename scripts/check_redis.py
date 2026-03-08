"""Quick script to verify connectivity to the Redis instance."""

import sys
import redis

REDIS_URL = "redis://localhost:6379/0"


def main() -> None:
    print(f"Connecting to Redis at {REDIS_URL} ...")
    try:
        r = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=5)
        pong = r.ping()
        if pong:
            print("✅  PONG received — Redis is reachable!")

        info = r.info(section="server")
        print(f"    Redis version : {info.get('redis_version', 'unknown')}")
        print(f"    Uptime (sec)  : {info.get('uptime_in_seconds', 'unknown')}")
        print(f"    TCP port      : {info.get('tcp_port', 'unknown')}")

        db_info = r.info(section="keyspace")
        if db_info:
            print("    Databases     :")
            for db, stats in db_info.items():
                print(f"      {db}: {stats}")
        else:
            print("    Databases     : (empty — no keys yet)")

    except redis.ConnectionError as exc:
        print(f"❌  Connection failed: {exc}")
        sys.exit(1)
    except redis.TimeoutError:
        print("❌  Connection timed out after 5 seconds.")
        sys.exit(1)
    except Exception as exc:
        print(f"❌  Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
