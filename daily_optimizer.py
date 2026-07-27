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
- Cuarteo (combinar 2+ fincas en un viaje) en el grupo barato exige minimo
  8 pallets para Santa Maria, 12 para las demas. En el grupo caro no aplica
  minimo (confirmado con caso real: San Bartolo con 6-7P combinado con
  Juana Pio salio mas barato).
- Demetrio: maximo 2 viajes/dia, COMPARTIDOS entre ambos grupos (1 camion).
- Edwin: maximo 2 viajes/dia, solo aplica al grupo barato (1 camion).
"""
import itertools

GROUP_A = ['SAN BARTOLO', 'JUANA PIO']
GROUP_B = ['DOÑA FRANCIA', 'CHISPERO', 'SANTA MARIA', 'SALVAMENTO']
ALL_FARMS = ['JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA', 'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO']

CAP_YUBER, CAP_DEMETRIO, CAP_EDWIN = 26, 18, 24

DEMETRIO_A_COST = 850_000
DEMETRIO_B_COST = 550_000
EDWIN_B_COST = 600_000

EDWIN_EXCLUDED_B = {'SANTA MARIA'}
CUARTEO_MIN_B = {'SANTA MARIA': 8}
CUARTEO_MIN_DEFAULT_B = 12


def yuber_A(n):
    if n <= 0:
        return 0
    return 1_050_000 + max(0, n - 20) * 25_000


def yuber_B(n):
    if n <= 0:
        return 0
    return 630_000 + max(0, n - 20) * 25_000


# ───────────────────────── Grupo A (San Bartolo + Juana Pio) ─────────────────────────
def _best_group_a(total, demetrio_budget, _memo={}):
    key = (total, demetrio_budget)
    if key in _memo:
        return _memo[key]
    if total <= 0:
        return (0, ())
    best = None
    for s in range(1, min(total, CAP_YUBER) + 1):
        sub_cost, sub_trips = _best_group_a(total - s, demetrio_budget)
        cost = yuber_A(s) + sub_cost
        if best is None or cost < best[0]:
            best = (cost, (('Yuber', s),) + sub_trips)
    if demetrio_budget > 0:
        for s in range(1, min(total, CAP_DEMETRIO) + 1):
            sub_cost, sub_trips = _best_group_a(total - s, demetrio_budget - 1)
            cost = DEMETRIO_A_COST + sub_cost
            if best is None or cost < best[0]:
                best = (cost, (('Demetrio', s),) + sub_trips)
    _memo[key] = best
    return best


def _allocate_group_a(trip_sizes, sb_total, jp_total):
    """Reparte los pallets de San Bartolo y Juana Pio entre los viajes ya
    decididos (por tamano), priorizando San Bartolo primero en cada viaje."""
    trips = sorted(trip_sizes, key=lambda t: -t[1])
    sb_left, jp_left = sb_total, jp_total
    out = []
    for carrier, size in trips:
        take_sb = min(sb_left, size)
        take_jp = min(size - take_sb, jp_left)
        remaining = size - take_sb - take_jp
        if remaining > 0:
            take_sb += min(remaining, sb_left - take_sb)
        sb_left -= take_sb
        jp_left -= take_jp
        farms = {}
        if take_sb > 0:
            farms['SAN BARTOLO'] = take_sb
        if take_jp > 0:
            farms['JUANA PIO'] = take_jp
        out.append({'carrier': carrier, 'total': size, 'farms': farms})
    return out


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


def _cuarteo_ok_b(group, amounts):
    if len(group) <= 1:
        return True
    for f in group:
        mn = CUARTEO_MIN_B.get(f, CUARTEO_MIN_DEFAULT_B)
        if amounts[f] < mn:
            return False
    return True


def _group_options_b(group, amounts):
    total = sum(amounts[f] for f in group)
    if not _cuarteo_ok_b(group, amounts):
        return []
    opts = []
    if total <= CAP_YUBER:
        opts.append(('Yuber', yuber_B(total)))
    if total <= CAP_DEMETRIO:
        opts.append(('Demetrio', DEMETRIO_B_COST))
    if total <= CAP_EDWIN and not (set(group) & EDWIN_EXCLUDED_B):
        opts.append(('Edwin', EDWIN_B_COST))
    return opts


def _split_oversized_b(farm, amount):
    candidates = []
    for a in range(1, amount):
        b = amount - a
        if a > CAP_YUBER or b > CAP_YUBER:
            continue
        for ca, cca in _group_options_b([farm], {farm: a}):
            for cb, ccb in _group_options_b([farm], {farm: b}):
                dem = (ca == 'Demetrio') + (cb == 'Demetrio')
                edw = (ca == 'Edwin') + (cb == 'Edwin')
                candidates.append((cca + ccb, dem, edw,
                                    [{'carrier': ca, 'total': a, 'farms': {farm: a}},
                                     {'carrier': cb, 'total': b, 'farms': {farm: b}}]))
    return candidates


def _cell_combos_b(amounts):
    farms = [f for f in amounts if amounts[f] > 0]
    if not farms:
        return [(0, 0, 0, [])]
    oversized = [f for f in farms if amounts[f] > CAP_YUBER]
    normal = [f for f in farms if amounts[f] <= CAP_YUBER]
    oversized_choice_lists = [_split_oversized_b(f, amounts[f]) for f in oversized]
    normal_partition_options = [(0, 0, 0, [])]
    if normal:
        normal_partition_options = []
        for part in _partitions(normal):
            opts_per_group = []
            feasible = True
            for group in part:
                opts = _group_options_b(group, amounts)
                if not opts:
                    feasible = False
                    break
                opts_per_group.append((group, sum(amounts[f] for f in group), opts))
            if not feasible:
                continue
            choice_lists = [[(g, t, c, cost) for (c, cost) in opts] for (g, t, opts) in opts_per_group]
            for combo in itertools.product(*choice_lists):
                cost = sum(x[3] for x in combo)
                dem = sum(1 for x in combo if x[2] == 'Demetrio')
                edw = sum(1 for x in combo if x[2] == 'Edwin')
                trips = [{'carrier': c, 'total': t, 'farms': {f: amounts[f] for f in g}}
                         for (g, t, c, cost) in combo]
                normal_partition_options.append((cost, dem, edw, trips))
    combos = []
    for over_combo in itertools.product(*oversized_choice_lists) if oversized_choice_lists else [()]:
        over_cost = sum(x[0] for x in over_combo)
        over_dem = sum(x[1] for x in over_combo)
        over_edw = sum(x[2] for x in over_combo)
        over_trips = []
        for x in over_combo:
            over_trips.extend(x[3])
        for ncost, ndem, nedw, ntrips in normal_partition_options:
            combos.append((over_cost + ncost, over_dem + ndem, over_edw + nedw, over_trips + ntrips))
    return combos


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
    T_a = sb_total + jp_total

    b_amounts = {f: pallets[f] for f in GROUP_B}
    b_combos = _prune_strict(_cell_combos_b(b_amounts))
    if not b_combos:
        b_combos = [(0, 0, 0, [])]

    best = None
    for demA in [0, 1, 2]:
        costA, tripsA_sizes = _best_group_a(T_a, demA)
        for cb in b_combos:
            demB, edwB = cb[1], cb[2]
            if demA + demB <= 2 and edwB <= 2:
                total = costA + cb[0]
                if best is None or total < best[0]:
                    best = (total, demA, tripsA_sizes, cb)

    total_cost, demA, tripsA_sizes, cb = best
    tripsA = _allocate_group_a(list(tripsA_sizes), sb_total, jp_total)
    tripsB = cb[3]

    def _trip_cost(t, is_group_a):
        if t['carrier'] == 'Demetrio':
            return DEMETRIO_A_COST if is_group_a else DEMETRIO_B_COST
        if t['carrier'] == 'Edwin':
            return EDWIN_B_COST
        return yuber_A(t['total']) if is_group_a else yuber_B(t['total'])

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
