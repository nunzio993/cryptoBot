# Exchange Adapter Implementation Guide

Questa guida descrive come implementare un nuovo adapter per un exchange (es. Kraken, OKX, Kucoin, Coinbase).

---

## 📁 Struttura File

```
src/
├── adapters.py          # Contiene tutti gli adapter (BinanceAdapter, BybitAdapter, ecc.)
├── exchange_factory.py  # Factory per creare l'adapter corretto
└── trading_utils.py     # Utility per formattazione prezzi/quantità
```

---

## 🏗️ Classe Base: ExchangeAdapter

Ogni adapter deve estendere questa classe base ed implementare tutti i metodi:

```python
class ExchangeAdapter:
    def get_balance(self, asset: str) -> float:
        """Ritorna il balance totale (free + locked) per un asset"""
        raise NotImplementedError

    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        """Piazza un ordine"""
        raise NotImplementedError

    def cancel_order(self, symbol: str, order_id):
        """Cancella un ordine"""
        raise NotImplementedError
    
    def get_open_orders(self, symbol: str) -> list:
        """Ritorna lista ordini aperti per un simbolo"""
        raise NotImplementedError
    
    def get_asset_balance_detail(self, asset: str) -> dict:
        """Ritorna dict con 'free' e 'locked'"""
        raise NotImplementedError
    
    def get_recent_trades(self, symbol: str, limit: int = 5) -> list:
        """Ritorna trades recenti"""
        raise NotImplementedError
```

---

## 📋 Metodi Obbligatori

### 1. `__init__(self, api_key, api_secret, testnet=True)`

Inizializza il client dell'exchange.

```python
def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
    from pybit.unified_trading import HTTP  # O la libreria dell'exchange
    
    self.session = HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret,
    )
    self.testnet = testnet
    self.client = self  # Per compatibilità con codice che chiama adapter.client
```

---

### 2. `get_symbol_price(self, symbol: str) -> float`

Ritorna il prezzo corrente di un simbolo.

**Input:** `symbol` (es. "BTCUSDC")  
**Output:** `float` (es. 42500.00)

```python
def get_symbol_price(self, symbol: str) -> float:
    try:
        result = self.session.get_tickers(category="spot", symbol=symbol)
        if result['retCode'] == 0:
            return float(result['result']['list'][0]['lastPrice'])
        return 0.0
    except Exception as e:
        print(f"get_symbol_price error: {e}")
        return 0.0
```

---

### 3. `get_balance(self, asset: str) -> float`

Ritorna il balance totale (free + locked) per un asset.

**Input:** `asset` (es. "USDC", "BTC")  
**Output:** `float`

```python
def get_balance(self, asset: str) -> float:
    try:
        result = self.session.get_wallet_balance(accountType="SPOT")
        if result['retCode'] == 0:
            for coin in result['result']['list'][0]['coin']:
                if coin['coin'] == asset:
                    return float(coin['walletBalance'])
        return 0.0
    except Exception as e:
        print(f"get_balance error: {e}")
        return 0.0
```

---

### 4. `get_asset_balance(self, asset: str) -> dict`

Ritorna balance dettagliato in formato Binance.

**Input:** `asset` (es. "USDC")  
**Output:** `{'free': '100.5', 'locked': '10.0'}`

```python
def get_asset_balance(self, asset: str) -> dict:
    try:
        # Recupera balance dall'exchange
        balance = self._get_balance_raw(asset)
        return {
            'free': str(balance['available']),
            'locked': str(balance['frozen'])
        }
    except:
        return {'free': '0', 'locked': '0'}
```

---

### 5. `place_order(self, symbol, side, type_, quantity, price=None) -> dict`

Piazza un ordine spot.

**Input:**
- `symbol`: "BTCUSDC"
- `side`: "BUY" o "SELL" 
- `type_`: "MARKET" o "LIMIT"
- `quantity`: float (es. 0.5)
- `price`: float o None (obbligatorio per LIMIT)

**Output:** Dict con almeno:
```python
{
    'orderId': '12345678',
    'symbol': 'BTCUSDC',
    'side': 'BUY',
    'status': 'FILLED' | 'NEW' | 'PARTIALLY_FILLED',
    'origQty': '0.5',
    'executedQty': '0.5',
    'fills': [{'qty': '0.5', 'price': '42500'}]  # Per market orders
}
```

```python
def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
    params = {
        "category": "spot",
        "symbol": symbol,
        "side": side.capitalize(),  # "Buy" o "Sell"
        "orderType": "Market" if type_.upper() == "MARKET" else "Limit",
        "qty": str(quantity),
    }
    
    if type_.upper() == "LIMIT" and price:
        params["price"] = str(price)
        params["timeInForce"] = "GTC"
    
    result = self.session.place_order(**params)
    if result['retCode'] != 0:
        raise Exception(f"Order failed: {result['retMsg']}")
    return result['result']
```

