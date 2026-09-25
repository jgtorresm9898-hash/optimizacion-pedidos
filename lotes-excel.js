// Lee archivos de Excel con el formato "Control de Pagos" de San Marino
// (una hoja por lote: CLIENTE, NUMERO DEL LOTE, VALOR DEL NEGOCIO,
//  plan de cuotas a la izquierda y pagos recibidos a la derecha).
// Sirve tanto para la plantilla nueva como para las hojas que ya existen.

const SHEETJS_URLS = [
  "https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs",
  "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/+esm",
];

let xlsxPromise = null;
export function cargarSheetJS() {
  if (!xlsxPromise) {
    xlsxPromise = (async () => {
      let lastErr;
      for (const url of SHEETJS_URLS) {
        try {
          const mod = await import(/* @vite-ignore */ url);
          return mod.default && mod.default.read ? mod.default : mod;
        } catch (e) {
          lastErr = e;
        }
      }
      xlsxPromise = null;
      throw new Error("No se pudo cargar el lector de Excel. Revisa tu conexión a internet. " + (lastErr?.message || ""));
    })();
  }
  return xlsxPromise;
}

const pad = (n) => String(n).padStart(2, "0");

function textoFecha(s) {
  const m = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{2,4})\s*$/.exec(s);
  if (!m) return null;
  let [d, mo, y] = [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)];
  if (y < 100) y += 2000;
  else if (y < 1000 && Math.floor(y / 10) === 20) y = 2020 + (y % 10); // "206" -> 2026
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || y < 1900) return null;
  return `${y}-${pad(mo)}-${pad(d)}`;
}

