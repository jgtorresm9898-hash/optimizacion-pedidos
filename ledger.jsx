// Funciones de cálculo y formato (mismas que la versión original en Claude).
import React from "react";
import { LOGO_SRC_WHITE } from "./logos.js";

export function formatCOP(v) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(v);
}

export function formatFecha(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${d} ${meses[parseInt(m, 10) - 1]} ${y}`;
}

// Fecha local (Colombia), no UTC: así después de las 7 p. m. no salta al día siguiente.
function isoLocal(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function todayISO() {
  return isoLocal(new Date());
}

export function tomorrowISO() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return isoLocal(d);
}

export function firstName(fullName) {
  if (!fullName) return "";
  const parts = fullName.trim().split(/\s+/);
  // Most records are "NOMBRE1 NOMBRE2 APELLIDO1 APELLIDO2" -> just take the first token, title-cased
  const w = parts[0];
  return w.charAt(0) + w.slice(1).toLowerCase();
}

export function buildRecordatorioMessage({ cliente, lote, concepto, fecha, valor }) {
  return (
    `Hola ${firstName(cliente)}, ¡buen día! 🌿\n\n` +
    `Te escribimos de *San Marino Lotes* para recordarte que mañana, ${formatFecha(fecha)}, ` +
    `vence tu ${concepto.toLowerCase()} del ${lote} por un valor de ${formatCOP(valor)}.\n\n` +
    `Gracias por tu compromiso y puntualidad. Cualquier duda, escríbenos con confianza.\n\n` +
    `— Asesora Natali Taborda Correa\nSan Marino Lotes`
  );
}

export function buildMoraMessage({ cliente, lote, concepto, fecha, diasMora, monto }) {
  return (
    `Hola ${firstName(cliente)}, ¡buen día! 🌿\n\n` +
    `Te escribimos de *San Marino Lotes* porque tu ${concepto.toLowerCase()} del ${lote}, ` +
    `con vencimiento el ${formatFecha(fecha)}, presenta un atraso de ${diasMora} días ` +
    `por un valor de ${formatCOP(monto)}.\n\n` +
    `Sabemos que a veces los pagos se atrasan — te invitamos a ponerte al día pronto para ` +
    `mantener tu inversión protegida. Si ya realizaste el pago, ignora este mensaje y cuéntanos ` +
    `para actualizarlo.\n\n` +
    `— Asesora Natali Taborda Correa\nSan Marino Lotes`
  );
}

export function buildEmailSubject(tipo, lote) {
  return tipo === "mora"
    ? `San Marino Lotes - Aviso de mora, ${lote}`
    : `San Marino Lotes - Recordatorio de pago, ${lote}`;
}

// Builds a standalone, self-contained HTML statement (logo embedded as base64,
// no external fonts/scripts) that the browser can print straight to PDF.
export function buildFichaHTML({ ledger, info, selectedLote, loteNum }) {
  const brand = "#6B8E35";
  const brandSoft = "#E4EAD2";
  const ink = "#2B3620";
  const inkSoft = "#5B6852";
  const rust = "#B5502E";
  const rustSoft = "#F6E7DF";

  const pendientes = ledger.cuotas.filter((c) => c.estado !== "pagada").slice(0, 10);
  const ultimosPagos = [...ledger.pagos].reverse().slice(0, 6);
  const msg = motivationalMessage(ledger);

  const cuotasRows = pendientes
    .map(
      (c) => `<tr>
        <td>${formatFecha(c.fecha_esperada)}</td>
        <td>${c.concepto || ""}</td>
        <td>${formatCOP(c.valor)}</td>
        <td><span class="tag ${c.estado}">${c.estado === "parcial" ? `parcial (saldo ${formatCOP(c.saldoCuota)})` : c.estado}</span></td>
      </tr>`
    )
    .join("");

  const pagosRows = ultimosPagos
    .map(
      (p) => `<tr>
        <td>${formatFecha(p.fecha_pago)}</td>
        <td>${formatCOP(p.valor)}</td>
        <td>${p.banco || "—"}</td>
      </tr>`
    )
    .join("");

  const moraBlock =
    ledger.cuotasEnMora.length > 0
      ? `<div class="alert">
          <strong>${ledger.cuotasEnMora.length} cuota${ledger.cuotasEnMora.length > 1 ? "s" : ""} vencida${
          ledger.cuotasEnMora.length > 1 ? "s" : ""
        } por ${formatCOP(ledger.montoEnMora)}</strong>
          <div>La cuota más antigua lleva ${ledger.diasMoraMax} días de atraso.</div>
        </div>`
      : "";

  return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Estado de cuenta - ${selectedLote}</title>
<style>
  * { box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }
  body {
    font-family: Georgia, 'Times New Roman', serif;
    color: ${ink};
    margin: 0;
    background: #EDEBE0;
  }
  .page {
    max-width: 780px;
    margin: 24px auto;
    background: #fff;
    box-shadow: 0 2px 18px rgba(0,0,0,0.12);
  }
  .header {
    background: ${brand} !important;
    background-color: ${brand} !important;
    color: #fff;
    padding: 26px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header img { height: 46px; display: block; }
  .header .logo-fallback { font-family: Georgia, serif; font-size: 22px; font-weight: 700; letter-spacing: 0.06em; color: #fff; }
  .header .titles { text-align: right; }
  .header h1 { font-size: 19px; margin: 0 0 4px; letter-spacing: 0.04em; }
  .header .meta { font-family: Arial, sans-serif; font-size: 10.5px; opacity: 0.9; }
  .body { padding: 26px 32px 10px; }
  .greeting h2 { font-size: 18px; margin: 0 0 4px; }
  .greeting p { font-family: Arial, sans-serif; font-size: 12px; color: ${inkSoft}; margin: 0 0 18px; }
  .cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
  .card { border: 1px solid #ddd8c8; border-radius: 6px; padding: 10px 14px; background: #FAFAF6 !important; }
  .card .label { font-family: Arial, sans-serif; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.06em; color: ${inkSoft}; margin-bottom: 4px; }
  .card .value { font-family: Arial, sans-serif; font-size: 17px; font-weight: 700; }
  .progress-wrap { margin: 6px 0 18px; }
  .progress-bar { width: 100%; height: 10px; border-radius: 6px; background: #E8E8E0 !important; overflow: hidden; }
  .progress-fill { height: 100%; background: ${brand} !important; border-radius: 6px; }
  .progress-label { font-family: Arial, sans-serif; font-size: 10.5px; color: ${inkSoft}; margin-top: 4px; text-align: right; }
  .alert { border: 1px solid ${rust}; background: ${rustSoft} !important; color: ${rust}; border-radius: 6px; padding: 10px 14px; margin-bottom: 18px; font-family: Arial, sans-serif; font-size: 12px; }
  .alert strong { display: block; margin-bottom: 3px; }
  h3.section { font-size: 14px; margin: 20px 0 8px; border-bottom: 1px dashed #ccc7b4; padding-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 11px; margin-bottom: 8px; }
  th { text-align: left; background: ${brand} !important; color: #fff; padding: 6px 8px; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.04em; }
  td { padding: 6px 8px; border-bottom: 1px solid #eee6d8; }
  tr:nth-child(even) td { background: #FAFAF6 !important; }
  .tag { font-size: 9px; padding: 1px 6px; border-radius: 3px; background: #eee !important; }
  .tag.pendiente { background: #eee !important; color: ${inkSoft}; }
  .tag.parcial { background: ${rustSoft} !important; color: ${rust}; }
  .motiv { background: ${brandSoft} !important; border-radius: 6px; padding: 14px 16px; margin: 20px 0; font-style: italic; font-size: 12.5px; }
  .footer { font-family: Arial, sans-serif; font-size: 9.5px; color: ${inkSoft}; text-align: center; padding: 14px 32px 26px; border-top: 1px solid #eee6d8; }
  .print-btn {
    display: block; margin: 18px auto 0; padding: 10px 22px; background: ${brand}; color: #fff;
    border: none; border-radius: 5px; font-family: Arial, sans-serif; font-size: 13px; cursor: pointer;
  }
  .print-hint { text-align: center; font-family: Arial, sans-serif; font-size: 11px; color: ${inkSoft}; margin-top: 8px; }
  @media print {
    body { background: #fff; }
    .page { box-shadow: none; margin: 0; max-width: 100%; }
    .print-btn, .print-hint { display: none; }
  }
</style>
</head>
<body>
  <div class="page">
    <div class="header">
      <img src="${LOGO_SRC_WHITE}" alt="San Marino Lotes" onerror="this.style.display='none';this.nextElementSibling.style.display='block'" />
      <div class="logo-fallback" style="display:none;">SAN MARINO LOTES</div>
      <div class="titles">
        <h1>ESTADO DE CUENTA</h1>
        <div class="meta">Generado el ${formatFecha(todayISO())} · Lote ${loteNum}</div>
      </div>
    </div>
    <div class="body">
      <div class="greeting">
        <h2>Estimado(a) ${info.cliente || ""},</h2>
        <p>Este es el resumen actual de tu cuenta con San Marino Lotes.</p>
      </div>

      <div class="cards">
        <div class="card"><div class="label">Valor del negocio</div><div class="value">${formatCOP(ledger.valorNegocio)}</div></div>
        <div class="card"><div class="label">Total pagado</div><div class="value">${formatCOP(ledger.totalPagado)}</div></div>
        <div class="card"><div class="label">Saldo pendiente</div><div class="value">${formatCOP(ledger.saldo)}</div></div>
        <div class="card"><div class="label">Avance de pago</div><div class="value">${Math.round(ledger.avance)}%</div></div>
      </div>

      <div class="progress-wrap">
        <div class="progress-bar"><div class="progress-fill" style="width:${Math.max(Math.round(ledger.avance), ledger.avance > 0 ? 3 : 0)}%"></div></div>
      </div>

      ${moraBlock}

      ${
        pendientes.length
          ? `<h3 class="section">Cuotas pendientes</h3>
        <table><thead><tr><th>Fecha</th><th>Concepto</th><th>Valor</th><th>Estado</th></tr></thead>
        <tbody>${cuotasRows}</tbody></table>`
          : ""
      }

      ${
        ultimosPagos.length
          ? `<h3 class="section">Últimos pagos recibidos</h3>
        <table><thead><tr><th>Fecha</th><th>Valor</th><th>Banco</th></tr></thead>
        <tbody>${pagosRows}</tbody></table>`
          : ""
      }

      <div class="motiv">${msg}</div>

      <button class="print-btn" onclick="window.print()">Imprimir / Guardar como PDF</button>
      <p class="print-hint">Al guardar como PDF, activa la opcion "Graficos de fondo" / "Background graphics" en el dialogo de impresion para que se vean el logo y los colores.</p>
    </div>
    <div class="footer">San Marino Lotes · Consultora Natali Taborda</div>
  </div>
</body>
</html>`;
}

