import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  Check,
  X,
  Trash2,
  Search,
  Loader2,
  ChevronRight,
  Building2,
  AlertCircle,
  Sparkles,
  Download,
  Plus,
  Bell,
  LogOut,
  LayoutDashboard,
  ClipboardList,
  RefreshCw,
  Upload,
  FileSpreadsheet,
} from "lucide-react";
import { supabase } from "./supabase.js";
import Dashboard from "./Dashboard.jsx";
import { leerArchivoExcel } from "./lotes-excel.js";
import plantillaUrl from "./plantilla_plan_de_pagos.xlsx?url";
import { LOGO_SRC } from "./logos.js";
import {
  formatCOP,
  formatFecha,
  todayISO,
  tomorrowISO,
  buildRecordatorioMessage,
  buildMoraMessage,
  buildEmailSubject,
  buildFichaHTML,
  computeLedger,
  ProgressStamp,
} from "./ledger.jsx";
import {
  cargarTodo,
  insertarPago,
  eliminarPago,
  crearLote,
  eliminarLote,
  actualizarContacto,
  descartarRecordatorio,
  importarRespaldo,
} from "./data.js";

function ordenarLotes(keys) {
  return [...keys].sort((a, b) => {
    const na = parseInt(a.replace(/\D/g, ""), 10) || 0;
    const nb = parseInt(b.replace(/\D/g, ""), 10) || 0;
    return na - nb || a.localeCompare(b);
  });
}

