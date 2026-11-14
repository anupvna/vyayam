from app.auth.ratelimit import FailureLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_then_unblocks_after_window() -> None:
    clock = FakeClock()
    lim = FailureLimiter(max_failures=3, window_seconds=60, clock=clock)

    for _ in range(3):
        assert lim.retry_after("k") is None
        lim.record_failure("k")
    assert lim.retry_after("k") == 60

    clock.now += 59
    assert lim.retry_after("k") == 1
    clock.now += 1
    assert lim.retry_after("k") is None  # oldest failure aged out


def test_window_slides() -> None:
    clock = FakeClock()
    lim = FailureLimiter(max_failures=2, window_seconds=60, clock=clock)
    lim.record_failure("k")
    clock.now += 50
    lim.record_failure("k")
    assert lim.retry_after("k") == 10  # unblocks when the first failure expires
    clock.now += 10
    assert lim.retry_after("k") is None


def test_keys_are_independent_and_reset_clears() -> None:
    lim = FailureLimiter(max_failures=1, window_seconds=60, clock=FakeClock())
    lim.record_failure("a")
    assert lim.retry_after("a") is not None
    assert lim.retry_after("b") is None
    lim.reset("a")
    assert lim.retry_after("a") is None