export function motivationalMessage(ledger) {
  if (ledger.saldo <= 0) {
    return "\u00a1Felicitaciones! Completaste el pago total de tu lote. Gracias por tu confianza y compromiso con San Marino Lotes.";
  }
  if (ledger.cuotasEnMora.length > 0) {
    return "Sabemos que a veces los pagos se atrasan. Ponerte al d\u00eda hoy protege tu inversi\u00f3n y evita contratiempos m\u00e1s adelante. Estamos para acompa\u00f1arte en el proceso, \u00a1t\u00fa puedes ponerte al d\u00eda!";
  }
  return "\u00a1Vas muy bien! Cada cuota que pagas te acerca m\u00e1s a ser due\u00f1o total de tu lote. Sigue as\u00ed de juicioso con tus pagos.";
}

// Merge original plan payments with app-added payments, then allocate each peso
// FIFO into cuotas in chronological order (oldest unpaid cuota first) so every
// payment is tied to the specific installment(s) it covers.
export function computeLedger(lote, extraPagos, allData) {
  const info = allData[lote];
  const pagos = [...(info.pagos_registrados || []), ...(extraPagos || [])]
    .filter((p) => p.valor)
    .sort((a, b) => (a.fecha_pago || "").localeCompare(b.fecha_pago || ""));

  const totalPagado = pagos.reduce((s, p) => s + (Number(p.valor) || 0), 0);
  const valorNegocio =
    info.valor_negocio || info.cuotas_plan.reduce((s, c) => s + (Number(c.valor) || 0), 0);
  const saldo = Math.max(valorNegocio - totalPagado, 0);
  const avance = valorNegocio ? Math.min((totalPagado / valorNegocio) * 100, 100) : 0;

  const hoy = todayISO();

  // FIFO allocation: walk cuotas in plan order, draining totalPagado into each.
  // Si ya pagó el valor total del negocio (p. ej. con descuento por pronto pago),
  // todas las cuotas quedan pagadas aunque el plan original sumara más.
  const pagoCompleto = valorNegocio > 0 && totalPagado >= valorNegocio;
  let restante = totalPagado;
  const cuotas = info.cuotas_plan.map((c) => {
    const valorCuota = Number(c.valor) || 0;
    const montoPagado = pagoCompleto ? valorCuota : Math.min(Math.max(restante, 0), valorCuota);
    restante -= montoPagado;
    const saldoCuota = valorCuota - montoPagado;
    let estado = "pendiente";
    if (saldoCuota <= 0) estado = "pagada";
    else if (montoPagado > 0) estado = "parcial";

    let diasMora = 0;
    let enMora = false;
    if (estado !== "pagada" && c.fecha_esperada && c.fecha_esperada < hoy) {
      const dias = Math.floor((new Date(hoy) - new Date(c.fecha_esperada)) / 86400000);
      if (dias > 0) {
        diasMora = dias;
        enMora = true;
      }
    }

    return { ...c, montoPagado, saldoCuota, estado, enMora, diasMora };
  });

  const proxima = cuotas.find((c) => c.estado !== "pagada") || null;
  const cuotasEnMora = cuotas.filter((c) => c.enMora);
  const montoEnMora = cuotasEnMora.reduce((s, c) => s + c.saldoCuota, 0);
  const diasMoraMax = cuotasEnMora.reduce((m, c) => Math.max(m, c.diasMora), 0);

  // Tag which payments went toward mora-catchup vs which cuota each payment
  // primarily closed, for display: walk pagos in order re-simulating the fill.
  let acumulado = 0;
  const pagosConCuota = pagos.map((p) => {
    const inicioAcum = acumulado;
    acumulado += Number(p.valor) || 0;
    // find first cuota this payment starts filling
    let run = 0;
    let cuotaConcepto = null;
    for (const c of info.cuotas_plan) {
      const cVal = Number(c.valor) || 0;
      if (inicioAcum < run + cVal) {
        cuotaConcepto = c.concepto;
        break;
      }
      run += cVal;
    }
    return { ...p, cuotaAplicada: cuotaConcepto };
  });

  return {
    pagos: pagosConCuota,
    totalPagado,
    valorNegocio,
    saldo,
    avance,
    cuotas,
    proxima,
    cuotasEnMora,
    montoEnMora,
    diasMoraMax,
  };
}

export function ProgressStamp({ avance, loteNum }) {
  const pct = Math.round(avance);
  return (
    <div className="cdp-stamp" aria-hidden="true">
      <svg viewBox="0 0 120 120" className="cdp-stamp-ring">
        <circle cx="60" cy="60" r="52" className="cdp-stamp-ring-bg" />
        <circle
          cx="60"
          cy="60"
          r="52"
          className="cdp-stamp-ring-fg"
          strokeDasharray={`${(pct / 100) * 326.7} 326.7`}
        />
      </svg>
      <div className="cdp-stamp-text">
        <span className="cdp-stamp-pct">{pct}%</span>
        <span className="cdp-stamp-label">LOTE {loteNum}</span>
      </div>
    </div>
  );
}
