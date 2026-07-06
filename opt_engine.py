#!/usr/bin/env python3
"""
Motor de optimizacion de rutas - Exportadora de Banano
Yuber: precio base 20P, +$25.000 por pallet adicional hasta 24P.
Viaje combinado Chigorodo+Apartado: +$100.000 entrada Apartado.
Demetrio: puede hacer 2 viajes por dia (Viaje 1 y Viaje 2).
Edwin Echavarria: Mula 24P — $1.050.000 desde Chigorodo, $600.000 desde Apartado.
"""

import pandas as pd
import re
import math
import io
import copy
from itertools import combinations
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Flota ────────────────────────────────────────────────────
VEHICLE_DISPLAY = {
    'YUBER_MULA_1':        {'conductor': 'Yuber',   'vehicle': 'Mula 1 - 24P'},
    'YUBER_MULA_2':        {'conductor': 'Yuber',   'vehicle': 'Mula 2 - 24P'},
    'YUBER_MULA_3':        {'conductor': 'Yuber',   'vehicle': 'Mula 3 - 24P'},
    'YUBER_MULA_4':        {'conductor': 'Yuber',   'vehicle': 'Mula 4 - 24P'},
    'DEMETRIO_PATINETA':   {'conductor': 'Demetrio', 'vehicle': 'Patineta 18P (Viaje 1)'},
    'DEMETRIO_PATINETA_2': {'conductor': 'Demetrio', 'vehicle': 'Patineta 18P (Viaje 2)'},
    'EDWIN_MULA':          {'conductor': 'Edwin',   'vehicle': 'Mula 24P (Viaje 1)'},
    'EDWIN_MULA_2':        {'conductor': 'Edwin',   'vehicle': 'Mula 24P (Viaje 2)'},
}

ALL_VEHICLE_IDS = list(VEHICLE_DISPLAY.keys())

# Yuber: costo = precio base (≤20P). Pallets 21-24: +$25.000 c/u.
_YUBER_CHIGORODO = [
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_1'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_2'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_3'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_4'},
]
_YUBER_APARTADO = [
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 630000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_1'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 630000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_2'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 630000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_3'},
    {'conductor': 'YUBER', 'tipo': 'MULA', 'capacidad': 24, 'costo': 630000,
     'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'YUBER_MULA_4'},
]

_EDWIN_CHIGORODO = [
    {'conductor': 'EDWIN', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'vehicle_id': 'EDWIN_MULA'},
    {'conductor': 'EDWIN', 'tipo': 'MULA', 'capacidad': 24, 'costo': 1050000,
     'vehicle_id': 'EDWIN_MULA_2'},
]
_EDWIN_APARTADO = [
    {'conductor': 'EDWIN', 'tipo': 'MULA', 'capacidad': 24, 'costo': 600000,
     'vehicle_id': 'EDWIN_MULA'},
    {'conductor': 'EDWIN', 'tipo': 'MULA', 'capacidad': 24, 'costo': 600000,
     'vehicle_id': 'EDWIN_MULA_2'},
]

VEHICLES_BY_ROUTE = {
    ('CHIGORODO', 'PUERTO ANTIOQUIA'): _YUBER_CHIGORODO + _EDWIN_CHIGORODO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
    ],
    ('CHIGORODO', 'UNIBAN ZUNGO'): _YUBER_CHIGORODO + _EDWIN_CHIGORODO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
    ],
    ('APARTADO', 'PUERTO ANTIOQUIA'): _YUBER_APARTADO + _EDWIN_APARTADO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
    ],
    ('APARTADO', 'UNIBAN ZUNGO'): _YUBER_APARTADO + _EDWIN_APARTADO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
    ],
}

CONSOLIDACION_ROUTES = {}

FARM_ZONES = {
    'SANTA MARIA DEL MONTE': 'APARTADO',
    'STA MARIA DEL MONTE':   'APARTADO',
    'DONA FRANCIA':          'APARTADO',
    'DOÑA FRANCIA':          'APARTADO',
    'CHISPERO':              'APARTADO',
    'SALVAMENTO':            'APARTADO',
    'JUANA PIO':             'CHIGORODO',
    'SAN BARTOLO':           'CHIGORODO',
}

# Capacidad máxima disponible al mediodía por finca (pallets).
# Fincas no listadas: sin restricción (salen todos al mediodía si hace falta).
FARM_MEDIODIA_MAX = {
    'CHISPERO':              12,
    'SANTA MARIA DEL MONTE': 16,
    'STA MARIA DEL MONTE':   16,
    'DONA FRANCIA':          20,
    'DOÑA FRANCIA':          20,
    'SAN BARTOLO':           15,
    'JUANA PIO':             13,
    'SALVAMENTO':            99,
}

DAY_ORDER  = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO']
DAY_EMOJIS = {'LUNES': '🟢', 'MARTES': '🔵', 'MIERCOLES': '🟡', 'JUEVES': '🟠', 'VIERNES': '🔴', 'SABADO': '⚪'}
DAY_COLORS = {'LUNES': '1B5E20', 'MARTES': '0D47A1', 'MIERCOLES': 'F57F17', 'JUEVES': 'E65100', 'VIERNES': 'B71C1C', 'SABADO': '424242'}

ALL_CONDUCTORS = list({v['conductor'] for v in VEHICLE_DISPLAY.values()})


# ── Parser ────────────────────────────────────────────────────
def parse_orders(pedidos_file):
    df = pd.read_excel(pedidos_file, sheet_name=0, header=None)
    day_row = df.iloc[2]
    day_start_cols = {}
    for col_idx, val in enumerate(day_row):
        if pd.notna(val):
            val_upper = str(val).strip().upper()
            for d in DAY_ORDER:
                if val_upper == d:
                    day_start_cols[col_idx] = d
                    break
            if col_idx not in day_start_cols:
                for d in DAY_ORDER:
                    if d in val_upper or val_upper in d:
                        day_start_cols[col_idx] = d
                        break
    if not day_start_cols:
        raise ValueError("No se encontraron dias en fila 3 del Excel")
    sorted_starts = sorted(day_start_cols.keys())
    day_ranges = {}
    for i, start in enumerate(sorted_starts):
        end = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else df.shape[1]
        day_ranges[day_start_cols[start]] = (start, end)
    port_row        = df.iloc[3]
    pallet_size_row = df.iloc[5]
    farm_data       = df.iloc[6:].copy()
    orders = {}
    for day_name, (start_col, end_col) in day_ranges.items():
        port = 'PUERTO ANTIOQUIA'
        if pd.notna(port_row.iloc[start_col]):
            pv = str(port_row.iloc[start_col]).upper()
            if 'ZUNGO' in pv or 'UNIBAN' in pv:
                port = 'UNIBAN ZUNGO'
        pallet_sizes = []
        last_ps = 55
        for col_idx in range(start_col, end_col):
            v = pallet_size_row.iloc[col_idx]
            if pd.notna(v):
                m = re.search(r'(\d+)', str(v))
                if m:
                    last_ps = int(m.group(1))
            pallet_sizes.append(last_ps)
        for _, row in farm_data.iterrows():
            farm_raw = row.iloc[0]
            if pd.isna(farm_raw):
                continue
            farm_name     = str(farm_raw).strip().upper()
            total_cajas   = 0.0
            total_pallets = 0
            pallets_by_size = {}
            for i, col_idx in enumerate(range(start_col, end_col)):
                val = row.iloc[col_idx]
                if pd.isna(val):
                    continue
                try:
                    cajas = float(val)
                except (ValueError, TypeError):
                    continue
                if cajas > 0:
                    ps = pallet_sizes[i]
                    p  = math.ceil(cajas / ps)
                    total_cajas   += cajas
                    total_pallets += p
                    pallets_by_size[ps] = pallets_by_size.get(ps, 0) + p
            if total_cajas > 0:
                if day_name not in orders:
                    orders[day_name] = {}
                if farm_name not in orders[day_name]:
                    orders[day_name][farm_name] = {}
                orders[day_name][farm_name][port] = {
                    'cajas':           int(round(total_cajas)),
                    'pallets':         total_pallets,
                    'pallets_by_size': pallets_by_size,
                }
    return orders


# ── Knapsack 0/1 con snapshot traceback ──────────────────────
def min_cost_assignment_bounded(total_pallets, vehicles):
    P = math.ceil(total_pallets)
    if P <= 0:
        return 0, []
    if not vehicles:
        return float('inf'), []
    INF     = float('inf')
    max_cap = sum(v['capacidad'] for v in vehicles)
    dp_cost = [INF] * (max_cap + 1)
    dp_cost[0] = 0
    snapshots = [dp_cost[:]]
    for v in vehicles:
        cap  = v['capacidad']
        cost = v['costo']
        for j in range(max_cap, cap - 1, -1):
            prev_j = j - cap
            if dp_cost[prev_j] == INF:
                continue
            new_cost = dp_cost[prev_j] + cost
            if new_cost < dp_cost[j]:
                dp_cost[j] = new_cost
        snapshots.append(dp_cost[:])
    best_j = -1
    for j in range(P, max_cap + 1):
        if dp_cost[j] == INF:
            continue
        if best_j == -1 or dp_cost[j] < dp_cost[best_j]:
            best_j = j
        elif dp_cost[j] == dp_cost[best_j] and (j - P) < (best_j - P):
            best_j = j
    if best_j == -1:
        for j in range(max_cap, -1, -1):
            if dp_cost[j] != INF:
                best_j = j
                break
    if best_j == -1:
        return INF, []
    selected = []
    j = best_j
    for i in range(len(vehicles) - 1, -1, -1):
        v    = vehicles[i]
        cap  = v['capacidad']
        cost = v['costo']
        if j >= cap:
            prev_j = j - cap
            if (snapshots[i][prev_j] != INF and
                    snapshots[i][prev_j] + cost == snapshots[i + 1][j]):
                selected.append(v)
                j = prev_j
    trips     = []
    remaining = P
    for v in sorted(selected, key=lambda x: -x['capacidad']):
        load = min(v['capacidad'], remaining)
        trips.append({
            'conductor':          v['conductor'],
            'tipo':               v['tipo'],
            'capacidad':          v['capacidad'],
            'costo':              v['costo'],
            'costo_base':         v['costo'],
            'pallets_negociados': v.get('pallets_negociados', v['capacidad']),
            'costo_extra_pallet': v.get('costo_extra_pallet', 0),
            'vehicle_id':         v.get('vehicle_id', ''),
            'pallets_cargados':   max(1, load),
            'farms':              {},
        })
        remaining -= load
    return dp_cost[best_j], trips