// Convierte la hoja a una matriz; las fechas quedan como {fecha: "YYYY-MM-DD"}
function hojaAMatriz(XLSX, ws) {
  if (!ws || !ws["!ref"]) return [];
  const rango = XLSX.utils.decode_range(ws["!ref"]);
  const filas = [];
  for (let r = rango.s.r; r <= rango.e.r; r++) {
    const fila = [];
    for (let c = 0; c <= rango.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r, c })];
      if (!cell || cell.v === undefined || cell.v === null || cell.v === "") {
        fila.push(null);
      } else if (cell.t === "n" && cell.z && XLSX.SSF.is_date(cell.z)) {
        const p = XLSX.SSF.parse_date_code(cell.v);
        fila.push({ fecha: `${p.y}-${pad(p.m)}-${pad(p.d)}` });
      } else if (cell.t === "d" && cell.v instanceof Date) {
        const d = cell.v;
        fila.push({ fecha: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` });
      } else {
        fila.push(cell.v);
      }
    }
    filas.push(fila);
  }
  return filas;
}

const esNum = (v) => typeof v === "number" && isFinite(v);
const fechaDe = (v) => (v && typeof v === "object" && v.fecha ? v.fecha : typeof v === "string" ? textoFecha(v) : null);
const texto = (v) => (typeof v === "string" ? v.trim() : v === null || v === undefined ? "" : String(v));
const soloDigitos = (s) => {
  const d = String(s).replace(/[^\d]/g, "");
  return d ? parseInt(d, 10) : null;
};
const limpiar = (s) => String(s).replace(/\s+/g, " ").trim();

// Valor de una etiqueta "CLIENTE: Juan" o "CLIENTE:" | "Juan" (celda de la derecha)
function valorEtiqueta(fila, j, t) {
  const despues = t.split(":").slice(1).join(":").trim();
  if (despues) return despues;
  for (let k = j + 1; k < fila.length; k++) {
    if (fila[k] !== null && texto(fila[k]) !== "") return fila[k];
  }
  return null;
}

export function leerHoja(XLSX, ws, nombreHoja) {
  const filas = hojaAMatriz(XLSX, ws);
  let cliente = null, numero = null, vnEncabezado = null, vnResumen = null, recaudoResumen = null;
  let telefono = null, correo = null;
  let planHdr = null, pagosHdr = null;

  filas.forEach((fila, i) => {
    fila.forEach((c, j) => {
      if (typeof c !== "string") return;
      const t = c.trim();
      const T = t.toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      if (T.startsWith("CLIENTE")  && T.includes(":")) cliente = texto(valorEtiqueta(fila, j, t));
      else if (T.startsWith("NUMERO DEL LOTE")) {
        const v = valorEtiqueta(fila, j, t);
        numero = v === null ? null : soloDigitos(v);
      } else if (T.startsWith("VALOR DEL NEGOCIO") && T.includes("$")) vnEncabezado = soloDigitos(t.split("$")[1]);
      else if (T.startsWith("VALOR DEL NEGOCIO") && T.includes(":")) {
        const v = valorEtiqueta(fila, j, t);
        vnEncabezado = esNum(v) ? v : v === null ? null : soloDigitos(v);
      } else if (T === "VALOR DEL NEGOCIO" && filas[i + 1]) {
        if (esNum(filas[i + 1][j])) vnResumen = filas[i + 1][j];
        if (esNum(filas[i + 1][j + 1])) recaudoResumen = filas[i + 1][j + 1];
      } else if (T.startsWith("TELEFONO") || T.startsWith("WHATSAPP")) {
        const v = valorEtiqueta(fila, j, t);
        if (v !== null) telefono = String(v).replace(/\D/g, "") || null;
      } else if (T.startsWith("CORREO")) {
        const v = valorEtiqueta(fila, j, t);
        if (v !== null && String(v).includes("@")) correo = String(v).trim();
      } else if ((T === "FECHA DE PAGO" || T === "FECHA ESPERADA") && !planHdr) planHdr = [i, j];
      else if (T === "FECHA" && !pagosHdr && texto(fila[j + 1]).toUpperCase() === "VALOR") pagosHdr = [i, j];
    });
  });

  const avisos = [];
  const cuotas = [];
  let totalPlanHoja = null;
  if (planHdr) {
    const [i0, j0] = planHdr;
    for (const fila of filas.slice(i0 + 1)) {
      const con = fila[j0 + 1];
      const val = fila[j0 + 2];
      if (typeof con === "string" && con.trim().toUpperCase() === "TOTAL") {
        totalPlanHoja = esNum(val) ? val : null;
        break;
      }
      if (!esNum(val) || val <= 0) continue;
      cuotas.push({
        fecha_esperada: fechaDe(fila[j0]),
        concepto: limpiar(con || "CUOTA"),
        valor: Math.round(val * 100) / 100,
      });
    }
  } else avisos.push("No encontré la tabla del plan de cuotas (columna 'FECHA DE PAGO').");

  const pagos = [];
  let totalPagosHoja = null;
  if (pagosHdr) {
    const [i1, j1] = pagosHdr;
    for (const fila of filas.slice(i1 + 1)) {
      const f = fila[j1];
      if (typeof f === "string" && f.trim().toUpperCase() === "TOTAL") {
        totalPagosHoja = esNum(fila[j1 + 1]) ? fila[j1 + 1] : null;
        break;
      }
      const fecha = fechaDe(f);
      const val = fila[j1 + 1];
      if (!fecha || !esNum(val) || val <= 0) continue;
      const comp = fila[j1 + 2];
      const banco = fila[j1 + 3];
      pagos.push({
        fecha_pago: fecha,
        valor: Math.round(val * 100) / 100,
        comprobante: comp === null || comp === undefined || fechaDe(comp) ? null : texto(comp) || null,
        banco: banco === null || banco === undefined || fechaDe(banco) ? null : texto(banco) || null,
      });
    }
  }

  const sumaPlan = cuotas.reduce((s, c) => s + c.valor, 0);
  const sumaPagos = pagos.reduce((s, p) => s + p.valor, 0);
  const valorNegocio = vnResumen || vnEncabezado || sumaPlan || null;

  if (!numero) {
    const n = soloDigitos(nombreHoja || "");
    if (n) numero = n;
    else avisos.push("Falta el número del lote.");
  }
  if (!cliente) avisos.push("Falta el nombre del cliente.");
  if (cuotas.length === 0) avisos.push("El plan de cuotas está vacío.");
  if (valorNegocio && sumaPlan && Math.abs(sumaPlan - valorNegocio) > 1 && sumaPagos < valorNegocio)
    avisos.push(`Las cuotas suman ${sumaPlan.toLocaleString("es-CO")} y el valor del negocio es ${valorNegocio.toLocaleString("es-CO")}.`);
  if (totalPagosHoja !== null && Math.abs(totalPagosHoja - sumaPagos) > 1)
    avisos.push(`Los pagos leídos suman ${sumaPagos.toLocaleString("es-CO")} pero el TOTAL de la hoja dice ${totalPagosHoja.toLocaleString("es-CO")}.`);
  if (cuotas.some((c) => !c.fecha_esperada)) avisos.push("Hay cuotas sin fecha.");

  return {
    hoja: nombreHoja,
    lote: numero ? `LOTE ${numero}` : null,
    cliente: cliente ? limpiar(cliente) : null,
    valorNegocio,
    telefono,
    correo,
    cuotas,
    pagos,
    sumaPlan,
    sumaPagos,
    avisos,
  };
}

// Devuelve un lote por cada hoja que tenga plan de cuotas
export async function leerArchivoExcel(file) {
  const XLSX = await cargarSheetJS();
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { cellNF: true, cellDates: false });
  const lotes = [];
  for (const nombre of wb.SheetNames) {
    const ws = wb.Sheets[nombre];
    const l = leerHoja(XLSX, ws, nombre);
    if (l.cuotas.length === 0 && !l.cliente) continue; // hojas de instrucciones u otras
    lotes.push(l);
  }
  return lotes;
}
