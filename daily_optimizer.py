"""
Optimizador de ruta diaria - Exportadora de Banano.

Logica validada con el usuario (julio 2026):
- Grupo "caro" (San Bartolo + Juana Pio), SIN Edwin. El costo de cada viaje
  depende solo del TOTAL de pallets que lleve (no de que finca vengan), asi
  que se optimiza como llenado de camiones sobre la suma de ambas fincas.
    Yuber:    $1.050.000 hasta 20P, +$25.000 por pallet adicional, tope 26P (mula nueva).
    Demetrio: $850.000 fijo, tope 18P.
- Grupo "barato" (Dona Francia, Chispero, Santa Maria), con Edwin disponible
  salvo para Santa Maria. Aqui si importa la finca porque hay minimos de
  pallets para poder cuartear (combinar 2+ fincas en un viaje) y Edwin no
  puede recoger Santa Maria.
    Yuber:    $630.000 hasta 20P, +$25.000 por pallet adicional, tope 26P.
    Demetrio: $550.000 fijo, tope 18P.
    Edwin:    $600.000 fijo, tope 24P (no Santa Maria).
- Cuarteo (combinar 2+ fincas en un viaje): sin minimo de pallets por finca
  en ningun grupo (regla de minimo 8P/12P eliminada en agosto 2026 — el
  optimizador puede combinar cualquier cantidad si sale mas barato).
- Demetrio: maximo 2 viajes/dia, COMPARTIDOS entre ambos grupos (1 camion).
- Edwin: maximo 2 viajes/dia, solo aplica al grupo barato (1 camion).
- Edwin SI puede recoger Juana Pio (habilitado agosto 2026), a $1.050.000 fijo
  (tarifa Chigorodo), tope 24P, y puede cuartear Juana Pio con fincas del
  grupo barato (Dona Francia, Chispero, Salvamento) en el mismo viaje. Edwin
  sigue SIN poder recoger San Bartolo ni Santa Maria.
- Recargo por cuarteo: cada viaje que combine 2 o mas fincas distintas suma
  $100.000 sobre el costo base del viaje (aplica a cualquier transportista,
  cualquier grupo). Un viaje con una sola finca no paga este recargo.
"""
import itertools
import functools

GROUP_A = ['SAN BARTOLO', 'JUANA PIO']
GROUP_B = ['DOÑA FRANCIA', 'CHISPERO', 'SANTA MARIA', 'SALVAMENTO']
ALL_FARMS = ['JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA', 'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO']

CAP_YUBER, CAP_DEMETRIO, CAP_EDWIN = 26, 18, 24

DEMETRIO_A_COST = 850_000
DEMETRIO_B_COST = 550_000
EDWIN_B_COST = 600_000
EDWIN_JP_COST = 1_050_000  # Edwin con Juana Pio (mezclada o no con grupo barato)
CUARTEO_SURCHARGE = 100_000  # recargo por viaje que mezcla 2+ fincas

EDWIN_EXCLUDED_B = {'SANTA MARIA'}


def yuber_A(n):
    if n <= 0:
        return 0
    return 1_050_000 + max(0, n - 20) * 25_000


def yuber_B(n):
    if n <= 0:
        return 0
    return 630_000 + max(0, n - 20) * 25_000


# ───────────────────────── Grupo A (San Bartolo + Juana Pio) ─────────────────────────
def _cost_a(carrier, total, mixed):
    base = yuber_A(total) if carrier == 'Yuber' else DEMETRIO_A_COST
    return base + (CUARTEO_SURCHARGE if mixed else 0)


def _best_group_a(sb_remaining, jp_remaining, demetrio_budget, _memo={}):
    """DP sobre (San Bartolo restante, Juana Pio restante, presupuesto de
    Demetrio). Se rastrea cada finca por separado (en vez de solo el total)
    para saber, viaje a viaje, si mezcla San Bartolo + Juana Pio y por lo
    tanto paga el recargo de cuarteo."""
    key = (sb_remaining, jp_remaining, demetrio_budget)
    if key in _memo:
        return _memo[key]
    if sb_remaining <= 0 and jp_remaining <= 0:
        _memo[key] = (0, ())
        return _memo[key]

    best = None

    def try_carrier(carrier, cap, budget_ok):
        nonlocal best
        if not budget_ok:
            return
        for sb_take in range(0, min(sb_remaining, cap) + 1):
            max_jp = min(jp_remaining, cap - sb_take)
            for jp_take in range(0, max_jp + 1):
                total = sb_take + jp_take
                if total == 0:
                    continue
                mixed = sb_take > 0 and jp_take > 0
                cost = _cost_a(carrier, total, mixed)
                next_budget = demetrio_budget - 1 if carrier == 'Demetrio' else demetrio_budget
                sub_cost, sub_trips = _best_group_a(
                    sb_remaining - sb_take, jp_remaining - jp_take, next_budget)
                total_cost = cost + sub_cost
                if best is None or total_cost < best[0]:
                    farms = {}
                    if sb_take:
                        farms['SAN BARTOLO'] = sb_take
                    if jp_take:
                        farms['JUANA PIO'] = jp_take
                    trip = {'carrier': carrier, 'total': total, 'farms': farms}
                    best = (total_cost, (trip,) + sub_trips)

    try_carrier('Yuber', CAP_YUBER, True)
    try_carrier('Demetrio', CAP_DEMETRIO, demetrio_budget > 0)

    _memo[key] = best
    return best