def recalculate_variable_costs(trips):
    """Actualiza el costo de viajes con precio variable (ej. Yuber) segun pallets cargados."""
    for t in trips:
        if t.get('costo_extra_pallet', 0) > 0:
            extra    = max(0, t['pallets_cargados'] - t['pallets_negociados'])
            t['costo'] = t['costo_base'] + extra * t['costo_extra_pallet']
    return trips


# ── Etiqueta de pallets por talla ─────────────────────────────
def pallet_size_label(assigned_int_pallets, farm_total_pallets, pallets_by_size):
    if not pallets_by_size or farm_total_pallets <= 0:
        return str(assigned_int_pallets) + "P"
    ratio      = assigned_int_pallets / farm_total_pallets
    raw        = {ps: cnt * ratio for ps, cnt in pallets_by_size.items()}
    floors     = {ps: int(v) for ps, v in raw.items()}
    remainders = {ps: raw[ps] - floors[ps] for ps in raw}
    extra      = assigned_int_pallets - sum(floors.values())
    for ps, _ in sorted(remainders.items(), key=lambda x: -x[1])[:max(0, int(extra))]:
        floors[ps] += 1
    parts = [str(cnt) + "P (" + str(ps) + "c)"
             for ps, cnt in sorted(floors.items(), key=lambda x: -x[0]) if cnt > 0]
    return " + ".join(parts)


def format_pallets_by_size(pallets_by_size, total_pallets=0):
    """Texto tipo '30P x55c + 30P x44c' a partir de un dict {talla: cantidad}."""
    parts = [f"{cnt}P x{ps}c"
             for ps, cnt in sorted(pallets_by_size.items(), key=lambda x: -x[0]) if cnt > 0]
    if parts:
        return " + ".join(parts)
    return f"{int(total_pallets)}P" if total_pallets else '-'


# ── Distribución de fincas en viajes ─────────────────────────
def assign_farms_to_trips(farm_pallets, farm_cajas, trips):
    sorted_farms = sorted(farm_pallets.items(), key=lambda x: -x[1])
    for trip in trips:
        trip['remaining'] = trip['pallets_cargados']
        trip['farms']     = {}
    for farm, fpallets in sorted_farms:
        rem_pallets = int(fpallets)
        rem_cajas   = farm_cajas[farm]
        for trip in trips:
            if trip['remaining'] > 0 and rem_pallets > 0:
                take = min(int(trip['remaining']), rem_pallets)
                rem_pallets -= take
                if rem_pallets == 0:
                    take_cajas = rem_cajas
                else:
                    ratio      = take / fpallets if fpallets > 0 else 0
                    take_cajas = min(int(round(ratio * farm_cajas[farm])), rem_cajas)
                trip['farms'][farm] = {'pallets': take, 'cajas': take_cajas}
                trip['remaining']  -= take
                rem_cajas          -= take_cajas
    return trips


# ── Relleno combinado Chigorodó→Apartadó ─────────────────────
def _combined_fill(chigorodo_trips, apart_route_data):
    """
    Rellena la capacidad sobrante de camiones Chigorodó con fincas de Apartadó.
    Yuber: cobra $100.000 extra por la entrada a Apartadó.
    Demetrio/Edwin: tarifa plana, sin costo adicional por mezclar zonas.
    El recorrido es siempre en ruta: Chigorodó primero, luego Apartadó.
    Modifica apart_route_data in-place reduciendo los pallets consumidos.
    """
    ENTRADA_APARTADO  = 100_000
    CONDUCTORS_TARDE  = {'YUBER', 'DEMETRIO', 'EDWIN'}

    for trip in chigorodo_trips:
        conductor = trip.get('conductor', '')
        if conductor not in CONDUCTORS_TARDE:
            continue
        spare = trip['capacidad'] - trip['pallets_cargados']
        if spare <= 0:
            continue

        added_any = False
        for farm in sorted(apart_route_data, key=lambda f: -apart_route_data[f]['pallets']):
            if spare <= 0:
                break
            fdata = apart_route_data[farm]
            if fdata['pallets'] <= 0:
                continue
            take_p = min(spare, fdata['pallets'])
            # Cajas proporcionales (exactas si es el ultimo trozo)
            if take_p == fdata['pallets']:
                take_c = fdata['cajas']
            else:
                take_c = min(int(round(take_p / fdata['pallets'] * fdata['cajas'])), fdata['cajas'])

            existing = trip['farms'].get(farm, {'pallets': 0, 'cajas': 0})
            trip['farms'][farm] = {
                'pallets': existing['pallets'] + take_p,
                'cajas':   existing['cajas']   + take_c,
            }
            trip['pallets_cargados'] += take_p
            fdata['pallets'] -= take_p
            fdata['cajas']   -= take_c
            spare             -= take_p
            added_any          = True

        if added_any and conductor == 'YUBER':
            # Yuber: recalcular costo con entrada Apartadó + extra pallets
            extra      = max(0, trip['pallets_cargados'] - trip['pallets_negociados'])
            trip['costo'] = (trip['costo_base']
                             + ENTRADA_APARTADO
                             + extra * trip['costo_extra_pallet'])
        # Demetrio/Edwin: tarifa plana, costo no cambia


# ── Etiquetas Mediodía / Tarde ────────────────────────────────
def label_trip_times(trips):
    """
    Asigna 'hora' = 'Mediodía' o 'Tarde' a cada viaje de exportación.
    - Yuber: siempre 'Tarde'
    - Demetrio/Edwin con 2+ viajes en el día:
        El viaje con una sola zona (zona pura) y más pallets = 'Mediodía'.
        El resto = 'Tarde' (incluyendo los que mezclan Chigorodó→Apartadó).
    - Demetrio/Edwin con 1 solo viaje → 'Tarde'
    """
    export_trips = [t for t in trips if t.get('trip_type') == 'export']

    by_conductor = {}
    for t in export_trips:
        by_conductor.setdefault(t.get('conductor', ''), []).append(t)

    for conductor, ctrips in by_conductor.items():
        if conductor not in ('DEMETRIO', 'EDWIN'):
            for t in ctrips:
                t['hora'] = 'Tarde'
            continue

        if len(ctrips) >= 2:
            # Ordena: zona pura (1 zona) primero, luego pallets desc.
            # El trip más lleno y sin mezcla de zonas = Mediodía.
            # Trips con mezcla Chigorodó→Apartadó siempre quedan como Tarde.
            def _key(t):
                n_zones = len({FARM_ZONES.get(f, t.get('zone', ''))
                               for f in t.get('farms', {})})
                return (n_zones, -t.get('pallets_cargados', 0))
            ctrips_sorted = sorted(ctrips, key=_key)
            ctrips_sorted[0]['hora'] = 'Mediodía'
            for t in ctrips_sorted[1:]:
                t['hora'] = 'Tarde'
        else:
            ctrips[0]['hora'] = 'Tarde'

    return trips


