#!/usr/bin/env python3
"""
Motor de optimizacion de rutas - Exportadora de Banano
Yuber: precio base 20P, +$25.000 por pallet adicional hasta 24P.
Viaje combinado Chigorodo+Apartado: +$100.000 entrada Apartado.
Demetrio: puede hacer 2 viajes por dia (Viaje 1 y Viaje 2).
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
    'YUBER_MULA_1':      {'conductor': 'Yuber',    'vehicle': 'Mula 1 - 24P'},
    'YUBER_MULA_2':      {'conductor': 'Yuber',    'vehicle': 'Mula 2 - 24P'},
    'YUBER_MULA_3':      {'conductor': 'Yuber',    'vehicle': 'Mula 3 - 24P'},
    'YUBER_MULA_4':      {'conductor': 'Yuber',    'vehicle': 'Mula 4 - 24P'},
    'DEMETRIO_PATINETA':   {'conductor': 'Demetrio', 'vehicle': 'Patineta 18P (Viaje 1)'},
    'DEMETRIO_PATINETA_2': {'conductor': 'Demetrio', 'vehicle': 'Patineta 18P (Viaje 2)'},
    'MERBIN_CAMION':     {'conductor': 'Merbin',   'vehicle': 'Camion 8P'},
    'CFS_CAMION':        {'conductor': 'CFS',      'vehicle': 'Camion 24P'},
    'CFS_MULA':          {'conductor': 'CFS',      'vehicle': 'Mula 24P'},
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

VEHICLES_BY_ROUTE = {
    ('CHIGORODO', 'PUERTO ANTIOQUIA'): _YUBER_CHIGORODO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
    ],
    ('CHIGORODO', 'UNIBAN ZUNGO'): _YUBER_CHIGORODO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 850000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
        {'conductor': 'MERBIN',   'tipo': 'CAMION',   'capacidad': 8,  'costo': 600000,
         'vehicle_id': 'MERBIN_CAMION'},
    ],
    ('APARTADO', 'PUERTO ANTIOQUIA'): _YUBER_APARTADO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
        {'conductor': 'CFS',      'tipo': 'CAMION',   'capacidad': 24, 'costo': 440000,
         'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'CFS_CAMION'},
        {'conductor': 'CFS',      'tipo': 'MULA',     'capacidad': 24, 'costo': 660000,
         'pallets_negociados': 20, 'costo_extra_pallet': 25000, 'vehicle_id': 'CFS_MULA'},
    ],
    ('APARTADO', 'UNIBAN ZUNGO'): _YUBER_APARTADO + [
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA'},
        {'conductor': 'DEMETRIO', 'tipo': 'PATINETA', 'capacidad': 18, 'costo': 550000,
         'vehicle_id': 'DEMETRIO_PATINETA_2'},
        {'conductor': 'MERBIN',   'tipo': 'CAMION',   'capacidad': 8,  'costo': 300000,
         'vehicle_id': 'MERBIN_CAMION'},
    ],
}

CONSOLIDACION_ROUTES = {
    'SALVAMENTO': [
        {'conductor': 'MERBIN', 'tipo': 'CAMION', 'capacidad': 14, 'costo': 150000,
         'vehicle_id': 'MERBIN_CAMION'},
    ],
    'CHISPERO': [
        {'conductor': 'MERBIN', 'tipo': 'CAMION', 'capacidad': 14, 'costo': 150000,
         'vehicle_id': 'MERBIN_CAMION'},
    ],
}

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
    Rellena la capacidad sobrante de camiones Yuber en Chigorodó con fincas de Apartadó.
    Cobra $100.000 extra por la entrada a Apartadó (una sola vez por camion).
    Modifica apart_route_data in-place reduciendo los pallets consumidos.
    """
    ENTRADA_APARTADO = 100_000

    for trip in chigorodo_trips:
        if trip.get('conductor') != 'YUBER':
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

        if added_any:
            # Recalcular costo: base Chigorodo + entrada Apartado + extra pallets
            extra      = max(0, trip['pallets_cargados'] - trip['pallets_negociados'])
            trip['costo'] = (trip['costo_base']
                             + ENTRADA_APARTADO
                             + extra * trip['costo_extra_pallet'])


# ── Optimizacion diaria ───────────────────────────────────────
def optimize_day(day_orders, unavailable_vehicle_ids=None):
    if unavailable_vehicle_ids is None:
        unavailable_vehicle_ids = set()

    route_groups = {}
    for farm, port_data in day_orders.items():
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
        return max(0, total_p - excl_cap)

    sorted_routes = sorted(
        route_groups.items(),
        key=lambda x: _shared_demand(x[0]),
        reverse=True,
    )

    combined_done = set()  # puertos donde ya se intento relleno combinado

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

        # Relleno combinado: si acabamos de procesar Chigorodo,
        # aprovechar capacidad sobrante de Yuber para recoger fincas de Apartado.
        if zone == 'CHIGORODO' and port not in combined_done:
            apart_key = ('APARTADO', port)
            if apart_key in route_groups:
                combined_done.add(port)
                chigorodo_trips = [t for t in all_trips
                                   if t.get('zone') == 'CHIGORODO'
                                   and t.get('destination') == port
                                   and t.get('trip_type') == 'export']
                _combined_fill(chigorodo_trips, route_groups[apart_key])

    return all_trips


