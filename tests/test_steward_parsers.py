from datetime import date, time
from decimal import Decimal

from app.steward.parsers.alipay import parse_alipay_csv_text
from app.steward.parsers.cmb import parse_cmb_statement_text
from app.steward.parsers.icbc import parse_icbc_statement_text
from app.steward.parsers.registry import parse_statement_file


def test_parse_cmb_statement_text_normalizes_transaction_rows():
    text = """招商银行交易流水
Transaction Statement of China Merchants Bank
账号：6214********3949
记账日期 货币 交易金额 联机余额 交易摘要
Date Currency Transaction
Amount Balance Transaction Type
2026-07-13 CNY 100.00 1,100.00 朝朝宝转出
2026-07-13 CNY -88.50 1,011.50 快捷支付
"""

    result = parse_cmb_statement_text(text)

    assert result.institution == "cmb"
    assert result.warnings == []
    assert len(result.transactions) == 2
    txn = result.transactions[1]
    assert txn.institution == "cmb"
    assert txn.account_label == "6214********3949"
    assert txn.transaction_date == date(2026, 7, 13)
    assert txn.transaction_time is None
    assert txn.currency == "CNY"
    assert txn.amount == Decimal("-88.50")
    assert txn.balance == Decimal("1011.50")
    assert txn.summary == "快捷支付"


def test_parse_icbc_statement_text_normalizes_wrapped_transaction_rows():
    text = """中国工商银行借记账户历史明细（电子版）
卡号 621226********8795 户名：测试用户 起止日期：2026-01-15 — 2026-07-15
交易日期 账号 储种 序号 币种 钞汇 摘要 地区 收入/支出金额 余额 渠道
2026-07-14
17:08:13 1001295101239559906 活期 00000 人民币 钞 他行汇入 1001 +4,000.00 21,361.55 其他
2026-07-15
04:16:44 1001295101239559906 活期 00000 人民币 钞 贷款本息 1001 -15,598.26 5,763.29 其他
"""

    result = parse_icbc_statement_text(text)

    assert result.institution == "icbc"
    assert result.warnings == []
    assert len(result.transactions) == 2
    txn = result.transactions[0]
    assert txn.institution == "icbc"
    assert txn.account_label == "621226********8795"
    assert txn.transaction_date == date(2026, 7, 14)
    assert txn.transaction_time == time(17, 8, 13)
    assert txn.currency == "CNY"
    assert txn.amount == Decimal("4000.00")
    assert txn.balance == Decimal("21361.55")
    assert txn.summary == "他行汇入"
    assert txn.channel == "其他"


def test_parse_alipay_csv_text_normalizes_signed_amounts():
    text = """支付宝交易明细
交易创建时间,付款时间,交易来源地,类型,交易对方,商品名称,金额（元）,收/支,交易状态,备注
2026-07-14 10:01:02,2026-07-14 10:01:05,,即时到账交易,示例商户,示例商品,88.50,支出,交易成功,
2026-07-15 09:30:00,2026-07-15 09:30:02,,转账,示例用户,转账收款,120.00,收入,交易成功,
"""

    result = parse_alipay_csv_text(text)

    assert result.institution == "alipay"
    assert result.warnings == []
    assert len(result.transactions) == 2
    assert result.transactions[0].amount == Decimal("-88.50")
    assert result.transactions[0].summary == "示例商户 - 示例商品"
    assert result.transactions[1].amount == Decimal("120.00")
    assert result.transactions[1].transaction_date == date(2026, 7, 15)


def test_parse_statement_file_dispatches_by_filename_and_suffix(tmp_path):
    path = tmp_path / "支付宝交易明细.csv"
    path.write_text(
        "交易创建时间,金额（元）,收/支,交易状态,交易对方,商品名称\n"
        "2026-07-15 09:30:00,120.00,收入,交易成功,示例用户,转账收款\n",
        encoding="utf-8",
    )

    result = parse_statement_file(path)

    assert result.institution == "alipay"
    assert len(result.transactions) == 1