# ── Optimizacion diaria ───────────────────────────────────────
def _optimize_phase(phase_orders, unavailable_vehicle_ids=None, enable_combined_fill=True):
    if unavailable_vehicle_ids is None:
        unavailable_vehicle_ids = set()

    route_groups = {}
    for farm, port_data in phase_orders.items():
        zone = FARM_ZONES.get(farm, 'APARTADO')
        for port, data in port_data.items():
            key = (zone, port)
            if key not in route_groups:
                route_groups[key] = {}
            route_groups[key][farm] = {
                'pallets':         data['pallets'],
                'cajas':           data['cajas'],
                'pallets_by_size': data.get('pallets_by_size', {}),
            }

    all_trips        = []
    used_vehicle_ids = set()

    _route_avail = {
        rk: [v for v in VEHICLES_BY_ROUTE.get(rk, [])
             if v.get('vehicle_id', '') not in unavailable_vehicle_ids]
        for rk in route_groups
    }

    def _shared_demand(route_key):
        my_vids    = {v['vehicle_id'] for v in _route_avail[route_key]}
        other_vids = set()
        for k in route_groups:
            if k != route_key:
                other_vids |= {v['vehicle_id'] for v in _route_avail[k]}
        excl_cap = sum(v['capacidad'] for v in _route_avail[route_key]
                       if v['vehicle_id'] not in other_vids)
        total_p  = sum(d['pallets'] for d in route_groups[route_key].values())
        # Rutas sin capacidad exclusiva dependen 100% de vehículos compartidos
        # → deben procesarse primero para garantizar que no pierdan cajas.
        if excl_cap == 0:
            return float('inf')
        return max(0, total_p - excl_cap)

    sorted_routes = sorted(
        route_groups.items(),
        key=lambda x: _shared_demand(x[0]),
        reverse=True,
    )

    combined_done   = set()  # puertos donde ya se intento relleno combinado
    processed_routes = set()  # rutas (zona, puerto) ya procesadas

    for (zone, port), farm_data in sorted_routes:
        # Filtrar fincas con pallets reales (pueden haberse reducido por relleno combinado)
        farm_pallets = {f: d['pallets'] for f, d in farm_data.items() if d['pallets'] > 0}
        farm_cajas   = {f: d['cajas']   for f, d in farm_data.items() if d['pallets'] > 0}
        farm_psize   = {f: d.get('pallets_by_size', {}) for f, d in farm_data.items() if d['pallets'] > 0}
        total = sum(farm_pallets.values())
        if total <= 0:
            continue

        def avail(v):
            vid = v.get('vehicle_id', '')
            return vid not in unavailable_vehicle_ids and vid not in used_vehicle_ids

        vehicles = [v for v in VEHICLES_BY_ROUTE.get((zone, port), []) if avail(v)]
        if not vehicles:
            continue

        def tag(trips_list, dest, ttype):
            for t in trips_list:
                t['zone']               = zone
                t['destination']        = dest
                t['trip_type']          = ttype
                t['farm_pallets_size']  = farm_psize
                t['farm_total_pallets'] = farm_pallets

        cost_a, trips_a = min_cost_assignment_bounded(total, vehicles)
        trips_a = assign_farms_to_trips(farm_pallets, farm_cajas, trips_a)
        recalculate_variable_costs(trips_a)
        tag(trips_a, port, 'export')

        consol_candidates = [f for f in farm_pallets if f in CONSOLIDACION_ROUTES]
        if not consol_candidates:
            for t in trips_a:
                used_vehicle_ids.add(t.get('vehicle_id', ''))
            all_trips.extend(trips_a)
        else:
            consol_trips = []
            consol_cost  = 0
            consol_used  = set()
            for farm in consol_candidates:
                cv = [v for v in CONSOLIDACION_ROUTES[farm]
                      if v.get('vehicle_id') not in unavailable_vehicle_ids
                      and v.get('vehicle_id') not in used_vehicle_ids
                      and v.get('vehicle_id') not in consol_used]
                if not cv:
                    continue
                fp = {farm: farm_pallets[farm]}
                fc = {farm: farm_cajas[farm]}
                cc, ct = min_cost_assignment_bounded(farm_pallets[farm], cv)
                consol_cost += cc
                ct = assign_farms_to_trips(fp, fc, ct)
                tag(ct, 'DONA FRANCIA', 'consolidacion')
                for t in ct:
                    consol_used.add(t.get('vehicle_id', ''))
                consol_trips.extend(ct)
            vehicles_b     = [v for v in vehicles if v.get('vehicle_id') not in consol_used]
            cost_b_exp, trips_b = min_cost_assignment_bounded(total, vehicles_b)
            trips_b = assign_farms_to_trips(farm_pallets, farm_cajas, trips_b)
            recalculate_variable_costs(trips_b)
            tag(trips_b, port, 'export')
            cost_b       = consol_cost + cost_b_exp
            chosen_trips = consol_trips + trips_b if cost_b < cost_a else trips_a
            for t in chosen_trips:
                used_vehicle_ids.add(t.get('vehicle_id', ''))
            all_trips.extend(chosen_trips)

        processed_routes.add((zone, port))

        # Relleno combinado: si acabamos de procesar Chigorodo y Apartado aun
        # no ha sido procesado, aprovechar capacidad sobrante de Yuber/Edwin
        # para recoger fincas de Apartado (reduce lo que Apartado tendra que cubrir).
        # Si Apartado ya fue procesado primero, NO hacer relleno para evitar
        # contar cajas dos veces.
        if enable_combined_fill and zone == 'CHIGORODO' and port not in combined_done:
            apart_key = ('APARTADO', port)
            if apart_key in route_groups and apart_key not in processed_routes:
                combined_done.add(port)
                chigorodo_trips = [t for t in all_trips
                                   if t.get('zone') == 'CHIGORODO'
                                   and t.get('destination') == port
                                   and t.get('trip_type') == 'export']
                _combined_fill(chigorodo_trips, route_groups[apart_key])

    return all_trips


# ── Sugerencias de consolidacion entre dias ──────────────────

# ── Helpers para split mediodía / tarde ──────────────────────
def _cap_to_mediodia(day_orders):
    """Demanda capada a FARM_MEDIODIA_MAX: solo lo que está listo al mediodía."""
    result = {}
    for farm, port_data in day_orders.items():
        cap = FARM_MEDIODIA_MAX.get(farm, float('inf'))
        if cap <= 0:
            continue
        for port, data in port_data.items():
            if data.get('pallets', 0) <= 0:
                continue
            m_p = min(data['pallets'], cap)
            if m_p <= 0:
                continue
            ratio = m_p / data['pallets']
            result.setdefault(farm, {})[port] = {
                'pallets':         m_p,
                'cajas':           int(round(ratio * data['cajas'])),
                'pallets_by_size': {k: max(1, int(round(v * ratio)))
                                    for k, v in data.get('pallets_by_size', {}).items()
                                    if v > 0},
            }
    return result


def _compute_tarde_demand(day_orders, mediodia_trips):
    """Demanda restante = pedido original menos lo ya asignado en la fase mediodía."""
    assigned = {}
    for t in mediodia_trips:
        if t.get('trip_type') != 'export':
            continue
        port = t.get('destination', '')
        for farm, fdata in t['farms'].items():
            key = (farm, port)
            assigned.setdefault(key, {'pallets': 0, 'cajas': 0})
            assigned[key]['pallets'] += fdata.get('pallets', 0)
            assigned[key]['cajas']   += fdata.get('cajas', 0)

    result = {}
    for farm, port_data in day_orders.items():
        for port, data in port_data.items():
            asgn  = assigned.get((farm, port), {'pallets': 0, 'cajas': 0})
            rem_p = data['pallets'] - asgn['pallets']
            rem_c = data['cajas']   - asgn['cajas']
            if rem_p <= 0:
                continue
            ratio = rem_p / data['pallets'] if data['pallets'] > 0 else 0
            result.setdefault(farm, {})[port] = {
                'pallets':         rem_p,
                'cajas':           max(0, rem_c),
                'pallets_by_size': {k: max(0, int(round(v * ratio)))
                                    for k, v in data.get('pallets_by_size', {}).items()},
            }
    return result


# ── Optimizacion diaria (dos fases: mediodía + tarde) ────────
def optimize_day(day_orders, unavailable_vehicle_ids=None, relaxed=False):
    """
    Optimiza un día completo en dos fases:
    - Mediodía: demanda capada a FARM_MEDIODIA_MAX. Sin mezcla de zonas.
    - Tarde:    demanda restante. Combined fill Chigorodó→Apartadó habilitado.
    """
    if unavailable_vehicle_ids is None:
        unavailable_vehicle_ids = set()

    # Fase 1: Mediodía — solo lo que está listo, zona pura
    # Viaje 2 de Demetrio/Edwin siempre reservados para tarde
    VIAJE2_VIDS = {'DEMETRIO_PATINETA_2', 'EDWIN_MULA_2'}
    mediodia_orders = _cap_to_mediodia(day_orders)
    mediodia_trips  = _optimize_phase(
        mediodia_orders,
        unavailable_vehicle_ids=unavailable_vehicle_ids | VIAJE2_VIDS,
        enable_combined_fill=False,
    )
    # Descartar viajes mediodía que salgan con menos del 80% de la
    # capacidad disponible de las fincas al mediodía — no vale la pena
    # mandar una mula medio vacía.
    # Umbral mediodía por tipo de vehículo:
    #   Mulas (24P): necesitan ≥ 80% = 19P para justificar el viaje de mañana
    #   Patinetas (18P): umbral más suave 60% = 11P (rutas más cortas, menor costo)
    def _mediodia_min(cap):
        if relaxed:
            return 0
        return int(cap * (0.60 if cap <= 18 else 0.80))
    mediodia_trips = [t for t in mediodia_trips
                      if t.get('trip_type') != 'export'
                      or t.get('pallets_cargados', 0) >= _mediodia_min(t.get('capacidad', 24))]
    for t in mediodia_trips:
        t['hora'] = 'Mediodía'

    # Fase 2: Tarde — sobrante, combined fill habilitado
    mediodia_vids = {t['vehicle_id'] for t in mediodia_trips}
    # Viaje1 de conductores con 2 slots (Demetrio/Edwin): si no salió en mediodía,
    # bloquearlo también en tarde — un conductor no puede hacer 2 viajes de tarde.
    VIAJE1_VIDS = {'DEMETRIO_PATINETA', 'EDWIN_MULA'}
    unused_viaje1 = VIAJE1_VIDS - mediodia_vids - unavailable_vehicle_ids
    tarde_orders  = _compute_tarde_demand(day_orders, mediodia_trips)
    tarde_trips   = _optimize_phase(
        tarde_orders,
        unavailable_vehicle_ids=unavailable_vehicle_ids | mediodia_vids | unused_viaje1,
        enable_combined_fill=True,
    )
    for t in tarde_trips:
        t['hora'] = 'Tarde'

    # Filtro tarde: descartar viajes con menos de 5 pallets
    # (remanentes mínimos — se consolidan al día siguiente).
    TARDE_MIN_PALLETS = 0 if relaxed else 5
    tarde_trips = [t for t in tarde_trips
                   if t.get('trip_type') != 'export'
                   or t.get('pallets_cargados', 0) >= TARDE_MIN_PALLETS]

    return mediodia_trips + tarde_trips


def _day_metrics(day_orders, unavailable_vehicle_ids=None):
    """Devuelve (costo_total, cajas_perdidas) para un pedido de un dia."""
    trips = optimize_day(day_orders, unavailable_vehicle_ids=unavailable_vehicle_ids)
    export_trips = [t for t in trips if t.get('trip_type') == 'export']
    cost          = sum(t['costo'] for t in trips)
    cajas_shipped = sum(sum(f['cajas'] for f in t['farms'].values()) for t in export_trips)
    cajas_total   = sum(d['cajas'] for port_data in day_orders.values() for d in port_data.values())
    return cost, max(0, cajas_total - cajas_shipped)


def _split_blocks(entry):
    """Divide el pedido de una finca/puerto en bloques por talla de pallet."""
    pallets_by_size = entry.get('pallets_by_size', {})
    total_pallets   = entry['pallets']
    total_cajas     = entry['cajas']
    if not pallets_by_size or total_pallets <= 0:
        return [{'size': None, 'pallets': total_pallets, 'cajas': total_cajas}]
    items = sorted(pallets_by_size.items())
    blocks = []
    assigned_cajas = 0
    for idx, (size, count) in enumerate(items):
        if count <= 0:
            continue
        if idx == len(items) - 1:
            cajas = total_cajas - assigned_cajas
        else:
            cajas = int(round(total_cajas * (count / total_pallets)))
            assigned_cajas += cajas
        blocks.append({'size': size, 'pallets': count, 'cajas': cajas})
    return blocks


