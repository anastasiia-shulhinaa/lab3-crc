"""
Лабораторна робота № 3. Алгоритми CRC (циклічні надлишкові коди).
Варіант 16: CRC-8, x^8 + x^7 + x^6 + x^4 + x^2 + 1.

Запуск:  python main.py
"""

import os
import platform
import random
import re
import statistics
import sys
import time

from crc_algorithms import (
    WIDTH, POLY, POLY_FULL, POLY_REFLECTED, CRC8_DVB_S2,
    reflect, bits_to_bytes_msb, bits_to_bytes_lsb, bytes_to_bits,
    crc_simple, crc_simple_trace, make_table, crc_table,
    crc_reflected, make_reflected_table, crc_reflected_table,
    crc_standard,
)

K = 1000            # довжина повідомлення в бітах
SEED = 16           # фіксований seed (= номер варіанта), щоб результат повторювався
SERIES = 7          # кількість серій вимірювань
CALLS = 2000        # кількість обчислень CRC в одній серії
WARMUP = 200        # прогрівальні запуски (не входять у статистику)

# ---------------------------------------------------------------------------
# Оформлення виводу
# ---------------------------------------------------------------------------
sys.stdout.reconfigure(encoding="utf-8")
os.system("")       # вмикає кольори ANSI у консолі Windows

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, RED, YELLOW = "\033[96m", "\033[92m", "\033[91m", "\033[93m"
ANSI = re.compile(r"\033\[[0-9;]*m")
LINE = 86


def visible_len(text):
    return len(ANSI.sub("", text))


def pad(text, width, align="<"):
    space = " " * max(0, width - visible_len(text))
    return text + space if align == "<" else space + text


def header(number, title):
    print()
    print(CYAN + "═" * LINE + RESET)
    print(CYAN + BOLD + f" {number}. {title}" + RESET)
    print(CYAN + "═" * LINE + RESET)


def mark(condition):
    return GREEN + "✓" + RESET if condition else RED + "✗" + RESET