---

### 6. `cancel_order(self, symbol: str, order_id) -> dict`

Cancella un ordine.

**Input:**
- `symbol`: "BTCUSDC"
- `order_id`: str o int (l'ID dell'ordine)

```python
def cancel_order(self, symbol: str, order_id):
    result = self.session.cancel_order(
        category="spot",
        symbol=symbol,
        orderId=str(order_id)
    )
    if result['retCode'] != 0:
        raise Exception(f"Cancel failed: {result['retMsg']}")
    return result['result']
```

---

### 7. `order_market_buy(self, symbol: str, quantity: float) -> dict`

Shortcut per ordine market buy.

```python
def order_market_buy(self, symbol: str, quantity: float) -> dict:
    return self.place_order(symbol=symbol, side='Buy', type_='market', quantity=quantity)
```

---

### 8. `close_position_market(self, symbol: str, quantity: float) -> dict`

Vende a mercato una posizione (usato per SL e chiusura manuale).

```python
def close_position_market(self, symbol: str, quantity: float):
    # Tronca quantità per evitare errori di saldo
    precision = self.get_symbol_precision(symbol)
    truncated_qty = self.truncate(float(quantity) * 0.999, precision)
    
    return self.place_order(
        symbol=symbol,
        side='Sell',
        type_='market',
        quantity=truncated_qty
    )
```

---

### 9. `get_open_orders(self, symbol: str) -> list`

Ritorna ordini aperti per un simbolo.

**Output:** Lista normalizzata:
```python
[
    {
        'side': 'SELL',           # Sempre uppercase
        'orderId': '12345678',
        'origQty': 0.5,           # float
        'price': 45000.0          # float
    }
]
```

```python
def get_open_orders(self, symbol: str) -> list:
    result = self.session.get_open_orders(category="spot", symbol=symbol)
    if result['retCode'] == 0:
        return [
            {
                'side': o['side'].upper(),
                'orderId': o['orderId'],
                'origQty': float(o['qty']),
                'price': float(o['price'])
            }
            for o in result['result'].get('list', [])
        ]
    return []
```

---

### 10. `update_spot_tp_sl(self, symbol, quantity, new_tp, new_sl, user_id=None, old_tp=None, tp_order_id=None) -> str`

**CRITICO** - Aggiorna TP/SL per una posizione esistente.

**Logica:**
1. Valida che il nuovo ordine rispetti MIN_NOTIONAL
2. Cancella il vecchio TP (usando `tp_order_id` o cercando per `old_tp`)
3. Crea nuovo ordine LIMIT SELL al prezzo `new_tp`
4. Ritorna il nuovo `tp_order_id`

**Output:** `str` - nuovo order ID del TP

```python
def update_spot_tp_sl(self, symbol: str, quantity: float, new_tp: float, new_sl: float, 
                       user_id: int = None, old_tp: float = None, tp_order_id: str = None) -> str:
    import logging
    logger = logging.getLogger('adapter')
    
    try:
        # 1. Valida MIN_NOTIONAL PRIMA di cancellare il vecchio TP
        min_notional = 5.0  # Valore minimo ordine in USDC
        order_value = float(quantity) * float(new_tp)
        if order_value < min_notional:
            raise ValueError(f"Order value ${order_value:.2f} below minimum ${min_notional}")
        
        # 2. Cancella vecchio TP
        if tp_order_id:
            try:
                self.cancel_order(symbol, tp_order_id)
            except Exception as e:
                logger.warning(f"Could not cancel TP {tp_order_id}: {e}")
        elif old_tp:
            # Cerca ordine per prezzo
            for order in self.get_open_orders(symbol):
                if order['side'] == 'SELL' and abs(order['price'] - float(old_tp)) < 0.01:
                    self.cancel_order(symbol, order['orderId'])
                    break
        
        # 3. Crea nuovo TP
        precision = self.get_symbol_precision(symbol)
        truncated_qty = self.truncate(float(quantity), precision)
        
        new_order = self.place_order(
            symbol=symbol,
            side='Sell',
            type_='limit',
            quantity=truncated_qty,
            price=new_tp
        )
        
        return str(new_order.get('orderId', ''))
        
    except Exception as e:
        logger.error(f"update_spot_tp_sl error: {e}")
        raise
```

---

### 11. `get_symbol_info(self, symbol: str) -> dict`

Ritorna info simbolo normalizzate in formato Binance.

**Output:**
```python
{
    'symbol': 'BTCUSDC',
    'status': 'TRADING',
    'filters': [
        {'filterType': 'LOT_SIZE', 'stepSize': '0.00001', 'minQty': '0.00001'},
        {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
        {'filterType': 'NOTIONAL', 'minNotional': '5'},
        {'filterType': 'MIN_NOTIONAL', 'minNotional': '5'}
    ]
}
```

