import yfinance as yf
import time

tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
data = {}

for ticker in tickers:
    try:
        data[ticker] = yf.download(ticker, period='1mo', progress=False)
        time.sleep(2)  # 每次请求间隔 2 秒
    except Exception as e:
        print(f"{ticker} 下载失败: {e}")
        time.sleep(5)  # 遇到错误时等待更长时间