def _remove_blocks(day_orders, farm, port, blocks):
    """Copia day_orders sin los bloques indicados (restados de farm/port)."""
    new_orders = copy.deepcopy(day_orders)
    entry = new_orders.get(farm, {}).get(port)
    if not entry:
        return new_orders
    for b in blocks:
        entry['pallets'] -= b['pallets']
        entry['cajas']   -= b['cajas']
        if b['size'] is not None:
            psz = entry.get('pallets_by_size', {})
            psz[b['size']] = psz.get(b['size'], 0) - b['pallets']
            if psz[b['size']] <= 0:
                psz.pop(b['size'], None)
    if entry['pallets'] <= 0:
        del new_orders[farm][port]
        if not new_orders[farm]:
            del new_orders[farm]
    return new_orders


def _add_blocks(day_orders, farm, port, blocks):
    """Copia day_orders con los bloques indicados sumados a farm/port."""
    new_orders = copy.deepcopy(day_orders)
    if farm not in new_orders:
        new_orders[farm] = {}
    if port not in new_orders[farm]:
        new_orders[farm][port] = {'cajas': 0, 'pallets': 0, 'pallets_by_size': {}}
    entry = new_orders[farm][port]
    entry.setdefault('pallets_by_size', {})
    for b in blocks:
        entry['pallets'] += b['pallets']
        entry['cajas']   += b['cajas']
        if b['size'] is not None:
            entry['pallets_by_size'][b['size']] = entry['pallets_by_size'].get(b['size'], 0) + b['pallets']
    return new_orders


def suggest_consolidations(orders, unavailable_vehicle_ids_by_day=None, min_savings=30000):
    """
    Busca oportunidades de juntar (total o parcialmente) el pedido de una
    misma finca+puerto entre dos dias consecutivos para ahorrar costo de
    transporte, sin aumentar las cajas perdidas.
    Devuelve una lista de sugerencias ordenadas por ahorro descendente.
    """
    if unavailable_vehicle_ids_by_day is None:
        unavailable_vehicle_ids_by_day = {}

    sorted_days = sorted(orders.keys(), key=lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else 99)
    suggestions = []

    for i in range(len(sorted_days) - 1):
        day_a, day_b = sorted_days[i], sorted_days[i + 1]
        unavail_a = unavailable_vehicle_ids_by_day.get(day_a, set())
        unavail_b = unavailable_vehicle_ids_by_day.get(day_b, set())
        orders_a, orders_b = orders[day_a], orders[day_b]

        cost_a0, loss_a0 = _day_metrics(orders_a, unavail_a)
        cost_b0, loss_b0 = _day_metrics(orders_b, unavail_b)
        base_cost = cost_a0 + cost_b0
        base_loss = loss_a0 + loss_b0

        farms_ports = set()
        for farm, pd_ in orders_a.items():
            for port in pd_:
                farms_ports.add((farm, port))
        for farm, pd_ in orders_b.items():
            for port in pd_:
                farms_ports.add((farm, port))

        for farm, port in farms_ports:
            for from_day, to_day, src_orders, dst_orders, unavail_src, unavail_dst in (
                (day_a, day_b, orders_a, orders_b, unavail_a, unavail_b),
                (day_b, day_a, orders_b, orders_a, unavail_b, unavail_a),
            ):
                entry = src_orders.get(farm, {}).get(port)
                if not entry or entry['pallets'] <= 0:
                    continue
                blocks = _split_blocks(entry)
                n = len(blocks)
                best = None
                for r in range(1, n + 1):
                    for combo in combinations(range(n), r):
                        move_blocks = [blocks[k] for k in combo]
                        new_src = _remove_blocks(src_orders, farm, port, move_blocks)
                        new_dst = _add_blocks(dst_orders, farm, port, move_blocks)
                        if from_day == day_a:
                            cost_a1, loss_a1 = _day_metrics(new_src, unavail_a)
                            cost_b1, loss_b1 = _day_metrics(new_dst, unavail_b)
                        else:
                            cost_b1, loss_b1 = _day_metrics(new_src, unavail_b)
                            cost_a1, loss_a1 = _day_metrics(new_dst, unavail_a)
                        new_cost = cost_a1 + cost_b1
                        new_loss = loss_a1 + loss_b1
                        if new_loss > base_loss:
                            continue
                        savings = base_cost - new_cost
                        if savings <= 0:
                            continue
                        if best is None or savings > best['savings']:
                            best = {'savings': savings, 'blocks': move_blocks, 'is_full': (r == n)}
                if best and best['savings'] >= min_savings:
                    suggestions.append({
                        'farm':     farm,
                        'port':     port,
                        'from_day': from_day,
                        'to_day':   to_day,
                        'blocks':   best['blocks'],
                        'pallets':  sum(b['pallets'] for b in best['blocks']),
                        'cajas':    sum(b['cajas'] for b in best['blocks']),
                        'is_full':  best['is_full'],
                        'savings':  best['savings'],
                    })

    suggestions.sort(key=lambda s: -s['savings'])
    return suggestions


def apply_consolidation(orders, suggestion):
    """Aplica una sugerencia de consolidacion, modificando 'orders' in-place."""
    farm, port   = suggestion['farm'], suggestion['port']
    from_day     = suggestion['from_day']
    to_day       = suggestion['to_day']
    blocks       = suggestion['blocks']
    orders[from_day] = _remove_blocks(orders[from_day], farm, port, blocks)
    orders[to_day]   = _add_blocks(orders[to_day], farm, port, blocks)
    return orders


# ── Consolidación entre días ──────────────────────────────────
def compute_inter_day_moves(orders):
    """
    Detecta y propone movimientos de pallets entre días consecutivos.
    Regla 1 – DIFERIMIENTO: pallets no enviados el día D van al día D+1
              si la finca tiene pedido en D+1.
    Regla 2 – ANTICIPACIÓN: pallets del día D+1 muy pocos (< 5P) se
              adelantan al día D si la finca tiene pedido en D.
    Retorna (adjusted_orders, moves_list).
    """
    ANTICIPATION_MAX = 5
    dias     = [d for d in DAY_ORDER if d in orders]
    adjusted = copy.deepcopy(orders)
    moves    = []

    # Paso 1: Diferimientos
    for i, dia in enumerate(dias):
        if i + 1 >= len(dias):
            break
        next_dia   = dias[i + 1]
        day_orders = orders.get(dia, {})
        if not day_orders:
            continue
        trips   = optimize_day(day_orders)
        shipped = {}
        for t in trips:
            if t.get('trip_type') != 'export':
                continue
            port = t.get('destination', '')
            for farm, fd in t['farms'].items():
                shipped[(farm, port)] = shipped.get((farm, port), 0) + fd['pallets']

        for farm, port_data in day_orders.items():
            if farm not in adjusted.get(next_dia, {}):
                continue
            for port, data in port_data.items():
                diff = data['pallets'] - shipped.get((farm, port), 0)
                if diff <= 0:
                    continue
                ratio       = diff / data['pallets'] if data['pallets'] > 0 else 0
                extra_cajas = max(1, int(round(ratio * data['cajas'])))
                adjusted[dia][farm][port]['pallets'] -= diff
                adjusted[dia][farm][port]['cajas']    = max(0,
                    adjusted[dia][farm][port]['cajas'] - extra_cajas)
                if adjusted[dia][farm][port]['pallets'] <= 0:
                    adjusted[dia][farm].pop(port, None)
                if not adjusted[dia].get(farm):
                    adjusted[dia].pop(farm, None)
                if port not in adjusted[next_dia].get(farm, {}):
                    adjusted[next_dia].setdefault(farm, {})[port] = {
                        'pallets': 0, 'cajas': 0, 'pallets_by_size': {}}
                adjusted[next_dia][farm][port]['pallets'] += diff
                adjusted[next_dia][farm][port]['cajas']   += extra_cajas
                moves.append({'type': 'diferimiento', 'farm': farm,
                              'from_day': dia, 'to_day': next_dia,
                              'pallets': diff, 'cajas': extra_cajas,
                              'reason': f'Sin enviar el {dia.title()} — pocas unidades sin viaje disponible'})

    # Paso 2: Anticipaciones
    for i, dia in enumerate(dias[:-1]):
        next_dia = dias[i + 1]
        for farm, port_data in list(adjusted.get(next_dia, {}).items()):
            for port, data in list(port_data.items()):
                p = data['pallets']
                if p <= 0 or p >= ANTICIPATION_MAX:
                    continue
                if farm not in adjusted.get(dia, {}):
                    continue
                c = data['cajas']
                if port not in adjusted[dia].get(farm, {}):
                    adjusted[dia].setdefault(farm, {})[port] = {
                        'pallets': 0, 'cajas': 0, 'pallets_by_size': {}}
                adjusted[dia][farm][port]['pallets'] += p
                adjusted[dia][farm][port]['cajas']   += c
                adjusted[next_dia][farm][port]['pallets'] -= p
                adjusted[next_dia][farm][port]['cajas']    = max(0,
                    adjusted[next_dia][farm][port]['cajas'] - c)
                if adjusted[next_dia][farm][port]['pallets'] <= 0:
                    adjusted[next_dia][farm].pop(port, None)
                if not adjusted[next_dia].get(farm):
                    adjusted[next_dia].pop(farm, None)
                moves.append({'type': 'anticipación', 'farm': farm,
                              'from_day': next_dia, 'to_day': dia,
                              'pallets': p, 'cajas': c,
                              'reason': f'Solo {p}P solos en {next_dia.title()} — se adelantan a {dia.title()}'})

    return adjusted, moves


