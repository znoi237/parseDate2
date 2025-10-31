"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from signal_engine import aggregate_signal, decide_entry, _tf_score_from_pb, decide_exit
Реальная логика вынесена в пакет signal_pkg.
"""
from signal_pkg.agg import aggregate_signal, _tf_score_from_pb  # noqa: F401
from signal_pkg.decisions import decide_entry, decide_exit  # noqa: F401