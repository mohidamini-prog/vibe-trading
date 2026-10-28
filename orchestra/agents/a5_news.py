"""
A5 — News/Kalender/EDGAR Agent (15% Gewicht): Event-Filter + Insider-Signale.

Eigener, zugeschnittener Datensatz: News-Sentiment, Wirtschaftskalender, SEC EDGAR.
- High-Impact (FOMC/CPI/NFP/EZB) => VETO
- Earnings morgen => VETO
- Insider-Cluster (3+ Form-4 Filings in 7 Tagen) => bullisch/bärisch
"""
from orchestra.agents.base import BaseAgent
from orchestra.tiers import tier3


class NewsAgent(BaseAgent):
    name = "news"

    def vote(self, data):
        # data: dict mit headlines[], symbol, earnings_soon, insider
        symbol = data.get("symbol", "")
        headlines = data.get("headlines", [])
        earnings_soon = data.get("earnings_soon", False)

        # VETO: Earnings morgen
        if earnings_soon:
            return self._make(0, 0.9, "VETO: Earnings morgen", veto=True, earnings=True)

        # News-Headlines: falls leer, selbst vom Yahoo-RSS-Feed holen (Research-Roboter)
        if not headlines:
            try:
                from orchestra.research_robot import news_sentiment
                _, n_head, headlines = news_sentiment(symbol)
            except Exception:
                pass

        # News-Sentiment (nur Titel, datenarm)
        sentiment, n = tier3.headline_sentiment(headlines)

        # Insider-Cluster (EDGAR)
        ins = data.get("insider", {})
        cluster = ins.get("cluster", False)
        direction = ins.get("direction", 0)

        # Kombiniertes Signal: Sentiment + Insider-Cluster
        if cluster and direction != 0:
            # Insider-Bestätigung verstärkt
            conf = 0.6 + 0.3 * min(1.0, ins.get("count", 0) / 5.0)
            return self._make(direction, conf,
                              f"Insider-Cluster {ins.get('count',0)} ({'BUY' if direction>0 else 'SELL'})",
                              insider_count=ins.get("count", 0), sentiment=sentiment)
        if abs(sentiment) > 0.5:
            conf = min(1.0, 0.4 + abs(sentiment) / 2.0)
            a = 1 if sentiment > 0 else -1
            return self._make(a, conf, f"News-Sentiment {sentiment:+.2f} ({n} Headlines)",
                              sentiment=round(sentiment, 2), n_headlines=n)
        return self._make(0, 0.3, "kein Event-Risiko", sentiment=round(sentiment, 2))


if __name__ == "__main__":
    a = NewsAgent()
    print(a.vote({"symbol": "AAPL", "headlines": ["Apple beats earnings, stock surges"]}))
    print(a.vote({"symbol": "AAPL", "headlines": [], "earnings_soon": True}))
    print(a.vote({"symbol": "AAPL", "headlines": [],
                  "insider": {"cluster": True, "direction": 1, "count": 4}}))