def write_suggested_pedido_sheet(wb, orders_orig, adjusted_orders, moves,
                                 semana_num, unavailable_vehicle_ids_by_day=None):
    """Hoja PEDIDO SUGERIDO: tabla comparativa + distribución de viajes por día."""
    if unavailable_vehicle_ids_by_day is None:
        unavailable_vehicle_ids_by_day = {}

    ws   = wb.create_sheet('PEDIDO SUGERIDO')
    dias = [d for d in DAY_ORDER if d in orders_orig]

    HDR_BG   = '1B5E20'
    HDR2_BG  = '2E7D32'
    BANA_BG  = 'E3F2FD'   # azul claro — original
    SUG_BG   = 'E8F5E9'   # verde claro — sugerido
    TOTAL_BG = 'F1F8E9'
    MOVE_HDR = 'E65100'
    SAVE_HDR = '01579B'
    ORIG_HDR = '1565C0'
    SB_HDR   = '2E7D32'
    alt      = ['FFFFFF', 'F8F9FA']

    def cell_fmt(c, value=None, bold=False, bg=None, color='000000',
                 halign='center', size=9, num_fmt=None, italic=False):
        if value is not None:
            c.value = value
        c.font      = Font(name='Arial', size=size, bold=bold,
                           color=color, italic=italic)
        if bg:
            c.fill  = PatternFill('solid', fgColor=bg)
        c.alignment = Alignment(horizontal=halign, vertical='center',
                                wrap_text=True)
        if num_fmt:
            c.number_format = num_fmt

    def fmt_farms(trip):
        farms = trip.get('farms', {})
        return '  ·  '.join(
            '{}: {}P'.format(fn.title(), fd['pallets'])
            for fn, fd in farms.items()
        )

    # Fixed column layout (11 cols, A=1..K=11)
    # A: Farm name / Conductor label
    # B-I: farm distribution (merged for trips) / day values for table
    # J: pallets / total
    # K: costo
    NCOLS = 11
    ws.column_dimensions['A'].width = 22
    for ci in range(2, 10):   # B-I
        ws.column_dimensions[get_column_letter(ci)].width = 9
    ws.column_dimensions['J'].width = 9
    ws.column_dimensions['K'].width = 14

    # ── ROW 1: Título ──────────────────────────────────────────────
    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    cell_fmt(ws.cell(row, 1),
             'PEDIDO SUGERIDO — SEMANA {}'.format(semana_num),
             bold=True, bg=HDR_BG, color='FFFFFF', size=12)
    ws.row_dimensions[row].height = 26
    row += 1

    # ── ROW 2: Subtítulo ───────────────────────────────────────────
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    cell_fmt(ws.cell(row, 1),
             'Banafrut = pedido original recibido  |  Sugerido = pedido optimizado sugerido',
             bg='F9FBE7', color='33691E', italic=True, size=9)
    ws.row_dimensions[row].height = 15
    row += 1

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 0: RESUMEN COMPARATIVO — Banafrut vs Sugerido totales
    # ══════════════════════════════════════════════════════════════
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    cell_fmt(ws.cell(row, 1), 'RESUMEN COMPARATIVO — BANAFRUT vs SUGERIDO',
             bold=True, bg='263238', color='FFFFFF', size=10)
    ws.row_dimensions[row].height = 20
    row += 1

    # Fila de grupos
    cell_fmt(ws.cell(row, 1), 'DÍA', bold=True, bg=HDR2_BG, color='FFFFFF', size=9)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
    cell_fmt(ws.cell(row, 2), 'PEDIDO BANAFRUT', bold=True, bg=ORIG_HDR, color='FFFFFF', size=9)
    ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=9)
    cell_fmt(ws.cell(row, 6), 'NUESTRA SUGERENCIA', bold=True, bg=SB_HDR, color='FFFFFF', size=9)
    ws.merge_cells(start_row=row, start_column=10, end_row=row, end_column=NCOLS)
    cell_fmt(ws.cell(row, 10), 'DIFERENCIA (+/−)', bold=True, bg=MOVE_HDR, color='FFFFFF', size=9)
    ws.row_dimensions[row].height = 16
    row += 1

    # Sub-cabeceras
    for ci, h in enumerate(['DÍA', 'Viajes', 'Cajas', 'Pallets', 'Costo',
                                 'Viajes', 'Cajas', 'Pallets', 'Costo',
                                 'Pallets', 'Costo'], 1):
        cell_fmt(ws.cell(row, ci), h, bold=True, bg='ECEFF1', size=8)
    border_all(ws, row-1, row, 1, NCOLS)
    ws.row_dimensions[row].height = 14
    row += 1

    grand_b0 = {'v':0,'c':0,'p':0,'co':0}
    grand_s0 = {'v':0,'c':0,'p':0,'co':0}
    for ri0, dia0 in enumerate(dias):
        unavail0 = unavailable_vehicle_ids_by_day.get(dia0, set())
        b_exp0 = [t for t in optimize_day(orders_orig.get(dia0, {}),
                  unavailable_vehicle_ids=unavail0, relaxed=True)
                  if t.get('trip_type') == 'export']
        sug_d0 = adjusted_orders.get(dia0, {})
        s_exp0 = ([t for t in optimize_day(sug_d0, unavailable_vehicle_ids=unavail0)
                   if t.get('trip_type') == 'export'] if sug_d0 else [])
        bv=len(b_exp0)
        bc=int(sum(sum(f['cajas'] for f in t['farms'].values()) for t in b_exp0))
        bp=int(sum(t['pallets_cargados'] for t in b_exp0))
        bco=int(sum(t['costo'] for t in b_exp0))
        sv=len(s_exp0)
        sc=int(sum(sum(f['cajas'] for f in t['farms'].values()) for t in s_exp0))
        sp=int(sum(t['pallets_cargados'] for t in s_exp0))
        sco=int(sum(t['costo'] for t in s_exp0))
        dp=sp-bp; dco=sco-bco
        bg0 = alt[ri0 % 2]
        dp_col  = 'C62828' if dp<0 else ('1B5E20' if dp>0 else '000000')
        dco_col = '1B5E20' if dco<0 else ('C62828' if dco>0 else '000000')
        row_vals = [dia0.capitalize(), bv, bc, bp, bco, sv, sc, sp, sco,
                    ('+' if dp>0 else '')+str(dp) if dp!=0 else '-',
                    dco if dco!=0 else '-']
        for ci0, val0 in enumerate(row_vals, 1):
            c0 = ws.cell(row, ci0)
            if ci0 == 5:
                cell_fmt(c0, bco, size=8, bg=bg0, num_fmt='"$"#,##0')
            elif ci0 == 9:
                cell_fmt(c0, sco, size=8, bg=bg0, num_fmt='"$"#,##0')
            elif ci0 in (3,7):
                cell_fmt(c0, bc if ci0==3 else sc, size=8, bg=bg0, num_fmt='#,##0')
            elif ci0 == 10:
                cell_fmt(c0, val0, size=8, bg=bg0, color=dp_col,
                         bold=(dp!=0), halign='center')
            elif ci0 == 11:
                cell_fmt(c0, dco if dco!=0 else '-', size=8, bg=bg0,
                         color=dco_col, bold=(dco!=0),
                         num_fmt='"$"#,##0' if dco!=0 else '@')
            else:
                cell_fmt(c0, val0, size=8, bg=bg0)
        grand_b0['v']+=bv; grand_b0['c']+=bc; grand_b0['p']+=bp; grand_b0['co']+=bco
        grand_s0['v']+=sv; grand_s0['c']+=sc; grand_s0['p']+=sp; grand_s0['co']+=sco
        border_all(ws, row, row, 1, NCOLS)
        ws.row_dimensions[row].height = 14
        row += 1

    # Fila TOTAL
    tot_dp=grand_s0['p']-grand_b0['p']; tot_dco=grand_s0['co']-grand_b0['co']
    tot_row=[('TOTAL',),
             (grand_b0['v'],None,False),(grand_b0['c'],'#,##0',False),
             (grand_b0['p'],None,False),(grand_b0['co'],'"$"#,##0',False),
             (grand_s0['v'],None,False),(grand_s0['c'],'#,##0',False),
             (grand_s0['p'],None,False),(grand_s0['co'],'"$"#,##0',False),
             (('+' if tot_dp>0 else '')+str(tot_dp) if tot_dp!=0 else '-', None, True),
             (tot_dco if tot_dco!=0 else '-', '"$"#,##0' if tot_dco!=0 else '@', True)]
    dco_tot_col = '1B5E20' if tot_dco<0 else ('C62828' if tot_dco>0 else '000000')
    dp_tot_col  = 'C62828' if tot_dp<0 else ('1B5E20' if tot_dp>0 else '000000')
    for ci0, item in enumerate(tot_row, 1):
        val0=item[0]; fmt0=item[1] if len(item)>1 else None; bld=item[2] if len(item)>2 else False
        col0='000000'
        if ci0==10: col0=dp_tot_col
        if ci0==11: col0=dco_tot_col
        c0=ws.cell(row, ci0)
        cell_fmt(c0, val0, bold=True, bg='E0E0E0', size=9, num_fmt=fmt0 or '', color=col0)
    border_all(ws, row, row, 1, NCOLS)
    ws.row_dimensions[row].height = 16
    row += 2

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 1: Tabla comparativa Banafrut vs Sugerido por finca
    # ══════════════════════════════════════════════════════════════
    all_farms = sorted({f for day in orders_orig.values() for f in day.keys()})

    # Cabeceras de días  (cols 2..1+len(dias)*2, 2 cols por día)
    ws.cell(row, 1).value = ''
    for ci, dia in enumerate(dias):
        col = 2 + ci * 2
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=col + 1)
        cell_fmt(ws.cell(row, col), dia.title(),
                 bold=True, bg=DAY_COLORS.get(dia, HDR_BG),
                 color='FFFFFF', size=9)
    ws.row_dimensions[row].height = 16
    row += 1

    # Sub-cabeceras FINCA / Banafrut / Sugerido
    cell_fmt(ws.cell(row, 1), 'FINCA', bold=True, bg=HDR2_BG, color='FFFFFF', size=9)
    for ci, dia in enumerate(dias):
        col = 2 + ci * 2
        cell_fmt(ws.cell(row, col),   'Banafrut', bold=True, bg=ORIG_HDR, color='FFFFFF', size=8)
        cell_fmt(ws.cell(row, col+1), 'Sugerido', bold=True, bg=SB_HDR,   color='FFFFFF', size=8)
    border_all(ws, row, row, 1, 1 + len(dias)*2)
    ws.row_dimensions[row].height = 14
    row += 1

    grand_orig = {d: 0 for d in dias}
    grand_sug  = {d: 0 for d in dias}
    for fi, farm in enumerate(all_farms):
        bg = alt[fi % 2]
        cell_fmt(ws.cell(row, 1), farm.title(), halign='left', size=9, bg=bg)
        for ci, dia in enumerate(dias):
            col  = 2 + ci * 2
            op   = orders_orig.get(dia, {}).get(farm, {})
            sp   = adjusted_orders.get(dia, {}).get(farm, {})
            ov   = sum(d['pallets'] for d in op.values()) if op else None
            sv   = sum(d['pallets'] for d in sp.values()) if sp else None
            diff_bg = 'FFF9C4' if sv != ov else bg
            cell_fmt(ws.cell(row, col),   ov if ov else '', size=9, bg=bg)
            cell_fmt(ws.cell(row, col+1), sv if sv else '', size=9, bg=diff_bg)
            if ov: grand_orig[dia] += ov
            if sv: grand_sug[dia]  += sv
        border_all(ws, row, row, 1, 1 + len(dias)*2)
        ws.row_dimensions[row].height = 14
        row += 1

    # Fila TOTAL
    cell_fmt(ws.cell(row, 1), 'TOTAL', bold=True, bg=TOTAL_BG, size=9)
    for ci, dia in enumerate(dias):
        col = 2 + ci * 2
        cell_fmt(ws.cell(row, col),   grand_orig[dia], bold=True, bg=TOTAL_BG, size=9)
        cell_fmt(ws.cell(row, col+1), grand_sug[dia],  bold=True, bg=TOTAL_BG, size=9)
    border_all(ws, row, row, 1, 1 + len(dias)*2)
    ws.row_dimensions[row].height = 16
    row += 2

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 2: Distribución de viajes por día (Original vs Sugerido)
    # ══════════════════════════════════════════════════════════════
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    cell_fmt(ws.cell(row, 1), 'DISTRIBUCIÓN DE VIAJES POR DÍA',
             bold=True, bg='263238', color='FFFFFF', size=10)
    ws.row_dimensions[row].height = 20
    row += 1

    # Cabeceras de la tabla de viajes
    trip_hdrs = ['Conductor', 'Hora', 'Distribución por finca (pallets por camión)',
                 '', '', '', '', '', 'Total P', 'Costo']
    # Cols: A=Conductor  B=Hora  C-I=farm distr(merged)  J=pallets  K=costo

    for dia in dias:
        unavail    = unavailable_vehicle_ids_by_day.get(dia, set())
        orig_trips = [t for t in
                      optimize_day(orders_orig.get(dia, {}),
                                   unavailable_vehicle_ids=unavail, relaxed=True)
                      if t.get('trip_type') == 'export']
        sug_ord    = adjusted_orders.get(dia, {})
        sug_trips  = ([t for t in
                       optimize_day(sug_ord, unavailable_vehicle_ids=unavail)
                       if t.get('trip_type') == 'export']
                      if sug_ord else [])

        # ── Mostrar 1 sección si no hubo cambios al pedido, 2 si sí ────────────
        orig_fp_d = {fn: sum(d.get('pallets', 0) for d in ports.values())
                     for fn, ports in orders_orig.get(dia, {}).items()}
        sug_fp_d  = {fn: sum(d.get('pallets', 0) for d in ports.values())
                     for fn, ports in adjusted_orders.get(dia, {}).items()}
        has_mod_d = (orig_fp_d != sug_fp_d)

        sections_to_show = (
            [('DESPACHO ÓPTIMO', sug_trips, SB_HDR, SUG_BG)]
            if not has_mod_d else
            [('ORIGINAL — Banafrut', orig_trips, ORIG_HDR, BANA_BG),
             ('SUGERIDO',            sug_trips,  SB_HDR,   SUG_BG)]
        )

        # Encabezado del día
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        cell_fmt(ws.cell(row, 1),
                 '{} {}'.format(DAY_EMOJIS.get(dia, ''), dia.title()),
                 bold=True, bg=DAY_COLORS.get(dia, HDR_BG), color='FFFFFF',
                 size=10)
        ws.row_dimensions[row].height = 18
        row += 1

        day_total_p = 0; day_total_c = 0; day_total_co = 0; day_total_v = 0

        for label, trips_list, hdr_bg, row_bg in sections_to_show:
            # Sub-cabecera
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
            cell_fmt(ws.cell(row, 1), label,
                     bold=True, bg=hdr_bg, color='FFFFFF', size=9)
            ws.row_dimensions[row].height = 15
            row += 1

            # Cabeceras de columnas
            cell_fmt(ws.cell(row, 1), 'Conductor',     bold=True, bg='ECEFF1', size=8)
            cell_fmt(ws.cell(row, 2), 'Hora',          bold=True, bg='ECEFF1', size=8)
            ws.merge_cells(start_row=row, start_column=3,
                           end_row=row, end_column=9)
            cell_fmt(ws.cell(row, 3), 'Distribución de pallets por finca',
                     bold=True, bg='ECEFF1', size=8, halign='left')
            cell_fmt(ws.cell(row, 10), 'Total P',      bold=True, bg='ECEFF1', size=8)
            cell_fmt(ws.cell(row, 11), 'Costo',        bold=True, bg='ECEFF1', size=8)
            border_all(ws, row, row, 1, NCOLS)
            ws.row_dimensions[row].height = 14
            row += 1

            if not trips_list:
                ws.merge_cells(start_row=row, start_column=1,
                               end_row=row, end_column=NCOLS)
                cell_fmt(ws.cell(row, 1), 'Sin viajes este día.',
                         italic=True, color='888888', size=8, halign='left')
                ws.row_dimensions[row].height = 14
                row += 1
            else:
                for ti, t in enumerate(trips_list):
                    bg2 = alt[ti % 2]
                    cond  = t.get('conductor', '')
                    hora  = t.get('hora', '')
                    fstr  = fmt_farms(t)
                    pallets = t.get('pallets_cargados', 0)
                    costo   = t.get('costo', 0)
                    cell_fmt(ws.cell(row, 1), cond,    halign='left', size=8, bg=bg2)
                    cell_fmt(ws.cell(row, 2), hora,    size=8, bg=bg2)
                    ws.merge_cells(start_row=row, start_column=3,
                                   end_row=row, end_column=9)
                    cell_fmt(ws.cell(row, 3), fstr,
                             halign='left', size=8, bg=bg2)
                    cell_fmt(ws.cell(row, 10), pallets, size=8, bg=bg2)
                    cell_fmt(ws.cell(row, 11), costo,
                             num_fmt='"$"#,##0', size=8, bg=bg2)
                    border_all(ws, row, row, 1, NCOLS)
                    ws.row_dimensions[row].height = 18
                    day_total_p  += pallets
                    day_total_c  += sum(f.get('cajas', 0) for f in t.get('farms', {}).values())
                    day_total_co += costo
                    day_total_v  += 1
                    row += 1

        # ── Fila TOTAL del día ────────────────────────────────────────────
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
        cell_fmt(ws.cell(row, 1),
                 'TOTAL {} — {} viajes  ·  {:,} cajas'.format(
                     dia.upper(), day_total_v, day_total_c),
                 bold=True, bg='37474F', color='FFFFFF', size=9)
        cell_fmt(ws.cell(row, 10), day_total_p,
                 bold=True, bg='37474F', color='FFFFFF', size=9)
        cell_fmt(ws.cell(row, 11), day_total_co,
                 bold=True, bg='37474F', color='FFFFFF', size=9,
                 num_fmt='"$"#,##0')
        border_all(ws, row, row, 1, NCOLS)
        ws.row_dimensions[row].height = 16
        row += 2   # espacio entre días

    row += 1

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 3: Movimientos propuestos
    # ══════════════════════════════════════════════════════════════
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    cell_fmt(ws.cell(row, 1), 'MOVIMIENTOS PROPUESTOS',
             bold=True, bg=MOVE_HDR, color='FFFFFF', size=10)
    ws.row_dimensions[row].height = 20
    row += 1

    if not moves:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell_fmt(ws.cell(row, 1),
                 'Sin movimientos sugeridos — semana optimizada sin consolidaciones.',
                 size=9, color='555555', halign='left')
        ws.row_dimensions[row].height = 15
        row += 1
    else:
        move_hdrs = ['Tipo', 'Finca', 'De', 'A', 'Pallets', 'Razón']
        for ci, h in enumerate(move_hdrs, 1):
            cell_fmt(ws.cell(row, ci), h, bold=True, bg='FFE0B2', color='BF360C', size=9)
        border_all(ws, row, row, 1, 6)
        ws.row_dimensions[row].height = 15
        row += 1
        for m in moves:
            tipo_label = 'Diferimiento' if m['type'] == 'diferimiento' else 'Anticipación'
            tipo_bg    = 'FFF3E0' if m['type'] == 'diferimiento' else 'E8F5E9'
            cell_fmt(ws.cell(row, 1), tipo_label, bg=tipo_bg, size=9)
            cell_fmt(ws.cell(row, 2), m['farm'].title(), halign='left', size=9)
            cell_fmt(ws.cell(row, 3), m['from_day'].title(), size=9)
            cell_fmt(ws.cell(row, 4), m['to_day'].title(),   size=9)
            cell_fmt(ws.cell(row, 5), m['pallets'],          size=9)
            cell_fmt(ws.cell(row, 6), m['reason'], halign='left', size=9)
            ws.column_dimensions['F'].width = 50
            border_all(ws, row, row, 1, 6)
            ws.row_dimensions[row].height = 15
            row += 1
    row += 1

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 4: Impacto en costo
    # ══════════════════════════════════════════════════════════════
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    cell_fmt(ws.cell(row, 1), 'IMPACTO EN COSTO',
             bold=True, bg=SAVE_HDR, color='FFFFFF', size=10)
    ws.row_dimensions[row].height = 20
    row += 1

    cost_hdrs = ['Dia', 'Costo original', 'Costo sugerido', 'Diferencia', '']
    for ci, h in enumerate(cost_hdrs, 1):
        cell_fmt(ws.cell(row, ci), h, bold=True, bg='BBDEFB', color='0D47A1', size=9)
    border_all(ws, row, row, 1, 4)
    ws.row_dimensions[row].height = 16
    row += 1

    total_orig_cost = 0
    total_sug_cost  = 0
    for dia in dias:
        unavail   = unavailable_vehicle_ids_by_day.get(dia, set())
        orig_cost = sum(t['costo'] for t in
                        optimize_day(orders_orig.get(dia, {}),
                                     unavailable_vehicle_ids=unavail)
                        if t.get('trip_type') == 'export')
        sug_ord   = adjusted_orders.get(dia, {})
        sug_cost  = (sum(t['costo'] for t in
                         optimize_day(sug_ord, unavailable_vehicle_ids=unavail)
                         if t.get('trip_type') == 'export')
                     if sug_ord else 0)
        diff      = sug_cost - orig_cost
        diff_col  = 'A32D2D' if diff > 0 else ('3B6D11' if diff < 0 else '444444')
        diff_str  = ('+${:,}'.format(diff) if diff > 0
                     else ('-${:,}'.format(abs(diff)) if diff < 0 else '---'))
        cell_fmt(ws.cell(row, 1), dia.title(), halign='left', size=9)
        cell_fmt(ws.cell(row, 2), orig_cost,   num_fmt='"$"#,##0', size=9)
        cell_fmt(ws.cell(row, 3), sug_cost,    num_fmt='"$"#,##0', size=9)
        cell_fmt(ws.cell(row, 4), diff_str,    color=diff_col, bold=(diff != 0), size=9)
        border_all(ws, row, row, 1, 4)
        ws.row_dimensions[row].height = 15
        row += 1
        total_orig_cost += orig_cost
        total_sug_cost  += sug_cost

    total_diff = total_sug_cost - total_orig_cost
    tdiff_str  = ('+${:,}'.format(total_diff) if total_diff > 0
                  else ('-${:,}'.format(abs(total_diff)) if total_diff < 0 else '---'))
    tdiff_col  = 'A32D2D' if total_diff > 0 else ('3B6D11' if total_diff < 0 else '444444')
    cell_fmt(ws.cell(row, 1), 'TOTAL SEMANA', bold=True, bg=TOTAL_BG, halign='left', size=9)
    cell_fmt(ws.cell(row, 2), total_orig_cost, bold=True, bg=TOTAL_BG, num_fmt='"$"#,##0', size=9)
    cell_fmt(ws.cell(row, 3), total_sug_cost,  bold=True, bg=TOTAL_BG, num_fmt='"$"#,##0', size=9)
    cell_fmt(ws.cell(row, 4), tdiff_str,        bold=True, bg=TOTAL_BG, color=tdiff_col, size=9)
    border_all(ws, row, row, 1, 4)
    ws.row_dimensions[row].height = 16
    ws.freeze_panes = 'B5'