def print_table(headers, rows, aligns=None):
    aligns = aligns or "<" * len(headers)
    widths = [max(visible_len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    top = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    mid = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    bot = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"
    print(top)
    print("│" + "│".join(" " + BOLD + pad(h, w) + RESET + " " for h, w in zip(headers, widths)) + "│")
    print(mid)
    for row in rows:
        print("│" + "│".join(" " + pad(str(c), w, a) + " " for c, w, a in zip(row, widths, aligns)) + "│")
    print(bot)


def h8(value):
    return f"0x{value:02X}"


def b8(value, width=WIDTH):
    return format(value, f"0{width}b")


def poly_to_text(poly_full):
    terms = []
    for p in range(poly_full.bit_length() - 1, -1, -1):
        if poly_full >> p & 1:
            terms.append("1" if p == 0 else "x" if p == 1 else f"x^{p}")
    return " + ".join(terms)


def group_bits(bits, size=8):
    s = "".join(map(str, bits))
    return " ".join(s[i:i + size] for i in range(0, len(s), size))


# ---------------------------------------------------------------------------
# Вимірювання часу
# ---------------------------------------------------------------------------
def measure(func, *args, calls=CALLS, series=SERIES, warmup=WARMUP):
    """Повертає список: середній час ОДНОГО виклику (мкс) у кожній серії."""
    for _ in range(warmup):
        func(*args)
    results = []
    for _ in range(series):
        start = time.perf_counter()
        for _ in range(calls):
            func(*args)
        results.append((time.perf_counter() - start) / calls * 1e6)
    return results


def main():
    print(BOLD + "\n  ЛАБОРАТОРНА РОБОТА № 3. АЛГОРИТМИ CRC (ЦИКЛІЧНІ НАДЛИШКОВІ КОДИ)" + RESET)
    print(DIM + "  Варіант 16 · джерела: методичні вказівки до лаб. робіт (с. 17-32), лекції 5-6" + RESET)

    # =======================================================================
    header(1, "ПАРАМЕТРИ ВАРІАНТА")
    print_table(
        ["Параметр", "Значення"],
        [
            ["Назва (табл. 4.2)", "CRC-8 (використання: ETSI EN 302 307)"],
            ["Утворюючий поліном G(x)", poly_to_text(POLY_FULL)],
            ["Коефіцієнти x^8 ... x^0", format(POLY_FULL, "b")],
            ["Степінь n (ширина CRC)", f"{WIDTH} біт"],
            ["Поліном без старшого біта", f"{h8(POLY)}  ({b8(POLY)})"],
            ["Дзеркальний поліном", f"{h8(POLY_REFLECTED)}  ({b8(POLY_REFLECTED)})"],
            ["Стандарт з табл. 4.1", "CRC-8/DVB-S2: Init=0x00, RefIn=false, RefOut=false, XorOut=0x00"],
            ["Довжина повідомлення K", f"{K} біт = {K // 8} байт"],
        ],
    )

    # =======================================================================
    header(2, "ПЕРЕВІРКА НА ПРИКЛАДІ З МЕТОДИЧКИ (Рис. 4.1)")
    example = [int(c) for c in "1101011011"]
    print("  Повідомлення: 1101011011,  поліном 10011 (x^4 + x + 1),  n = 4")
    print("  Простий послідовний алгоритм дописує 4 нулі: 1101011011" + YELLOW + "0000" + RESET)
    print("  Регістр зсувається вліво; якщо висунуто «1» → регістр XOR 0011\n")
    result, trace = crc_simple_trace(example, width=4, poly=0b0011)
    rows = []
    for step, (bit, popped, reg) in enumerate(trace, 1):
        xor = YELLOW + "так, XOR 0011" + RESET if popped else DIM + "ні" + RESET
        bit_txt = YELLOW + str(bit) + RESET if step > len(example) else str(bit)
        rows.append([step, bit_txt, popped, xor, format(reg, "04b")])
    print_table(["Крок", "Вхідний біт", "Висунутий біт", "XOR з поліномом?", "Регістр"],
                rows, "><<<<")
    same = crc_simple(example, width=4, poly=0b0011) == result
    print(f"  Результат: {BOLD}{format(result, '04b')}{RESET}   "
          f"очікувалось за Рис. 4.1: 1110   {mark(format(result, '04b') == '1110' and same)}")

    # =======================================================================
    table = make_table()
    rtable = make_reflected_table()

    header(3, "ЕТАЛОННА ПЕРЕВІРКА: РЯДОК \"123456789\" (стовпчик Check у табл. 4.1)")
    check_data = b"123456789"
    check_bits = bytes_to_bits(check_data)
    checks = [
        ("Простий послідовний", crc_simple(check_bits)),
        ("Прямий табличний", crc_table(check_data, table)),
        ("Дзеркальний послідовний", reflect(crc_reflected(check_bits), WIDTH)),
        ("Дзеркальний табличний",
         reflect(crc_reflected_table(bits_to_bytes_lsb(check_bits), rtable), WIDTH)),
        ("Стандартний CRC-8/DVB-S2", crc_standard(check_data, **CRC8_DVB_S2)),
    ]
    print_table(["Алгоритм", "CRC", "Check з табл. 4.1", ""],
                [[n, h8(v), h8(CRC8_DVB_S2["check"]), mark(v == CRC8_DVB_S2["check"])]
                 for n, v in checks])
    print(DIM + "  (для дзеркальних алгоритмів результат відображено назад — див. розділ 6)" + RESET)

    print("\n  Додатково: стандартизований алгоритм перевірено й на інших рядках табл. 4.1")
    other = [
        dict(name="CRC-8", width=8, poly=0x07, init=0x0, refin=False, refout=False, xorout=0x0, check=0xF4),
        dict(name="CRC-8/MAXIM", width=8, poly=0x31, init=0x0, refin=True, refout=True, xorout=0x0, check=0xA1),
        dict(name="CRC-16/ARC", width=16, poly=0x8005, init=0x0, refin=True, refout=True, xorout=0x0, check=0xBB3D),
        dict(name="CRC-16/CCITT-FALSE", width=16, poly=0x1021, init=0xFFFF, refin=False, refout=False,
             xorout=0x0, check=0x29B1),
        dict(name="CRC-32/zlib", width=32, poly=0x4C11DB7, init=0xFFFFFFFF, refin=True, refout=True,
             xorout=0xFFFFFFFF, check=0xCBF43926),
    ]
    rows = []
    for p in other:
        value = crc_standard(check_data, **p)
        rows.append([p["name"], f"0x{value:X}", f"0x{p['check']:X}", mark(value == p["check"])])
    print_table(["Стандарт", "Обчислено", "Check", ""], rows)

    # =======================================================================
    header(4, "ТАБЛИЦІ ДЛЯ ТАБЛИЧНИХ АЛГОРИТМІВ (256 значень по 1 байту)")
    for title, tbl in (("Пряма таблиця: table[i] = залишок від ділення i·x^8 на G(x)", table),
                       ("Дзеркальна таблиця (будується з дзеркальним поліномом 0xAB)", rtable)):
        print(f"  {BOLD}{title}{RESET}")
        print(DIM + "        " + " ".join(f"_{c:X}" for c in range(16)) + RESET)
        for r in range(16):
            print(f"   {DIM}{r:X}_ {RESET}  " + " ".join(f"{tbl[r * 16 + c]:02X}" for c in range(16)))
        print()
    mirror_ok = all(rtable[i] == reflect(table[reflect(i, 8)], WIDTH) for i in range(256))
    print(f"  Перевірка «дзеркальна таблиця = дзеркальне відображення прямої»:")
    print(f"  rtable[i] == reflect(table[reflect(i)]) для всіх 256 i   {mark(mirror_ok)}")

    # =======================================================================
    header(5, f"ВХІДНЕ ПОВІДОМЛЕННЯ: K = {K} ВИПАДКОВИХ БІТІВ")
    random.seed(SEED)
    bits = [random.randint(0, 1) for _ in range(K)]
    data_msb = bits_to_bytes_msb(bits)      # для прямого табличного і стандартного
    data_lsb = bits_to_bytes_lsb(bits)      # для дзеркального табличного
    print(f"  Згенеровано random.seed({SEED}); одиниць: {sum(bits)}, нулів: {K - sum(bits)}\n")
    print("  Повне повідомлення (по 80 біт у рядку, групи по 8 = байти):")
    for i in range(0, K, 80):
        print(f"   {DIM}{i:4}{RESET}  {group_bits(bits[i:i + 80])}")
    print(f"\n  Ті самі біти як {len(data_msb)} байт (перші 16): "
          + " ".join(f"{b:02X}" for b in data_msb[:16]) + " ...")

    # =======================================================================
    header(6, "РЕЗУЛЬТАТИ ОБЧИСЛЕННЯ CRC ДЛЯ ПОВІДОМЛЕННЯ")
    r_simple = crc_simple(bits)
    r_table = crc_table(data_msb, table)
    r_refl = crc_reflected(bits)
    r_refl_t = crc_reflected_table(data_lsb, rtable)
    r_std = crc_standard(data_msb, **CRC8_DVB_S2)
    results = [
        ("Простий послідовний", f"{K}+8 нулів = {K + 8} біт", r_simple, r_simple),
        ("Прямий табличний", f"{K // 8} байт", r_table, r_table),
        ("Дзеркальний послідовний", f"{K} біт", r_refl, reflect(r_refl, WIDTH)),
        ("Дзеркальний табличний", f"{K // 8} байт", r_refl_t, reflect(r_refl_t, WIDTH)),
        ("Стандартний CRC-8/DVB-S2", f"{K // 8} байт", r_std, r_std),
    ]
    rows = []
    for name, unit, raw, crc in results:
        is_refl = name.startswith("Дзеркальний")
        rows.append([name, unit, f"{h8(raw)} = {b8(raw)}",
                     YELLOW + "reflect →" + RESET if is_refl else DIM + "—" + RESET,
                     BOLD + f"{h8(crc)} = {b8(crc)}" + RESET, mark(crc == r_simple)])
    print_table(["Алгоритм", "Обробляє", "Вміст регістру", "", "CRC", "Збіг"], rows)
    print(f"\n  Дзеркальний регістр зберігає біти «задом наперед», тому його вміст "
          f"{h8(r_refl)} = {b8(r_refl)}")
    print(f"  — це дзеркальне відображення прямого CRC {h8(r_simple)} = {b8(r_simple)}.")
    print(f"\n  {BOLD}CRC повідомлення = {h8(r_simple)} ({b8(r_simple)}){RESET}")

    # Додаткові тести коректності
    print("\n  Додаткові тести коректності:")
    rng = random.Random(1)
    all_ok = True
    for _ in range(300):
        tb = [rng.randint(0, 1) for _ in range(8 * rng.randint(1, 250))]
        expected = crc_simple(tb)
        got = [crc_table(bits_to_bytes_msb(tb), table),
               reflect(crc_reflected(tb), WIDTH),
               reflect(crc_reflected_table(bits_to_bytes_lsb(tb), rtable), WIDTH),
               crc_standard(bits_to_bytes_msb(tb), **CRC8_DVB_S2)]
        all_ok &= all(g == expected for g in got)
    zeros = [0] * K
    ones = [1] * K
    zero_ok = crc_simple(zeros) == 0 == crc_reflected(zeros)
    ones_ok = crc_simple(ones) == crc_table(bits_to_bytes_msb(ones), table) == \
        reflect(crc_reflected_table(bits_to_bytes_lsb(ones), rtable), WIDTH)
    repeat_ok = crc_simple(bits) == r_simple and crc_table(data_msb, table) == r_table
    print(f"   • 300 випадкових повідомлень довжиною 8…2000 біт — усі 5 алгоритмів збігаються  {mark(all_ok)}")
    print(f"   • повідомлення з {K} нулів → CRC = 0x00                                    {mark(zero_ok)}")
    print(f"   • повідомлення з {K} одиниць → однаковий CRC у всіх алгоритмах            {mark(ones_ok)}")
    print(f"   • повторне обчислення того ж повідомлення дає той самий CRC                {mark(repeat_ok)}")

    # =======================================================================
    header(7, "НАВІЩО CRC: ВИЯВЛЕННЯ ПОМИЛКИ ПРИ ПЕРЕДАЧІ")
    pos = random.Random(7).randrange(K)
    damaged = bits.copy()
    damaged[pos] ^= 1
    r_damaged = crc_table(bits_to_bytes_msb(damaged), table)
    print(f"  Відправник передає повідомлення разом із CRC = {h8(r_simple)}.")
    print(f"  У каналі пошкоджено біт № {pos}: {bits[pos]} → {damaged[pos]}.")
    print(f"  Приймач обчислює CRC отриманого повідомлення: {h8(r_damaged)}  "
          f"≠ {h8(r_simple)} → помилку виявлено {mark(r_damaged != r_simple)}")
    codeword = bits + [int(c) for c in b8(r_simple)]
    print(f"\n  Повідомлення + дописаний CRC ({K + WIDTH} біт) ділиться на G(x) без остачі:")
    print(f"  CRC(повідомлення + {b8(r_simple)}) = {h8(crc_simple(codeword))}  "
          f"{mark(crc_simple(codeword) == 0)}  (так приймач перевіряє цілісність)")

    # =======================================================================
    header(8, "ВИМІРЮВАННЯ ЧАСУ")
    print(f"  Методика: {WARMUP} прогрівальних запусків, потім {SERIES} серій × {CALLS} обчислень;")
    print("  час серії ділиться на кількість обчислень → час одного обчислення CRC.")
    print("  Генерація повідомлення, друк і побудова таблиць у вимір НЕ входять.")
    print(f"  Платформа: {platform.system()} {platform.release()}, {platform.machine()}; "
          f"Python {platform.python_version()}; таймер time.perf_counter\n")
    print(DIM + "  вимірювання триває кілька секунд..." + RESET)

    bench = [
        ("Простий послідовний", crc_simple, (bits,)),
        ("Прямий табличний", crc_table, (data_msb, table)),
        ("Дзеркальний послідовний", crc_reflected, (bits,)),
        ("Дзеркальний табличний", crc_reflected_table, (data_lsb, rtable)),
        ("Стандартний CRC-8/DVB-S2", crc_standard, (data_msb,)),
    ]
    timings = {}
    for name, func, args in bench:
        if func is crc_standard:
            timings[name] = measure(lambda d: crc_standard(d, **CRC8_DVB_S2), *args)
        else:
            timings[name] = measure(func, *args)
    t_table = measure(make_table, calls=200)
    t_rtable = measure(make_reflected_table, calls=200)

    base = statistics.mean(timings["Простий послідовний"])
    rows = []
    for name, _, _ in bench:
        t = timings[name]
        rows.append([name, f"{statistics.mean(t):.2f}", f"{statistics.median(t):.2f}",
                     f"{statistics.stdev(t):.2f}", f"×{base / statistics.mean(t):.1f}",
                     "так" if "табличний" in name else "ні"])
    print_table(["Алгоритм", "Середнє, мкс", "Медіана, мкс", "Ст. відх., мкс",
                 "Прискорення", "Таблиця"], rows, "<>>>><")
    print(f"  Побудова прямої таблиці (одноразово):      {statistics.mean(t_table):8.2f} мкс")
    print(f"  Побудова дзеркальної таблиці (одноразово): {statistics.mean(t_rtable):8.2f} мкс")

    # =======================================================================
    header(9, "ДІАГРАМА СЕРЕДНЬОГО ЧАСУ (менше = швидше)")
    longest = max(statistics.mean(t) for t in timings.values())
    for name, _, _ in bench:
        mean = statistics.mean(timings[name])
        bar = "█" * max(1, round(mean / longest * 50))
        color = GREEN if "табличний" in name else YELLOW
        print(f"  {pad(name, 26)} {color}{bar}{RESET} {mean:.1f} мкс")

    # =======================================================================
    header(10, "РЕСУРСНА СКЛАДНІСТЬ")
    print_table(
        ["Алгоритм", "Одиниця", "Ітерацій (K=1000)", "Попередні витрати", "Дод. пам'ять", "Складність"],
        [
            ["Простий послідовний", "1 біт", f"K + n = {K + WIDTH}", "немає", "регістр 1 байт", "O(K)"],
            ["Прямий табличний", "1 байт", f"K / 8 = {K // 8}", "таблиця: 256×8 кроків", "256 байт", "O(K/8)"],
            ["Дзеркальний послідовний", "1 біт", f"K = {K}", "немає", "регістр 1 байт", "O(K)"],
            ["Дзеркальний табличний", "1 байт", f"K / 8 = {K // 8}", "таблиця: 256×8 кроків", "256 байт", "O(K/8)"],
            ["Стандартний (побітовий)", "1 байт", f"{K // 8}×8 = {K}", "немає", "регістр 1 байт", "O(K)"],
        ],
    )
    print("  Послідовні алгоритми на кожному біті роблять зсув, перевірку біта і, можливо, XOR.")
    print("  Табличні на кожному байті роблять лише XOR, звернення до таблиці (і зсув) —")
    print("  тобто 8 побітових кроків замінено одним зверненням до наперед обчисленої таблиці.")

    # =======================================================================
    header(11, "ВИСНОВОК")
    means = {n: statistics.mean(t) for n, t in timings.items()}
    fastest = min(means, key=means.get)
    slowest = max(means, key=means.get)
    print(f"  • Усі 4 обов'язкові алгоритми і стандартний CRC-8/DVB-S2 дали однаковий CRC = "
          f"{h8(r_simple)}")
    print("    (для дзеркальних — після дзеркального відображення бітів регістру).")
    print(f"  • Коректність підтверджено прикладом з Рис. 4.1 і значенням Check = 0xBC з табл. 4.1.")
    print(f"  • Найшвидший: {fastest} ({means[fastest]:.1f} мкс), "
          f"найповільніший: {slowest} ({means[slowest]:.1f} мкс).")
    t_avg = (means["Прямий табличний"] + means["Дзеркальний табличний"]) / 2
    s_avg = (means["Простий послідовний"] + means["Дзеркальний послідовний"]) / 2
    print(f"  • Табличні алгоритми в середньому у ~{s_avg / t_avg:.0f} разів швидші за послідовні:"
          f" {K // 8} ітерацій замість ~{K}.")
    print(f"  • Ціна прискорення — 256 байт пам'яті під таблицю та одноразова її побудова "
          f"(~{statistics.mean(t_table):.0f} мкс).")
    k_seq = means["Простий послідовний"] / means["Дзеркальний послідовний"]
    k_tab = means["Прямий табличний"] / means["Дзеркальний табличний"]
    if k_seq > 1.15 and k_tab > 1.15:
        print(f"  • Дзеркальні виявилися швидшими за прямі того ж типу (послідовний ×{k_seq:.1f},"
              f" табличний ×{k_tab:.1f}).")
        print("    Причина — менше операцій на кроці: при зсуві вправо зайві біти «випадають» самі,")
        print("    тому не потрібні маскування (& mask) і вставка біта (| bit); простий алгоритм")
        print(f"    до того ж обробляє ще {WIDTH} дописаних нулів. Кількість ітерацій та сама.")
    else:
        print(f"  • Дзеркальні та прямі алгоритми одного типу мають близький час "
              f"(×{k_seq:.1f} і ×{k_tab:.1f}),")
        print("    бо виконують однакову кількість ітерацій; дзеркальність сама по собі не прискорює.")
    print()


if __name__ == "__main__":
    main()
