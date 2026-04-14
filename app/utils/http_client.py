import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
LONG_IO_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
DEFAULT_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=20)

_default_client = httpx.Client(
    timeout=DEFAULT_TIMEOUT,
    limits=DEFAULT_LIMITS,
    follow_redirects=True,
)
_default_insecure_client = httpx.Client(
    timeout=DEFAULT_TIMEOUT,
    limits=DEFAULT_LIMITS,
    follow_redirects=True,
    verify=False,
)
_long_io_client = httpx.Client(
    timeout=LONG_IO_TIMEOUT,
    limits=DEFAULT_LIMITS,
    follow_redirects=True,
)
_long_io_insecure_client = httpx.Client(
    timeout=LONG_IO_TIMEOUT,
    limits=DEFAULT_LIMITS,
    follow_redirects=True,
    verify=False,
)


def _coerce_timeout(timeout):
    if timeout is None or isinstance(timeout, httpx.Timeout):
        return timeout
    if isinstance(timeout, (int, float)):
        return httpx.Timeout(timeout)
    if isinstance(timeout, tuple) and len(timeout) == 2:
        connect, read = timeout
        return httpx.Timeout(read, connect=connect)
    return timeout


def _retryable_exception(exc):
    return isinstance(exc, (
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.RemoteProtocolError,
        httpx.PoolTimeout,
    ))


def _retryable_fast_exception(exc):
    return isinstance(exc, (
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.PoolTimeout,
    ))


def _retryable_5xx(response):
    return isinstance(response, httpx.Response) and response.status_code >= 500


def _return_last_response_or_raise(retry_state: RetryCallState):
    """重试耗尽后：异常则抛出，5xx 响应则返回最后的 Response（而非 RetryError）"""
    outcome = retry_state.outcome
    assert outcome is not None
    if outcome.failed:
        raise outcome.exception()
    return outcome.result()


def _select_client(use_long_io=False, verify=True):
    if use_long_io:
        return _long_io_client if verify else _long_io_insecure_client
    return _default_client if verify else _default_insecure_client


def _send(method, url, *, use_long_io=False, **kwargs):
    verify = kwargs.pop("verify", True)
    timeout = _coerce_timeout(kwargs.pop("timeout", None))
    client = _select_client(use_long_io=use_long_io, verify=verify)
    if timeout is not None:
        kwargs["timeout"] = timeout
    return client.request(method, url, **kwargs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=10) + wait_random(0, 0.5),
    retry=retry_if_exception(_retryable_exception) | retry_if_result(_retryable_5xx),
    retry_error_callback=_return_last_response_or_raise,
    reraise=False,
)
def http_request(method, url, **kwargs):
    return _send(method, url, **kwargs)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.25, min=0.25, max=2) + wait_random(0, 0.25),
    retry=retry_if_exception(_retryable_fast_exception),
    reraise=True,
)
def http_request_fast(method, url, **kwargs):
    return _send(method, url, **kwargs)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 0.5),
    retry=retry_if_exception(_retryable_exception) | retry_if_result(_retryable_5xx),
    retry_error_callback=_return_last_response_or_raise,
    reraise=False,
)
def http_request_long(method, url, **kwargs):
    return _send(method, url, use_long_io=True, **kwargs)


def get(url, **kwargs):
    return http_request("GET", url, **kwargs)


def post(url, **kwargs):
    return http_request("POST", url, **kwargs)