```python
def get_symbol_info(self, symbol: str) -> dict:
    try:
        result = self.session.get_instruments_info(category="spot", symbol=symbol)
        if result['retCode'] == 0 and result['result']['list']:
            info = result['result']['list'][0]
            return {
                'symbol': symbol,
                'status': 'TRADING',
                'filters': [
                    {
                        'filterType': 'LOT_SIZE',
                        'stepSize': info.get('lotSizeFilter', {}).get('basePrecision', '0.00000001'),
                        'minQty': info.get('lotSizeFilter', {}).get('minOrderQty', '0.00000001'),
                    },
                    {
                        'filterType': 'PRICE_FILTER',
                        'tickSize': info.get('priceFilter', {}).get('tickSize', '0.01'),
                    },
                    {
                        'filterType': 'NOTIONAL',
                        'minNotional': info.get('lotSizeFilter', {}).get('minOrderAmt', '5'),
                    },
                    {
                        'filterType': 'MIN_NOTIONAL',
                        'minNotional': info.get('lotSizeFilter', {}).get('minOrderAmt', '5'),
                    }
                ]
            }
        return {'symbol': symbol, 'filters': []}
    except:
        return {'symbol': symbol, 'filters': []}
```

---

### 12. `get_symbol_precision(self, symbol: str) -> int`

Ritorna il numero di decimali per la quantità.

```python
def get_symbol_precision(self, symbol: str) -> int:
    try:
        result = self.session.get_instruments_info(category="spot", symbol=symbol)
        if result['retCode'] == 0 and result['result']['list']:
            base_precision = result['result']['list'][0].get('lotSizeFilter', {}).get('basePrecision', '0.00000001')
            if '.' in base_precision:
                return len(base_precision.split('.')[1].rstrip('0'))
        return 8
    except:
        return 8
```

---

### 13. `get_all_tickers(self) -> list`

Ritorna tutti i ticker in formato Binance.

```python
def get_all_tickers(self) -> list:
    try:
        result = self.session.get_tickers(category="spot")
        if result['retCode'] == 0:
            return [
                {'symbol': t['symbol'], 'price': t['lastPrice']}
                for t in result['result'].get('list', [])
            ]
        return []
    except:
        return []
```

---

### 14. `get_account(self) -> dict`

Ritorna info account in formato Binance.

```python
def get_account(self) -> dict:
    try:
        result = self.session.get_wallet_balance(accountType="SPOT")
        if result['retCode'] == 0:
            balances = []
            for coin in result['result']['list'][0].get('coin', []):
                wallet = float(coin.get('walletBalance', 0))
                locked = float(coin.get('locked', 0))
                balances.append({
                    'asset': coin['coin'],
                    'free': str(wallet - locked),
                    'locked': str(locked)
                })
            return {'balances': balances}
        return {'balances': []}
    except:
        return {'balances': []}
```

---

### 15. `get_klines(self, symbol, interval, limit=2) -> list`

Ritorna candele storiche in formato Binance.

**Intervalli supportati:**
- `1m`, `5m`, `15m`, `30m`
- `1h`, `4h`
- `1d`, `1w`

**Output Binance format:**
```python
[
    [
        1704067200000,    # Open time (ms)
        "42500.00",       # Open
        "42800.00",       # High
        "42400.00",       # Low
        "42600.00",       # Close
        "1000.5",         # Volume
        1704070799999,    # Close time (ms)
        "42650000.00",    # Quote asset volume
        1500,             # Number of trades
        "500.25",         # Taker buy base volume
        "21325000.00",    # Taker buy quote volume
        "0"               # Ignore
    ],
    ...
]
```

**IMPORTANTE:** L'ordine deve essere dal più vecchio al più recente (come Binance).

```python
def get_klines(self, symbol: str, interval: str, limit: int = 2) -> list:
    try:
        # Mappa intervalli Binance -> Exchange
        interval_map = {
            '1m': '1', '5m': '5', '15m': '15', '30m': '30',
            '1h': '60', '4h': '240', '1d': 'D'
        }
        exchange_interval = interval_map.get(interval, '60')
        
        result = self.session.get_kline(
            category="spot",
            symbol=symbol,
            interval=exchange_interval,
            limit=limit
        )
        
        if result['retCode'] == 0:
            klines = []
            for k in result['result'].get('list', []):
                klines.append([
                    int(k[0]),      # Open time
                    k[1],           # Open
                    k[2],           # High
                    k[3],           # Low
                    k[4],           # Close
                    k[5],           # Volume
                    int(k[0]) + 60000,  # Close time (stima)
                    k[6] if len(k) > 6 else '0',  # Quote volume
                    0, '0', '0', '0'
                ])
            # INVERTIRE se l'exchange ritorna dal più recente
            klines.reverse()
            return klines
        return []
    except:
        return []
```