# ── Sugerencias de consolidacion entre dias ──────────────────
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


# ── Formato Excel ─────────────────────────────────────────────
def border_all(ws, min_row, max_row, min_col, max_col):
    thin = Side(style='thin', color='CCCCCC')
    b    = Border(left=thin, right=thin, top=thin, bottom=thin)
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(row=r, column=c).border = b


def write_day_sheet(wb, day, trips, first_sheet):
    export_trips   = [t for t in trips if t.get('trip_type') == 'export']
    all_trips_list = trips
    day_cost    = sum(t['costo'] for t in all_trips_list)
    day_cajas   = sum(sum(f['cajas'] for f in t['farms'].values()) for t in export_trips)
    day_pallets = sum(t['pallets_cargados'] for t in export_trips)
    day_viajes  = len(export_trips)
    emoji   = DAY_EMOJIS.get(day, '🔵')
    color   = DAY_COLORS.get(day, '1B5E20')
    day_cap = day.capitalize()
    ws = wb.active if first_sheet else wb.create_sheet(day_cap)
    if first_sheet:
        ws.title = day_cap
    ws.merge_cells('A1:K1')
    c = ws['A1']
    c.value     = f"{emoji} {day}  -  {day_viajes} viajes  -  {day_cajas:,} cajas  -  {int(day_pallets)} pallets  -  ${day_cost:,.0f}".replace(",", ".")
    c.font      = Font(name='Arial', size=13, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor=color)
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28
    headers    = ['#', 'Conductor', 'Vehiculo', 'Cap.', 'Ruta', 'Cajas por finca', 'Pallets por finca', 'Total cajas', 'Pallets', 'Entregar en', 'Costo']
    col_widths = [5,    16,          22,          8,      38,     45,                 22,                  13,            10,         22,            16]
    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        c = ws.cell(row=2, column=ci, value=h)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor=color)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[2].height = 18
    row      = 3
    trip_num = 1
    for trip in all_trips_list:
        is_consol = trip.get('trip_type') == 'consolidacion'
        bg = 'FFF3E0' if is_consol else ('F1F8E9' if trip_num % 2 == 0 else 'FFFFFF')
        farms = trip.get('farms', {})
        zone  = trip.get('zone', '')
        if len(farms) == 1:
            fname = list(farms.keys())[0]
            ruta  = f"-> {fname} ({zone.title()})"
        else:
            ruta = "-> " + " -> ".join(farms.keys()) + f" ({zone.title()})"
        fps         = trip.get('farm_pallets_size', {})
        ftp         = trip.get('farm_total_pallets', {})
        cajas_str   = "  |  ".join(f"{f}: {d['cajas']:,}" for f, d in farms.items())
        pallets_str = "  |  ".join(
            f"{f}: {pallet_size_label(d.get('pallets', 0), ftp.get(f, 1), fps.get(f, {}))}"
            for f, d in farms.items()
        )
        total_cajas = sum(d['cajas'] for d in farms.values())
        label_tipo  = f"{trip['tipo']} - {trip['capacidad']}P"
        if is_consol:
            label_tipo += "  (consol.)"
        vals = [
            trip_num, trip['conductor'], label_tipo, f"{trip['capacidad']}P",
            ruta, cajas_str, pallets_str, total_cajas,
            int(round(trip['pallets_cargados'])), trip['destination'], trip['costo'],
        ]
        for ci, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=ci, value=val)
            c.font      = Font(name='Arial', size=9)
            c.fill      = PatternFill('solid', fgColor=bg)
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            if ci == 11:
                c.number_format = '"$"#,##0'
            if ci == 8:
                c.number_format = '#,##0'
        ws.row_dimensions[row].height = 22
        trip_num += 1
        row += 1
    ws.merge_cells(f'A{row}:F{row}')
    c = ws.cell(row=row, column=1, value='TOTAL DEL DIA')
    c.font      = Font(name='Arial', size=9, bold=True)
    c.fill      = PatternFill('solid', fgColor='FFE082')
    c.alignment = Alignment(horizontal='right', vertical='center')
    for ci, val in [(8, day_cajas), (9, int(day_pallets)), (10, ''), (11, day_cost)]:
        c = ws.cell(row=row, column=ci, value=val)
        c.font      = Font(name='Arial', size=9, bold=True)
        c.fill      = PatternFill('solid', fgColor='FFE082')
        c.alignment = Alignment(horizontal='center', vertical='center')
        if ci == 11:
            c.number_format = '"$"#,##0'
        if ci == 8:
            c.number_format = '#,##0'
    ws.row_dimensions[row].height = 20
    border_all(ws, 2, row, 1, 11)
    return day_cost, day_cajas, day_pallets, day_viajes