# ───────────────────────── Grupo B (Doña Francia, Chispero, Santa Maria) ─────────────────────────
def _partitions(collection):
    if len(collection) == 1:
        yield [collection]
        return
    first = collection[0]
    for smaller in _partitions(collection[1:]):
        for i, subset in enumerate(smaller):
            yield smaller[:i] + [[first] + subset] + smaller[i + 1:]
        yield [[first]] + smaller


def _farm_split_options(farm, amount):
    """Formas de partir el pedido de una finca en 1 o 2 piezas que quepan
    cada una en un camion (<=CAP_YUBER). Sin division si ya cabe entera.
    Cada pieza queda disponible para combinarse con piezas de OTRAS fincas
    (a diferencia de la version anterior, que solo dejaba combinar piezas
    de fincas que ya cabian solas en un camion)."""
    if amount <= CAP_YUBER:
        return [[(farm, amount)]]
    opts = []
    for a in range(1, amount):
        b = amount - a
        if a <= CAP_YUBER and b <= CAP_YUBER:
            opts.append([(farm, a), (farm, b)])
    return opts


@functools.lru_cache(maxsize=None)
def _group_cost_options_cached(farms_in_group, total):
    """El costo/las opciones de un grupo (viaje) dependen solo de QUE fincas
    lo componen y del TOTAL de pallets -- nunca de como ese total se repartio
    en piezas para llegar ahi. Antes esto se recalculaba desde cero para
    cada (idx_group, pieces) posible entre todas las combinaciones de split
    y particiones evaluadas (decenas de millones de llamadas para pedidos
    grandes, siendo el cuello de botella real del calculo). Cachear por
    (fincas, total) -- un espacio minusculo de combinaciones reales -- da el
    mismo resultado exacto pero evita rehacer el mismo trabajo una y otra
    vez."""
    surcharge = CUARTEO_SURCHARGE if len(farms_in_group) > 1 else 0
    opts = []
    if 'JUANA PIO' in farms_in_group:
        # Puente Juana Pio -> grupo barato: solo Edwin puede recogerla aqui,
        # a su tarifa de Chigorodo, sola o cuarteada con fincas del grupo
        # barato. Santa Maria sigue excluida (no se puede mezclar con Edwin).
        if total <= CAP_EDWIN and not (farms_in_group & EDWIN_EXCLUDED_B):
            opts.append(('Edwin', EDWIN_JP_COST + surcharge))
        return opts
    if total <= CAP_YUBER:
        opts.append(('Yuber', yuber_B(total) + surcharge))
    if total <= CAP_DEMETRIO:
        opts.append(('Demetrio', DEMETRIO_B_COST + surcharge))
    if total <= CAP_EDWIN and not (farms_in_group & EDWIN_EXCLUDED_B):
        opts.append(('Edwin', EDWIN_B_COST + surcharge))
    return opts


def _group_cost_options_pieces(idx_group, pieces):
    farms_in_group = frozenset(pieces[i][0] for i in idx_group)
    total = sum(pieces[i][1] for i in idx_group)
    return _group_cost_options_cached(farms_in_group, total)


_partitions_cache = {}


def _cached_partitions(n):
    """_partitions(range(n)) depende solo de n (la cantidad de piezas), no de
    cuales sean esas piezas. Cada opcion de split de una finca siempre
    produce la MISMA cantidad de piezas (1 si cabe entera, 2 si no), asi que
    n es constante para todas las combinaciones de split dentro de una misma
    llamada a _cell_combos_b -- y tambien se repite entre llamadas (p.ej. al
    variar Juana Pio de 0 a jp_total en optimize_day). Antes se regeneraba
    esta lista de particiones (que crece como el numero de Bell) en cada
    iteracion del loop de splits, haciendo el mismo trabajo cientos de veces
    de forma identica. Cachearla por n elimina ese trabajo repetido sin
    cambiar el resultado."""
    cached = _partitions_cache.get(n)
    if cached is None:
        cached = list(_partitions(list(range(n))))
        _partitions_cache[n] = cached
    return cached


