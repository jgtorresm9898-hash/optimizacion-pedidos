"""
Optimizador de ruta diaria - Exportadora de Banano.

Logica validada con el usuario (julio-octubre 2026):

Transportistas (octubre 2026): solo Yuber y Demetrio. Edwin (su carro de
24P y el Trailer Azul) ya no trabaja -- se quito del todo, incluido el
escenario "Optimizacion con dos viajes Edwin".

- Yuber: camiones ILIMITADOS de 24P, van a todas las fincas (incluida
  Salvamento), sin tope de viajes/dia.
  Ademas tiene disponibles MAXIMO 2 camiones de 26P:
    * cada uno hace maximo 1 viaje por dia (o sea, maximo 2 viajes de
      26P por dia entre los dos);
    * NO pueden entrar a Salvamento.
  Un viaje de Yuber de 25 o 26 pallets solo se puede hacer en uno de esos
  camiones de 26P. Misma tarifa para todos los camiones de Yuber:
    Chigorodo: $1.050.000 hasta 20P, +$37.500 por pallet adicional.
    Apartado:  $630.000 hasta 20P, +$25.000 por pallet adicional.
- Demetrio: $850.000 Chigorodo / $550.000 Apartado, fijo, tope 18P.
  Maximo 2 viajes/dia, COMPARTIDOS entre ambos municipios (1 camion).
- Chigorodo = San Bartolo + Juana Pio. Apartado = Dona Francia, Chispero,
  Santa Maria, Salvamento. Cada viaje es de un solo municipio (la app no
  mezcla Chigorodo con Apartado).
- Cuarteo (tarifas de septiembre 2026): Demetrio nunca cobra cuarteo.
  Yuber: cuartear fincas del MISMO municipio no tiene recargo.

Motor de calculo: solver exacto de programacion entera (Google OR-Tools
CP-SAT). Se modelan "cupos" de viaje por transportista/municipio, se deja
que CUALQUIER combinacion de pallets de cualquier finca entre en cualquier
cupo elegible, y se minimiza el costo total sujeto a los topes de
capacidad y de viajes/dia.
"""
import math
from ortools.sat.python import cp_model

GROUP_A = ['SAN BARTOLO', 'JUANA PIO']
GROUP_B = ['DOÑA FRANCIA', 'CHISPERO', 'SANTA MARIA', 'SALVAMENTO']
ALL_FARMS = ['JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA', 'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO']

CAP_YUBER = 24          # camiones normales de Yuber (ilimitados)
CAP_YUBER_26 = 26       # camiones grandes de Yuber
MAX_VIAJES_YUBER_26 = 2 # 2 camiones de 26P x 1 viaje/dia cada uno
CAP_DEMETRIO = 18

CARRIERS = ['YUBER', 'DEMETRIO']
CARRIER_LABELS = {'YUBER': 'Yuber', 'DEMETRIO': 'Demetrio'}

DEMETRIO_A_COST = 850_000
DEMETRIO_B_COST = 550_000
YUBER_A_BASE = 1_050_000
YUBER_B_BASE = 630_000
YUBER_OVERAGE_CHIG = 37_500  # Yuber Chigorodo: por pallet por encima de 20P
YUBER_OVERAGE_APTO = 25_000  # Yuber Apartado: por pallet por encima de 20P
YUBER_INCLUDED = 20          # pallets incluidos en la tarifa base de Yuber
# Freno interno de cuarteo (NO se cobra, no aparece en ningun total): la app
# "hace de cuenta" que cada parada extra de un viaje cuesta $100.000. Asi
# solo cuartea si de verdad ahorra mas que eso y las rutas quedan ordenadas.
# Los costos que se muestran son los reales (sin este freno).
FRENO_CUARTEO = 100_000


def yuber_A(n):
    if n <= 0:
        return 0
    return YUBER_A_BASE + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE_CHIG


def yuber_B(n):
    if n <= 0:
        return 0
    return YUBER_B_BASE + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE_APTO


# ───────────────────────── Modelo CP-SAT ─────────────────────────
def _num_slots(total_demand, cap, minimum=1, margin=1):
    """Cuantos 'cupos' de viaje de Yuber (sin tope de viajes/dia) alcanzan
    para cubrir, en el peor caso, toda la demanda de ese municipio."""
    if total_demand <= 0:
        return minimum
    return max(minimum, math.ceil(total_demand / cap) + margin)