# -- Formato Excel -----------------------------------------------------------
def border_all(ws, min_row, max_row, min_col, max_col):
    thin = Side(style='thin', color='CCCCCC')
    b    = Border(left=thin, right=thin, top=thin, bottom=thin)
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(r, c).border = b


def _write_trip_section(ws, start_row, trips, color, title, NCOLS):
    """Escribe una sección de viajes (título + cabeceras + filas + total).
    Retorna (next_row, total_cajas, total_pallets, total_costo, n_viajes)."""
    row = start_row
    alt = ['FFFFFF', 'F1F8E9']

    # Cabecera de sección
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row, 1, title)
    c.font      = Font(name='Arial', size=10, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor=color)
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[row].height = 20
    row += 1

    # Cabeceras columnas
    headers    = ['#', 'CONDUCTOR', 'VEHICULO', 'CAP.', 'RUTA',
                  'CAJAS POR FINCA', 'PALLETS POR FINCA',
                  'TOTAL CAJAS', 'PALLETS', 'HORA', 'ENTREGAR EN', 'COSTO']
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row, ci, h)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor=color)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[row].height = 22
    row += 1

    sec_cajas = 0; sec_pallets = 0; sec_costo = 0; sec_viajes = 0
    trip_num = 0

    for trip in trips:
        if trip.get('trip_type') != 'export':
            continue
        trip_num  += 1
        hora        = trip.get('hora', '')
        conductor   = trip.get('conductor', '')
        vehicle     = VEHICLE_DISPLAY.get(trip.get('vehicle_id', ''), {}).get(
                          'vehicle', trip.get('vehicle_id', ''))
        cap         = trip.get('capacidad', '')
        zone        = trip.get('zone', '')
        farms       = trip.get('farms', {})
        pallets     = trip.get('pallets_cargados', 0)
        costo       = trip.get('costo', 0)
        destination = trip.get('destination', '')
        farm_psize      = trip.get('farm_pallets_size', {})
        farm_total_pals = trip.get('farm_total_pallets', {})

        farm_zones_in_trip = {FARM_ZONES.get(f, zone) for f in farms}
        if len(farm_zones_in_trip) > 1:
            zone_label = 'Chigorodo -> Apartado'
        else:
            zone_label = list(farm_zones_in_trip)[0].title() if farm_zones_in_trip else zone.title()
        if len(farms) == 1:
            fname = list(farms.keys())[0]
            ruta  = '-> {} ({})'.format(fname.title(), zone_label)
        else:
            ruta  = '-> {} ({})'.format(' -> '.join(f.title() for f in farms), zone_label)

        cajas_total = sum(d.get('cajas', 0) for d in farms.values())
        cajas_str   = '  |  '.join(
            '{}: {:,}'.format(fn.title(), fd.get('cajas', 0))
            for fn, fd in farms.items())
        pallet_parts = []
        for fn, fd in farms.items():
            psz = farm_psize.get(fn, {})
            assigned_p = int(fd.get('pallets', 0))
            total_p    = int(farm_total_pals.get(fn, assigned_p) or assigned_p or 1)
            lbl = pallet_size_label(assigned_p, total_p, psz) \
                  if psz else '{}P'.format(assigned_p)
            pallet_parts.append('{}: {}'.format(fn.title(), lbl))
        pallets_str = '  |  '.join(pallet_parts)

        bg   = alt[(row - start_row) % 2]
        vals = [trip_num, conductor, vehicle, cap, ruta,
                cajas_str, pallets_str,
                int(cajas_total), int(pallets), hora, destination, costo]
        for ci, val in enumerate(vals, 1):
            c = ws.cell(row, ci, val)
            c.font      = Font(name='Arial', size=9)
            c.fill      = PatternFill('solid', fgColor=bg)
            c.alignment = Alignment(
                horizontal='left' if ci in (5, 6, 7) else 'center',
                vertical='center', wrap_text=True)
            if ci == 12: c.number_format = '"$"#,##0'
            if ci == 8:  c.number_format = '#,##0'
        ws.row_dimensions[row].height = 22
        sec_cajas   += cajas_total
        sec_pallets += pallets
        sec_costo   += costo
        sec_viajes  += 1
        row += 1

    # Fila subtotal
    if sec_viajes > 0:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
        c = ws.cell(row, 1, 'SUBTOTAL — {} viajes'.format(sec_viajes))
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor=color)
        c.alignment = Alignment(horizontal='center', vertical='center')
        for ci, (val, fmt) in enumerate([(int(sec_cajas), '#,##0'),
                                          (int(sec_pallets), '#,##0'),
                                          ('', None), ('', None),
                                          (sec_costo, '"$"#,##0')], 8):
            c = ws.cell(row, ci, val)
            c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
            c.fill      = PatternFill('solid', fgColor=color)
            c.alignment = Alignment(horizontal='center', vertical='center')
            if fmt: c.number_format = fmt
        ws.row_dimensions[row].height = 18
        border_all(ws, start_row + 2, row, 1, NCOLS)
        row += 1
    else:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        c = ws.cell(row, 1, 'Sin viajes este día')
        c.font      = Font(name='Arial', size=9, italic=True, color='888888')
        c.fill      = PatternFill('solid', fgColor='F5F5F5')
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[row].height = 15
        row += 1

    return row, sec_cajas, sec_pallets, sec_costo, sec_viajes


