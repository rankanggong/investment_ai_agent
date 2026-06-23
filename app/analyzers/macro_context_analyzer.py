from app.models.analysis import MacroContext, PriceSignal


def analyze_macro_context(signals: dict[str, PriceSignal]) -> MacroContext:
    rates_context = _rates_context(signals)
    usd_context = _usd_context(signals)
    credit_context = _credit_context(signals)
    gold_context = _gold_context(signals)
    overall_regime = _overall_regime(
        signals, rates_context, usd_context, credit_context
    )
    notes = _notes(rates_context, usd_context, credit_context, gold_context)

    return MacroContext(
        rates_context=rates_context,
        usd_context=usd_context,
        credit_context=credit_context,
        gold_context=gold_context,
        overall_regime=overall_regime,
        notes=notes,
    )


def _rates_context(signals: dict[str, PriceSignal]) -> str:
    tlt = _return_5d(signals, "TLT")
    if tlt is None:
        return "unknown"
    if tlt > 0.015:
        return "duration_supported"
    if tlt < -0.015:
        return "rates_pressure"
    return "mixed"


def _usd_context(signals: dict[str, PriceSignal]) -> str:
    uup = _return_5d(signals, "UUP")
    if uup is None:
        return "unknown"
    if uup > 0.01:
        return "usd_strengthening"
    if uup < -0.01:
        return "usd_weakening"
    return "mixed"


def _credit_context(signals: dict[str, PriceSignal]) -> str:
    hyg = _return_5d(signals, "HYG")
    lqd = _return_5d(signals, "LQD")
    if hyg is None:
        return "unknown"

    lqd_value = lqd if lqd is not None else 0.0
    if hyg > 0.01 and hyg >= lqd_value:
        return "risk_appetite_supportive"
    if hyg < -0.01:
        return "credit_stress"
    return "mixed"


def _gold_context(signals: dict[str, PriceSignal]) -> str:
    gld = _return_5d(signals, "GLD")
    usd = _return_5d(signals, "UUP")
    if gld is None:
        return "unknown"
    if gld > 0.01 and (usd is None or usd <= 0.005):
        return "gold_supported"
    if gld < -0.01 or (usd is not None and usd > 0.01):
        return "gold_pressure"
    return "mixed"


def _overall_regime(
    signals: dict[str, PriceSignal],
    rates_context: str,
    usd_context: str,
    credit_context: str,
) -> str:
    spy = _return_5d(signals, "SPY")
    if spy is None:
        return "unknown"

    supportive = [
        rates_context == "duration_supported",
        usd_context == "usd_weakening",
        credit_context == "risk_appetite_supportive",
    ]
    pressure = [
        rates_context == "rates_pressure",
        usd_context == "usd_strengthening",
        credit_context == "credit_stress",
    ]

    if spy > 0.01 and sum(supportive) >= 2:
        return "risk_on_with_macro_support"
    if spy < -0.01 and sum(pressure) >= 2:
        return "risk_off_with_macro_pressure"
    return "mixed"


def _notes(
    rates_context: str,
    usd_context: str,
    credit_context: str,
    gold_context: str,
) -> list[str]:
    note_by_context = {
        "duration_supported": "Long-duration proxies are firm, suggesting lower-rate support.",
        "rates_pressure": "Long-duration proxies are weak, suggesting rate pressure.",
        "usd_weakening": "A weaker USD proxy is supportive for global risk assets and gold.",
        "usd_strengthening": "A stronger USD proxy can pressure risk assets and gold.",
        "risk_appetite_supportive": "High-yield credit is firm versus investment-grade credit.",
        "credit_stress": "High-yield credit weakness points to risk appetite stress.",
        "gold_supported": "Gold strength aligns with weaker USD or softer rate pressure.",
        "gold_pressure": "Gold is under pressure from price weakness or USD strength.",
    }
    return [
        note_by_context[context]
        for context in [rates_context, usd_context, credit_context, gold_context]
        if context in note_by_context
    ]


def _return_5d(signals: dict[str, PriceSignal], symbol: str) -> float | None:
    signal = signals.get(symbol)
    if signal is None:
        return None
    return signal.return_5d