def _cell_combos_b(amounts):
    """Devuelve, por cada combinacion (viajes de Demetrio, viajes de Edwin)
    factible, el trip-set de menor costo. Se poda en el momento (en vez de
    acumular todas las combinaciones) porque con varias fincas grandes a la
    vez el numero de combinaciones crudas puede dispararse a decenas de
    millones y agotar memoria."""
    farms = [f for f in amounts if amounts[f] > 0]
    if not farms:
        return [(0, 0, 0, [])]

    split_choices = [_farm_split_options(f, amounts[f]) for f in farms]

    best_by_key = {}
    for split_combo in itertools.product(*split_choices):
        pieces = [piece for group in split_combo for piece in group]
        n = len(pieces)
        for part in _cached_partitions(n):
            opts_per_group = []
            feasible = True
            for idx_group in part:
                opts = _group_cost_options_pieces(idx_group, pieces)
                if not opts:
                    feasible = False
                    break
                opts_per_group.append((idx_group, opts))
            if not feasible:
                continue
            choice_lists = [[(g, c, cost) for (c, cost) in opts] for (g, opts) in opts_per_group]
            for combo in itertools.product(*choice_lists):
                dem = sum(1 for x in combo if x[1] == 'Demetrio')
                edw = sum(1 for x in combo if x[1] == 'Edwin')
                if dem > 2 or edw > 2:
                    continue
                cost = sum(x[2] for x in combo)
                key = (dem, edw)
                prev = best_by_key.get(key)
                if prev is not None and cost >= prev[0]:
                    continue
                trips = []
                for (idx_group, carrier, _tcost) in combo:
                    farms_amt = {}
                    for i in idx_group:
                        f, sz = pieces[i]
                        farms_amt[f] = farms_amt.get(f, 0) + sz
                    trips.append({'carrier': carrier, 'total': sum(farms_amt.values()), 'farms': farms_amt})
                best_by_key[key] = (cost, dem, edw, trips)
    return list(best_by_key.values())


def _prune_strict(combos):
    by_key = {}
    for cost, dem, edw, trips in combos:
        if dem > 2 or edw > 2:
            continue
        key = (dem, edw)
        if key not in by_key or cost < by_key[key][0]:
            by_key[key] = (cost, dem, edw, trips)
    return list(by_key.values())


# ───────────────────────── Optimizador principal ─────────────────────────
def optimize_day(pallets):
    """
    pallets: dict con llaves 'JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA',
             'CHISPERO', 'SAN BARTOLO' (0 si no hay pedido ese dia).
    Retorna: {'trips': [{'carrier', 'total', 'farms': {finca: pallets}}], 'total_cost': int}
    """
    pallets = {f: int(pallets.get(f, 0) or 0) for f in ALL_FARMS}

    sb_total = pallets['SAN BARTOLO']
    jp_total = pallets['JUANA PIO']

    # Juana Pio se puede repartir entre el grupo A (con San Bartolo, via
    # Yuber/Demetrio) y el grupo B (via Edwin, sola o cuarteada con Dona
    # Francia/Chispero/Salvamento). Se prueba cada reparto posible.
    best = None
    for jp_to_b in range(0, jp_total + 1):
        jp_to_a = jp_total - jp_to_b

        b_amounts = {f: pallets[f] for f in GROUP_B}
        b_amounts['JUANA PIO'] = jp_to_b
        b_combos = _prune_strict(_cell_combos_b(b_amounts))
        if jp_to_b > 0 and not b_combos:
            continue  # este reparto no es factible (p.ej. excede tope Edwin)
        if not b_combos:
            b_combos = [(0, 0, 0, [])]

        for demA in [0, 1, 2]:
            costA, tripsA = _best_group_a(sb_total, jp_to_a, demA)
            for cb in b_combos:
                demB, edwB = cb[1], cb[2]
                if demA + demB <= 2 and edwB <= 2:
                    total = costA + cb[0]
                    if best is None or total < best[0]:
                        best = (total, tripsA, cb)

    total_cost, tripsA, cb = best
    tripsB = cb[3]

    def _trip_cost(t, is_group_a):
        farms_in_trip = t.get('farms', {})
        surcharge = CUARTEO_SURCHARGE if len(farms_in_trip) > 1 else 0
        if t['carrier'] == 'Demetrio':
            base = DEMETRIO_A_COST if is_group_a else DEMETRIO_B_COST
            return base + surcharge
        if t['carrier'] == 'Edwin':
            base = EDWIN_JP_COST if 'JUANA PIO' in farms_in_trip else EDWIN_B_COST
            return base + surcharge
        base = yuber_A(t['total']) if is_group_a else yuber_B(t['total'])
        return base + surcharge

    all_trips = []
    for t in tripsA:
        if t['total'] > 0:
            t['cost'] = _trip_cost(t, True)
            all_trips.append(t)
    for t in tripsB:
        if t['total'] > 0:
            t['cost'] = _trip_cost(t, False)
            all_trips.append(t)

    return {'trips': all_trips, 'total_cost': total_cost}
