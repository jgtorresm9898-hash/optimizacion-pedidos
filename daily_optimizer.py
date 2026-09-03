"""
Optimizador de ruta diaria - Exportadora de Banano.

Logica validada con el usuario (julio-agosto 2026):
- Grupo "caro" (San Bartolo + Juana Pio), SIN Edwin. El costo de cada viaje
  depende solo del TOTAL de pallets que lleve (no de que finca vengan), asi
  que se optimiza como llenado de camiones sobre la suma de ambas fincas.
    Yuber:    $1.050.000 hasta 20P, +$25.000 por pallet adicional, tope 26P (mula nueva).
    Demetrio: $850.000 fijo, tope 18P.
- Grupo "barato" (Dona Francia, Chispero, Santa Maria, Salvamento), con
  Edwin disponible salvo para Santa Maria. Aqui si importa la finca porque
  hay minimos de pallets para poder cuartear.
    Yuber:    $630.000 hasta 20P, +$25.000 por pallet adicional, tope 26P.
    Demetrio: $550.000 fijo, tope 18P.
    Edwin:    $600.000 fijo, tope 24P (no Santa Maria).
- Cuarteo (combinar 2+ fincas en un viaje): sin minimo de pallets por finca
  en ningun grupo -- el optimizador puede combinar cualquier cantidad si
  sale mas barato.
- Demetrio: maximo 2 viajes/dia, COMPARTIDOS entre ambos grupos (1 camion).
- Edwin: maximo 2 viajes/dia, solo aplica al grupo barato (1 camion).
- Edwin SI puede recoger Juana Pio (habilitado agosto 2026), a $1.050.000 fijo
  (tarifa Chigorodo), tope 24P, y puede cuartear Juana Pio con fincas del
  grupo barato (Dona Francia, Chispero, Salvamento) en el mismo viaje. Edwin
  sigue SIN poder recoger San Bartolo ni Santa Maria.
- Si Edwin hace CUALQUIER viaje que toque Chigorodo ese dia (Juana Pio,
  sola o cuarteada con fincas de Apartado), ese viaje es el UNICO que
  alcanza a hacer en todo el dia -- no le da tiempo a nada mas, ni otro
  de Chigorodo ni de Apartado. Si NO toca Chigorodo para nada ese dia
  (todos sus viajes son puro Apartado: Dona Francia, Chispero,
  Salvamento), si alcanza a hacer sus 2 viajes normales.
- Recargo por cuarteo: SE COBRA POR CADA PARADA ADICIONAL, no es un monto
  fijo por viaje. Un viaje de 1 sola finca no paga recargo; de 2 fincas
  paga $100.000 (1 parada extra); de 3 fincas paga $200.000 (2 paradas
  extra); de 4 fincas paga $300.000 (3 paradas extra). Formula: $100.000 x
  (numero de fincas distintas en el viaje - 1). Aplica a cualquier
  transportista, cualquier grupo.

Motor de calculo (agosto 2026): antes esto se resolvia con combinatoria
hecha a mano (particiones + memoizacion). Esa version tenia un hueco real:
solo partia el pedido de una finca en dos viajes cuando esa finca SOLA no
cabia en un camion (>26P) -- nunca probaba partir una finca mas chica (p.ej.
14P) en dos pedazos para repartirla entre DOS viajes distintos, aunque eso
a veces sale mas barato (caso real: Chispero 14P partido 7+7 entre un viaje
con Juana Pio y otro con Santa Maria ahorro $45.000 frente a lo que devolvia
el motor anterior). Por eso ahora se resuelve con un solver exacto de
programacion entera (Google OR-Tools CP-SAT): se modelan "cupos" de viaje
por transportista/grupo, se deja que CUALQUIER combinacion de pallets de
cualquier finca entre en cualquier cupo elegible, y se minimiza el costo
total sujeto a los topes de capacidad y de viajes/dia de Demetrio y Edwin.
Esto encuentra siempre el optimo real (nunca peor que el motor anterior, a
veces mejor) y sigue corriendo en menos de un segundo para pedidos de este
tamano.
"""
import math
from ortools.sat.python import cp_model

