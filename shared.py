import time


class Shared:

    app_start_time = time.time()

    has_imported_decoder: bool = False

    @staticmethod
    def uptime() -> float:
        return time.time() - Shared.app_start_time