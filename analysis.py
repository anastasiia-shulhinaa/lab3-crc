"""
Лабораторна робота № 3. Порівняльний аналіз ресурсної складності алгоритмів CRC.
Варіант 16: CRC-8, x^8 + x^7 + x^6 + x^4 + x^2 + 1.

Що робить програма:
  1. рахує кількість XOR з поліномом (X) і порівнює з теорією E[X] = K/2;
  2. вимірює середній час на 500 різних випадкових повідомленнях;
  3. вимірює час для K = 1000 ... 32000 і перевіряє, що T(K) = Θ(K);
  4. порівнює теоретичну кількість операцій з виміряним часом;
  5. перевіряє коректність порівняння (таймер, перетворення бітів у байти);
  6. порівнює теоретичну і фактичну пам'ять у Python.

Запуск:  python analysis.py            (python analysis.py --json файл.json - ще й зберегти числа)
"""

import gc
import json
import math
import platform
import random
import statistics
import sys
import time
import tracemalloc

from crc_algorithms import (
    WIDTH, POLY, CRC8_DVB_S2,
    reflect, bits_to_bytes_msb, bits_to_bytes_lsb, bytes_to_bits,
    crc_simple, crc_simple_trace, make_table, crc_table,
    crc_reflected, make_reflected_table, crc_reflected_table, crc_standard,
)
from main import BOLD, DIM, RESET, GREEN, YELLOW, header, print_table, mark, pad, measure

K = 1000
SEED = 16
MESSAGES = 500          # кількість різних випадкових повідомлень
CALLS_PER_MESSAGE = 20  # обчислень CRC для кожного повідомлення
SIZES = [1000, 2000, 4000, 8000, 16000, 32000]

TABLE = make_table()
RTABLE = make_reflected_table()


def crc_std(data):
    return crc_standard(data, **CRC8_DVB_S2)


# (назва, функція, який вхід потрібен, додаткові аргументи)
ALGS = [
    ("Простий послідовний", crc_simple, "bits", ()),
    ("Прямий табличний", crc_table, "msb", (TABLE,)),
    ("Дзеркальний послідовний", crc_reflected, "bits", ()),
    ("Дзеркальний табличний", crc_reflected_table, "lsb", (RTABLE,)),
    ("Стандартний CRC-8/DVB-S2", crc_std, "msb", ()),
]
NAMES = [a[0] for a in ALGS]

