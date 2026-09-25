// Todo el acceso a Supabase vive aquí, para que el componente solo maneje pantalla.
import { supabase } from "./supabase.js";

const PAGE = 1000; // Supabase devuelve máximo 1000 filas por consulta

async function fetchAll(table, columns, orderBy) {
  const rows = [];
  for (let from = 0; ; from += PAGE) {
    let q = supabase.from(table).select(columns);
    for (const col of orderBy) q = q.order(col, { ascending: true });
    const { data, error } = await q.range(from, from + PAGE - 1);
    if (error) throw error;
    rows.push(...data);
    if (data.length < PAGE) break;
  }
  return rows;
}

function toPago(r) {
  return {
    id: r.id,
    fecha_pago: r.fecha_pago,
    valor: Number(r.valor),
    banco: r.banco,
    comprobante: r.comprobante,
    origen: r.origen,
  };
}

// Devuelve { lotes: {LOTE X: {cliente, valor_negocio, cuotas_plan, pagos_registrados, es_nuevo, telefono, correo}},
//            pagos: {LOTE X: [pago, ...]}, descartados: {id: fecha} }
export async function cargarTodo() {
  const [lotes, cuotas, pagos, descartados] = await Promise.all([
    fetchAll("lotes", "id, cliente, valor_negocio, telefono, correo, es_nuevo", ["id"]),
    fetchAll("cuotas_plan", "lote_id, orden, fecha_esperada, concepto, valor", ["lote_id", "orden"]),
    fetchAll("pagos", "id, lote_id, fecha_pago, valor, banco, comprobante, origen", ["fecha_pago", "secuencia"]),
    fetchAll("recordatorios_descartados", "id, fecha", ["id"]),
  ]);

  const lotesMap = {};
  for (const l of lotes) {
    lotesMap[l.id] = {
      cliente: l.cliente,
      valor_negocio: Number(l.valor_negocio),
      cuotas_plan: [],
      pagos_registrados: [], // todos los pagos van en el mapa de pagos
      es_nuevo: l.es_nuevo,
      telefono: l.telefono,
      correo: l.correo,
    };
  }
  for (const c of cuotas) {
    if (!lotesMap[c.lote_id]) continue;
    lotesMap[c.lote_id].cuotas_plan.push({
      fecha_esperada: c.fecha_esperada,
      concepto: c.concepto,
      valor: Number(c.valor),
    });
  }

  const pagosMap = {};
  for (const p of pagos) {
    (pagosMap[p.lote_id] ||= []).push(toPago(p));
  }

  const descMap = {};
  for (const d of descartados) descMap[d.id] = d.fecha;

  // Lotes por vender (si la tabla aún no existe, la app sigue funcionando)
  let disponibles = [];
  try {
    disponibles = (
      await fetchAll("lotes_disponibles", "id, numero, area_m2, valor_m2, valor_sugerido, nota, vendido", ["numero"])
    ).map((d) => ({ ...d, valor_sugerido: d.valor_sugerido === null ? null : Number(d.valor_sugerido) }));
  } catch (e) {
    disponibles = [];
  }

  return { lotes: lotesMap, pagos: pagosMap, descartados: descMap, disponibles };
}

export async function insertarPago(loteId, pago) {
  const { data, error } = await supabase
    .from("pagos")
    .insert({
      lote_id: loteId,
      fecha_pago: pago.fecha_pago,
      valor: pago.valor,
      banco: pago.banco || null,
      comprobante: pago.comprobante || null,
      origen: "manual",
    })
    .select("id, fecha_pago, valor, banco, comprobante, origen")
    .single();
  if (error) throw error;
  return toPago(data);
}

export async function eliminarPago(id) {
  const { error } = await supabase.from("pagos").delete().eq("id", id).neq("origen", "original");
  if (error) throw error;
}

export async function crearLote({ id, cliente, valorNegocio, cuotas, telefono, correo, pagos }) {
  const args = {
    p_id: id,
    p_cliente: cliente,
    p_valor_negocio: valorNegocio,
    p_cuotas: cuotas,
    p_telefono: telefono || null,
    p_correo: correo || null,
  };
  if (pagos && pagos.length) args.p_pagos = pagos;
  const { error } = await supabase.rpc("crear_lote", args);
  if (error) throw error;
}

export async function eliminarLote(id) {
  const { error } = await supabase.from("lotes").delete().eq("id", id).eq("es_nuevo", true);
  if (error) throw error;
  // Si venía de la lista de lotes por vender, vuelve a quedar disponible
  await supabase.from("lotes_disponibles").update({ vendido: false }).eq("id", id);
}

export async function actualizarContacto(id, { telefono, correo }) {
  const { error } = await supabase
    .from("lotes")
    .update({ telefono: telefono || null, correo: correo || null })
    .eq("id", id);
  if (error) throw error;
}

export async function descartarRecordatorio(id, fecha) {
  const { error } = await supabase.from("recordatorios_descartados").upsert({ id, fecha });
  if (error) throw error;
}

// Importa el respaldo copiado desde la versión que corría dentro de Claude.
// Acepta { extra_pagos_all, custom_lotes, recordatorios_dismissed } (cualquiera puede faltar).
// Se puede correr varias veces: no duplica pagos ni lotes.
export async function importarRespaldo(respaldo, lotesExistentes) {
  const parse = (v) => (typeof v === "string" ? JSON.parse(v) : v || {});
  const customLotes = parse(respaldo.custom_lotes);
  const extraPagos = parse(respaldo.extra_pagos_all);
  const dismissed = parse(respaldo.recordatorios_dismissed);

  const conocidos = new Set(Object.keys(lotesExistentes));
  let lotesCreados = 0;
  for (const [key, l] of Object.entries(customLotes)) {
    if (conocidos.has(key)) continue;
    await crearLote({
      id: key,
      cliente: l.cliente,
      valorNegocio: Number(l.valor_negocio) || 0,
      cuotas: (l.cuotas_plan || []).map((c) => ({
        fecha_esperada: c.fecha_esperada || null,
        concepto: c.concepto || "CUOTA",
        valor: Number(c.valor) || 0,
      })),
    });
    conocidos.add(key);
    lotesCreados++;
  }

  const filas = [];
  let pagosOmitidos = 0;
  for (const [lote, lista] of Object.entries(extraPagos)) {
    for (const p of lista || []) {
      if (!conocidos.has(lote)) {
        pagosOmitidos++;
        continue;
      }
      if (!p || !Number(p.valor)) continue;
      filas.push({
        lote_id: lote,
        fecha_pago: p.fecha_pago,
        valor: Number(p.valor),
        banco: p.banco || null,
        comprobante: p.comprobante || null,
        origen: p.origen === "ia" ? "ia" : "manual",
        id_anterior: p.id ? String(p.id) : `${lote}|${p.fecha_pago}|${p.valor}|${p.comprobante || ""}`,
      });
    }
  }
  let pagosImportados = 0;
  for (let i = 0; i < filas.length; i += 500) {
    const { data, error } = await supabase
      .from("pagos")
      .upsert(filas.slice(i, i + 500), { onConflict: "id_anterior", ignoreDuplicates: true })
      .select("id");
    if (error) throw error;
    pagosImportados += data.length;
  }

  const descRows = Object.entries(dismissed).map(([id, fecha]) => ({ id, fecha }));
  if (descRows.length) {
    const { error } = await supabase.from("recordatorios_descartados").upsert(descRows);
    if (error) throw error;
  }

  return { lotesCreados, pagosImportados, pagosEnRespaldo: filas.length, pagosOmitidos };
}
