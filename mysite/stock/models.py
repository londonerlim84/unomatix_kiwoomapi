from django.db import models


class Stock(models.Model):
    """종목 정보"""
    MARKET_CHOICES = [
        ('KOSPI', '코스피'),
        ('KOSDAQ', '코스닥'),
    ]

    code = models.CharField('종목코드', max_length=10, unique=True)
    name = models.CharField('종목명', max_length=100)
    market = models.CharField('시장구분', max_length=10, choices=MARKET_CHOICES)
    is_active = models.BooleanField('활성여부', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '종목'
        verbose_name_plural = '종목 목록'
        ordering = ['code']

    def __str__(self):
        return f"[{self.code}] {self.name}"


class StockPrice(models.Model):
    """종목 시세"""
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='prices')
    current_price = models.IntegerField('현재가', default=0)
    open_price = models.IntegerField('시가', default=0)
    high_price = models.IntegerField('고가', default=0)
    low_price = models.IntegerField('저가', default=0)
    prev_close = models.IntegerField('전일종가', default=0)
    volume = models.BigIntegerField('거래량', default=0)
    change_rate = models.FloatField('등락률', default=0.0)
    timestamp = models.DateTimeField('시세시각', auto_now=True)

    class Meta:
        verbose_name = '시세'
        verbose_name_plural = '시세 목록'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.stock.name} - {self.current_price}원"


class TradingConfig(models.Model):
    """매매 설정 (모의/실투자 전환)"""
    MODE_CHOICES = [
        ('mock', '모의투자'),
        ('real', '실투자'),
    ]

    name = models.CharField('설정명', max_length=100, default='기본설정')
    trade_mode = models.CharField('투자모드', max_length=10, choices=MODE_CHOICES, default='mock')
    app_key = models.CharField('APP KEY', max_length=200, blank=True)
    app_secret = models.CharField('APP SECRET', max_length=200, blank=True)
    account_no = models.CharField('계좌번호', max_length=20, blank=True)
    is_active = models.BooleanField('활성여부', default=True)
    max_buy_amount = models.IntegerField('최대매수금액', default=1000000)
    max_buy_per_stock = models.IntegerField('종목당최대매수금액', default=500000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '매매설정'
        verbose_name_plural = '매매설정 목록'

    def __str__(self):
        return f"{self.name} ({self.get_trade_mode_display()})"


class ConditionSearch(models.Model):
    """조건검색식"""
    STATUS_CHOICES = [
        ('active', '실행중'),
        ('stopped', '중지'),
        ('error', '오류'),
    ]

    condition_index = models.IntegerField('조건식인덱스')
    condition_name = models.CharField('조건식명', max_length=200)
    is_realtime = models.BooleanField('실시간조건검색', default=True)
    auto_trade = models.BooleanField('자동매매여부', default=False)
    status = models.CharField('상태', max_length=10, choices=STATUS_CHOICES, default='stopped')
    config = models.ForeignKey(
        TradingConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='conditions',
        verbose_name='매매설정'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '조건검색식'
        verbose_name_plural = '조건검색식 목록'
        unique_together = ['condition_index', 'condition_name']

    def __str__(self):
        return f"[{self.condition_index}] {self.condition_name}"


class ConditionMatch(models.Model):
    """조건검색 편입/이탈 종목"""
    TYPE_CHOICES = [
        ('I', '편입'),
        ('D', '이탈'),
    ]

    condition = models.ForeignKey(
        ConditionSearch, on_delete=models.CASCADE,
        related_name='matches', verbose_name='조건검색식'
    )
    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE,
        related_name='condition_matches', verbose_name='종목'
    )
    match_type = models.CharField('편입/이탈', max_length=1, choices=TYPE_CHOICES)
    matched_at = models.DateTimeField('검출시각', auto_now_add=True)

    class Meta:
        verbose_name = '조건검색 결과'
        verbose_name_plural = '조건검색 결과 목록'
        ordering = ['-matched_at']

    def __str__(self):
        return f"{self.condition.condition_name} - {self.stock.name} ({self.get_match_type_display()})"


class Order(models.Model):
    """주문"""
    ORDER_TYPE_CHOICES = [
        ('buy', '매수'),
        ('sell', '매도'),
    ]
    PRICE_TYPE_CHOICES = [
        ('limit', '지정가'),
        ('market', '시장가'),
    ]
    STATUS_CHOICES = [
        ('pending', '대기'),
        ('submitted', '접수'),
        ('filled', '체결'),
        ('partial', '부분체결'),
        ('cancelled', '취소'),
        ('rejected', '거부'),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='orders', verbose_name='종목')
    order_type = models.CharField('주문유형', max_length=4, choices=ORDER_TYPE_CHOICES)
    price_type = models.CharField('가격유형', max_length=10, choices=PRICE_TYPE_CHOICES, default='market')
    quantity = models.IntegerField('주문수량')
    price = models.IntegerField('주문가격', default=0)
    filled_quantity = models.IntegerField('체결수량', default=0)
    filled_price = models.IntegerField('체결가격', default=0)
    status = models.CharField('상태', max_length=10, choices=STATUS_CHOICES, default='pending')
    order_no = models.CharField('주문번호', max_length=20, blank=True)
    trade_mode = models.CharField('투자모드', max_length=10, default='mock')
    condition = models.ForeignKey(
        ConditionSearch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
        verbose_name='조건검색식'
    )
    reason = models.CharField('주문사유', max_length=200, blank=True)
    created_at = models.DateTimeField('주문시각', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '주문'
        verbose_name_plural = '주문 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.stock.name} {self.get_order_type_display()} {self.quantity}주"


class Balance(models.Model):
    """잔고 (보유종목)"""
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='balances', verbose_name='종목')
    quantity = models.IntegerField('보유수량', default=0)
    avg_price = models.IntegerField('평균매입가', default=0)
    current_price = models.IntegerField('현재가', default=0)
    profit_rate = models.FloatField('수익률', default=0.0)
    profit_amount = models.IntegerField('평가손익', default=0)
    trade_mode = models.CharField('투자모드', max_length=10, default='mock')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '잔고'
        verbose_name_plural = '잔고 목록'
        unique_together = ['stock', 'trade_mode']

    def __str__(self):
        return f"{self.stock.name} {self.quantity}주 (수익률: {self.profit_rate}%)"


class TradeHistory(models.Model):
    """체결내역"""
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='trades', verbose_name='종목')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, related_name='trades', verbose_name='주문')
    order_type = models.CharField('매매유형', max_length=4)
    quantity = models.IntegerField('체결수량')
    price = models.IntegerField('체결가격')
    total_amount = models.IntegerField('체결금액', default=0)
    trade_mode = models.CharField('투자모드', max_length=10, default='mock')
    traded_at = models.DateTimeField('체결시각', auto_now_add=True)

    class Meta:
        verbose_name = '체결내역'
        verbose_name_plural = '체결내역 목록'
        ordering = ['-traded_at']

    def __str__(self):
        return f"{self.stock.name} {self.order_type} {self.quantity}주 @ {self.price}원"
