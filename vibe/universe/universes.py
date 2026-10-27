"""
Universum-Definitionen für vibe-trading Backtests.
US-Top-100 (liquid Mega/Large Caps) + DAX-40.
"""

# Top-100 US Large Caps (Yahoo-Ticker)
US_TOP100 = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","BRK-B","JPM",
    "LLY","V","UNH","XOM","MA","COST","HD","PG","JNJ","ABBV",
    "BAC","CVX","MRK","KO","PEP","WMT","ORCL","TMO","AMD","ADBE",
    "CRM","LIN","ACN","CSCO","MCD","ABT","NFLX","TMUS","CAT","GE",
    "PM","IBM","TXN","NKE","VZ","DIS","QCOM","UNP","AMGN","RTX",
    "HON","DHR","BA","LOW","GS","INTU","SPGI","AMT","PLD","PFE",
    "ELV","SBUX","BLK","T","MDT","COP","ISRG","BKNG","LRCX","NOW",
    "AXP","MS","C","GILD","ADP","TJX","CI","MDLZ","MMC","MO",
    "SO","ETN","LMT","DUK","DE","REGN","KLAC","PGR","NOC","CB",
    "SHW","PH","TT","EMR","BSX","AON","FDX","FCX","WELL","MPC",
]

# DAX 40 (Deutschland)
DAX_40 = [
    "SAP.DE","AIR.DE","SIE.DE","ALV.DE","DTE.DE","DHL.DE","BAYN.DE","MBG.DE",
    "BAS.DE","BMW.DE","VOW3.DE","ADS.DE","DB1.DE","MUV2.DE","IFX.DE","CON.DE",
    "SZG.DE","TKA.DE","P911.DE","HEI.DE","QGEN.DE","MOWI.DE","BNR.DE","HEN3.DE",
    "BESI.DE","RHM.DE","SY1.DE","MTX.DE","NEM.DE","WDI.DE","FRE.DE","ZAL.DE",
    "TUI1.DE","GXI.DE","HNR1.DE","EVK.DE","COV.DE","1COV.DE","UTDI.DE","KRN.DE",
]

# Komplettes Universum
ALL = US_TOP100 + DAX_40


def by_market(market):
    return US_TOP100 if market == "US" else DAX_40 if market == "DAX" else ALL