def write_day_sheet(wb, day, orig_trips, sug_trips, first_sheet, banafrut_orders=None, inter_day_moves=None, has_modifications=False):
    NCOLS   = 12
    color   = DAY_COLORS.get(day, '1B5E20')
    ORIG_C  = '1565C0'   # azul — Banafrut original
    SUG_C   = '2E7D32'   # verde — sugerido

    if first_sheet:
        ws = wb.active; ws.title = day
    else:
        ws = wb.create_sheet(title=day)

    # Anchos de columna
    col_widths = [4, 16, 22, 6, 38, 30, 28, 11, 9, 10, 16, 14]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Calcular totales sugeridos para el título
    sug_exp = [t for t in sug_trips if t.get('trip_type') == 'export']
    sug_c   = sum(sum(f.get('cajas',0) for f in t['farms'].values()) for t in sug_exp)
    sug_p   = sum(t.get('pallets_cargados', 0) for t in sug_exp)
    sug_co  = sum(t.get('costo', 0) for t in sug_exp)

    # Fila 1: título
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NCOLS)
    c = ws.cell(1, 1, '{} {}  —  {:,} cajas  ·  {}P  ·  ${:,}'.format(
        DAY_EMOJIS.get(day, ''), day, int(sug_c), int(sug_p), int(sug_co)))
    c.font      = Font(name='Arial', size=12, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor=color)
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    row = 2

    if not has_modifications:
        # ── Sin cambios al pedido de Banafrut: mostrar solo la ruta óptima ──
        _title = 'DESPACHO ÓPTIMO  ({}P  ·  {:,} cajas  ·  ${:,})'.format(
            int(sug_p), int(sug_c), int(sug_co))
        row, s_cajas, s_pallets, s_costo, s_viajes = _write_trip_section(
            ws, row, sug_trips, SUG_C, _title, NCOLS)
    else:
        # ── Pedido modificado: mostrar Banafrut original arriba, sugerencia abajo ──
        # Sección 1: PEDIDO BANAFRUT
        b_ordered_p = int(sum(d.get('pallets', 0) for d in (banafrut_orders or {}).values()))
        b_ordered_c = int(sum(d.get('cajas', 0)   for d in (banafrut_orders or {}).values()))
        b_orig_exp  = [t for t in orig_trips if t.get('trip_type') == 'export']
        b_shipped_p = int(sum(t.get('pallets_cargados', 0) for t in b_orig_exp))
        b_shipped_c = int(sum(sum(f.get('cajas', 0) for f in t['farms'].values()) for t in b_orig_exp))
        b_unshipped = max(0, b_ordered_p - b_shipped_p)
        if b_unshipped > 0:
            _b_title = 'PEDIDO BANAFRUT — Sin modificaciones  ({} ordenados | {} enviados | ⚠️ {}P sin despachar)'.format(
                '{}P · {:,}c'.format(b_ordered_p, b_ordered_c),
                '{}P · {:,}c'.format(b_shipped_p, b_shipped_c),
                b_unshipped)
        else:
            _b_title = 'PEDIDO BANAFRUT — Sin modificaciones  ({}P  ·  {:,} cajas  ·  ${:,})'.format(
                b_shipped_p, b_shipped_c,
                int(sum(t.get('costo', 0) for t in b_orig_exp)))
        row, b_cajas, b_pallets, b_costo, b_viajes = _write_trip_section(
            ws, row, orig_trips, ORIG_C, _b_title, NCOLS)
        row += 1  # espacio

        # Sección 2: NUESTRA SUGERENCIA (con movimientos entre días)
        _moves = inter_day_moves or {}
        _defer_out = sum(m.get('pallets', 0) for m in _moves.get(day, []) if m.get('type') == 'deferral')
        _moved_to  = sum(
            m.get('pallets', 0)
            for d2, mvs in _moves.items()
            for m in mvs
            if m.get('type') == 'deferral' and m.get('to_day') == day
        )
        _extra = []
        if _defer_out:
            _extra.append('↓ {}P diferidos al día siguiente'.format(_defer_out))
        if _moved_to:
            _extra.append('↑ {}P recibidos del día anterior'.format(_moved_to))
        _move_str = '  |  '.join(_extra)
        _s_title = 'NUESTRA SUGERENCIA — Optimizado  ({}P  ·  {:,} cajas  ·  ${:,})  {}'.format(
            int(sug_p), int(sug_c), int(sug_co),
            '  ⚠️ ' + _move_str if _move_str else '')
        row, s_cajas, s_pallets, s_costo, s_viajes = _write_trip_section(
            ws, row, sug_trips, SUG_C, _s_title, NCOLS)

    ws.freeze_panes = 'A3'
    return s_costo, s_cajas, s_pallets, s_viajes