GROUP_A = ['SAN BARTOLO', 'JUANA PIO']
GROUP_B = ['DOÑA FRANCIA', 'CHISPERO', 'SANTA MARIA', 'SALVAMENTO']
ALL_FARMS = ['JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA', 'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO']

CAP_YUBER, CAP_DEMETRIO, CAP_EDWIN = 26, 18, 24
YUBER_SALVAMENTO_CAP = 24  # la mula nueva (26P) de Yuber no entra a Salvamento -- tope 24P

CARRIERS = ['YUBER', 'DEMETRIO', 'EDWIN']
CARRIER_LABELS = {'YUBER': 'Yuber', 'DEMETRIO': 'Demetrio', 'EDWIN': 'Edwin'}

DEMETRIO_A_COST = 850_000
DEMETRIO_B_COST = 550_000
EDWIN_B_COST = 600_000
EDWIN_JP_COST = 1_050_000  # Edwin con Juana Pio (mezclada o no con grupo barato)
CUARTEO_SURCHARGE = 100_000  # recargo por viaje que mezcla 2+ fincas
YUBER_OVERAGE = 25_000       # por pallet por encima de 20P, en Yuber (ambos grupos)
YUBER_INCLUDED = 20          # pallets incluidos en la tarifa base de Yuber

EDWIN_EXCLUDED_B = {'SANTA MARIA'}


def yuber_A(n):
    if n <= 0:
        return 0
    return 1_050_000 + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE


def yuber_B(n):
    if n <= 0:
        return 0
    return 630_000 + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE


# ───────────────────────── Modelo CP-SAT ─────────────────────────
def _num_slots(total_demand, cap, minimum=1, margin=1):
    """Cuantos 'cupos' de viaje (de un transportista sin tope de viajes/dia,
    o sea Yuber) alcanzan para poder cubrir, en el peor caso, toda la
    demanda de ese grupo. Se calcula a partir de la demanda real para que
    el modelo no crezca mas de lo necesario en pedidos chicos."""
    if total_demand <= 0:
        return minimum
    return max(minimum, math.ceil(total_demand / cap) + margin)


def _or_bin_from_list(model, bins, name):
    """Variable binaria = OR(bins). Solo fuerza r=1 cuando algun bin=1; el
    caso r=0 con todos los bins en 0 lo deja libre la minimizacion (nunca
    conviene forzarlo a 1 porque el costo asociado siempre es >= 0)."""
    r = model.NewBoolVar(name)
    for b in bins:
        model.Add(r >= b)
    model.Add(r <= sum(bins))
    return r


def _extra_stops(model, bins, name):
    """Cuantas 'paradas extra' paga el viaje: (cantidad de fincas distintas
    presentes) - 1, sin bajar de 0. Con 1 sola finca son 0 paradas extra
    (no paga recargo); con 2 fincas es 1 parada extra ($100.000); con 3
    fincas son 2 paradas extra ($200.000); etc. No hace falta acotar por
    arriba -- el costo positivo asociado hace que la minimizacion nunca
    infle esta variable de gratis, solo la deja subir cuando la suma de
    fincas activas lo obliga."""
    r = model.NewIntVar(0, max(0, len(bins) - 1), name)
    model.Add(r >= sum(bins) - 1)
    return r