# Кількість елементарних операцій на одну ітерацію основного циклу (див. звіт, розділ 4).
# Рахуємо: крок циклу, зсуви, AND, OR, XOR, віднімання, перевірку умови, індексацію.
# XOR з поліномом (виконується не завжди) рахується окремо - це X.
OPS = {
    "Простий послідовний":      dict(per_iter=8, iters=lambda k: k + WIDTH, xor=True, outer=0),
    "Прямий табличний":         dict(per_iter=8, iters=lambda k: k // 8, xor=False, outer=0),
    "Дзеркальний послідовний":  dict(per_iter=5, iters=lambda k: k, xor=True, outer=0),
    "Дзеркальний табличний":    dict(per_iter=6, iters=lambda k: k // 8, xor=False, outer=0),
    "Стандартний CRC-8/DVB-S2": dict(per_iter=5, iters=lambda k: k, xor=True, outer=5),
}


def ops_count(name, k, x):
    o = OPS[name]
    w = o["per_iter"] * o["iters"](k) + o["outer"] * (k // 8)
    return w + (x if o["xor"] else 0)


def make_message(bits):
    return {"bits": bits, "msb": bits_to_bytes_msb(bits), "lsb": bits_to_bytes_lsb(bits)}


def call(alg, msg):
    name, func, key, extra = alg
    return func(msg[key], *extra)


def time_calls(alg, msg, calls):
    name, func, key, extra = alg
    arg = msg[key]
    start = time.perf_counter()
    for _ in range(calls):
        func(arg, *extra)
    return (time.perf_counter() - start) / calls * 1e6


def crc_value(alg, msg):
    """CRC, приведений до прямого вигляду (для дзеркальних - відображений)."""
    value = call(alg, msg)
    return reflect(value, WIDTH) if alg[0].startswith("Дзеркальний") else value


def xor_count(bits):
    """X - скільки разів простий алгоритм виконав XOR з поліномом."""
    _, steps = crc_simple_trace(bits, WIDTH, POLY)
    return sum(popped for _, popped, _ in steps)


def slope(xs, ys):
    """Нахил a прямої log T = a log K + b (метод найменших квадратів)."""
    lx, ly = [math.log(x) for x in xs], [math.log(y) for y in ys]
    mx, my = statistics.mean(lx), statistics.mean(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def main():
    out = {}
    print(BOLD + "\n  ЛАБОРАТОРНА РОБОТА № 3. ПОРІВНЯЛЬНИЙ АНАЛІЗ РЕСУРСНОЇ СКЛАДНОСТІ АЛГОРИТМІВ CRC" + RESET)
    print(DIM + f"  Платформа: {platform.system()} {platform.release()}, Python {platform.python_version()}"
          + RESET)

    random.seed(SEED)
    base_bits = [random.randint(0, 1) for _ in range(K)]
    base = make_message(base_bits)

    # =======================================================================
    header(1, "КІЛЬКІСТЬ XOR З ПОЛІНОМОМ X (від неї залежить час побітових алгоритмів)")
    x_seed = xor_count(base_bits)
    rng = random.Random(2026)
    messages = [make_message([rng.randint(0, 1) for _ in range(K)]) for _ in range(MESSAGES)]
    xs = [xor_count(m["bits"]) for m in messages]
    print("  Перші n = 8 кроків простого алгоритму висувають нулі початкового регістру,")
    print("  далі висунутий біт рівноймовірно 0 або 1  ⇒  теорія: E[X] = K / 2 = 500, 0 ≤ X ≤ K.\n")
    print_table(["Повідомлення", "X", "E[X] = K/2"], [
        [f"seed = {SEED} (основне)", x_seed, K // 2],
        [f"{MESSAGES} випадкових: середнє", f"{statistics.mean(xs):.1f}", K // 2],
        [f"{MESSAGES} випадкових: мін … макс", f"{min(xs)} … {max(xs)}", "0 … 1000"],
    ], "<>>")
    out["x"] = dict(seed=x_seed, mean=statistics.mean(xs), min=min(xs), max=max(xs))

    # =======================================================================
    header(2, f"СЕРЕДНІЙ ЧАС НА {MESSAGES} РІЗНИХ ПОВІДОМЛЕННЯХ (K = {K})")
    print(f"  Для кожного з {MESSAGES} повідомлень кожен алгоритм виконує 3 серії по {CALLS_PER_MESSAGE} обчислень;")
    print("  час повідомлення = медіана 3 серій (відкидає випадкові переривання ОС).")
    print(f"  Усього {MESSAGES * 3 * CALLS_PER_MESSAGE * len(ALGS)} обчислень CRC; алгоритми чергуються на тому самому")
    print("  повідомленні; таблиці побудовано заздалегідь; збирач сміття вимкнено (як у timeit).\n")
    print(DIM + "  вимірювання триває кілька секунд..." + RESET)
    times = {n: [] for n in NAMES}
    agree = True
    gc.disable()
    for msg in messages[:20]:                   # прогрів процесора та інтерпретатора
        for alg in ALGS:
            time_calls(alg, msg, CALLS_PER_MESSAGE)
    for msg in messages:
        values = {crc_value(a, msg) for a in ALGS}
        agree &= len(values) == 1
        for alg in ALGS:
            series = [time_calls(alg, msg, CALLS_PER_MESSAGE) for _ in range(3)]
            times[alg[0]].append(statistics.median(series))
    gc.enable()
    multi = {}
    rows = []
    base_mean = statistics.mean(times[NAMES[0]])
    for n in NAMES:
        t = times[n]
        m, s = statistics.mean(t), statistics.stdev(t)
        ci = 1.96 * s / math.sqrt(len(t))
        multi[n] = dict(mean=m, std=s, ci=ci, min=min(t), max=max(t), median=statistics.median(t))
        rows.append([n, f"{m:.2f}", f"± {ci:.2f}", f"{statistics.median(t):.2f}", f"{s:.2f}",
                     f"{min(t):.1f} … {max(t):.1f}", f"×{base_mean / m:.1f}"])
    print_table(["Алгоритм", "Середнє, мкс", "95% ДІ", "Медіана", "Ст. відх.", "Мін … макс",
                 "Прискорення"], rows, "<>>>>>>")
    print(f"  Усі алгоритми дали однаковий CRC на всіх {MESSAGES} повідомленнях   {mark(agree)}")
    out["multi"] = multi
    out["agree"] = agree

    # =======================================================================
    header(3, "МАСШТАБУВАННЯ: ЗАЛЕЖНІСТЬ ЧАСУ ВІД ДОВЖИНИ ПОВІДОМЛЕННЯ K")
    print("  Для кожного K — нове випадкове повідомлення; 5 серій, у серії ≈ 30 мс обчислень.\n")
    print(DIM + "  вимірювання триває кілька секунд..." + RESET)
    scale = {n: [] for n in NAMES}
    gc.disable()
    for k in SIZES:
        r = random.Random(k)
        msg = make_message([r.randint(0, 1) for _ in range(k)])
        for name, func, key, extra in ALGS:
            est = time_calls((name, func, key, extra), msg, 3)
            calls = max(5, round(30000 / est))
            series = measure(func, msg[key], *extra, calls=calls, series=5, warmup=3)
            scale[name].append(statistics.mean(series))
    gc.enable()
    rows = []
    for n in NAMES:
        rows.append([n] + [f"{t:.1f}" for t in scale[n]])
    print("  Середній час одного обчислення, мкс:")
    print_table(["Алгоритм"] + [f"K={k}" for k in SIZES], rows, "<" + ">" * len(SIZES))
    rows = []
    slopes = {}
    for n in NAMES:
        per_bit = [t / k * 1000 for t, k in zip(scale[n], SIZES)]
        slopes[n] = slope(SIZES, scale[n])
        rows.append([n] + [f"{v:.1f}" for v in per_bit] + [f"{slopes[n]:.3f}"])
    print("  Час на один біт T(K)/K, нс, і нахил a у log T = a·log K + b:")
    print_table(["Алгоритм"] + [f"K={k}" for k in SIZES] + ["нахил a"], rows,
                "<" + ">" * (len(SIZES) + 1))
    lin_ok = all(abs(a - 1) < 0.1 for a in slopes.values())
    print(f"  Для всіх алгоритмів a ≈ 1, тобто T(K) = Θ(K)   {mark(lin_ok)}")
    out["scale"] = dict(sizes=SIZES, times=scale, slopes=slopes)

    # =======================================================================
    header(4, "ТЕОРЕТИЧНА КІЛЬКІСТЬ ОПЕРАЦІЙ W(K) ПРОТИ ВИМІРЯНОГО ЧАСУ (K = 1000)")
    x_mean = statistics.mean(xs)
    w_simple = ops_count(NAMES[0], K, x_mean)
    rows = []
    ops = {}
    for n in NAMES:
        o = OPS[n]
        w = ops_count(n, K, x_mean)
        pred = w_simple / w
        meas = multi[NAMES[0]]["mean"] / multi[n]["mean"]
        ops[n] = dict(per_iter=o["per_iter"], iters=o["iters"](K), w=w, pred=pred, meas=meas,
                      ns_per_op=multi[n]["mean"] / w * 1000)
        per_iter = f"{o['per_iter']} (+5/байт)" if o["outer"] else o["per_iter"]
        rows.append([n, o["iters"](K), per_iter, "X" if o["xor"] else "—",
                     f"{w:.0f}", f"×{pred:.2f}", f"×{meas:.2f}", f"{ops[n]['ns_per_op']:.1f}"])
    print(f"  W = (операцій на ітерацію) · (ітерацій) + X,  X ≈ {x_mean:.0f};  для стандартного ще 5 операцій на байт\n")
    print_table(["Алгоритм", "Ітерацій", "Оп./ітер.", "XOR", "W (операцій)", "Прогноз",
                 "Виміряно", "нс/операцію"], rows, "<>>c>>>>")
    print("  Прогноз = W(простий) / W(алгоритм);  виміряно = час(простий) / час(алгоритм).")
    out["ops"] = ops
    out["x_used"] = x_mean
    build = measure(make_table, calls=200, series=5, warmup=5)
    out["build"] = statistics.mean(build)
    w_build = 256 * (4 + 8 * 5) + 0.5 * 256 * 8
    m_star = w_build / (w_simple - ops_count(NAMES[1], K, x_mean))
    m_meas = statistics.mean(build) / (multi[NAMES[0]]["mean"] - multi[NAMES[1]]["mean"])
    print(f"\n  Побудова таблиці: W_build ≈ {w_build:.0f} операцій, виміряно {statistics.mean(build):.1f} мкс.")
    print(f"  Таблиця окуповується, коли m·W(простий) > W_build + m·W(табличний):")
    print(f"  теорія m > {m_star:.2f},  вимірювання m > {m_meas:.2f}  ⇒  з {math.ceil(max(m_star, m_meas))}-го повідомлення")
    out["w_build"] = w_build
    out["m_star"] = m_star
    out["m_meas"] = m_meas

    # =======================================================================
    header(5, "КОРЕКТНІСТЬ ПОРІВНЯННЯ ШВИДКОДІЇ")
    info = time.get_clock_info("perf_counter")
    shortest = CALLS_PER_MESSAGE * min(m["min"] for m in multi.values())   # найкоротша серія
    print(f"  Таймер perf_counter: роздільна здатність {info.resolution * 1e9:.0f} нс, монотонний: "
          f"{info.monotonic}")
    print(f"  Найкоротший виміряний інтервал: {shortest:.0f} мкс  ⇒  похибка квантування ≤ "
          f"{info.resolution * 1e6 / shortest * 100:.3f} %")
    out["timer_res_ns"] = info.resolution * 1e9
    out["shortest_us"] = shortest

    conv = {
        "bits → байти (старший біт першим)": statistics.mean(
            measure(bits_to_bytes_msb, base_bits, calls=2000, series=5, warmup=50)),
        "bits → байти (молодший біт першим)": statistics.mean(
            measure(bits_to_bytes_lsb, base_bits, calls=2000, series=5, warmup=50)),
        "байти → bits": statistics.mean(
            measure(bytes_to_bits, base["msb"], calls=2000, series=5, warmup=50)),
    }
    print("\n  Табличні алгоритми отримують готові байти. Якщо повідомлення задане як список бітів,")
    print("  перетворення теж коштує часу — порівняємо чесно, з ним і без нього:\n")
    print_table(["Перетворення (K = 1000)", "Час, мкс"], [[k, f"{v:.2f}"] for k, v in conv.items()], "<>")
    t = {n: multi[n]["mean"] for n in NAMES}
    conv_msb = conv["bits → байти (старший біт першим)"]
    conv_lsb = conv["bits → байти (молодший біт першим)"]
    rows = [
        ["Простий послідовний", f"{t[NAMES[0]]:.1f}", f"{t[NAMES[0]]:.1f}", f"{t[NAMES[0]]:.1f}"],
        ["Прямий табличний", f"{t[NAMES[1]]:.1f}", f"{t[NAMES[1]] + conv_msb:.1f}",
         f"{t[NAMES[1]] + conv_msb + out['build']:.1f}"],
        ["Дзеркальний послідовний", f"{t[NAMES[2]]:.1f}", f"{t[NAMES[2]]:.1f}", f"{t[NAMES[2]]:.1f}"],
        ["Дзеркальний табличний", f"{t[NAMES[3]]:.1f}", f"{t[NAMES[3]] + conv_lsb:.1f}",
         f"{t[NAMES[3]] + conv_lsb + out['build']:.1f}"],
    ]
    print_table(["Алгоритм", "Лише CRC", "+ перетворення", "+ перетв. + таблиця"], rows, "<>>>")
    out["conv"] = conv

    # =======================================================================
    header(6, "ПАМ'ЯТЬ: ТЕОРІЯ ПРОТИ ФАКТИЧНОЇ ПАМ'ЯТІ PYTHON")
    small_cached = all(v is int(str(v)) for v in TABLE + RTABLE)
    mem = [
        ["Регістр CRC (одне число)", "n = 8 бітів = 1 байт", sys.getsizeof(0x8F)],
        ["Таблиця: list з 256 int", "256 · 8 бітів = 256 байтів", sys.getsizeof(TABLE)],
        ["Таблиця: bytes(256)", "256 байтів", sys.getsizeof(bytes(TABLE))],
        ["Повідомлення: list з 1000 int", "1000 бітів = 125 байтів", sys.getsizeof(base_bits)],
        ["Повідомлення: bytes(125)", "125 байтів", sys.getsizeof(base["msb"])],
        ["Один int у Python (напр. 1)", "1 біт", sys.getsizeof(1)],
    ]
    print_table(["Об'єкт", "Теорія", "Python, байтів"], [[a, b, c] for a, b, c in mem], "<<>")
    print(f"  Усі 512 значень обох таблиць — кешовані «малі» int (-5…256), спільні для всієї")
    print(f"  програми, тому list зберігає лише 256 посилань по 8 байтів   {mark(small_cached)}")
    out["mem"] = mem
    out["small_cached"] = small_cached

    print("\n  Додаткова пам'ять під час ОДНОГО обчислення CRC (пік за tracemalloc):\n")
    tracemalloc.start()
    peaks = {}
    rows = []
    theory = {
        "Простий послідовний": "O(1) — регістр",
        "Прямий табличний": "O(1) + таблиця",
        "Дзеркальний послідовний": "O(1) — регістр",
        "Дзеркальний табличний": "O(1) + таблиця",
        "Стандартний CRC-8/DVB-S2": "O(1) — регістр",
    }
    for alg in ALGS:
        call(alg, base)
        tracemalloc.reset_peak()
        before = tracemalloc.get_traced_memory()[0]
        call(alg, base)
        peak = tracemalloc.get_traced_memory()[1] - before
        peaks[alg[0]] = peak
        rows.append([alg[0], theory[alg[0]], peak])
    tracemalloc.stop()
    print_table(["Алгоритм", "Теорія (дод. пам'ять)", "Пік, байтів"], rows, "<<>")
    print("  Простий алгоритм копіює список бітів і дописує 8 нулів — звідси O(K) пам'яті в реалізації.")
    out["peaks"] = peaks
    print()

    if "--json" in sys.argv:
        path = sys.argv[sys.argv.index("--json") + 1]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
