import React, { useMemo, useState } from "react";
import { AlertCircle, ChevronRight } from "lucide-react";
import { formatCOP, formatFecha, computeLedger } from "./ledger.jsx";

function pct(parte, total) {
  return total > 0 ? (parte / total) * 100 : 0;
}

function fmtPct(v) {
  return `${v.toLocaleString("es-CO", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;
}

const ORDENES = {
  lote: { label: "Lote", fn: (a, b) => a.num - b.num || a.lote.localeCompare(b.lote) },
  avance: { label: "Avance", fn: (a, b) => b.avance - a.avance },
  saldo: { label: "Saldo", fn: (a, b) => b.saldo - a.saldo },
  mora: { label: "Mora", fn: (a, b) => b.montoEnMora - a.montoEnMora || b.diasMoraMax - a.diasMoraMax },
};

export default function Dashboard({ allLotesData, extraPagos, onOpenLote }) {
  const [orden, setOrden] = useState("lote");

  const { filas, tot } = useMemo(() => {
    const filas = Object.keys(allLotesData).map((lote) => {
      const info = allLotesData[lote];
      const led = computeLedger(lote, extraPagos[lote] || [], allLotesData);
      return {
        lote,
        num: parseInt(lote.replace(/\D/g, ""), 10) || 0,
        cliente: info.cliente,
        valorNegocio: led.valorNegocio,
        totalPagado: led.totalPagado,
        saldo: led.saldo,
        avance: led.avance,
        cuotasEnMora: led.cuotasEnMora.length,
        montoEnMora: led.montoEnMora,
        diasMoraMax: led.diasMoraMax,
        moraDesde: led.cuotasEnMora[0]?.fecha_esperada || null,
      };
    });
    const tot = filas.reduce(
      (t, f) => {
        t.negocio += f.valorNegocio;
        t.pagado += Math.min(f.totalPagado, f.valorNegocio);
        t.saldo += f.saldo;
        t.mora += f.montoEnMora;
        if (f.montoEnMora > 0) t.clientesMora += 1;
        if (f.saldo <= 0) t.pagados += 1;
        return t;
      },
      { negocio: 0, pagado: 0, saldo: 0, mora: 0, clientesMora: 0, pagados: 0 }
    );
    tot.clientes = filas.length;
    return { filas, tot };
  }, [allLotesData, extraPagos]);

  const enMora = useMemo(() => filas.filter((f) => f.montoEnMora > 0).sort(ORDENES.mora.fn), [filas]);
  const ordenadas = useMemo(() => [...filas].sort(ORDENES[orden].fn), [filas, orden]);

  const pctRecaudado = pct(tot.pagado, tot.negocio);
  const pctPendiente = pct(tot.saldo, tot.negocio);
  const pctMoraSaldo = pct(tot.mora, tot.saldo);
  const pctClientesMora = pct(tot.clientesMora, tot.clientes);
  const alDia = tot.clientes - tot.clientesMora;

  return (
    <main className="cdp-main cdp-dash">
      <div className="cdp-dash-head">
        <h2>Resumen de cartera</h2>
        <span className="cdp-dash-sub">
          {tot.clientes} lotes · valor total de negocios {formatCOP(tot.negocio)}
        </span>
      </div>

      {/* ---------- Cifras principales ---------- */}
      <div className="cdp-kpis">
        <div className="cdp-kpi">
          <div className="cdp-card-label">Recaudado</div>
          <div className="cdp-kpi-value moss">{formatCOP(tot.pagado)}</div>
          <div className="cdp-kpi-pct">{fmtPct(pctRecaudado)} del total</div>
        </div>
        <div className="cdp-kpi">
          <div className="cdp-card-label">Por recaudar</div>
          <div className="cdp-kpi-value">{formatCOP(tot.saldo)}</div>
          <div className="cdp-kpi-pct">{fmtPct(pctPendiente)} del total</div>
        </div>
        <div className="cdp-kpi">
          <div className="cdp-card-label">Clientes en mora</div>
          <div className="cdp-kpi-value rust">
            {tot.clientesMora} <span className="cdp-kpi-of">de {tot.clientes}</span>
          </div>
          <div className="cdp-kpi-pct">{fmtPct(pctClientesMora)} de los clientes</div>
        </div>
        <div className="cdp-kpi">
          <div className="cdp-card-label">Valor en mora</div>
          <div className="cdp-kpi-value rust">{formatCOP(tot.mora)}</div>
          <div className="cdp-kpi-pct">{fmtPct(pctMoraSaldo)} de lo que falta por recaudar</div>
        </div>
      </div>

      {/* ---------- Barra recaudado vs pendiente ---------- */}
      <div className="cdp-dash-card">
        <div className="cdp-dash-card-title">Avance de recaudo</div>
        <div
          className="cdp-bigbar"
          role="img"
          aria-label={`Recaudado ${fmtPct(pctRecaudado)}, en mora ${fmtPct(pct(tot.mora, tot.negocio))}, por vencer ${fmtPct(
            pct(tot.saldo - tot.mora, tot.negocio)
          )}`}
        >
          <div
            className="seg pagado"
            style={{ width: `${pctRecaudado}%` }}
            title={`Recaudado: ${formatCOP(tot.pagado)} (${fmtPct(pctRecaudado)})`}
          />
          <div
            className="seg mora"
            style={{ width: `${pct(tot.mora, tot.negocio)}%` }}
            title={`En mora: ${formatCOP(tot.mora)} (${fmtPct(pct(tot.mora, tot.negocio))})`}
          />
          <div
            className="seg pendiente"
            style={{ width: `${pct(tot.saldo - tot.mora, tot.negocio)}%` }}
            title={`Por vencer: ${formatCOP(tot.saldo - tot.mora)} (${fmtPct(pct(tot.saldo - tot.mora, tot.negocio))})`}
          />
        </div>
        <div className="cdp-legend">
          <span>
            <i className="sw pagado" /> Recaudado <b>{formatCOP(tot.pagado)}</b> · {fmtPct(pctRecaudado)}
          </span>
          <span>
            <i className="sw mora" /> Vencido sin pagar <b>{formatCOP(tot.mora)}</b> · {fmtPct(pct(tot.mora, tot.negocio))}
          </span>
          <span>
            <i className="sw pendiente" /> Por vencer <b>{formatCOP(tot.saldo - tot.mora)}</b> ·{" "}
            {fmtPct(pct(tot.saldo - tot.mora, tot.negocio))}
          </span>
        </div>
        <div className="cdp-dash-foot">
          {alDia} cliente{alDia === 1 ? "" : "s"} al día
          {tot.pagados > 0 ? ` · ${tot.pagados} con el lote pagado en su totalidad` : ""}
        </div>
      </div>

      {/* ---------- Clientes en mora ---------- */}
      <div className="cdp-dash-card">
        <div className="cdp-dash-card-title">
          <AlertCircle size={15} color="var(--rust)" /> Clientes en mora ({enMora.length})
        </div>
        {enMora.length === 0 ? (
          <div className="cdp-dash-empty">Ningún cliente en mora. 🎉</div>
        ) : (
          <div className="cdp-dash-tablewrap">
            <table className="cdp-table cdp-dash-table">
              <thead>
                <tr>
                  <th>Lote</th>
                  <th>Cliente</th>
                  <th className="num">Cuotas vencidas</th>
                  <th className="num">Días de atraso</th>
                  <th className="num">Valor en mora</th>
                  <th className="num">% del negocio</th>
                  <th className="num">% de la mora total</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {enMora.map((f) => (
                  <tr key={f.lote} className="clickable" onClick={() => onOpenLote(f.lote)}>
                    <td>{f.lote}</td>
                    <td className="txt">{f.cliente}</td>
                    <td className="num">{f.cuotasEnMora}</td>
                    <td className="num" title={f.moraDesde ? `Desde ${formatFecha(f.moraDesde)}` : ""}>
                      {f.diasMoraMax}
                    </td>
                    <td className="num rust">{formatCOP(f.montoEnMora)}</td>
                    <td className="num">{fmtPct(pct(f.montoEnMora, f.valorNegocio))}</td>
                    <td className="num">{fmtPct(pct(f.montoEnMora, tot.mora))}</td>
                    <td>
                      <ChevronRight size={14} color="var(--ink-soft)" />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={2}>Total</td>
                  <td className="num">{enMora.reduce((s, f) => s + f.cuotasEnMora, 0)}</td>
                  <td></td>
                  <td className="num rust">{formatCOP(tot.mora)}</td>
                  <td className="num">{fmtPct(pct(tot.mora, tot.negocio))}</td>
                  <td className="num">100,0%</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* ---------- Todos los lotes ---------- */}
      <div className="cdp-dash-card">
        <div className="cdp-dash-card-title cdp-dash-title-row">
          <span>Estado de todos los lotes</span>
          <label className="cdp-dash-sort">
            Ordenar por{" "}
            <select value={orden} onChange={(e) => setOrden(e.target.value)}>
              {Object.entries(ORDENES).map(([k, o]) => (
                <option key={k} value={k}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="cdp-dash-tablewrap">
          <table className="cdp-table cdp-dash-table">
            <thead>
              <tr>
                <th>Lote</th>
                <th>Cliente</th>
                <th className="num">Valor negocio</th>
                <th className="num">Pagado</th>
                <th className="num">Saldo</th>
                <th>Avance</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {ordenadas.map((f) => (
                <tr key={f.lote} className="clickable" onClick={() => onOpenLote(f.lote)}>
                  <td>{f.lote}</td>
                  <td className="txt">{f.cliente}</td>
                  <td className="num">{formatCOP(f.valorNegocio)}</td>
                  <td className="num">{formatCOP(f.totalPagado)}</td>
                  <td className="num">{formatCOP(f.saldo)}</td>
                  <td>
                    <div className="cdp-minibar" title={`${fmtPct(f.avance)} pagado`}>
                      <div style={{ width: `${Math.min(f.avance, 100)}%` }} />
                    </div>
                    <span className="cdp-minibar-pct">{Math.round(f.avance)}%</span>
                  </td>
                  <td>
                    {f.saldo <= 0 ? (
                      <span className="cdp-tag pagada">pagado</span>
                    ) : f.montoEnMora > 0 ? (
                      <span className="cdp-tag parcial">mora {f.diasMoraMax}d</span>
                    ) : (
                      <span className="cdp-tag pendiente">al día</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
