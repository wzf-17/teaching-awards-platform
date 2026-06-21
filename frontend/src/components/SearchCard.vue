<template>
  <div class="card">
    <button class="close" v-if="closable" @click="$emit('close')" title="关闭查询卡片">×</button>

    <div class="header">
      <div>
        <p class="cardEyebrow">Analysis Card {{ index + 1 }}</p>
        <h3 class="title">查询框 {{ index + 1 }}</h3>
      </div>
    </div>

    <div class="controlsGrid">
      <label class="field">
        <span class="fieldLabel">省份</span>
        <select v-model="province" class="sel">
          <option v-for="opt in provinceOptionsSafe" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>

      <label class="field">
        <span class="fieldLabel">年份</span>
        <select v-model="year" class="sel">
          <option v-for="y in yearOptionsSafe" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>

      <label class="field">
        <span class="fieldLabel">分析类型</span>
        <select v-model="qtype" class="sel">
          <option v-for="opt in qtypeOptionsSafe" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <button class="btn" @click="doSearch" :disabled="card.loading">
        {{ card.loading ? "查询中…" : "查询数据" }}
      </button>
    </div>

    <div class="resultMeta">
      <button class="download" @click="download" :disabled="!canDownload" title="下载当前结果">
        <svg class="downloadIcon" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3v10m0 0l4-4m-4 4L8 9M5 19h14"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span>下载</span>
      </button>
    </div>

    <div class="display">
      <div v-if="card.error" class="error">{{ card.error }}</div>

      <template v-else-if="isWordcloud">
        <div class="wordcloudWrap">
          <img
            :src="wordcloudUrl(props.card?.payload?.year, props.card?.payload?.province)"
            alt="词云图"
            class="wordcloudImg"
            @error="onWordcloudError"
          />
          <div v-if="wordcloudError" class="errorText">{{ wordcloudError }}</div>
        </div>
      </template>

      <template v-else-if="card.view === 'chart' && card.chartData">
        <ChartCanvas
          ref="chartRef"
          :type="card.chartType || 'bar'"
          :data="card.chartData"
          :options="card.chartOptions"
          :height="280"
          :titleText="card.exportTitle"
          backgroundColor="#f8fafc"
        />
      </template>

      <template v-else-if="isThemeTable && card.view === 'table' && card.tableData">
        <div class="themeTableWrap">
          <table class="themeTbl">
            <colgroup>
              <col style="width: 78px" />
              <col style="width: 130px" />
              <col style="width: auto" />
              <col style="width: 70px" />
              <col style="width: 86px" />
            </colgroup>

            <thead>
              <tr>
                <th>层次</th>
                <th>类别</th>
                <th>内容</th>
                <th>奖数</th>
                <th>占比(%)</th>
              </tr>
            </thead>

            <tbody>
              <tr
                v-for="(r, i) in themeRows"
                :key="i"
                :class="{
                  subtotal: !!r._isSubtotal || r['条目'] === '小计',
                  total:
                    !!r._isTotal ||
                    String(r['条目'] || '').includes('合计') ||
                    String(r['层次'] || '') === '合计',
                }"
              >
                <td
                  v-if="themeSpan && themeSpan.spanLevel[i] > 0"
                  :rowspan="themeSpan.spanLevel[i]"
                  class="levelCell"
                >
                  {{ r["层次"] }}
                </td>

                <td
                  v-if="themeSpan && themeSpan.spanCat[i] > 0"
                  :rowspan="themeSpan.spanCat[i]"
                  class="catCell"
                >
                  {{ r["类别"] }}
                </td>
                <td v-else-if="!r['类别']" class="catCell"></td>

                <td class="itemCell">{{ r["条目"] }}</td>
                <td class="numCell">{{ r["奖数"] }}</td>
                <td class="pctCell pctBarCell">
                  <div class="pctTrack">
                    <div class="pctBar" :style="{ width: pctWidth(r['占比(%)']) }"></div>
                  </div>
                  <div class="pctText">{{ formatPct(r["占比(%)"]) }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <template v-else-if="card.view === 'table' && card.tableData">
        <div class="tableWrap">
          <table class="tbl">
            <thead>
              <tr>
                <th v-for="c in card.tableData.columns" :key="c">{{ c }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in card.tableData.rows" :key="i">
                <td v-for="c in card.tableData.columns" :key="c">{{ r[c] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <template v-else-if="card.raw">
        <pre class="pre">{{ pretty(card.raw) }}</pre>
      </template>

      <div v-else class="placeholder">
        <div class="placeholderText">选择年份和分析类型后发起查询，结果会在这里展示。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from "vue"
import ChartCanvas from "./ChartCanvas.vue"

const API_BASE = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE || "http://127.0.0.1:5000")

function pctWidth(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return "0%"
  const clamped = Math.max(0, Math.min(100, n))
  return `${clamped}%`
}

function formatPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v ?? "")
  return n.toFixed(2)
}

const props = defineProps({
  index: { type: Number, required: true },
  card: { type: Object, required: true },
  closable: { type: Boolean, default: true },
  provinceOptions: { type: Array, default: () => [] },
  provinceMeta: { type: Array, default: () => [] },
  yearOptions: { type: Array, default: () => [] },
  qtypeOptions: { type: Array, default: () => [] },
  defaultProvince: { type: String, default: "浙江省" },
})

const emit = defineEmits(["search", "close"])

const fallbackYearOptions = [2021, 2025]
const fallbackQtypeOptions = [
  { label: "地理位置分布", value: "geo_dist" },
  { label: "学科类型分布", value: "discipline" },
  { label: "学校层次分布", value: "org_level" },
  { label: "研究主题情况表", value: "theme_table" },
  { label: "获奖成果完成模式情况", value: "completion_mode" },
  { label: "完成人员合作情况表", value: "collab" },
  { label: "研究主题词云图", value: "wordcloud" },
]

const provinceOptionsSafe = computed(() =>
  props.provinceOptions?.length ? props.provinceOptions : [{ value: props.defaultProvince, label: props.defaultProvince }]
)
const province = ref(props.card.payload?.province ?? props.defaultProvince)
const currentProvinceMeta = computed(() =>
  (props.provinceMeta || []).find((item) => item?.value === province.value) || null
)
const yearOptionsSafe = computed(() => currentProvinceMeta.value?.years?.length ? currentProvinceMeta.value.years : (props.yearOptions?.length ? props.yearOptions : fallbackYearOptions))
const qtypeOptionsSafe = computed(() => currentProvinceMeta.value?.qtypes?.length ? currentProvinceMeta.value.qtypes : (props.qtypeOptions?.length ? props.qtypeOptions : fallbackQtypeOptions))
const year = ref(props.card.payload?.year ?? yearOptionsSafe.value[yearOptionsSafe.value.length - 1] ?? 2025)
const qtype = ref(props.card.payload?.qtype ?? qtypeOptionsSafe.value[0]?.value ?? "geo_dist")

watch(
  () => props.card.payload,
  (p) => {
    if (!p) return
    province.value = p.province ?? province.value
    year.value = p.year ?? year.value
    qtype.value = p.qtype ?? qtype.value
  },
  { deep: true }
)

watch(
  yearOptionsSafe,
  (years) => {
    if (!Array.isArray(years) || !years.length) return
    if (!years.includes(year.value)) year.value = years[years.length - 1]
  },
  { deep: true }
)

watch(
  qtypeOptionsSafe,
  (options) => {
    if (!Array.isArray(options) || !options.length) return
    if (!options.some((opt) => opt.value === qtype.value)) qtype.value = options[0].value
  },
  { deep: true }
)

watch(
  province,
  (nextProvince, prevProvince) => {
    if (!nextProvince || nextProvince === prevProvince) return
    const nextYears = yearOptionsSafe.value
    if (Array.isArray(nextYears) && nextYears.length && !nextYears.includes(year.value)) {
      year.value = nextYears[nextYears.length - 1]
    }
    const nextQtypes = qtypeOptionsSafe.value
    if (Array.isArray(nextQtypes) && nextQtypes.length) {
      qtype.value = nextQtypes[0].value
    }
  }
)

const chartRef = ref(null)
const wordcloudError = ref("")
const isWordcloud = computed(() => props.card?.payload?.qtype === "wordcloud")
const isThemeTable = computed(() => props.card?.payload?.qtype === "theme_table")
const canDownload = computed(() => {
  const p = props.card.payload || {}
  if (p.qtype === "wordcloud") return Boolean(p.year)
  return Boolean(props.card.view === "chart" || props.card.tableData || props.card.raw)
})

function wordcloudUrl(y, p = province.value) {
  const yy = Number(y)
  if (!yy) return ""
  return `${API_BASE}/api/v2/wordcloud/${yy}?province=${encodeURIComponent(p || props.defaultProvince)}`
}

function onWordcloudError() {
  wordcloudError.value =
    "词云图加载失败：请确认后端接口可访问 " + `${API_BASE}/api/v2/wordcloud/2021`
}

function doSearch() {
  wordcloudError.value = ""
  emit("search", {
    province: String(province.value || props.defaultProvince),
    year: Number(year.value),
    qtype: String(qtype.value),
    keyword: "",
  })
}

function pretty(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function cleanText(v) {
  if (v == null) return ""
  let s = String(v)
  s = s.replace(/[\u3000\s]+/g, "").trim()
  s = s.replace(/^小\s*计$/, "小计")
  s = s.replace(/^合\s*计$/, "合计")
  s = s.replace(/（/g, "(").replace(/）/g, ")")
  return s
}

function normLevel2025(v) {
  const s = cleanText(v)
  if (!s) return ""
  if (s.includes("战略")) return "战略性"
  if (s.includes("结构")) return "结构性"
  if (s.includes("制度")) return "制度性"
  if (s.includes("机制")) return "机制性"
  return s
}

const THEME_CANON = {}

function canon(s) {
  const t = cleanText(s)
  return THEME_CANON[t] || t
}

function normalizeThemeRow(yearVal, r) {
  const y = Number(yearVal)

  let level = canon(r["层次"] ?? r.level_name ?? "")
  let cat = canon(r["类别"] ?? r.category ?? "")
  let item = canon(r["条目"] ?? r.item ?? r["内容"] ?? "")

  const awardCnt = r["奖数"] ?? r.award_count ?? ""
  const pct = r["占比(%)"] ?? r.pct ?? ""

  if (y === 2021) {
    if (item.includes("/") && item.startsWith("人才培养战略/")) {
      level = "战略性"
      cat = "人才培养战略"
      item = canon(item.replace(/^人才培养战略\//, ""))
    }

    if (level === "人才培养战略" || level.includes("人才培养战略")) {
      level = "战略性"
      if (cat && !item) item = cat
      cat = "人才培养战略"
    }
  }

  level = normLevel2025(level)

  return {
    ...r,
    层次: level,
    类别: cat,
    条目: item,
    奖数: awardCnt,
    "占比(%)": pct,
  }
}

const themeRows = computed(() => {
  const rows = props.card?.tableData?.rows || []
  const y = props.card?.payload?.year
  return rows.map((r) => normalizeThemeRow(y, r))
})

function buildRowSpans(rows) {
  const spanLevel = Array(rows.length).fill(0)
  const spanCat = Array(rows.length).fill(0)

  for (let i = 0; i < rows.length; ) {
    const v = rows[i]["层次"]
    let j = i
    while (j < rows.length && rows[j]["层次"] === v) j++
    spanLevel[i] = j - i
    i = j
  }

  for (let i = 0; i < rows.length; ) {
    const level = rows[i]["层次"]
    let end = i
    while (end < rows.length && rows[end]["层次"] === level) end++

    for (let k = i; k < end; ) {
      const cat = rows[k]["类别"]
      let j = k
      while (j < end && rows[j]["类别"] === cat) j++

      if (cat) spanCat[k] = j - k
      k = j
    }
    i = end
  }

  return { spanLevel, spanCat }
}

const themeSpan = computed(() => {
  if (!isThemeTable.value) return null
  const rows = themeRows.value
  if (!rows.length) return null
  return buildRowSpans(rows)
})

function exportThemeTableCsv() {
  const columns = ["层次", "类别", "内容", "奖数", "占比(%)"]
  const rows = themeRows.value.map((row) => ({
    层次: row["层次"] ?? "",
    类别: row["类别"] ?? "",
    内容: row["条目"] ?? row["内容"] ?? "",
    奖数: row["奖数"] ?? "",
    "占比(%)": row["占比(%)"] ?? "",
  }))
  return toCsv(columns, rows)
}

function themeTableExportRows() {
  return themeRows.value.map((row) => ({
    层次: row["层次"] ?? "",
    类别: row["类别"] ?? "",
    内容: row["条目"] ?? row["内容"] ?? "",
    奖数: row["奖数"] ?? "",
    "占比(%)": row["占比(%)"] ?? "",
  }))
}

function escapeXml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;")
}

function xmlCell(value, styleId = "cell", type = "String") {
  return `<Cell ss:StyleID="${styleId}"><Data ss:Type="${type}">${escapeXml(value)}</Data></Cell>`
}

function exportThemeTableExcelXml() {
  const rows = themeTableExportRows()
  const headerCells = ["层次", "类别", "内容", "奖数", "占比(%)"]
    .map((label) => xmlCell(label, "header"))
    .join("")

  const bodyRows = rows
    .map((row) => {
      const award = Number(row["奖数"])
      const pct = Number(row["占比(%)"])
      return [
        xmlCell(row["层次"]),
        xmlCell(row["类别"]),
        xmlCell(row["内容"]),
        xmlCell(Number.isFinite(award) ? award : row["奖数"], "cell", Number.isFinite(award) ? "Number" : "String"),
        xmlCell(Number.isFinite(pct) ? pct : row["占比(%)"], "cell", Number.isFinite(pct) ? "Number" : "String"),
      ].join("")
    })
    .map((cells) => `<Row>${cells}</Row>`)
    .join("")

  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Styles>
    <Style ss:ID="Default" ss:Name="Normal">
      <Alignment ss:Vertical="Center"/>
      <Font ss:FontName="等线" ss:Size="11"/>
    </Style>
    <Style ss:ID="header">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:FontName="等线" ss:Size="11" ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
      </Borders>
    </Style>
    <Style ss:ID="cell">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:FontName="等线" ss:Size="11"/>
    </Style>
  </Styles>
  <Worksheet ss:Name="${escapeXml(exportFileBase(props.card.payload || {}))}">
    <Table>
      <Column ss:Width="90"/>
      <Column ss:Width="170"/>
      <Column ss:Width="250"/>
      <Column ss:Width="80"/>
      <Column ss:Width="90"/>
      <Row ss:Height="22">${headerCells}</Row>
      ${bodyRows}
    </Table>
  </Worksheet>
</Workbook>`
}

async function download() {
  const p = props.card.payload || {}
  const filenameBase = exportFileBase(p)

  if (p.qtype === "wordcloud") {
    const y = p.year || year.value
    if (!y) {
      alert("请先选择年份再查询")
      return
    }
    const url = wordcloudUrl(y)
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error("下载失败")
      const blob = await res.blob()
      const objUrl = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = objUrl
      a.download = `${filenameBase}.png`
      a.click()
      URL.revokeObjectURL(objUrl)
    } catch {
      alert("词云图下载失败：请确认后端 /api/v2/wordcloud/<year> 可用")
    }
    return
  }

  if (props.card.view === "chart" && chartRef.value) {
    chartRef.value.downloadPng(`${filenameBase}.png`)
    return
  }
  if (props.card.view === "table" && props.card.tableData) {
    if (isThemeTable.value) {
      const xml = exportThemeTableExcelXml()
      downloadText(`${filenameBase}.xml`, xml, "application/xml;charset=utf-8;")
      return
    }
    const csv = toCsv(props.card.tableData.columns, props.card.tableData.rows)
    downloadText(`${filenameBase}.csv`, csv, "text/csv;charset=utf-8;")
    return
  }
  if (props.card.raw) {
    downloadText(`${filenameBase}.json`, pretty(props.card.raw), "application/json;charset=utf-8;")
    return
  }
  alert("没有可下载内容（请先查询）")
}

function exportFileBase(p) {
  const provinceLabel = p.province || province.value || props.defaultProvince || ""
  const provinceShort = String(provinceLabel).replace(/省$/, "").replace(/市$/, "")
  const y = p.year || year.value || ""
  const t = p.qtype || qtype.value || "result"
  const map = {
    geo_dist: "地理位置分布",
    discipline: "学科类型分布",
    org_level: "学校层次分布",
    theme_table: "研究主题情况表",
    completion_mode: "获奖成果完成模式情况",
    collab: "完成人员合作情况表",
    wordcloud: "研究主题词云图",
  }
  const tZh = map[t] || t
  return `${provinceShort}${y}年_${tZh}`
}

function toCsv(columns, rows) {
  const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`
  const head = columns.map(esc).join(",")
  const body = rows.map((r) => columns.map((c) => esc(r[c])).join(",")).join("\n")
  return `${head}\n${body}\n`
}

function downloadText(filename, text, mime) {
  const needsBom = String(mime).includes("text/csv")
  const content = needsBom ? [`\uFEFF`, text] : [text]
  const blob = new Blob(content, { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.card {
  position: relative;
  width: 440px;
  min-height: 620px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.88));
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
  flex: 0 0 auto;
}

.close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 12px;
  background: rgba(241, 245, 249, 0.9);
  color: #475569;
  cursor: pointer;
  font-size: 18px;
}

.header {
  padding-right: 48px;
}

.cardEyebrow {
  margin: 0 0 6px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.title {
  margin: 0;
  color: #10233d;
  font-size: 24px;
  font-weight: 800;
}

.controlsGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.field {
  display: grid;
  gap: 8px;
}

.fieldLabel {
  color: #52637a;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.sel,
.input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.94);
  padding: 12px 14px;
  color: #10233d;
  font-size: 14px;
  outline: none;
}

.sel:focus,
.input:focus {
  border-color: rgba(15, 118, 110, 0.42);
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08);
}

.btn {
  border: none;
  border-radius: 16px;
  padding: 0 18px;
  min-height: 48px;
  grid-column: 1 / -1;
  background: linear-gradient(135deg, #10233d, #1e3a5f);
  color: #ffffff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
}

.btn:disabled,
.download:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.resultMeta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
}

.download {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  padding: 10px 14px;
  color: #10233d;
  cursor: pointer;
  font-weight: 700;
}

.downloadIcon {
  width: 16px;
  height: 16px;
}

.display {
  margin-top: 16px;
  min-height: 360px;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(241, 245, 249, 0.8));
  padding: 16px;
  overflow: auto;
}

.placeholder {
  display: grid;
  place-items: center;
  min-height: 320px;
  text-align: center;
}

.placeholderText {
  max-width: 280px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.error,
.errorText {
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.7;
}

.pre {
  margin: 0;
  color: #10233d;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.tableWrap,
.themeTableWrap {
  overflow: auto;
}

.tbl,
.themeTbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.tbl th,
.tbl td,
.themeTbl th,
.themeTbl td {
  border: 1px solid rgba(226, 232, 240, 0.96);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.tbl thead th,
.themeTbl thead th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #10233d;
  font-weight: 800;
  z-index: 1;
}

.wordcloudWrap {
  padding: 6px;
}

.wordcloudImg {
  width: 100%;
  height: auto;
  border-radius: 16px;
  background: #ffffff;
  display: block;
}

.themeTableWrap {
  min-height: 360px;
  max-height: 540px;
}

.themeTbl {
  table-layout: auto;
}

.levelCell,
.catCell {
  font-weight: 800;
  text-align: center;
  white-space: normal;
}

.itemCell {
  white-space: normal;
  overflow-wrap: anywhere;
}

.numCell,
.pctCell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.pctBarCell {
  min-width: 108px;
}

.pctTrack {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  overflow: hidden;
  margin-bottom: 8px;
}

.pctBar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0f766e, #14b8a6);
}

.pctText {
  color: #334155;
}

.themeTbl tr.subtotal td {
  font-weight: 900;
  background: rgba(248, 250, 252, 0.96);
}

.themeTbl tr.total td {
  font-weight: 900;
  background: rgba(241, 245, 249, 0.96);
}

@media (max-width: 768px) {
  .card {
    width: min(92vw, 440px);
    min-height: 560px;
  }

  .controlsGrid {
    grid-template-columns: 1fr;
  }

  .resultMeta {
    align-items: start;
    flex-direction: column;
  }
}
</style>