export default function ControlPagos({ session }) {
  const [allLotesData, setAllLotesData] = useState({});
  const [extraPagos, setExtraPagos] = useState({});
  const [dismissedRecordatorios, setDismissedRecordatorios] = useState({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const [selectedLote, setSelectedLote] = useState(null);
  const [tab, setTab] = useState("registro");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState(null);
  const [savingPago, setSavingPago] = useState(false);
  const [toast, setToast] = useState(null);
  const [exportingPDF, setExportingPDF] = useState(false);
  const [showNewLoteForm, setShowNewLoteForm] = useState(false);
  const [newLote, setNewLote] = useState(null);
  const [savingNewLote, setSavingNewLote] = useState(false);
  const [showRecordatorios, setShowRecordatorios] = useState(false);
  const [contactoEdit, setContactoEdit] = useState(null);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [disponibles, setDisponibles] = useState([]);
  const [showExcel, setShowExcel] = useState(false);
  const [excelLotes, setExcelLotes] = useState(null); // resultado de leer el archivo
  const [excelSel, setExcelSel] = useState({});
  const [excelBusy, setExcelBusy] = useState(false);
  const [excelError, setExcelError] = useState(null);
  const excelInputRef = useRef(null);
  const lastLoad = useRef(0);

  // ---------- Carga de datos desde Supabase ----------
  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const { lotes, pagos, descartados, disponibles: disp } = await cargarTodo();
      setDisponibles(disp || []);
      setAllLotesData(lotes);
      setExtraPagos(pagos);
      setDismissedRecordatorios(descartados);
      setLoadError(null);
      lastLoad.current = Date.now();
      setSelectedLote((prev) => (prev && lotes[prev] ? prev : ordenarLotes(Object.keys(lotes))[0] || null));
    } catch (e) {
      if (silent) setToast({ type: "error", msg: `No se pudo actualizar: ${e?.message || e}` });
      else setLoadError(e?.message || String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Si otra persona registró pagos, al volver a la pestaña se actualiza solo (máx. cada 30 s).
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible" && Date.now() - lastLoad.current > 30000) {
        load({ silent: true });
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const allLoteKeys = useMemo(() => ordenarLotes(Object.keys(allLotesData)), [allLotesData]);

  // Lotes que faltan por vender (para la lista desplegable)
  const lotesPorVender = useMemo(
    () => disponibles.filter((d) => !d.vendido && !allLotesData[d.id]).sort((a, b) => a.numero - b.numero),
    [disponibles, allLotesData]
  );

  const ledger = useMemo(
    () =>
      selectedLote && allLotesData[selectedLote]
        ? computeLedger(selectedLote, extraPagos[selectedLote] || [], allLotesData)
        : null,
    [selectedLote, extraPagos, allLotesData]
  );

  // ---------- Recordatorios ----------
  async function handleDismissRecordatorio(id) {
    const fecha = todayISO();
    setDismissedRecordatorios((prev) => ({ ...prev, [id]: fecha }));
    try {
      await descartarRecordatorio(id, fecha);
    } catch (e) {
      // no crítico
    }
  }

  const recordatorios = useMemo(() => {
    if (loading) return [];
    const manana = tomorrowISO();
    const list = [];
    for (const lote of allLoteKeys) {
      const info = allLotesData[lote];
      const contacto = { telefono: info.telefono, correo: info.correo };
      const led = computeLedger(lote, extraPagos[lote] || [], allLotesData);

      if (led.proxima && led.proxima.fecha_esperada === manana) {
        const id = `recordatorio:${lote}:${led.proxima.concepto}:${led.proxima.fecha_esperada}`;
        if (!dismissedRecordatorios[id]) {
          list.push({
            id,
            tipo: "recordatorio",
            lote,
            cliente: info.cliente,
            contacto,
            concepto: led.proxima.concepto,
            fecha: led.proxima.fecha_esperada,
            valor: led.proxima.saldoCuota,
          });
        }
      }

      if (led.cuotasEnMora.length > 0) {
        const primera = led.cuotasEnMora[0];
        const id = `mora:${lote}:${primera.concepto}:${primera.fecha_esperada}`;
        if (!dismissedRecordatorios[id]) {
          list.push({
            id,
            tipo: "mora",
            lote,
            cliente: info.cliente,
            contacto,
            concepto: primera.concepto,
            fecha: primera.fecha_esperada,
            diasMora: led.diasMoraMax,
            valor: led.montoEnMora,
          });
        }
      }
    }
    return list;
  }, [loading, allLoteKeys, allLotesData, extraPagos, dismissedRecordatorios]);

  const filteredLotes = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return allLoteKeys;
    return allLoteKeys.filter(
      (k) => k.toUpperCase().includes(q) || (allLotesData[k].cliente || "").toUpperCase().includes(q)
    );
  }, [query, allLoteKeys, allLotesData]);

  // ---------- Nuevo lote ----------
  function openNewLoteForm() {
    setNewLote({
      key: "",
      cliente: "",
      valorNegocio: "",
      telefono: "",
      correo: "",
      cuotas: [{ fecha_esperada: "", concepto: "CUOTA 1", valor: "" }],
      genNumCuotas: 12,
      genValorCuota: "",
      genFechaInicio: todayISO(),
    });
    setShowNewLoteForm(true);
  }

  function updateNewLoteField(field, value) {
    setNewLote((prev) => ({ ...prev, [field]: value }));
  }

  function elegirLoteDisponible(id) {
    if (id === "__otro") {
      setNewLote((prev) => ({ ...prev, key: "", otro: true }));
      return;
    }
    const d = disponibles.find((x) => x.id === id);
    setNewLote((prev) => {
      const sugeridoAnterior = prev.valorSugerido;
      const usarSugerido = !prev.valorNegocio || String(prev.valorNegocio) === String(sugeridoAnterior || "");
      return {
        ...prev,
        key: id,
        valorSugerido: d?.valor_sugerido || "",
        valorNegocio: usarSugerido && d?.valor_sugerido ? String(d.valor_sugerido) : prev.valorNegocio,
      };
    });
  }

  function updateCuotaRow(idx, field, value) {
    setNewLote((prev) => {
      const cuotas = prev.cuotas.map((c, i) => (i === idx ? { ...c, [field]: value } : c));
      return { ...prev, cuotas };
    });
  }

  function addCuotaRow() {
    setNewLote((prev) => ({
      ...prev,
      cuotas: [...prev.cuotas, { fecha_esperada: "", concepto: `CUOTA ${prev.cuotas.length}`, valor: "" }],
    }));
  }

  function removeCuotaRow(idx) {
    setNewLote((prev) => ({ ...prev, cuotas: prev.cuotas.filter((_, i) => i !== idx) }));
  }

  function generarCuotasAutomaticas() {
    setNewLote((prev) => {
      const n = Math.max(1, parseInt(prev.genNumCuotas, 10) || 1);
      const valorCuota = Number(prev.genValorCuota) || 0;
      const start = prev.genFechaInicio || todayISO();
      const [y, m, d] = start.split("-").map((x) => parseInt(x, 10));
      const cuotas = Array.from({ length: n }).map((_, i) => {
        const dt = new Date(y, m - 1 + i, d);
        const fecha = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(
          dt.getDate()
        ).padStart(2, "0")}`;
        const concepto = i === n - 1 ? "CUOTA FINAL" : i === 0 ? "CUOTA INICIAL" : `CUOTA ${i}`;
        return { fecha_esperada: fecha, concepto, valor: valorCuota };
      });
      return { ...prev, cuotas };
    });
  }

  async function handleSaveNewLote() {
    if (!newLote) return;
    const key = newLote.key.trim().toUpperCase().replace(/\s+/g, " ");
    const cliente = newLote.cliente.trim();
    const valorNegocio = Number(newLote.valorNegocio);
    const cuotasValidas = newLote.cuotas
      .filter((c) => c.valor && Number(c.valor) > 0)
      .map((c) => ({
        fecha_esperada: c.fecha_esperada || null,
        concepto: c.concepto || "CUOTA",
        valor: Number(c.valor),
      }));

    if (!key || !cliente || !valorNegocio || cuotasValidas.length === 0) {
      setToast({ type: "error", msg: "Completa lote, cliente, valor del negocio y al menos una cuota." });
      return;
    }
    if (allLotesData[key]) {
      setToast({ type: "error", msg: `Ya existe un lote llamado "${key}".` });
      return;
    }

    setSavingNewLote(true);
    try {
      await crearLote({
        id: key,
        cliente,
        valorNegocio,
        cuotas: cuotasValidas,
        telefono: newLote.telefono.replace(/\D/g, ""),
        correo: newLote.correo.trim(),
      });
      setAllLotesData((prev) => ({
        ...prev,
        [key]: {
          cliente,
          valor_negocio: valorNegocio,
          cuotas_plan: cuotasValidas,
          pagos_registrados: [],
          es_nuevo: true,
          telefono: newLote.telefono.replace(/\D/g, "") || null,
          correo: newLote.correo.trim() || null,
        },
      }));
      setDisponibles((prev) => prev.map((d) => (d.id === key ? { ...d, vendido: true } : d)));
      setToast({ type: "ok", msg: `${key} creado correctamente` });
      setShowNewLoteForm(false);
      setNewLote(null);
      setSelectedLote(key);
    } catch (e) {
      setToast({ type: "error", msg: `No se pudo guardar el nuevo lote: ${e?.message || e}` });
    } finally {
      setSavingNewLote(false);
    }
  }

  async function handleDeleteCustomLote(key) {
    if (!window.confirm(`¿Eliminar ${key} y todos sus pagos? Esto no se puede deshacer.`)) return;
    try {
      await eliminarLote(key);
      setAllLotesData((prev) => {
        const next = { ...prev };
        delete next[key];
        if (selectedLote === key) setSelectedLote(ordenarLotes(Object.keys(next))[0] || null);
        return next;
      });
      setExtraPagos((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      setDisponibles((prev) => prev.map((d) => (d.id === key ? { ...d, vendido: false } : d)));
      setToast({ type: "ok", msg: `${key} eliminado` });
    } catch (e) {
      setToast({ type: "error", msg: `No se pudo eliminar el lote: ${e?.message || e}` });
    }
  }

  // ---------- Pagos ----------
  function handleManualEntry() {
    setDraft({
      fecha_pago: todayISO(),
      valor: "",
      banco: "",
      comprobante: "",
      loteDestino: selectedLote,
    });
  }

  async function handleConfirmSave() {
    if (!draft || !draft.valor || !draft.fecha_pago) return;
    const destino = draft.loteDestino;
    setSavingPago(true);
    try {
      const nuevoPago = await insertarPago(destino, {
        fecha_pago: draft.fecha_pago,
        valor: Number(draft.valor),
        comprobante: draft.comprobante.trim(),
        banco: draft.banco.trim(),
      });
      setExtraPagos((prev) => ({ ...prev, [destino]: [...(prev[destino] || []), nuevoPago] }));
      setToast({ type: "ok", msg: `Pago guardado en ${destino}` });
      setDraft(null);
      if (destino !== selectedLote) setSelectedLote(destino);
    } catch (e) {
      console.error("Error guardando pago:", e);
      setToast({ type: "error", msg: `No se pudo guardar el pago: ${e?.message || e}` });
    } finally {
      setSavingPago(false);
    }
  }

  async function handleDeletePago(pago) {
    if (
      !window.confirm(`¿Eliminar el pago de ${formatCOP(pago.valor)} del ${formatFecha(pago.fecha_pago)}?`)
    )
      return;
    try {
      await eliminarPago(pago.id);
      setExtraPagos((prev) => ({
        ...prev,
        [selectedLote]: (prev[selectedLote] || []).filter((p) => p.id !== pago.id),
      }));
      setToast({ type: "ok", msg: "Pago eliminado" });
    } catch (e) {
      setToast({ type: "error", msg: `No se pudo eliminar el pago: ${e?.message || e}` });
    }
  }

  // ---------- Contacto ----------
  async function handleSaveContacto() {
    const { lote, telefono, correo } = contactoEdit;
    const tel = telefono.replace(/\D/g, "");
    try {
      await actualizarContacto(lote, { telefono: tel, correo: correo.trim() });
      setAllLotesData((prev) => ({
        ...prev,
        [lote]: { ...prev[lote], telefono: tel || null, correo: correo.trim() || null },
      }));
      setContactoEdit(null);
      setToast({ type: "ok", msg: "Contacto actualizado" });
    } catch (e) {
      setToast({ type: "error", msg: `No se pudo guardar el contacto: ${e?.message || e}` });
    }
  }

  // ---------- Cargar lotes desde Excel ----------
  function openExcel() {
    setExcelLotes(null);
    setExcelSel({});
    setExcelError(null);
    setShowExcel(true);
  }

  function estadoExcel(l) {
    if (!l.lote || !l.cliente || l.cuotas.length === 0) return "error";
    if (allLotesData[l.lote]) return "existe";
    return "ok";
  }

  async function handleExcelFile(e) {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    setExcelBusy(true);
    setExcelError(null);
    try {
      const lotes = await leerArchivoExcel(f);
      if (lotes.length === 0) throw new Error("No encontré ninguna hoja con plan de cuotas en ese archivo.");
      // Si el mismo lote aparece en dos hojas, solo se toma la primera
      const vistos = new Set();
      const sel = {};
      lotes.forEach((l, i) => {
        const dup = l.lote && vistos.has(l.lote);
        if (dup) l.avisos.push("Este lote ya aparece en otra hoja del archivo.");
        if (l.lote) vistos.add(l.lote);
        sel[i] = estadoExcel(l) === "ok" && !dup;
      });
      setExcelLotes(lotes);
      setExcelSel(sel);
    } catch (err) {
      setExcelError(err?.message || String(err));
      setExcelLotes(null);
    } finally {
      setExcelBusy(false);
      if (excelInputRef.current) excelInputRef.current.value = "";
    }
  }

  async function handleExcelCrear() {
    const elegidos = (excelLotes || []).filter((l, i) => excelSel[i] && estadoExcel(l) === "ok");
    if (elegidos.length === 0) return;
    setExcelBusy(true);
    const creados = [];
    const fallidos = [];
    for (const l of elegidos) {
      try {
        await crearLote({
          id: l.lote,
          cliente: l.cliente,
          valorNegocio: l.valorNegocio || l.sumaPlan,
          cuotas: l.cuotas,
          telefono: l.telefono,
          correo: l.correo,
          pagos: l.pagos,
        });
        creados.push(l.lote);
      } catch (err) {
        fallidos.push(`${l.lote}: ${err?.message || err}`);
      }
    }
    await load({ silent: true });
    setExcelBusy(false);
    if (creados.length) {
      setSelectedLote(creados[0]);
      setTab("registro");
    }
    if (fallidos.length) {
      setExcelError(`No se pudieron crear: ${fallidos.join(" · ")}`);
      setExcelLotes((prev) => (prev || []).filter((l) => !creados.includes(l.lote)));
    } else {
      setShowExcel(false);
    }
    setToast({
      type: fallidos.length ? "error" : "ok",
      msg: `${creados.length} lote(s) creado(s)` + (fallidos.length ? `, ${fallidos.length} con error` : ""),
    });
  }

  // ---------- Importar respaldo de la versión de Claude ----------
  async function handleImport() {
    let respaldo;
    try {
      respaldo = JSON.parse(importText);
    } catch (e) {
      setToast({ type: "error", msg: "El texto pegado no es un JSON válido. Cópialo completo e intenta de nuevo." });
      return;
    }
    setImporting(true);
    try {
      const r = await importarRespaldo(respaldo, allLotesData);
      await load({ silent: true });
      setShowImport(false);
      setImportText("");
      setToast({
        type: "ok",
        msg:
          `Importados: ${r.pagosImportados} pago(s) nuevos de ${r.pagosEnRespaldo} en el respaldo` +
          (r.lotesCreados ? `, ${r.lotesCreados} lote(s) nuevos` : "") +
          (r.pagosOmitidos ? `. ${r.pagosOmitidos} omitido(s) porque su lote no existe.` : "."),
      });
    } catch (e) {
      setToast({ type: "error", msg: `No se pudo importar: ${e?.message || e}` });
    } finally {
      setImporting(false);
    }
  }

  // ---------- Exportar ----------
  function handleExportPDF() {
    setExportingPDF(true);
    try {
      const html = buildFichaHTML({ ledger, info, selectedLote, loteNum });
      const blob = new Blob([html], { type: "text/html;charset=utf-8;" });
      const url = URL.createObjectURL(blob);

      const opened = window.open(url, "_blank");
      if (!opened) {
        const filename = `Ficha_cuenta_${selectedLote.replace(/\s+/g, "_")}.html`;
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setToast({
          type: "ok",
          msg: "No se pudo abrir una pestaña nueva, asi que descargamos el archivo. Abrelo y usa 'Imprimir > Guardar como PDF'.",
        });
      } else {
        setToast({
          type: "ok",
          msg: "Ficha abierta en una pestaña nueva. Ahi usa 'Imprimir > Guardar como PDF'.",
        });
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setToast({ type: "error", msg: "No se pudo generar la ficha. Intenta de nuevo." });
    } finally {
      setExportingPDF(false);
    }
  }

  function handleExportCSV() {
    try {
      const rows = [];
      const hoyFmt = formatFecha(todayISO());

      rows.push(["ESTADO DE CUENTA - SAN MARINO LOTES"]);
      rows.push(["Cliente", info.cliente || ""]);
      rows.push(["Lote", selectedLote]);
      rows.push(["Fecha del reporte", hoyFmt]);
      rows.push(["Valor del negocio", ledger.valorNegocio]);
      rows.push(["Total pagado", ledger.totalPagado]);
      rows.push(["Saldo pendiente", ledger.saldo]);
      rows.push(["Avance", `${Math.round(ledger.avance)}%`]);
      if (ledger.cuotasEnMora.length > 0) {
        rows.push(["Cuotas en mora", ledger.cuotasEnMora.length]);
        rows.push(["Monto en mora", ledger.montoEnMora]);
      }
      rows.push([]);

      rows.push(["PLAN DE CUOTAS"]);
      rows.push(["Fecha esperada", "Concepto", "Valor", "Estado"]);
      ledger.cuotas.forEach((c) => {
        rows.push([formatFecha(c.fecha_esperada), c.concepto || "", c.valor || "", c.estado]);
      });
      rows.push([]);

      rows.push(["PAGOS REGISTRADOS"]);
      rows.push(["Fecha", "Valor", "Aplicado a", "Banco", "Comprobante"]);
      ledger.pagos.forEach((p) => {
        rows.push([formatFecha(p.fecha_pago), p.valor || "", p.cuotaAplicada || "", p.banco || "", p.comprobante || ""]);
      });

      const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
      const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const filename = `Estado_cuenta_${selectedLote.replace(/\s+/g, "_")}.csv`;

      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setToast({ type: "ok", msg: "Reporte exportado" });
    } catch (err) {
      setToast({ type: "error", msg: "No se pudo exportar el CSV. Intenta de nuevo." });
    }
  }

  // ---------- Pantallas de carga / error ----------
  if (loading) {
    return (
      <div className="cdp-root">
        <div className="cdp-center-msg">
          <Loader2 size={16} className="cdp-spin" /> Cargando lotes y pagos...
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="cdp-root">
        <div className="cdp-center-msg" style={{ flexDirection: "column" }}>
          <div className="cdp-error">
            <AlertCircle size={14} /> No se pudieron cargar los datos: {loadError}
          </div>
          <button className="cdp-upload-btn" onClick={() => load()}>
            <RefreshCw size={14} /> Reintentar
          </button>
          <button className="cdp-link-btn" onClick={() => supabase.auth.signOut()}>
            Cerrar sesión
          </button>
        </div>
      </div>
    );
  }

  const info = selectedLote ? allLotesData[selectedLote] : null;
  const loteNum = selectedLote ? selectedLote.replace(/\D/g, "") : "";
  const isCustomLote = !!info?.es_nuevo;

  return (
    <div className="cdp-root">
      <header className="cdp-header">
        <div className="cdp-header-brand">
          <img src={LOGO_SRC} alt="San Marino Lotes" className="cdp-logo" />
          <div className="cdp-header-titles">
            <h1>Registro de Pagos</h1>
            <div className="cdp-eyebrow">ASESORA NATALI TABORDA CORREA</div>
          </div>
        </div>
        <div className="cdp-header-right">
          <button className="cdp-recordatorios-btn" onClick={() => setShowRecordatorios(true)}>
            <Bell size={14} />
            Recordatorios
            {recordatorios.length > 0 && <span className="cdp-recordatorios-badge">{recordatorios.length}</span>}
          </button>
          <div className="cdp-eyebrow" style={{ fontWeight: 700 }}>
            {allLoteKeys.length} lotes activos
          </div>
          <div className="cdp-user-row">
            <button
              className="cdp-del-btn"
              title="Actualizar datos"
              onClick={() => load({ silent: true })}
              disabled={refreshing}
            >
              <RefreshCw size={13} className={refreshing ? "cdp-spin" : ""} />
            </button>
            <span>{session?.user?.email}</span>
            <button className="cdp-del-btn" title="Cerrar sesión" onClick={() => supabase.auth.signOut()}>
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </header>

      <nav className="cdp-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "registro"}
          className={`cdp-tab ${tab === "registro" ? "active" : ""}`}
          onClick={() => setTab("registro")}
        >
          <ClipboardList size={15} /> Registro de pagos
        </button>
        <button
          role="tab"
          aria-selected={tab === "dashboard"}
          className={`cdp-tab ${tab === "dashboard" ? "active" : ""}`}
          onClick={() => setTab("dashboard")}
        >
          <LayoutDashboard size={15} /> Dashboard
        </button>
      </nav>

      {tab === "dashboard" ? (
        <Dashboard
          allLotesData={allLotesData}
          extraPagos={extraPagos}
          onOpenLote={(k) => {
            setSelectedLote(k);
            setTab("registro");
            window.scrollTo(0, 0);
          }}
        />
      ) : (
      <div className="cdp-body">
        <aside className="cdp-sidebar">
          <div className="cdp-search">
            <Search size={14} color="var(--ink-soft)" />
            <input placeholder="Buscar lote o cliente..." value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <button className="cdp-new-lote-btn" onClick={openNewLoteForm}>
            <Plus size={14} /> Nuevo lote
          </button>
          <button className="cdp-new-lote-btn secondary" onClick={openExcel}>
            <FileSpreadsheet size={14} /> Cargar desde Excel
          </button>
          {filteredLotes.map((k) => {
            const isCustom = !!allLotesData[k].es_nuevo;
            return (
              <div
                key={k}
                className={`cdp-lote-item ${k === selectedLote ? "active" : ""}`}
                onClick={() => setSelectedLote(k)}
              >
                <div style={{ minWidth: 0 }}>
                  <div className="cdp-lote-num">
                    {k} {isCustom && <span className="cdp-tag ia" style={{ marginLeft: 4 }}>nuevo</span>}
                  </div>
                  <div className="cdp-lote-cliente">{allLotesData[k].cliente}</div>
                </div>
                {isCustom ? (
                  <button
                    className="cdp-del-btn"
                    title="Eliminar lote"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteCustomLote(k);
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                ) : (
                  <ChevronRight size={14} color="var(--ink-soft)" style={{ flexShrink: 0 }} />
                )}
              </div>
            );
          })}
        </aside>

        {!info || !ledger ? (
          <main className="cdp-main">
            <div className="cdp-center-msg">No hay lotes todavía. Crea uno con “Nuevo lote”.</div>
          </main>
        ) : (
          <main className="cdp-main">
            <div className="cdp-summary-row">
              <ProgressStamp avance={ledger.avance} loteNum={loteNum} />
              <div className="cdp-cliente-block">
                <h2>
                  {info.cliente} {isCustomLote && <span className="cdp-tag ia">nuevo</span>}
                </h2>
                <div className="cdp-meta">
                  <Building2 size={11} style={{ display: "inline", verticalAlign: -1, marginRight: 4 }} />
                  {selectedLote} · Negocio {formatCOP(ledger.valorNegocio)}
                </div>
                <div className="cdp-contacto-line">
                  <span>Tel: {info.telefono || "—"}</span>
                  <span>Correo: {info.correo || "—"}</span>
                  <button
                    className="cdp-link-btn"
                    onClick={() =>
                      setContactoEdit({ lote: selectedLote, telefono: info.telefono || "", correo: info.correo || "" })
                    }
                  >
                    Editar contacto
                  </button>
                </div>
              </div>
            </div>

            <div className="cdp-cards">
              <div className="cdp-card">
                <div className="cdp-card-label">Valor del negocio</div>
                <div className="cdp-card-value">{formatCOP(ledger.valorNegocio)}</div>
              </div>
              <div className="cdp-card moss">
                <div className="cdp-card-label">Total pagado</div>
                <div className="cdp-card-value">{formatCOP(ledger.totalPagado)}</div>
              </div>
              <div className="cdp-card rust">
                <div className="cdp-card-label">Saldo pendiente</div>
                <div className="cdp-card-value">{formatCOP(ledger.saldo)}</div>
              </div>
              <div className={`cdp-card ${ledger.cuotasEnMora.length > 0 ? "rust" : ""}`}>
                <div className="cdp-card-label">{ledger.cuotasEnMora.length > 0 ? "En mora" : "Proxima cuota"}</div>
                <div className="cdp-card-value" style={{ fontSize: 13 }}>
                  {ledger.cuotasEnMora.length > 0
                    ? `${ledger.cuotasEnMora.length} cuota${ledger.cuotasEnMora.length > 1 ? "s" : ""} · ${ledger.diasMoraMax}d`
                    : ledger.proxima
                    ? `${ledger.proxima.concepto} · ${formatFecha(ledger.proxima.fecha_esperada)}`
                    : "Al dia"}
                </div>
              </div>
            </div>

            {ledger.cuotasEnMora.length > 0 && (
              <div className="cdp-mora-banner">
                <AlertCircle size={16} />
                <div>
                  <strong>{ledger.cuotasEnMora.length}</strong> cuota
                  {ledger.cuotasEnMora.length > 1 ? "s" : ""} vencida
                  {ledger.cuotasEnMora.length > 1 ? "s" : ""} por <strong>{formatCOP(ledger.montoEnMora)}</strong> · la más
                  antigua lleva <strong>{ledger.diasMoraMax} días</strong> de atraso
                </div>
              </div>
            )}

            <h3 className="cdp-section-title">
              <Plus size={15} color="var(--blueprint)" /> Registrar pago
            </h3>
            <div className="cdp-upload-zone">
              {!draft && (
                <div className="cdp-upload-row">
                  <button className="cdp-upload-btn" onClick={handleManualEntry}>
                    <Plus size={15} /> Registrar un pago
                  </button>
                </div>
              )}

              {draft && (
                <div className="cdp-draft" style={{ marginTop: 0 }}>
                  <div className="cdp-modal-subtitle" style={{ margin: "0 0 10px" }}>
                    Datos del pago
                  </div>
                  <div className="cdp-draft-grid">
                    <div className="cdp-field">
                      <label>Fecha de pago</label>
                      <input
                        type="date"
                        value={draft.fecha_pago || ""}
                        onChange={(e) => setDraft({ ...draft, fecha_pago: e.target.value })}
                      />
                    </div>
                    <div className="cdp-field">
                      <label>Valor (COP)</label>
                      <input
                        type="number"
                        min="1"
                        value={draft.valor}
                        onChange={(e) => setDraft({ ...draft, valor: e.target.value })}
                      />
                    </div>
                    <div className="cdp-field">
                      <label>Banco</label>
                      <input value={draft.banco} onChange={(e) => setDraft({ ...draft, banco: e.target.value })} />
                    </div>
                    <div className="cdp-field">
                      <label>N. de comprobante</label>
                      <input
                        value={draft.comprobante}
                        onChange={(e) => setDraft({ ...draft, comprobante: e.target.value })}
                      />
                    </div>
                    <div className="cdp-field">
                      <label>Aplicar al lote</label>
                      <select
                        value={draft.loteDestino}
                        onChange={(e) => setDraft({ ...draft, loteDestino: e.target.value })}
                      >
                        {allLoteKeys.map((k) => (
                          <option key={k} value={k}>
                            {k} · {allLotesData[k].cliente}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="cdp-upload-btn"
                      onClick={handleConfirmSave}
                      disabled={!draft.valor || Number(draft.valor) <= 0 || !draft.fecha_pago || savingPago}
                    >
                      {savingPago ? <Loader2 size={15} className="cdp-spin" /> : <Check size={15} />}
                      {savingPago ? "Guardando..." : "Guardar pago"}
                    </button>
                    <button className="cdp-upload-btn secondary" onClick={() => setDraft(null)}>
                      <X size={15} /> Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="cdp-export-row">
              <span className="cdp-export-hint">Descarga la ficha e imprímela como PDF para enviar</span>
              <button className="cdp-export-btn secondary" onClick={handleExportCSV}>
                <Download size={13} /> Datos (CSV)
              </button>
              <button className="cdp-export-btn primary" onClick={handleExportPDF} disabled={exportingPDF}>
                {exportingPDF ? <Loader2 size={13} className="cdp-spin" /> : <Download size={13} />}
                {exportingPDF ? "Generando..." : "Ficha para el cliente"}
              </button>
            </div>

            <div className="cdp-tables-row">
              <div>
                <h3 className="cdp-section-title">Plan de cuotas</h3>
                <div className="cdp-table-wrap">
                  <table className="cdp-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Concepto</th>
                        <th>Valor</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ledger.cuotas.map((c, i) => (
                        <tr key={i}>
                          <td>{formatFecha(c.fecha_esperada)}</td>
                          <td style={{ fontFamily: "Inter, sans-serif" }}>{c.concepto}</td>
                          <td>
                            {formatCOP(c.valor)}
                            {c.estado === "parcial" && (
                              <div style={{ fontSize: 10, color: "var(--ink-soft)" }}>saldo {formatCOP(c.saldoCuota)}</div>
                            )}
                          </td>
                          <td>
                            <span className={`cdp-tag ${c.estado}`}>{c.estado}</span>
                            {c.enMora && (
                              <span className="cdp-tag parcial" style={{ marginLeft: 4 }}>
                                {c.diasMora}d mora
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="cdp-section-title">Pagos registrados</h3>
                <div className="cdp-table-wrap">
                  <table className="cdp-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Valor</th>
                        <th>Aplicado a</th>
                        <th>Banco</th>
                        <th>Comp.</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {ledger.pagos.map((p) => {
                        const isExtra = p.origen !== "original";
                        return (
                          <tr key={p.id}>
                            <td>
                              {formatFecha(p.fecha_pago)} {p.origen === "ia" && <span className="cdp-tag ia">IA</span>}
                              {p.origen === "manual" && <span className="cdp-tag ia">Manual</span>}
                            </td>
                            <td>{formatCOP(p.valor)}</td>
                            <td style={{ fontFamily: "Inter, sans-serif", fontSize: 11.5, color: "var(--ink-soft)" }}>
                              {p.cuotaAplicada || "—"}
                            </td>
                            <td style={{ fontFamily: "Inter, sans-serif" }}>{p.banco || "—"}</td>
                            <td>{p.comprobante || "—"}</td>
                            <td>
                              {isExtra && (
                                <button className="cdp-del-btn" title="Eliminar pago" onClick={() => handleDeletePago(p)}>
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </main>
        )}
      </div>
      )}

      {showRecordatorios && (
        <div className="cdp-modal-overlay" onClick={() => setShowRecordatorios(false)}>
          <div className="cdp-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cdp-modal-header">
              <h3>Recordatorios de pago</h3>
              <button
                className="cdp-del-btn"
                onClick={() => {
                  setShowRecordatorios(false);
                  setShowImport(true);
                }}
                title="Trae los pagos que registraste en la versión que corría dentro de Claude"
                style={{ fontSize: 11, width: "auto", padding: "4px 8px" }}
              >
                Importar respaldo
              </button>
              <button className="cdp-del-btn" onClick={() => setShowRecordatorios(false)}>
                <X size={16} />
              </button>
            </div>

            {recordatorios.length === 0 ? (
              <div style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>
                No hay recordatorios pendientes por ahora. Vuelve a revisar mañana.
              </div>
            ) : (
              recordatorios.map((r) => {
                const mensaje =
                  r.tipo === "mora"
                    ? buildMoraMessage({
                        cliente: r.cliente,
                        lote: r.lote,
                        concepto: r.concepto,
                        fecha: r.fecha,
                        diasMora: r.diasMora,
                        monto: r.valor,
                      })
                    : buildRecordatorioMessage({
                        cliente: r.cliente,
                        lote: r.lote,
                        concepto: r.concepto,
                        fecha: r.fecha,
                        valor: r.valor,
                      });
                const asunto = buildEmailSubject(r.tipo, r.lote);
                const waLink = r.contacto?.telefono
                  ? `https://wa.me/${r.contacto.telefono}?text=${encodeURIComponent(mensaje)}`
                  : null;
                const mailLink = r.contacto?.correo
                  ? `mailto:${r.contacto.correo}?subject=${encodeURIComponent(asunto)}&body=${encodeURIComponent(mensaje)}`
                  : null;

                return (
                  <div key={r.id} className={`cdp-recordatorio-card ${r.tipo === "mora" ? "mora" : ""}`}>
                    <div className="cdp-recordatorio-head">
                      <div>
                        <div className="cdp-recordatorio-titulo">
                          {r.cliente} · {r.lote}
                        </div>
                        <div className="cdp-recordatorio-meta">
                          {r.tipo === "mora"
                            ? `EN MORA · ${r.diasMora}d · ${formatCOP(r.valor)}`
                            : `VENCE MAÑANA · ${formatFecha(r.fecha)} · ${formatCOP(r.valor)}`}
                        </div>
                      </div>
                      <button
                        className="cdp-del-btn"
                        title="Descartar por hoy"
                        onClick={() => handleDismissRecordatorio(r.id)}
                      >
                        <X size={14} />
                      </button>
                    </div>

                    <div className="cdp-recordatorio-msg">{mensaje}</div>

                    <div className="cdp-recordatorio-actions">
                      {waLink ? (
                        <a className="whatsapp" href={waLink} target="_blank" rel="noopener noreferrer">
                          WhatsApp
                        </a>
                      ) : null}
                      {mailLink ? (
                        <a className="email" href={mailLink}>
                          Correo
                        </a>
                      ) : null}
                      {!waLink && !mailLink && (
                        <span className="cdp-sin-contacto">
                          Sin datos de contacto para este cliente —{" "}
                          <button
                            className="cdp-link-btn"
                            onClick={() => {
                              const l = allLotesData[r.lote];
                              setShowRecordatorios(false);
                              setContactoEdit({ lote: r.lote, telefono: l.telefono || "", correo: l.correo || "" });
                            }}
                          >
                            agrégalos aquí
                          </button>
                          .
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {contactoEdit && (
        <div className="cdp-modal-overlay" onClick={() => setContactoEdit(null)}>
          <div className="cdp-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="cdp-modal-header">
              <h3>Contacto · {contactoEdit.lote}</h3>
              <button className="cdp-del-btn" onClick={() => setContactoEdit(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="cdp-field" style={{ marginBottom: 10 }}>
              <label>WhatsApp (con indicativo, ej. 573001234567)</label>
              <input
                value={contactoEdit.telefono}
                onChange={(e) => setContactoEdit({ ...contactoEdit, telefono: e.target.value })}
              />
            </div>
            <div className="cdp-field" style={{ marginBottom: 14 }}>
              <label>Correo</label>
              <input
                type="email"
                value={contactoEdit.correo}
                onChange={(e) => setContactoEdit({ ...contactoEdit, correo: e.target.value })}
              />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="cdp-upload-btn" onClick={handleSaveContacto}>
                <Check size={15} /> Guardar
              </button>
              <button className="cdp-upload-btn secondary" onClick={() => setContactoEdit(null)}>
                <X size={15} /> Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {showImport && (
        <div className="cdp-modal-overlay" onClick={() => !importing && setShowImport(false)}>
          <div className="cdp-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cdp-modal-header">
              <h3>Importar respaldo de la versión de Claude</h3>
              <button className="cdp-del-btn" onClick={() => setShowImport(false)} disabled={importing}>
                <X size={16} />
              </button>
            </div>
            <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 0 }}>
              Pega aquí el JSON del respaldo (con <code>extra_pagos_all</code>, <code>custom_lotes</code> y{" "}
              <code>recordatorios_dismissed</code>). Puedes importarlo más de una vez: los pagos que ya existan no se
              duplican.
            </p>
            <textarea
              className="cdp-import-area"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{"extra_pagos_all": {...}, "custom_lotes": {...}, "recordatorios_dismissed": {...}}'
            />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="cdp-upload-btn" onClick={handleImport} disabled={importing || !importText.trim()}>
                {importing ? <Loader2 size={15} className="cdp-spin" /> : <Upload size={15} />}
                {importing ? "Importando..." : "Importar"}
              </button>
              <button className="cdp-upload-btn secondary" onClick={() => setShowImport(false)} disabled={importing}>
                <X size={15} /> Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {showExcel && (
        <div className="cdp-modal-overlay" onClick={() => !excelBusy && setShowExcel(false)}>
          <div className="cdp-modal cdp-modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="cdp-modal-header">
              <h3>Cargar lotes desde Excel</h3>
              <button className="cdp-del-btn" onClick={() => setShowExcel(false)} disabled={excelBusy}>
                <X size={16} />
              </button>
            </div>
            <ol className="cdp-excel-steps">
              <li>
                Descarga la{" "}
                <a href={plantillaUrl} download="Plantilla plan de pagos San Marino.xlsx">
                  plantilla de plan de pagos
                </a>{" "}
                y llénala en Excel: cliente, número del lote, valor del negocio y las cuotas. Una hoja por lote.
              </li>
              <li>También sirven las hojas del archivo "Control de Pagos" que ya usas.</li>
              <li>Súbela aquí, revisa lo que leyó la app y haz clic en "Crear lotes".</li>
            </ol>
            <input
              ref={excelInputRef}
              type="file"
              accept=".xlsx,.xls,.xlsm"
              onChange={handleExcelFile}
              style={{ display: "none" }}
            />
            <button className="cdp-upload-btn" onClick={() => excelInputRef.current?.click()} disabled={excelBusy}>
              {excelBusy ? <Loader2 size={15} className="cdp-spin" /> : <Upload size={15} />}
              {excelBusy ? "Procesando..." : excelLotes ? "Elegir otro archivo" : "Elegir archivo de Excel"}
            </button>
            {excelError && (
              <div className="cdp-error" style={{ marginTop: 12 }}>
                <AlertCircle size={14} /> {excelError}
              </div>
            )}
            {excelLotes && (
              <>
                <div className="cdp-dash-tablewrap" style={{ marginTop: 14 }}>
                  <table className="cdp-table cdp-dash-table">
                    <thead>
                      <tr>
                        <th></th>
                        <th>Lote</th>
                        <th>Cliente</th>
                        <th className="num">Valor negocio</th>
                        <th className="num">Cuotas</th>
                        <th className="num">Pagos recibidos</th>
                        <th>Revisión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {excelLotes.map((l, i) => {
                        const est = estadoExcel(l);
                        return (
                          <tr key={i}>
                            <td>
                              <input
                                type="checkbox"
                                checked={!!excelSel[i]}
                                disabled={est !== "ok"}
                                onChange={(e) => setExcelSel({ ...excelSel, [i]: e.target.checked })}
                              />
                            </td>
                            <td>{l.lote || "—"}</td>
                            <td className="txt">{l.cliente || "—"}</td>
                            <td className="num">{formatCOP(l.valorNegocio)}</td>
                            <td className="num">
                              {l.cuotas.length} · {formatCOP(l.sumaPlan)}
                            </td>
                            <td className="num">
                              {l.pagos.length} · {formatCOP(l.sumaPagos)}
                            </td>
                            <td className="txt">
                              {est === "existe" ? (
                                <span className="cdp-tag pendiente">ya existe, se omite</span>
                              ) : est === "error" ? (
                                <span className="cdp-tag parcial">no se puede crear</span>
                              ) : (
                                <span className="cdp-tag pagada">listo</span>
                              )}
                              {l.avisos.map((a, k) => (
                                <div key={k} className="cdp-excel-aviso">
                                  {a}
                                </div>
                              ))}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                  <button
                    className="cdp-upload-btn"
                    onClick={handleExcelCrear}
                    disabled={excelBusy || !Object.values(excelSel).some(Boolean)}
                  >
                    {excelBusy ? <Loader2 size={15} className="cdp-spin" /> : <Check size={15} />}
                    Crear {Object.values(excelSel).filter(Boolean).length} lote(s)
                  </button>
                  <button className="cdp-upload-btn secondary" onClick={() => setShowExcel(false)} disabled={excelBusy}>
                    <X size={15} /> Cancelar
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {showNewLoteForm && newLote && (
        <div className="cdp-modal-overlay" onClick={() => setShowNewLoteForm(false)}>
          <div className="cdp-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cdp-modal-header">
              <h3>Nuevo lote y plan de pagos</h3>
              <button
                className="cdp-del-btn"
                style={{ fontSize: 11, width: "auto", padding: "4px 8px" }}
                onClick={() => {
                  setShowNewLoteForm(false);
                  openExcel();
                }}
              >
                ¿Lo tienes en Excel? Cárgalo aquí
              </button>
              <button className="cdp-del-btn" onClick={() => setShowNewLoteForm(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="cdp-draft-grid" style={{ marginBottom: 4 }}>
              <div className="cdp-field">
                <label>Lote</label>
                {lotesPorVender.length > 0 && !newLote.otro ? (
                  <select value={newLote.key} onChange={(e) => elegirLoteDisponible(e.target.value)}>
                    <option value="">Elige un lote por vender…</option>
                    {lotesPorVender.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.id}
                        {d.area_m2 ? ` · ${Number(d.area_m2).toLocaleString("es-CO")} m²` : ""}
                        {d.valor_sugerido ? ` · ${formatCOP(d.valor_sugerido)}` : ""}
                        {d.nota ? ` · ${d.nota}` : ""}
                      </option>
                    ))}
                    <option value="__otro">Otro (escribir el número)…</option>
                  </select>
                ) : (
                  <input
                    placeholder="LOTE 200"
                    value={newLote.key}
                    onChange={(e) => updateNewLoteField("key", e.target.value)}
                  />
                )}
              </div>
              <div className="cdp-field">
                <label>Cliente</label>
                <input
                  placeholder="Nombre completo"
                  value={newLote.cliente}
                  onChange={(e) => updateNewLoteField("cliente", e.target.value)}
                />
              </div>
              <div className="cdp-field">
                <label>Valor del negocio (COP)</label>
                <input
                  type="number"
                  value={newLote.valorNegocio}
                  onChange={(e) => updateNewLoteField("valorNegocio", e.target.value)}
                />
              </div>
              <div className="cdp-field">
                <label>WhatsApp (opcional)</label>
                <input
                  placeholder="573001234567"
                  value={newLote.telefono}
                  onChange={(e) => updateNewLoteField("telefono", e.target.value)}
                />
              </div>
              <div className="cdp-field">
                <label>Correo (opcional)</label>
                <input
                  type="email"
                  value={newLote.correo}
                  onChange={(e) => updateNewLoteField("correo", e.target.value)}
                />
              </div>
            </div>

            <h4 className="cdp-modal-subtitle">Generar cuotas automaticamente (opcional)</h4>
            <div className="cdp-draft-grid" style={{ marginBottom: 4 }}>
              <div className="cdp-field">
                <label>N. de cuotas</label>
                <input
                  type="number"
                  value={newLote.genNumCuotas}
                  onChange={(e) => updateNewLoteField("genNumCuotas", e.target.value)}
                />
              </div>
              <div className="cdp-field">
                <label>Valor por cuota</label>
                <input
                  type="number"
                  value={newLote.genValorCuota}
                  onChange={(e) => updateNewLoteField("genValorCuota", e.target.value)}
                />
              </div>
              <div className="cdp-field">
                <label>Fecha primera cuota</label>
                <input
                  type="date"
                  value={newLote.genFechaInicio}
                  onChange={(e) => updateNewLoteField("genFechaInicio", e.target.value)}
                />
              </div>
              <div style={{ display: "flex", alignItems: "flex-end" }}>
                <button className="cdp-upload-btn secondary" onClick={generarCuotasAutomaticas} type="button">
                  <Sparkles size={14} /> Generar
                </button>
              </div>
            </div>

            <h4 className="cdp-modal-subtitle">Plan de cuotas</h4>
            <div className="cdp-cuotas-editor">
              {newLote.cuotas.map((c, idx) => (
                <div className="cdp-cuota-row" key={idx}>
                  <input
                    type="date"
                    value={c.fecha_esperada}
                    onChange={(e) => updateCuotaRow(idx, "fecha_esperada", e.target.value)}
                  />
                  <input
                    placeholder="Concepto"
                    value={c.concepto}
                    onChange={(e) => updateCuotaRow(idx, "concepto", e.target.value)}
                  />
                  <input
                    type="number"
                    placeholder="Valor"
                    value={c.valor}
                    onChange={(e) => updateCuotaRow(idx, "valor", e.target.value)}
                  />
                  <button className="cdp-del-btn" onClick={() => removeCuotaRow(idx)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button className="cdp-upload-btn secondary" onClick={addCuotaRow} type="button" style={{ marginTop: 8 }}>
              <Plus size={14} /> Agregar cuota
            </button>

            <div
              style={{ display: "flex", gap: 8, marginTop: 18, borderTop: "1px dashed var(--border)", paddingTop: 14 }}
            >
              <button className="cdp-upload-btn" onClick={handleSaveNewLote} disabled={savingNewLote}>
                {savingNewLote ? <Loader2 size={15} className="cdp-spin" /> : <Check size={15} />}
                {savingNewLote ? "Guardando..." : "Crear lote"}
              </button>
              <button className="cdp-upload-btn secondary" onClick={() => setShowNewLoteForm(false)}>
                <X size={15} /> Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`cdp-toast ${toast.type === "error" ? "error" : ""}`}>{toast.msg}</div>}
    </div>
  );
}
