"""
Лабораторна робота № 3. Алгоритми CRC.
Варіант 16: CRC-8, утворюючий поліном x^8 + x^7 + x^6 + x^4 + x^2 + 1.

Тут зібрано тільки самі алгоритми (за методичними вказівками, с. 17-32 / лекції 5-6):
  1) простий послідовний (прямий побітовий)   - crc_simple
  2) прямий табличний                          - make_table + crc_table
  3) дзеркальний послідовний                   - crc_reflected
  4) дзеркальний табличний                     - make_reflected_table + crc_reflected_table
  5) стандартизований за табл. 4.1 (додатково) - crc_standard
"""

# ---------------------------------------------------------------------------
# Параметри варіанта 16
# ---------------------------------------------------------------------------
WIDTH = 8                      # степінь полінома = кількість бітів CRC
POLY_FULL = 0b1_1101_0101      # x^8 + x^7 + x^6 + x^4 + x^2 + 1  (9 коефіцієнтів)
POLY = POLY_FULL & 0xFF        # 0xD5 - поліном без старшого біта (він завжди 1)


def reflect(value, width):
    """Дзеркальне відображення бітів: біт 0 <-> біт width-1, біт 1 <-> біт width-2 ..."""
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


POLY_REFLECTED = reflect(POLY, WIDTH)   # 0xAB - дзеркальний поліном


# ---------------------------------------------------------------------------
# Допоміжне: повідомлення - це послідовність бітів b0, b1, ..., b(K-1)
# ---------------------------------------------------------------------------
def bits_to_bytes_msb(bits):
    """Для прямих алгоритмів: перший біт потоку стає СТАРШИМ бітом байта."""
    data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        data.append(byte)
    return bytes(data)


def bits_to_bytes_lsb(bits):
    """Для дзеркальних алгоритмів: перший біт потоку стає МОЛОДШИМ бітом байта."""
    data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for k, bit in enumerate(bits[i:i + 8]):
            byte |= bit << k
        data.append(byte)
    return bytes(data)


def bytes_to_bits(data):
    """Байти -> біти (старший біт кожного байта йде першим)."""
    return [(byte >> (7 - k)) & 1 for byte in data for k in range(8)]


# ---------------------------------------------------------------------------
# 1. Простий послідовний алгоритм (CRC_простий з методички)
# ---------------------------------------------------------------------------
def crc_simple(bits, width=WIDTH, poly=POLY):
    """
    Кроки методички:
      1. Завантажити регістр нульовими бітами.
      2. Доповнити кінець повідомлення N нульовими бітами.
      3. Зсунути регістр на 1 біт вліво, черговий біт повідомлення - у позицію 0.
      4. Якщо з регістру був висунутий біт "1" - регістр = регістр XOR поліном.
      5. Повторювати 3-4, доки є біти. У регістрі залишиться CRC.
    """
    mask = (1 << width) - 1
    register = 0                                   # крок 1
    message = list(bits) + [0] * width             # крок 2
    for bit in message:
        popped = (register >> (width - 1)) & 1     # біт, який висувається зліва
        register = ((register << 1) & mask) | bit  # крок 3
        if popped:                                 # крок 4
            register ^= poly
    return register


def crc_simple_trace(bits, width, poly):
    """Той самий простий алгоритм, але запам'ятовує кожен крок (для демонстрації)."""
    mask = (1 << width) - 1
    register = 0
    steps = []
    for bit in list(bits) + [0] * width:
        popped = (register >> (width - 1)) & 1
        register = ((register << 1) & mask) | bit
        if popped:
            register ^= poly
        steps.append((bit, popped, register))
    return register, steps


# ---------------------------------------------------------------------------
# 2. Прямий табличний алгоритм
# ---------------------------------------------------------------------------
def make_table(poly=POLY, width=WIDTH):
    """
    Таблиця з 256 значень: table[i] = залишок від ділення числа i (з дописаними
    N нулями) на поліном. Тобто для кожного байта i наперед виконуємо 8 кроків
    побітового алгоритму. Будується ОДИН раз.
    """
    mask = (1 << width) - 1
    top_bit = 1 << (width - 1)
    table = []
    for i in range(256):
        register = i << (width - 8)
        for _ in range(8):
            if register & top_bit:
                register = ((register << 1) & mask) ^ poly
            else:
                register = (register << 1) & mask
        table.append(register)
    return table


def crc_table(data, table, width=WIDTH):
    """
    Методичка:  Top = старший_байт(Register)
                Register = (Register << 8) XOR Таблиця[Top XOR новий_байт]
    Для CRC-8 регістр і є одним байтом, тому зсув дає 0 і лишається:
                Register = Таблиця[Register XOR байт]
    """
    mask = (1 << width) - 1
    register = 0
    for byte in data:
        top = (register >> (width - 8)) ^ byte
        register = ((register << 8) & mask) ^ table[top]
    return register


# ---------------------------------------------------------------------------
# 3. Дзеркальний послідовний алгоритм
# ---------------------------------------------------------------------------
def crc_reflected(bits, rpoly=POLY_REFLECTED):
    """
    Дзеркальне відображення прямого алгоритму: регістр зсувається ВПРАВО,
    біти входять з боку молодшого розряду, використовується дзеркальний поліном.
    Нулі в кінець повідомлення не дописуються (як сказано в методичці).
    Результат - дзеркальне відображення прямого CRC.
    """
    register = 0
    for bit in bits:
        if (register ^ bit) & 1:          # висувається "1" (з урахуванням нового біта)
            register = (register >> 1) ^ rpoly
        else:
            register >>= 1
    return register


# ---------------------------------------------------------------------------
# 4. Дзеркальний табличний алгоритм
# ---------------------------------------------------------------------------
def make_reflected_table(rpoly=POLY_REFLECTED):
    """Дзеркальна таблиця: для кожного байта i - 8 кроків дзеркального алгоритму."""
    table = []
    for i in range(256):
        register = i
        for _ in range(8):
            if register & 1:
                register = (register >> 1) ^ rpoly
            else:
                register >>= 1
        table.append(register)
    return table


def crc_reflected_table(data, rtable):
    """
    Методичка: висуваємо байт регістру вправо, XOR з байтом повідомлення,
    результат - індекс у таблиці, значення з таблиці XOR з регістром.
    """
    register = 0
    for byte in data:
        register = (register >> 8) ^ rtable[(register ^ byte) & 0xFF]
    return register


# ---------------------------------------------------------------------------
# 5. Стандартизований алгоритм за параметрами табл. 4.1 (додатково)
# ---------------------------------------------------------------------------
# Для нашого полінома 0xD5 у табл. 4.1 є CRC-8/DVB-S2
CRC8_DVB_S2 = dict(name="CRC-8/DVB-S2", width=8, poly=0xD5, init=0x00,
                   refin=False, refout=False, xorout=0x00, check=0xBC)


def crc_standard(data, width, poly, init, refin, refout, xorout, **_):
    """Універсальний CRC за параметрами Width, Poly, Init, RefIn, RefOut, XorOut."""
    mask = (1 << width) - 1
    top_bit = 1 << (width - 1)
    register = init
    for byte in data:
        if refin:                           # RefIn: байт обробляється з молодшого біта
            byte = reflect(byte, 8)
        register ^= byte << (width - 8)
        for _ in range(8):
            if register & top_bit:
                register = ((register << 1) ^ poly) & mask
            else:
                register = (register << 1) & mask
    if refout:                              # RefOut: дзеркалимо результат
        register = reflect(register, width)
    return register ^ xorout                # XorOut: фінальний XOR