def _or_bin_from_list(model, bins, name):
    """Variable binaria = OR(bins)."""
    r = model.NewBoolVar(name)
    for b in bins:
        model.Add(r >= b)
    model.Add(r <= sum(bins))
    return r


def _extra_stops(model, bins, name):
    """(fincas distintas en el viaje) - 1, sin bajar de 0."""
    r = model.NewIntVar(0, max(0, len(bins) - 1), name)
    model.Add(r >= sum(bins) - 1)
    return r


def _over_two_farms(model, bins, name):
    """Fincas por encima de 2 en el viaje -- solo para desempatar (se
    prefiere no mezclar 3+ fincas en un camion si cuesta lo mismo)."""
    r = model.NewIntVar(0, max(0, len(bins) - 2), name)
    model.Add(r >= sum(bins) - 2)
    return r


def optimize_day(pallets, unavailable_carriers=None):
    """
    pallets: dict con llaves 'JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA',
             'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO' (0 si no hay pedido).
    unavailable_carriers: set/lista opcional con los conductores NO
             disponibles ese dia ('YUBER', 'DEMETRIO').
    Retorna: {'trips': [{'carrier', 'total', 'farms': {finca: pallets}, 'cost'}],
              'total_cost': int, 'notas': [str]}
    """
    unavailable_carriers = set(unavailable_carriers or [])
    d = {f: int(pallets.get(f, 0) or 0) for f in ALL_FARMS}
    if sum(d.values()) == 0:
        return {'trips': [], 'total_cost': 0, 'notas': []}

    SB, JP = 'SAN BARTOLO', 'JUANA PIO'
    SV = 'SALVAMENTO'

    model = cp_model.CpModel()

    demand_a = d[SB] + d[JP]
    demand_b = sum(d[f] for f in GROUP_B)

    yuber_ok = 'YUBER' not in unavailable_carriers
    dem_ok = 'DEMETRIO' not in unavailable_carriers

    slots = []

    def _break_symmetry(pool):
        """Cupos del mismo pool son intercambiables: ordenarlos por total
        elimina permutaciones redundantes y acelera mucho la busqueda."""
        for a, b in zip(pool, pool[1:]):
            model.Add(a['total'] >= b['total'])

    def _yuber_pool(tag, farms, demand, base, overage):
        if not yuber_ok:
            return []
        pool = []
        for i in range(_num_slots(demand, CAP_YUBER)):
            amt, in_bin = {}, {}
            for f in farms:
                amt[f] = model.NewIntVar(0, min(d[f], CAP_YUBER_26), f'{tag}_{f}_{i}')
                in_bin[f] = model.NewBoolVar(f'{tag}_in_{f}_{i}')
                model.Add(amt[f] <= CAP_YUBER_26 * in_bin[f]); model.Add(amt[f] >= in_bin[f])
            total = model.NewIntVar(0, CAP_YUBER_26, f'{tag}_tot_{i}')
            model.Add(total == sum(amt.values()))
            # big=1 -> el viaje va en uno de los 2 camiones de 26P.
            # Camion normal: max 24P. Camion de 26P: max 26P y NO Salvamento.
            big = model.NewBoolVar(f'{tag}_big_{i}')
            model.Add(total <= CAP_YUBER + (CAP_YUBER_26 - CAP_YUBER) * big)
            if SV in in_bin:
                model.Add(in_bin[SV] + big <= 1)
            bins = list(in_bin.values())
            active = _or_bin_from_list(model, bins, f'{tag}_act_{i}')
            model.Add(big <= active)
            extra = _extra_stops(model, bins, f'{tag}_extra_{i}')
            over_two = _over_two_farms(model, bins, f'{tag}_ot_{i}')
            over = model.NewIntVar(0, CAP_YUBER_26, f'{tag}_over_{i}')
            model.Add(over >= total - YUBER_INCLUDED)
            cost = model.NewIntVar(0, 3_000_000, f'{tag}_cost_{i}')
            model.Add(cost == base * active + overage * over)  # mismo municipio: sin cuarteo
            pool.append({'carrier': 'Yuber', 'farms': amt, 'active': active, 'cost': cost,
                         'total': total, 'extra': extra, 'over_two': over_two, 'big': big})
        _break_symmetry(pool)
        return pool

    def _demetrio_pool(tag, farms, cost_val):
        if not dem_ok:
            return []
        pool = []
        for i in range(2):  # tope real de Demetrio (compartido entre municipios abajo)
            amt, in_bin = {}, {}
            for f in farms:
                amt[f] = model.NewIntVar(0, min(d[f], CAP_DEMETRIO), f'{tag}_{f}_{i}')
                in_bin[f] = model.NewBoolVar(f'{tag}_in_{f}_{i}')
                model.Add(amt[f] <= CAP_DEMETRIO * in_bin[f]); model.Add(amt[f] >= in_bin[f])
            total = model.NewIntVar(0, CAP_DEMETRIO, f'{tag}_tot_{i}')
            model.Add(total == sum(amt.values()))
            bins = list(in_bin.values())
            active = _or_bin_from_list(model, bins, f'{tag}_act_{i}')
            extra = _extra_stops(model, bins, f'{tag}_extra_{i}')
            over_two = _over_two_farms(model, bins, f'{tag}_ot_{i}')
            cost = model.NewIntVar(0, 2_000_000, f'{tag}_cost_{i}')
            model.Add(cost == cost_val * active)  # Demetrio no cobra cuarteo
            pool.append({'carrier': 'Demetrio', 'farms': amt, 'active': active, 'cost': cost,
                         'total': total, 'extra': extra, 'over_two': over_two})
        _break_symmetry(pool)
        return pool

    slots += _yuber_pool('ay', GROUP_A, demand_a, YUBER_A_BASE, YUBER_OVERAGE_CHIG)
    slots += _demetrio_pool('ad', GROUP_A, DEMETRIO_A_COST)
    slots += _yuber_pool('by', GROUP_B, demand_b, YUBER_B_BASE, YUBER_OVERAGE_APTO)
    slots += _demetrio_pool('bd', GROUP_B, DEMETRIO_B_COST)

    # ── Conservacion de demanda por finca ──
    for f in ALL_FARMS:
        model.Add(sum(s['farms'][f] for s in slots if f in s['farms']) == d[f])

    # ── Topes de viajes/dia ──
    demetrio_slots = [s for s in slots if s['carrier'] == 'Demetrio']
    if demetrio_slots:
        model.Add(sum(s['active'] for s in demetrio_slots) <= 2)
    big_vars = [s['big'] for s in slots if 'big' in s]
    if big_vars:
        model.Add(sum(big_vars) <= MAX_VIAJES_YUBER_26)

    # ── Objetivo: costo manda; desempates no suben el costo ──
    total_over_two = model.NewIntVar(0, 10_000, 'total_over_two')
    model.Add(total_over_two == sum(s['over_two'] for s in slots))
    total_stops = model.NewIntVar(0, 10_000, 'total_stops')
    model.Add(total_stops == sum(s['active'] for s in slots) + sum(s['extra'] for s in slots))
    total_big = sum(big_vars) if big_vars else 0
    model.Minimize((sum(s['cost'] for s in slots) + FRENO_CUARTEO * sum(s['extra'] for s in slots)) * 1000
                   + total_over_two * 50 + total_stops * 2 + total_big)

    solver = cp_model.CpSolver()
    # Un solo hilo: mismo pedido, siempre exactamente el mismo resultado.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "No se encontro una solucion factible: los conductores "
            "disponibles no alcanzan a cubrir este pedido. Revisa cuales "
            "dejaste activos."
        )

    trips = []
    for s in slots:
        if solver.Value(s['active']) == 0:
            continue
        farms = {f: solver.Value(v) for f, v in s['farms'].items() if solver.Value(v) > 0}
        if not farms:
            continue
        total = sum(farms.values())
        carrier = s['carrier']
        if carrier == 'Yuber':
            carrier = 'Yuber (26P)' if total > CAP_YUBER else 'Yuber (24P)'
        trips.append({
            'carrier': carrier,
            'total':   total,
            'farms':   farms,
            'cost':    solver.Value(s['cost']),
        })

    total_cost = sum(t['cost'] for t in trips)
    return {'trips': trips, 'total_cost': total_cost, 'notas': []}