def generate_excel_bytes(orders, semana_num, unavailable_vehicle_ids_by_day=None):
    if unavailable_vehicle_ids_by_day is None:
        unavailable_vehicle_ids_by_day = {}
    wb          = Workbook()
    sorted_days = sorted(orders.keys(),
                         key=lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else 99)
    day_results = {}
    for day in sorted_days:
        unavail = unavailable_vehicle_ids_by_day.get(day, set())
        trips   = optimize_day(orders[day], unavailable_vehicle_ids=unavail)
        if trips:
            day_results[day] = trips
    if not day_results:
        return None, {}
    ws_sum = wb.active
    ws_sum.title = 'RESUMEN SEMANA'
    ws_sum.merge_cells('A1:F1')
    c = ws_sum['A1']
    c.value     = f'RESUMEN OPTIMIZACION - SEMANA {semana_num}'
    c.font      = Font(name='Arial', size=13, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor='1B5E20')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.row_dimensions[1].height = 28
    sum_headers = ['DIA', 'VIAJES', 'CAJAS', 'PALLETS', 'COSTO TOTAL', 'CONSOLIDACIONES']
    for ci, h in enumerate(sum_headers, 1):
        c = ws_sum.cell(row=2, column=ci, value=h)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor='2E7D32')
        c.alignment = Alignment(horizontal='center')
        ws_sum.column_dimensions[get_column_letter(ci)].width = [14, 10, 13, 11, 16, 18][ci-1]
    ws_sum.row_dimensions[2].height = 18
    sum_row = 3
    grand   = {'cost': 0, 'cajas': 0, 'pallets': 0, 'viajes': 0}
    for day in sorted_days:
        if day not in day_results:
            continue
        trips        = day_results[day]
        export_trips = [t for t in trips if t.get('trip_type') == 'export']
        consol_trips = [t for t in trips if t.get('trip_type') == 'consolidacion']
        d_cost    = sum(t['costo'] for t in trips)
        d_cajas   = sum(sum(f['cajas'] for f in t['farms'].values()) for t in export_trips)
        d_pallets = sum(t['pallets_cargados'] for t in export_trips)
        d_viajes  = len(export_trips)
        grand['cost']    += d_cost
        grand['cajas']   += d_cajas
        grand['pallets'] += d_pallets
        grand['viajes']  += d_viajes
        consol_str = ', '.join(set(f for t in consol_trips for f in t['farms'])) if consol_trips else '-'
        bg   = 'F1F8E9' if sum_row % 2 == 0 else 'FFFFFF'
        vals = [day.capitalize(), d_viajes, d_cajas, int(d_pallets), d_cost, consol_str]
        for ci, val in enumerate(vals, 1):
            c = ws_sum.cell(row=sum_row, column=ci, value=val)
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
        c = ws_sum.cell(row=sum_row, column=ci, value=val)
        c.font      = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        c.fill      = PatternFill('solid', fgColor='1B5E20')
        c.alignment = Alignment(horizontal='center', vertical='center')
        if ci == 5:
            c.number_format = '"$"#,##0'
        if ci == 3:
            c.number_format = '#,##0'
    ws_sum.row_dimensions[sum_row].height = 20
    border_all(ws_sum, 1, sum_row, 1, 6)

    # ── Detalle de pallets por finca y talla ───────────
    detail_row = sum_row + 2
    ws_sum.merge_cells(f'A{detail_row}:F{detail_row}')
    c = ws_sum.cell(row=detail_row, column=1, value='DETALLE DE PALLETS POR FINCA')
    c.font      = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    c.fill      = PatternFill('solid', fgColor='1B5E20')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.row_dimensions[detail_row].height = 22

    header_row      = detail_row + 1
    detail_headers  = ['DIA', 'FINCA', 'PUERTO', 'PALLETS POR TIPO', 'TOTAL PALLETS', 'TOTAL CAJAS']
    for ci, h in enumerate(detail_headers, 1):
        c = ws_sum.cell(row=header_row, column=ci, value=h)
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
                    c = ws_sum.cell(row=detail_row_idx, column=ci, value=val)
                    c.font      = Font(name='Arial', size=9)
                    c.fill      = PatternFill('solid', fgColor=bg)
                    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    if ci in (5, 6):
                        c.number_format = '#,##0'
                detail_row_idx += 1
    border_all(ws_sum, detail_row, detail_row_idx - 1, 1, 6)

    # Anchos de columna que sirvan para ambas tablas del resumen
    for ci, w in enumerate([14, 22, 16, 28, 14, 13], 1):
        ws_sum.column_dimensions[get_column_letter(ci)].width = w

    for day in sorted_days:
        if day not in day_results:
            continue
        trips = day_results[day]
        write_day_sheet(wb, day, trips, False)

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