def generate_excel_bytes(orders, semana_num, unavailable_vehicle_ids_by_day=None):
    if unavailable_vehicle_ids_by_day is None:
        unavailable_vehicle_ids_by_day = {}
    wb          = Workbook()
    sorted_days = sorted(orders.keys(),
                         key=lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else 99)
    day_results = {}
    for day in sorted_days:
        unavail = unavailable_vehicle_ids_by_day.get(day, set())
        trips   = optimize_day(orders[day], unavailable_vehicle_ids=unavail, relaxed=True)
        if trips:
            day_results[day] = trips
    if not day_results:
        return None, {}

    # Plan sugerido (pedido ajustado con consolidaciones inter-día)
    adjusted_orders_gen, _ = compute_inter_day_moves(orders)
    sug_day_results = {}
    for day in sorted_days:
        unavail   = unavailable_vehicle_ids_by_day.get(day, set())
        sug_trips = optimize_day(adjusted_orders_gen.get(day, {}),
                                 unavailable_vehicle_ids=unavail)
        if sug_trips:
            sug_day_results[day] = sug_trips

    ws_sum       = wb.active
    ws_sum.title = 'RESUMEN SEMANA'
    ws_sum.merge_cells('A1:F1')
    c           = ws_sum['A1']
    c.value     = 'RESUMEN OPTIMIZACION - SEMANA {}'.format(semana_num)
    c.font      = Font(name='Arial', size=13, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor='1B5E20')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.row_dimensions[1].height = 28

    sum_headers = ['DIA', 'VIAJES', 'CAJAS', 'PALLETS', 'COSTO TOTAL', 'CONSOLIDACIONES']
    for ci, h in enumerate(sum_headers, 1):
        c           = ws_sum.cell(row=2, column=ci, value=h)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor='2E7D32')
        c.alignment = Alignment(horizontal='center')
        ws_sum.column_dimensions[get_column_letter(ci)].width = [14, 10, 13, 11, 16, 18][ci-1]
    ws_sum.row_dimensions[2].height = 18

    sum_row = 3
    grand   = {'cost': 0, 'cajas': 0, 'pallets': 0, 'viajes': 0}
    for day in sorted_days:
        if day not in day_results and day not in sug_day_results:
            continue
        trips        = sug_day_results.get(day, day_results.get(day, []))
        export_trips = [t for t in trips if t.get('trip_type') == 'export']
        d_cost    = sum(t['costo'] for t in export_trips)
        d_cajas   = sum(sum(f['cajas'] for f in t['farms'].values()) for t in export_trips)
        d_pallets = sum(t['pallets_cargados'] for t in export_trips)
        d_viajes  = len(export_trips)
        grand['cost']    += d_cost
        grand['cajas']   += d_cajas
        grand['pallets'] += d_pallets
        grand['viajes']  += d_viajes
        bg  = 'F1F8E9' if sum_row % 2 == 0 else 'FFFFFF'
        row_vals = [day.capitalize(), d_viajes, d_cajas, int(d_pallets), d_cost, '']
        for ci, val in enumerate(row_vals, 1):
            c           = ws_sum.cell(row=sum_row, column=ci, value=val)
            c.font      = Font(name='Arial', size=9)
            c.fill      = PatternFill('solid', fgColor=bg)
            c.alignment = Alignment(horizontal='center', vertical='center')
            if ci == 5:
                c.number_format = '"$"#,##0'
            if ci == 3:
                c.number_format = '#,##0'
        sum_row += 1

    vals = ['TOTAL SEMANA', grand['viajes'], grand['cajas'], int(grand['pallets']), grand['cost'], '']
    for ci, val in enumerate(vals, 1):
        c           = ws_sum.cell(row=sum_row, column=ci, value=val)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor='1B5E20')
        c.alignment = Alignment(horizontal='center', vertical='center')
        if ci == 5:
            c.number_format = '"$"#,##0'
        if ci == 3:
            c.number_format = '#,##0'
    ws_sum.row_dimensions[sum_row].height = 20
    border_all(ws_sum, 1, sum_row, 1, 6)

    # Detalle pallets por finca
    detail_row = sum_row + 2
    ws_sum.merge_cells('A{}:F{}'.format(detail_row, detail_row))
    c           = ws_sum.cell(row=detail_row, column=1, value='DETALLE DE PALLETS POR FINCA')
    c.font      = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor='1B5E20')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.row_dimensions[detail_row].height = 22

    header_row     = detail_row + 1
    detail_headers = ['DIA', 'FINCA', 'PUERTO', 'PALLETS POR TIPO', 'TOTAL PALLETS', 'TOTAL CAJAS']
    for ci, h in enumerate(detail_headers, 1):
        c           = ws_sum.cell(row=header_row, column=ci, value=h)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor='2E7D32')
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws_sum.row_dimensions[header_row].height = 18

    detail_row_idx = header_row + 1
    for day in sorted_days:
        if day not in day_results:
            continue
        for farm in sorted(orders[day].keys()):
            for port, data in orders[day][farm].items():
                if data.get('pallets', 0) <= 0:
                    continue
                bg   = 'F1F8E9' if detail_row_idx % 2 == 0 else 'FFFFFF'
                vals = [
                    day.capitalize(), farm, port,
                    format_pallets_by_size(data.get('pallets_by_size', {}), data['pallets']),
                    int(data['pallets']), data['cajas'],
                ]
                for ci, val in enumerate(vals, 1):
                    c           = ws_sum.cell(row=detail_row_idx, column=ci, value=val)
                    c.font      = Font(name='Arial', size=9)
                    c.fill      = PatternFill('solid', fgColor=bg)
                    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    if ci in (5, 6):
                        c.number_format = '#,##0'
                detail_row_idx += 1
    border_all(ws_sum, detail_row, detail_row_idx - 1, 1, 6)

    for ci, w in enumerate([14, 22, 16, 28, 14, 13], 1):
        ws_sum.column_dimensions[get_column_letter(ci)].width = w

    # Build per-day movement index for write_day_sheet headers
    _, _raw_moves = compute_inter_day_moves(orders)
    inter_day_moves_by_day = {}
    for mv in (_raw_moves or []):
        fd = mv.get('from_day', '')
        td = mv.get('to_day', '')
        inter_day_moves_by_day.setdefault(fd, []).append({**mv, 'type': 'deferral'})
        inter_day_moves_by_day.setdefault(td, []).append({**mv, 'type': 'anticipation'})

    # Determinar qué días tuvieron modificaciones en el pedido (movimientos inter-día)
    def _farm_totals(day_orders):
        return {fn: sum(d.get('pallets', 0) for d in ports.values())
                for fn, ports in day_orders.items()}

    for day in sorted_days:
        if day not in day_results and day not in sug_day_results:
            continue
        orig_t = day_results.get(day, [])
        sug_t  = sug_day_results.get(day, [])
        orig_fp = _farm_totals(orders.get(day, {}))
        sug_fp  = _farm_totals(adjusted_orders_gen.get(day, {}))
        has_mod = (orig_fp != sug_fp)
        write_day_sheet(wb, day, orig_t, sug_t, False,
                        banafrut_orders=orders.get(day, {}),
                        inter_day_moves=inter_day_moves_by_day,
                        has_modifications=has_mod)

    # Hoja: Pedido Sugerido
    adjusted_orders, inter_day_moves = compute_inter_day_moves(orders)
    write_suggested_pedido_sheet(
        wb, orders, adjusted_orders, inter_day_moves,
        semana_num, unavailable_vehicle_ids_by_day,
    )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    summary = {
        'cost':    grand['cost'],
        'cajas':   grand['cajas'],
        'pallets': grand['pallets'],
        'viajes':  grand['viajes'],
    }
    return buf.read(), summary
