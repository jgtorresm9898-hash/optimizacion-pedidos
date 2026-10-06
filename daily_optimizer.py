"""
Optimizador de ruta diaria - Exportadora de Banano.

Logica validada con el usuario (julio-agosto 2026):
- Grupo "caro" (San Bartolo + Juana Pio), SIN Edwin. El costo de cada viaje
  depende solo del TOTAL de pallets que lleve (no de que finca vengan), asi
  que se optimiza como llenado de camiones sobre la suma de ambas fincas.
    Yuber:    $1.050.000 hasta 20P, +$37.500 por pallet adicional, tope 26P (mula nueva).
    Demetrio: $850.000 fijo, tope 18P.
- Grupo "barato" (Dona Francia, Chispero, Santa Maria, Salvamento), con
  Edwin disponible salvo para Santa Maria. Aqui si importa la finca porque
  hay minimos de pallets para poder cuartear.
    Yuber:    $630.000 hasta 20P, +$25.000 por pallet adicional, tope 26P.
    Demetrio: $550.000 fijo, tope 18P.
    Edwin:    $610.725 fijo, tope 24P (no Santa Maria).
- Cuarteo (combinar 2+ fincas en un viaje): sin minimo de pallets por finca
  en ningun grupo -- el optimizador puede combinar cualquier cantidad si
  sale mas barato.
- Demetrio: maximo 2 viajes/dia, COMPARTIDOS entre ambos grupos (1 camion).
- Edwin: maximo 2 viajes/dia, solo aplica al grupo barato (1 camion).
- Edwin SI puede recoger Juana Pio (habilitado agosto 2026), a $1.000.000 fijo
  (tarifa Chigorodo), tope 24P, y puede cuartear Juana Pio con fincas del
  grupo barato (Dona Francia, Chispero, Salvamento) en el mismo viaje. Edwin
  sigue SIN poder recoger San Bartolo ni Santa Maria.
- Si Edwin hace CUALQUIER viaje que toque Chigorodo ese dia (Juana Pio,
  sola o cuarteada con fincas de Apartado), ese viaje es el UNICO que
  alcanza a hacer en todo el dia -- no le da tiempo a nada mas, ni otro
  de Chigorodo ni de Apartado. Si NO toca Chigorodo para nada ese dia
  (todos sus viajes son puro Apartado: Dona Francia, Chispero,
  Salvamento), si alcanza a hacer sus 2 viajes normales.
- Edwin Trailer Azul (antes 'Mula Edwin 21P', septiembre 2026): vehiculo
  aparte, con su propio conductor, puede salir el mismo dia que el carro
  actual de Edwin.
    Tope 24P (octubre 2026: aunque se compro como de 21P, carga 24P), puede ir a TODAS las fincas (incluye San Bartolo y Santa
    Maria) y cuartear cualquier combinacion.
    Tarifa PLENA por viaje, sin importar cuantos pallets lleve:
    $1.000.000 si el viaje toca Chigorodo (San Bartolo o Juana Pio),
    $610.725 si es puro Apartado. NO cobra cuarteo.
    Maximo 2 viajes/dia; misma regla de Chigorodo que Edwin: si un viaje
    toca Chigorodo, es el UNICO del dia.
    Tiene su propio boton de disponibilidad ('MULA_EDWIN').
- Escenario "Optimizacion con dos viajes Edwin" (octubre 2026,
  forzar_trailer_dos_viajes=True): el Trailer Azul hace SI O SI un viaje
  LLENO (24P) de Chigorodo (San Bartolo / Juana Pio) y otro LLENO (24P) de
  Apartado (Doña Francia, Chispero, Santa Maria, Salvamento) el mismo dia
  -- aqui NO aplica la regla de "si toca Chigorodo es el unico viaje".
  Si un municipio no alcanza a sumar 24P ese dia, ese viaje no se hace y
  el Trailer queda con 1 solo viaje (o ninguno); lo de ese municipio se
  reparte normal entre los demas. Si el Trailer esta marcado no
  disponible, el escenario queda igual a la optimizacion normal. El resto
  del pedido se reparte de la forma mas barata entre los demas.
- Cuarteo (tarifas de septiembre 2026):
    Demetrio, Edwin y Edwin Trailer Azul: NUNCA cobran cuarteo.
    Yuber: cuartear fincas del MISMO municipio (solo Chigorodo o solo
    Apartado) no tiene recargo. Solo se cobra cuarteo si el viaje mezcla
    fincas de Chigorodo y de Apartado ($100.000 por parada).

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

CAP_MULA_EDWIN = 24  # Edwin Trailer Azul (antes 'Mula Edwin 21P'): oct 2026 se confirmo que carga 24P

CARRIERS = ['YUBER', 'DEMETRIO', 'EDWIN', 'MULA_EDWIN']
CARRIER_LABELS = {'YUBER': 'Yuber', 'DEMETRIO': 'Demetrio', 'EDWIN': 'Edwin',
                  'MULA_EDWIN': 'Edwin Tráiler Azul'}

DEMETRIO_A_COST = 850_000
DEMETRIO_B_COST = 550_000
EDWIN_B_COST = 610_725
EDWIN_JP_COST = 1_000_000  # Edwin con Juana Pio (mezclada o no con grupo barato)
MULA_EDWIN_CHIG_COST = 1_000_000  # mula nueva: viaje que toca Chigorodo (tarifa plena)
MULA_EDWIN_APTO_COST = 610_725    # mula nueva: viaje puro Apartado (tarifa plena)
CUARTEO_SURCHARGE = 100_000  # Yuber: por parada, solo si el viaje mezcla Chigorodo y Apartado
YUBER_OVERAGE_CHIG = 37_500  # Yuber Chigorodo: por pallet por encima de 20P
YUBER_OVERAGE_APTO = 25_000  # Yuber Apartado: por pallet por encima de 20P
# Freno interno de cuarteo (NO se cobra, no aparece en ningun total): la app
# "hace de cuenta" que cada parada extra de un viaje cuesta $100.000, igual
# que la regla vieja. Asi solo cuartea si de verdad ahorra mas que eso y las
# rutas quedan tan ordenadas como antes. Los costos que se muestran son los
# reales (sin este freno).
FRENO_CUARTEO = 100_000
YUBER_INCLUDED = 20          # pallets incluidos en la tarifa base de Yuber

EDWIN_EXCLUDED_B = {'SANTA MARIA'}


def yuber_A(n):
    if n <= 0:
        return 0
    return 1_050_000 + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE_CHIG


def yuber_B(n):
    if n <= 0:
        return 0
    return 630_000 + max(0, n - YUBER_INCLUDED) * YUBER_OVERAGE_APTO


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


def _over_two_farms(model, bins, name):
    """Cuantas fincas de mas hay por encima de 2 en el viaje (0 si el viaje
    tiene 1 o 2 fincas, 1 si tiene 3, 2 si tiene 4, etc.). No afecta el
    costo real del viaje -- se usa solo como criterio de desempate: entre
    dos formas de armar las rutas que cuestan exactamente lo mismo, se
    prefiere la que menos mezcle 3+ fincas en un mismo camion (mezclar 2
    esta bien, 3 o mas es logisticamente complicado). Si la unica forma de
    llegar al precio mas barato es con 3+ fincas, esa se sigue usando
    igual -- el costo siempre manda primero."""
    r = model.NewIntVar(0, max(0, len(bins) - 2), name)
    model.Add(r >= sum(bins) - 2)
    return r


def trailer_forced_plan(pallets, unavailable_carriers=None):
    """Que viajes obligados le tocan al Trailer Azul en el escenario
    'dos viajes Edwin'. Devuelve (viajes, notas): viajes es una lista de
    ('CHIG'|'APTO'), notas explica en palabras lo que no se pudo forzar."""
    unavailable_carriers = set(unavailable_carriers or [])
    d = {f: int(pallets.get(f, 0) or 0) for f in ALL_FARMS}
    if 'MULA_EDWIN' in unavailable_carriers:
        return [], [f"{CARRIER_LABELS['MULA_EDWIN']} está marcado como no disponible: "
                    "este escenario queda igual a la optimización normal."]
    viajes, notas = [], []
    for code, nombre, farms in (('CHIG', 'Chigorodó', GROUP_A), ('APTO', 'Apartadó', GROUP_B)):
        tot = sum(d[f] for f in farms)
        if tot >= CAP_MULA_EDWIN:
            viajes.append(code)
        elif tot == 0:
            notas.append(f"No hay pedido en {nombre}: ese día el Tráiler Azul no hace viaje de {nombre}.")
        else:
            notas.append(f"{nombre} solo tiene {tot}P (no alcanza para un viaje lleno de {CAP_MULA_EDWIN}P): "
                         f"el Tráiler Azul no hace viaje de {nombre} y esos pallets se reparten normal.")
    return viajes, notas


def optimize_day(pallets, unavailable_carriers=None, forzar_trailer_dos_viajes=False):
    """
    pallets: dict con llaves 'JUANA PIO', 'DOÑA FRANCIA', 'SANTA MARIA',
             'CHISPERO', 'SALVAMENTO', 'SAN BARTOLO' (0 si no hay pedido).
    unavailable_carriers: set/lista opcional con los conductores NO
             disponibles ese dia, de entre 'YUBER', 'DEMETRIO', 'EDWIN', 'MULA_EDWIN'
             (p.ej. {'DEMETRIO'} si tiene el carro varado). Sus cupos de
             viaje simplemente no se crean, asi que el solver reparte todo
             el pedido entre los conductores que si queden disponibles.
    forzar_trailer_dos_viajes: escenario 'Optimizacion con dos viajes
             Edwin' -- el Trailer Azul hace exactamente un viaje lleno
             (24P) de Chigorodo y uno lleno de Apartado (solo los que
             alcancen 24P ese dia), y nada mas. Ver trailer_forced_plan.
    Retorna: {'trips': [{'carrier', 'total', 'farms': {finca: pallets}, 'cost'}],
              'total_cost': int, 'notas': [str]}
    """
    unavailable_carriers = set(unavailable_carriers or [])
    d = {f: int(pallets.get(f, 0) or 0) for f in ALL_FARMS}
    forced_trips, notas = [], []
    if forzar_trailer_dos_viajes:
        forced_trips, notas = trailer_forced_plan(d, unavailable_carriers)
    if sum(d.values()) == 0:
        return {'trips': [], 'total_cost': 0, 'notas': notas}

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
    n_mula_e  = 0 if 'MULA_EDWIN' in unavailable_carriers else 2 # Mula nueva de Edwin: misma regla de viajes que Edwin
    if forzar_trailer_dos_viajes:
        n_mula_e = 0  # en el escenario forzado sus viajes se arman aparte (abajo)

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
        over_two = _over_two_farms(model, [sb_in, jp_in], f'ay_ot_{i}')
        over = model.NewIntVar(0, CAP_YUBER, f'ay_over_{i}')
        model.Add(over >= total - YUBER_INCLUDED)
        cost = model.NewIntVar(0, 3_000_000, f'ay_cost_{i}')
        model.Add(cost == 1_050_000 * active + YUBER_OVERAGE_CHIG * over)  # mismo municipio: sin cuarteo
        pool.append({'carrier': 'Yuber', 'farms': {SB: sb, JP: jp}, 'active': active, 'cost': cost, 'total': total,
                     'extra': extra, 'over_two': over_two})
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
        over_two = _over_two_farms(model, [sb_in, jp_in], f'ad_ot_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'ad_cost_{i}')
        model.Add(cost == DEMETRIO_A_COST * active)  # Demetrio no cobra cuarteo
        pool.append({'carrier': 'Demetrio', 'farms': {SB: sb, JP: jp}, 'active': active, 'cost': cost, 'total': total,
                     'extra': extra, 'over_two': over_two})
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
        over_two = _over_two_farms(model, list(in_bin.values()), f'by_ot_{i}')
        over = model.NewIntVar(0, CAP_YUBER, f'by_over_{i}')
        model.Add(over >= total - YUBER_INCLUDED)
        cost = model.NewIntVar(0, 3_000_000, f'by_cost_{i}')
        model.Add(cost == 630_000 * active + YUBER_OVERAGE_APTO * over)  # mismo municipio: sin cuarteo
        pool.append({'carrier': 'Yuber', 'farms': amt, 'active': active, 'cost': cost, 'total': total,
                     'extra': extra, 'over_two': over_two})
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
        over_two = _over_two_farms(model, list(in_bin.values()), f'bd_ot_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'bd_cost_{i}')
        model.Add(cost == DEMETRIO_B_COST * active)  # Demetrio no cobra cuarteo
        pool.append({'carrier': 'Demetrio', 'farms': amt, 'active': active, 'cost': cost, 'total': total,
                     'extra': extra, 'over_two': over_two})
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
        over_two = _over_two_farms(model, [in_bin[JP], in_bin[DF], in_bin[CH], in_bin[SV]], f'e_ot_{i}')
        active = _or_bin_from_list(model, list(in_bin.values()), f'e_act_{i}')
        cost = model.NewIntVar(0, 2_000_000, f'e_cost_{i}')
        model.Add(cost == EDWIN_JP_COST * jp_in + EDWIN_B_COST * b_only)  # Edwin no cobra cuarteo
        pool.append({'carrier': 'Edwin', 'farms': amt, 'active': active, 'cost': cost, 'total': total, 'jp_in': jp_in,
                     'extra': extra, 'over_two': over_two})
    _break_symmetry(pool)
    slots += pool

    # ── Cupos Mula nueva de Edwin: TODAS las fincas, 21P, tarifa plena ──
    pool = []
    for i in range(n_mula_e):
        amt    = {}
        in_bin = {}
        for f in ALL_FARMS:
            amt[f]    = model.NewIntVar(0, min(d[f], CAP_MULA_EDWIN), f'm_{f}_{i}')
            in_bin[f] = model.NewBoolVar(f'm_in_{f}_{i}')
            model.Add(amt[f] <= CAP_MULA_EDWIN * in_bin[f]); model.Add(amt[f] >= in_bin[f])
        total = model.NewIntVar(0, CAP_MULA_EDWIN, f'm_tot_{i}')
        model.Add(total == sum(amt.values()))
        model.Add(total <= CAP_MULA_EDWIN)
        chig_in   = _or_bin_from_list(model, [in_bin[SB], in_bin[JP]], f'm_chig_{i}')
        group_act = _or_bin_from_list(model, [in_bin[f] for f in GROUP_B], f'm_gact_{i}')
        b_only    = model.NewBoolVar(f'm_bonly_{i}')
        model.Add(b_only <= group_act)
        model.Add(b_only <= 1 - chig_in)
        model.Add(b_only >= group_act - chig_in)
        # chig_in solo puede valer 1 si de verdad hay SB o JP en el viaje
        model.Add(chig_in <= in_bin[SB] + in_bin[JP])
        extra    = _extra_stops(model, list(in_bin.values()), f'm_extra_{i}')
        over_two = _over_two_farms(model, list(in_bin.values()), f'm_ot_{i}')
        active   = _or_bin_from_list(model, list(in_bin.values()), f'm_act_{i}')
        cost = model.NewIntVar(0, 3_000_000, f'm_cost_{i}')
        model.Add(cost == MULA_EDWIN_CHIG_COST * chig_in + MULA_EDWIN_APTO_COST * b_only)  # no cobra cuarteo
        pool.append({'carrier': CARRIER_LABELS['MULA_EDWIN'], 'farms': amt, 'active': active, 'cost': cost,
                     'total': total, 'chig_in': chig_in, 'extra': extra, 'over_two': over_two})
    _break_symmetry(pool)
    slots += pool

    # ── Escenario 'dos viajes Edwin': viajes obligados del Trailer Azul ──
    # Un cupo por municipio que alcance 24P: solo fincas de ese municipio,
    # exactamente 24P (lleno), tarifa plena, siempre activo. No aplica la
    # regla de 'si toca Chigorodo es el unico del dia'.
    for code in forced_trips:
        farms_m = GROUP_A if code == 'CHIG' else GROUP_B
        amt, in_bin = {}, {}
        for f in farms_m:
            amt[f]    = model.NewIntVar(0, min(d[f], CAP_MULA_EDWIN), f'mf_{code}_{f}')
            in_bin[f] = model.NewBoolVar(f'mf_in_{code}_{f}')
            model.Add(amt[f] <= CAP_MULA_EDWIN * in_bin[f]); model.Add(amt[f] >= in_bin[f])
        total = model.NewIntVar(CAP_MULA_EDWIN, CAP_MULA_EDWIN, f'mf_tot_{code}')
        model.Add(total == sum(amt.values()))
        cost_val = MULA_EDWIN_CHIG_COST if code == 'CHIG' else MULA_EDWIN_APTO_COST
        extra    = _extra_stops(model, list(in_bin.values()), f'mf_extra_{code}')
        over_two = _over_two_farms(model, list(in_bin.values()), f'mf_ot_{code}')
        slots.append({'carrier': CARRIER_LABELS['MULA_EDWIN'], 'farms': amt,
                      'active': model.NewConstant(1), 'cost': model.NewConstant(cost_val),
                      'total': total, 'extra': extra, 'over_two': over_two, 'forced': True})

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

    # Mula nueva de Edwin: misma logica -- max 2 viajes/dia, pero si alguno
    # toca Chigorodo (San Bartolo o Juana Pio) es el unico del dia.
    mula_slots = [s for s in slots if s['carrier'] == CARRIER_LABELS['MULA_EDWIN'] and not s.get('forced')]
    if mula_slots:
        model.Add(sum(s['active'] for s in mula_slots) + sum(s['chig_in'] for s in mula_slots) <= 2)

    # ── Desempate entre soluciones igual de baratas ──
    # El costo SIEMPRE manda -- estos criterios solo deciden cual de varias
    # rutas igual de baratas se muestra, nunca escogen una mas cara.
    # 1) Evitar en lo posible viajes que mezclen 3 o mas fincas (2 esta
    #    bien, es logisticamente normal; 3+ es un enredo). Si la unica
    #    forma de llegar al precio mas barato es con 3+ fincas, se deja
    #    igual -- este criterio nunca sube el costo, solo desempata.
    # 2) Entre las que quedan, preferir la que en total tenga menos
    #    "paradas" (fincas distintas recogidas, sumando todos los viajes).
    total_over_two = model.NewIntVar(0, 10_000, 'total_over_two')
    model.Add(total_over_two == sum(s['over_two'] for s in slots))
    total_stops = model.NewIntVar(0, 10_000, 'total_stops')
    model.Add(total_stops == sum(s['active'] for s in slots) + sum(s['extra'] for s in slots))
    model.Minimize((sum(s['cost'] for s in slots) + FRENO_CUARTEO * sum(s['extra'] for s in slots)) * 1000
                   + total_over_two * 50 + total_stops)

    solver = cp_model.CpSolver()
    # Un solo hilo de busqueda: con varios hilos en paralelo (num_search_workers
    # alto) el solver puede devolver soluciones distintas -- igual de baratas,
    # pero con distinta repartición de camiones -- en corridas diferentes del
    # mismo pedido. Con un solo hilo la busqueda es determinística: mismo
    # pedido, siempre exactamente el mismo resultado.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
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
    return {'trips': trips, 'total_cost': total_cost, 'notas': notas}