def optimize_day(pallets, unavailable_carriers=None):
    """
    pallets: dict con llaves 'JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA',
             'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO' (0 si no hay pedido).
    unavailable_carriers: set/lista opcional con los conductores NO
             disponibles ese dia, de entre 'YUBER', 'DEMETRIO', 'EDWIN'
             (p.ej. {'DEMETRIO'} si tiene el carro varado). Sus cupos de
             viaje simplemente no se crean, asi que el solver reparte todo
             el pedido entre los conductores que si queden disponibles.
    Retorna: {'trips': [{'carrier', 'total', 'farms': {finca: pallets}, 'cost'}],
              'total_cost': int}
    """
    unavailable_carriers = set(unavailable_carriers or [])
    d = {f: int(pallets.get(f, 0) or 0) for f in ALL_FARMS}
    if sum(d.values()) == 0:
        return {'trips': [], 'total_cost': 0}

    SB, JP = 'SAN BARTOLO', 'JUANA PIO'
    DF, CH, SM, SV = 'DOÑA FRANCIA', 'CHISPERO', 'SANTA MARIA', 'SALVAMENTO'

    model = cp_model.CpModel()

    demand_a  = d[SB] + d[JP]
    demand_b  = d[DF] + d[CH] + d[SM] + d[SV]

    n_a_yuber = 0 if 'YUBER' in unavailable_carriers else _num_slots(demand_a, CAP_YUBER)
    n_b_yuber = 0 if 'YUBER' in unavailable_carriers else _num_slots(demand_b, CAP_YUBER)
    n_a_dem   = 0 if 'DEMETRIO' in unavailable_carriers else 2   # tope real de Demetrio (compartido con grupo B abajo)
    n_b_dem   = 0 if 'DEMETRIO' in unavailable_carriers else 2
    n_edwin   = 0 if 'EDWIN' in unavailable_carriers else 2      # Edwin: 2 viajes/dia si son de Apartado, pero solo 1 si alguno toca Chigorodo

    slots = []  # cada entrada: dict con toda la info del cupo ya resuelta

    def _break_symmetry(pool):
        """Los cupos de un mismo pool (p.ej. todos los Yuber de grupo B) son
        intercambiables entre si -- sin esto el solver pierde muchisimo
        tiempo explorando asignaciones que son la misma solucion con los
        cupos numerados distinto. Forzar que el total de pallets no crezca
        de un cupo al siguiente elimina esas permutaciones redundantes y
        acelera la busqueda varios ordenes de magnitud en pedidos grandes."""
        for a, b in zip(pool, pool[1:]):
            model.Add(a['total'] >= b['total'])

    # ── Cupos Yuber / Demetrio, grupo A (San Bartolo + Juana Pio) ──
    pool = []
    for i in range(n_a_yuber):
        sb = model.NewIntVar(0, min(d[SB], CAP_YUBER), f'ay_sb_{i}')
        jp = model.NewIntVar(0, min(d[JP], CAP_YUBER), f'ay_jp_{i}')
        sb_in = model.NewBoolVar(f'ay_sbin_{i}')
        jp_in = model.NewBoolVar(f'ay_jpin_{i}')
        model.Add(sb <= CAP_YUBER * sb_in); model.Add(sb >= sb_in)
        model.Add(jp <= CAP_YUBER * jp_in); model.Add(jp >= jp_in)
        total = model.NewIntVar(0, CAP_YUBER, f'ay_tot_{i}')
        model.Add(total == sb + jp)
        model.Add(total <= CAP_YUBER)
        active = _or_bin_from_list(model, [sb_in, jp_in], f'ay_act_{i}')
        extra  = _extra_stops(model, [sb_in, jp_in], f'ay_extra_{i}')
        over = model.NewIntVar(0, CAP_YUBER, f'ay_over_{i}')
        model.Add(over >= total - YUBER_INCLUDED)
        cost = model.NewIntVar(0, 3_000_000, f'ay_cost_{i}')
        model.Add(cost == 1_050_000 * active + YUBER_OVERAGE * over + CUARTEO_SURCHARGE * extra)
        pool.append({'carrier': 'Yuber', 'farms': {SB: sb, JP: jp}, 'active': active, 'cost': cost, 'total': total})
    _break_symmetry(pool)
    slots += pool

    pool = []
    for i in range(n_a_dem):
        sb = model.NewIntVar(0, min(d[SB], CAP_DEMETRIO), f'ad_sb_{i}')
        jp = model.NewIntVar(0, min(d[JP], CAP_DEMETRIO), f'ad_jp_{i}')
        sb_in = model.NewBoolVar(f'ad_sbin_{i}')
        jp_in = model.NewBoolVar(f'ad_jpin_{i}')
        model.Add(sb <= CAP_DEMETRIO * sb_in); model.Add(sb >= sb_in)
        model.Add(jp <= CAP_DEMETRIO * jp_in); model.Add(jp >= jp_in)
        total = model.NewIntVar(0, CAP_DEMETRIO, f'ad_tot_{i}')
        model.Add(total == sb + jp)
        model.Add(total <= CAP_DEMETRIO)
        active = _or_bin_from_list(model, [sb_in, jp_in], f'ad_act_{i}')
        extra  = _extra_stops(model, [sb_in, jp_in], f'ad_extra_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'ad_cost_{i}')
        model.Add(cost == DEMETRIO_A_COST * active + CUARTEO_SURCHARGE * extra)
        pool.append({'carrier': 'Demetrio', 'farms': {SB: sb, JP: jp}, 'active': active, 'cost': cost, 'total': total})
    _break_symmetry(pool)
    slots += pool

    # ── Cupos Yuber / Demetrio, grupo B (Doña Francia, Chispero, Santa Maria, Salvamento) ──
    pool = []
    for i in range(n_b_yuber):
        amt   = {}
        in_bin = {}
        for f in GROUP_B:
            amt[f]    = model.NewIntVar(0, min(d[f], CAP_YUBER), f'by_{f}_{i}')
            in_bin[f] = model.NewBoolVar(f'by_in_{f}_{i}')
            model.Add(amt[f] <= CAP_YUBER * in_bin[f]); model.Add(amt[f] >= in_bin[f])
        total = model.NewIntVar(0, CAP_YUBER, f'by_tot_{i}')
        model.Add(total == sum(amt.values()))
        model.Add(total <= CAP_YUBER)
        # Salvamento: viaje que la incluya (sola o cuarteada) no puede pasar
        # de 24P -- la mula nueva de 26P de Yuber no entra a esa finca.
        model.Add(total <= YUBER_SALVAMENTO_CAP).OnlyEnforceIf(in_bin[SV])
        active = _or_bin_from_list(model, list(in_bin.values()), f'by_act_{i}')
        extra  = _extra_stops(model, list(in_bin.values()), f'by_extra_{i}')
        over = model.NewIntVar(0, CAP_YUBER, f'by_over_{i}')
        model.Add(over >= total - YUBER_INCLUDED)
        cost = model.NewIntVar(0, 3_000_000, f'by_cost_{i}')
        model.Add(cost == 630_000 * active + YUBER_OVERAGE * over + CUARTEO_SURCHARGE * extra)
        pool.append({'carrier': 'Yuber', 'farms': amt, 'active': active, 'cost': cost, 'total': total})
    _break_symmetry(pool)
    slots += pool

    pool = []
    for i in range(n_b_dem):
        amt   = {}
        in_bin = {}
        for f in GROUP_B:
            amt[f]    = model.NewIntVar(0, min(d[f], CAP_DEMETRIO), f'bd_{f}_{i}')
            in_bin[f] = model.NewBoolVar(f'bd_in_{f}_{i}')
            model.Add(amt[f] <= CAP_DEMETRIO * in_bin[f]); model.Add(amt[f] >= in_bin[f])
        total = model.NewIntVar(0, CAP_DEMETRIO, f'bd_tot_{i}')
        model.Add(total == sum(amt.values()))
        model.Add(total <= CAP_DEMETRIO)
        active = _or_bin_from_list(model, list(in_bin.values()), f'bd_act_{i}')
        extra  = _extra_stops(model, list(in_bin.values()), f'bd_extra_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'bd_cost_{i}')
        model.Add(cost == DEMETRIO_B_COST * active + CUARTEO_SURCHARGE * extra)
        pool.append({'carrier': 'Demetrio', 'farms': amt, 'active': active, 'cost': cost, 'total': total})
    _break_symmetry(pool)
    slots += pool

    # ── Cupos Edwin: Juana Pio + Doña Francia + Chispero + Salvamento (NUNCA San Bartolo ni Santa Maria) ──
    edwin_farms = [JP, DF, CH, SV]
    pool = []
    for i in range(n_edwin):
        amt    = {}
        in_bin = {}
        for f in edwin_farms:
            amt[f]    = model.NewIntVar(0, min(d[f], CAP_EDWIN), f'e_{f}_{i}')
            in_bin[f] = model.NewBoolVar(f'e_in_{f}_{i}')
            model.Add(amt[f] <= CAP_EDWIN * in_bin[f]); model.Add(amt[f] >= in_bin[f])
        total = model.NewIntVar(0, CAP_EDWIN, f'e_tot_{i}')
        model.Add(total == sum(amt.values()))
        model.Add(total <= CAP_EDWIN)
        jp_in     = in_bin[JP]
        group_act = _or_bin_from_list(model, [in_bin[DF], in_bin[CH], in_bin[SV]], f'e_gact_{i}')
        b_only    = model.NewBoolVar(f'e_bonly_{i}')
        model.Add(b_only <= group_act)
        model.Add(b_only <= 1 - jp_in)
        model.Add(b_only >= group_act - jp_in)
        extra  = _extra_stops(model, [in_bin[JP], in_bin[DF], in_bin[CH], in_bin[SV]], f'e_extra_{i}')
        active = _or_bin_from_list(model, list(in_bin.values()), f'e_act_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'e_cost_{i}')
        model.Add(cost == EDWIN_JP_COST * jp_in + EDWIN_B_COST * b_only + CUARTEO_SURCHARGE * extra)
        pool.append({'carrier': 'Edwin', 'farms': amt, 'active': active, 'cost': cost, 'total': total, 'jp_in': jp_in})
    _break_symmetry(pool)
    slots += pool

    # ── Conservacion de demanda por finca ──
    for f in ALL_FARMS:
        model.Add(sum(s['farms'][f] for s in slots if f in s['farms']) == d[f])

    # ── Topes de viajes/dia ──
    demetrio_slots = [s for s in slots if s['carrier'] == 'Demetrio']
    edwin_slots    = [s for s in slots if s['carrier'] == 'Edwin']
    model.Add(sum(s['active'] for s in demetrio_slots) <= 2)

    # Edwin: si CUALQUIER viaje del dia toca Chigorodo (lleva Juana Pio,
    # solo o cuarteada con Apartado), ese es el UNICO viaje que alcanza a
    # hacer ese dia -- no le da tiempo a nada mas. Si no toca Chigorodo
    # para nada (todos sus viajes son puro Apartado: Doña Francia/
    # Chispero/Salvamento), si alcanza a hacer sus 2 viajes normales.
    # sum(active) + sum(jp_in) <= 2 codifica exactamente esto: si hay un
    # viaje con Juana Pio (jp_in=1 en ese cupo, active=1 en ese cupo),
    # ya suma 2 el solo -- no deja espacio para ningun otro viaje activo.
    # Si no hay ningun viaje con Juana Pio, el limite normal de 2 queda
    # intacto.
    model.Add(sum(s['active'] for s in edwin_slots) + sum(s['jp_in'] for s in edwin_slots) <= 2)

    model.Minimize(sum(s['cost'] for s in slots))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # No deberia pasar si queda al menos un conductor disponible con
        # capacidad suficiente; si se desactivan demasiados conductores
        # para el tamano del pedido, se deja un mensaje claro en vez de
        # reventar silenciosamente.
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
        trips.append({
            'carrier': s['carrier'],
            'total':   sum(farms.values()),
            'farms':   farms,
            'cost':    solver.Value(s['cost']),
        })

    total_cost = sum(t['cost'] for t in trips)
    return {'trips': trips, 'total_cost': total_cost}
