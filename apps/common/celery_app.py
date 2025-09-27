import os
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
TASK_SERIALIZER = os.getenv("CELERY_TASK_SERIALIZER", "json")
RESULT_SERIALIZER = os.getenv("CELERY_RESULT_SERIALIZER", "json")
ACCEPT_CONTENT = os.getenv("CELERY_ACCEPT_CONTENT", "json").split(",")
TIMEZONE = os.getenv("TZ", "UTC")


def _build_real_celery() -> Optional[Any]:
    """
    Spróbuj zbudować prawdziwą instancję Celery.
    Jeśli pakiet `celery` nie jest zainstalowany – zwróć None.
    """
    try:
        from celery import Celery  # type: ignore
    except Exception as e:  # ImportError lub inny błąd importu
        logger.warning(
            "Celery is not installed/available. Running with a dummy Celery shim. "
            "Install `celery` and run a worker to enable async tasks. Details: %s",
            repr(e),
        )
        return None

    app = Celery(
        "trader_ai",
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=[],
    )
    app.conf.update(
        task_serializer=TASK_SERIALIZER,
        result_serializer=RESULT_SERIALIZER,
        accept_content=ACCEPT_CONTENT,
        timezone=TIMEZONE,
        enable_utc=True,
        task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower()
        in ("1", "true", "yes"),
    )
    return app


class _DummyAsyncResult:
    def __init__(self, task_id: str = "dummy"):
        self.id = task_id
        self.status = "IGNORED"
        self.result = None

    def get(self, timeout: Optional[float] = None) -> None:
        return None


class _DummyCelery:
    """
    Minimalna atrapa Celery:
    - dekorator @task (noop)
    - send_task / delay (loguje i zwraca ‚fałszywy’ wynik)
    - .conf, .app (dla kompatybilności)
    """

    class _Conf(dict):
        pass

    def __init__(self) -> None:
        self.conf = self._Conf(
            broker_url=BROKER_URL,
            result_backend=RESULT_BACKEND,
            task_serializer=TASK_SERIALIZER,
            result_serializer=RESULT_SERIALIZER,
            accept_content=ACCEPT_CONTENT,
            timezone=TIMEZONE,
            enable_utc=True,
        )

    def task(self, *t_args, **t_kwargs):
        def decorator(func: Callable):
            # zwracamy funkcję bez modyfikacji, ale dodajemy .delay
            def delay(*args, **kwargs) -> _DummyAsyncResult:
                logger.info(
                    "[Celery SHIM] Task '%s' scheduled (noop). args=%s kwargs=%s",
                    getattr(func, "__name__", "anonymous"),
                    args,
                    kwargs,
                )
                return _DummyAsyncResult()

            setattr(func, "delay", delay)
            setattr(func, "apply_async", delay)
            return func

        # użycie zarówno @app.task jak i @app.task()
        if t_args and callable(t_args[0]) and not t_kwargs:
            return decorator(t_args[0])
        return decorator

    def send_task(self, name: str, args: Optional[list] = None, kwargs: Optional[dict] = None, **_):
        logger.info(
            "[Celery SHIM] send_task called (noop): name=%s args=%s kwargs=%s",
            name,
            args,
            kwargs,
        )
        return _DummyAsyncResult()

    # zgodność z niektórymi wzorcami użycia
    def __call__(self, *args, **kwargs):
        return self


# zbuduj prawdziwego Celery jeśli jest dostępny, inaczej użyj shima
_real = _build_real_celery()
app: Any = _real if _real is not None else _DummyCelery()


# Prosty task zdrowotny (działa i w realnym Celery, i w shimie)
@app.task(name="health.ping")
def ping() -> str:
    return "pong"