---

### 16. `create_order(...)` - Compatibilità Binance

Per compatibilità con lo scheduler che usa la firma Binance:

```python
def create_order(self, symbol: str, side: str, type: str, quantity: str, 
                 price: str = None, timeInForce: str = None, **kwargs) -> dict:
    """Create order - Binance-compatible signature"""
    order_result = self.place_order(
        symbol=symbol,
        side=side,
        type_=type,
        quantity=float(quantity),
        price=float(price) if price else None
    )
    
    # Per market orders, popola 'fills' per lo scheduler
    fills = []
    if type.upper() == 'MARKET':
        current_price = self.get_symbol_price(symbol)
        fills = [{'qty': str(quantity), 'price': str(current_price)}]
    
    return {
        'orderId': order_result.get('orderId'),
        'symbol': symbol,
        'side': side,
        'type': type,
        'origQty': quantity,
        'price': price,
        'status': 'NEW',
        'fills': fills
    }
```

---

### 17. Utility: `truncate(self, quantity, precision) -> float`

```python
def truncate(self, quantity: float, precision: int) -> float:
    factor = 10 ** precision
    return math.floor(quantity * factor) / factor
```

---

## 🏭 Registrazione in ExchangeFactory

Dopo aver creato l'adapter, registralo in `src/exchange_factory.py`:

```python
class ExchangeFactory:
    @staticmethod
    def create(exchange_name: str, api_key: str, secret_key: str, testnet: bool = False):
        from src.adapters import BinanceAdapter, BybitAdapter, KrakenAdapter  # Aggiungi qui
        
        adapters = {
            'binance': BinanceAdapter,
            'bybit': BybitAdapter,
            'kraken': KrakenAdapter,  # Nuovo adapter
            # Aggiungi altri qui
        }
        
        adapter_class = adapters.get(exchange_name.lower())
        if not adapter_class:
            raise ValueError(f"Unknown exchange: {exchange_name}")
        
        return adapter_class(api_key, secret_key, testnet=testnet)
```

---

## 🗄️ Registrazione Exchange nel Database

Aggiungi l'exchange in `db-init/init.sql`:

```sql
INSERT INTO exchanges (name, display_name, is_active) VALUES 
    ('kraken', 'Kraken', true)
ON CONFLICT (name) DO NOTHING;
```

O via query:
```sql
INSERT INTO exchanges (name, display_name, is_active) VALUES ('kraken', 'Kraken', true);
```

---

## ✅ Checklist Implementazione

- [ ] `__init__` - Inizializza client
- [ ] `get_symbol_price` - Prezzo corrente
- [ ] `get_balance` - Balance totale
- [ ] `get_asset_balance` - Balance con free/locked
- [ ] `place_order` - Piazza ordine
- [ ] `cancel_order` - Cancella ordine
- [ ] `order_market_buy` - Market buy shortcut
- [ ] `close_position_market` - Vendi a mercato
- [ ] `get_open_orders` - Ordini aperti
- [ ] `update_spot_tp_sl` - Aggiorna TP/SL
- [ ] `get_symbol_info` - Info simbolo (filters)
- [ ] `get_symbol_precision` - Decimali quantità
- [ ] `get_all_tickers` - Tutti i prezzi
- [ ] `get_account` - Account completo
- [ ] `get_klines` - Candele storiche
- [ ] `create_order` - Firma Binance-compatibile
- [ ] `truncate` - Utility troncamento
- [ ] Registrato in ExchangeFactory
- [ ] Aggiunto al database exchanges

---

## 🧪 Testing

Testa ogni metodo:

```python
from src.exchange_factory import ExchangeFactory

adapter = ExchangeFactory.create('kraken', 'API_KEY', 'SECRET', testnet=True)

# Test base
print(adapter.get_symbol_price('BTCUSDC'))
print(adapter.get_balance('USDC'))
print(adapter.get_asset_balance('USDC'))

# Test ordini
# order = adapter.order_market_buy('BTCUSDC', 0.001)
# print(order)
```

---

## ⚠️ Note Importanti

1. **Normalizzazione Output**: Tutti i metodi devono ritornare dati nel formato Binance
2. **Ordine Candele**: `get_klines` deve ritornare dal più vecchio al più recente
3. **MIN_NOTIONAL**: Valida PRIMA di cancellare il vecchio TP in `update_spot_tp_sl`
4. **Error Handling**: Cattura eccezioni e logga errori
5. **Testnet**: Supporta sempre sia testnet che mainnet
