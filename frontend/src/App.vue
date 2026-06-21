<template>
  <div class="page">
    <template v-if="activePage === 'home'">
      <div class="heroGlow heroGlow--left"></div>
      <div class="heroGlow heroGlow--right"></div>

      <header class="hero">
        <div class="heroCopy">
          <p class="eyebrow">Teaching Achievement Awards</p>
          <h1 class="heroTitle">高等教育教学成果奖数据分析平台</h1>
          <p class="heroLead">
            本平台聚焦高等教育教学成果奖数据的整合、展示与分析，提供成果检索、可视化展示、多维对比分析和智能问答等功能，帮助用户更加直观、高效地了解教学成果奖的分布特征、学科结构与发展趋势。
          </p>
        </div>
      </header>

      <section class="section featureEntrySection">
        <button class="featureEntryCard" type="button" @click="openMaterialLibrary">
          <span class="featureEntryMeta">Resource Library</span>
          <span class="featureEntryTitle">申报材料链接库</span>
          <span class="featureEntryText">按省份、年份和奖项等级检索成果申报材料汇总链接</span>
          <span class="featureEntryAction">进入功能页</span>
        </button>
      </section>

      <section class="section">
      <div class="sectionHeader">
        <div>
          <p class="sectionEyebrow">Query Workspace</p>
          <h2 class="sectionTitle">多维查询工作台</h2>
          <p class="sectionText">
            每张卡片独立承载一个分析任务。你可以并排放置不同年份、不同类型的查询结果，再按需发起对比。
          </p>
        </div>
      </div>

      <div class="workspaceBoard">
        <div class="workspaceRail">
          <template v-for="item in rowItems" :key="item.key">
            <SearchCard
              v-if="item.kind === 'card'"
              :key="`${item.card.id}_${provinceOptions.length}`"
              :index="item.index"
              :card="item.card"
              :closable="cards.length > 1"
              :province-options="provinceOptions"
              :province-meta="metaOptions?.provinces || []"
              :year-options="yearOptionsFor(item.card)"
              :qtype-options="qtypeOptionsFor(item.card)"
              :default-province="defaultProvince"
              @search="(payload) => onSearch(item.card.id, payload)"
              @close="removeCard(item.card.id)"
            />

            <div v-else class="compareSlot">
              <button
                class="compareBtn"
                :disabled="!canComparePair(item.leftId, item.rightId)"
                @click="doComparePair(item.leftId, item.rightId)"
              >
                对比
              </button>
              <div class="compareConnector"></div>
              <div class="compareHint" v-if="pairHint(item.leftId, item.rightId)">
                {{ pairHint(item.leftId, item.rightId) }}
              </div>
            </div>
          </template>

          <div class="addRailWrap">
            <button class="add add--rail" @click="addCard">
              <span class="addIcon">＋</span>
              <span>新增查询框</span>
            </button>
            <div class="addRailHint">支持同类型对比</div>
          </div>
        </div>
      </div>
      </section>

      <section class="section">
      <div class="sectionHeader">
        <div>
          <p class="sectionEyebrow">Comparison</p>
          <h2 class="sectionTitle">对比结果</h2>
          <p class="sectionText">
            选择相同类型的查询结果后，可以在这里查看不同年份或不同对象之间的结构差异。
          </p>
        </div>
      </div>

      <div class="analysisLayout">
        <div class="analysisMain">
          <div ref="comparePanelRef" class="comparePanel">
            <div class="panelHeader">
              <div>
                <p class="panelEyebrow">Comparison Board</p>
                <div class="panelTitle">
                  <template v-if="compare.active">
                    {{ leftTitle }} <span class="panelVs">vs</span> {{ rightTitle }}
                  </template>
                  <template v-else>等待选择对比对象</template>
                </div>
              </div>

              <button
                v-if="compare.active"
                class="iconBtn iconBtn--ghost"
                @click="cancelCompare"
                title="关闭对比"
              >
                ×
              </button>
            </div>

            <div v-if="compare.active" class="panelBody">
              <div v-if="isWordcloudCompare" class="wordcloudCompareGrid">
                <article class="wordcloudCard">
                  <div class="wordcloudYear">{{ leftCard?.payload?.year }} 年词云</div>
                  <img
                    class="wordcloudImage"
                    :src="wordcloudUrl(leftCard?.payload?.year, leftCard?.payload?.province)"
                    :alt="`${leftCard?.payload?.year} 年词云图`"
                  />
                </article>

                <article class="wordcloudCard">
                  <div class="wordcloudYear">{{ rightCard?.payload?.year }} 年词云</div>
                  <img
                    class="wordcloudImage"
                    :src="wordcloudUrl(rightCard?.payload?.year, rightCard?.payload?.province)"
                    :alt="`${rightCard?.payload?.year} 年词云图`"
                  />
                </article>
              </div>

              <div v-else-if="compareChartData" class="compareChartWrap">
                <button
                  class="compareDownloadBtn"
                  @click="downloadCompare"
                  :disabled="!compareChartData"
                  title="下载对比图 PNG"
                >
                  <svg class="compareDownloadIcon" viewBox="0 0 24 24" aria-hidden="true">
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

                <ChartCanvas
                  ref="compareChartRef"
                  :type="'bar'"
                  :data="compareChartData"
                  :options="compareChartOptions"
                  :height="340"
                  :titleText="compareExportTitle"
                  backgroundColor="#f8fafc"
                />
              </div>

              <div v-else class="panelEmpty">
                两边都需要生成同类型图表结果后，系统才能绘制结构对比图。
              </div>
            </div>

            <div v-else class="panelEmpty panelEmpty--idle">
              从上方任意两张相邻卡片发起对比。当前支持同类型图表对比，以及词云图的双图并排查看。
            </div>
          </div>
        </div>
      </div>
      </section>

      <section class="section">
      <div class="sectionHeader">
        <div>
          <p class="sectionEyebrow">AI Copilot</p>
          <h2 class="sectionTitle">智能问答</h2>
          <p class="sectionText">
            智能问答支持结合当前查询结果生成分析说明、趋势解读和文字总结，也可回答教学成果奖相关问题。
          </p>
        </div>
      </div>

      <div class="analysisLayout">
        <div class="analysisMain">
          <div class="chatPanel">
            <div class="chatToolbar">
              <button
                class="chatClear"
                @click="clearChat"
                :disabled="chatLoading || (chatMessages.length === 0 && !chatSessionId)"
              >
                清空对话
              </button>
            </div>

            <div ref="chatBodyRef" class="chatBody">
              <div
                v-for="(m, idx) in chatMessages"
                :key="idx"
                :class="['chatMsg', `chatMsg--${m.role}`]"
              >
                <div class="chatRole">{{ m.role === "user" ? "我" : "助手" }}</div>

                <div v-if="m.role === 'assistant' && m.thinking && !m.text" class="thinkingRow">
                  <span class="thinkingDot"></span>
                  <span class="thinkingDot"></span>
                  <span class="thinkingDot"></span>
                  <span class="thinkingText">思考中</span>
                </div>

                <pre v-else class="chatText">{{ m.text }}</pre>

                <div v-if="m.role === 'assistant'" class="aiNotice">
                  本回答由 AI 基于平台数据生成，仅供参考。
                </div>
              </div>
            </div>

            <div class="chatInputRow">
              <input
                v-model="chatInput"
                class="chatInput"
                placeholder="请输入需要分析或解答的问题"
                @keydown.enter="sendChat"
              />
              <button class="chatSend" @click="sendChat" :disabled="chatLoading || !chatInput.trim()">
                {{ chatLoading ? "思考中…" : "发送" }}
              </button>
            </div>
          </div>
        </div>
      </div>
      </section>
    </template>

    <section v-else class="section materialPage">
      <button class="backBtn" type="button" @click="backHome">返回首页</button>
      <div class="materialShell">
        <p class="sectionEyebrow">Resource Library</p>
        <h2 class="sectionTitle">申报材料链接库</h2>
        <p class="sectionText">
          支持按省份、年份和奖项等级检索已收录的成果申报材料汇总链接
        </p>

        <div class="materialFilters">
          <label class="materialField">
            <span class="materialLabel">省份</span>
            <select v-model="materialFilters.province" class="materialSelect">
              <option v-for="opt in provinceOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>

          <label class="materialField">
            <span class="materialLabel">年份</span>
            <select v-model="materialFilters.year" class="materialSelect">
              <option v-for="year in materialYearOptions" :key="year" :value="year">{{ year }}</option>
            </select>
          </label>

          <label class="materialField">
            <span class="materialLabel">奖项等级</span>
            <select v-model="materialFilters.awardLevel" class="materialSelect">
              <option v-for="level in materialAwardLevels" :key="level" :value="level">{{ level }}</option>
            </select>
          </label>

          <button class="materialSearchBtn" type="button" @click="fetchMaterialLinks" :disabled="materialLoading">
            {{ materialLoading ? "查询中..." : "查询链接" }}
          </button>
        </div>

        <div class="materialResultArea">
          <div class="materialResultHeader">
            <div>
              <p class="materialResultEyebrow">Result Preview</p>
              <h3 class="materialResultTitle">申报材料汇总链接</h3>
            </div>
            <span class="materialResultBadge">{{ materialQueried ? `${materialResults.length} 条` : "待查询" }}</span>
          </div>

          <div v-if="materialLoading" class="materialState">正在查询申报材料链接...</div>
          <div v-else-if="materialError" class="materialState materialState--error">{{ materialError }}</div>
          <div v-else-if="materialQueried && materialResults.length === 0" class="materialState">
            暂无已收录的申报材料链接
          </div>

          <div v-else-if="materialResults.length" class="materialTableWrap">
            <table class="materialTable">
              <thead>
                <tr>
                  <th>成果名称</th>
                  <th>对应链接</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in materialResults" :key="`${item.award_name}-${item.material_url}`">
                  <td class="materialTitleCell">{{ item.award_name }}</td>
                  <td>
                    <div class="materialLinkCell">
                      <span class="materialLinkText">{{ item.material_url }}</span>
                      <div class="materialLinkActions">
                        <button class="materialMiniBtn" type="button" @click="copyMaterialLink(item.material_url)">
                          复制链接
                        </button>
                        <button
                          class="materialMiniBtn materialMiniBtn--solid"
                          type="button"
                          @click="openMaterialLink(item.material_url)"
                        >
                          打开链接
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="materialState">请选择条件后点击“查询链接”</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from "vue"
import axios from "axios"

import SearchCard from "./components/SearchCard.vue"
import ChartCanvas from "./components/ChartCanvas.vue"

// ===================== 后端地址/路径 =====================
const API_BASE = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE || "http://127.0.0.1:5000")
const API_QUERY_PATH = "/api/v2/dist"
const API_THEME_TABLE_PATH = "/api/v2/theme-table"
const API_WORDCLOUD_PATH = "/api/v2/wordcloud"
const API_META_OPTIONS_PATH = "/api/meta/options"
const API_CHAT_PATH = "/chat/v2"
const API_MATERIAL_LINKS_PATH = "/api/material-links"

const chartPalette = ["#0f766e", "#ea580c", "#2563eb", "#7c3aed", "#ca8a04", "#dc2626"]
const piePalette = [
  "#0f766e",
  "#14b8a6",
  "#f97316",
  "#fb7185",
  "#2563eb",
  "#7c3aed",
  "#eab308",
  "#84cc16",
]

const fallbackQtypeOptions = [
  { label: "地理位置分布", value: "geo_dist" },
  { label: "学科类型分布", value: "discipline" },
  { label: "学校层次分布", value: "org_level" },
  { label: "获奖等级分布", value: "award_level" },
  { label: "研究主题情况表", value: "theme_table" },
  { label: "完成模式情况", value: "completion_mode" },
  { label: "完成人员合作情况", value: "collab" },
  { label: "研究主题词云图", value: "wordcloud" },
]

const metaOptions = ref(null)
const defaultProvince = ref("浙江省")
const activePage = ref("home")
const materialFilters = reactive({
  province: "浙江省",
  year: 2025,
  awardLevel: "全部",
})
const materialYearOptions = [2025, 2021]
const materialAwardLevels = ["全部", "特等奖", "一等奖", "二等奖"]
const materialResults = ref([])
const materialLoading = ref(false)
const materialError = ref("")
const materialQueried = ref(false)

const provinceOptions = computed(() => metaOptions.value?.provinces?.map((item) => ({
  value: item.value,
  label: item.label,
})) || [{ value: defaultProvince.value, label: defaultProvince.value }])

const provinceMetaMap = computed(() => {
  const map = new Map()
  for (const item of metaOptions.value?.provinces || []) {
    map.set(item.value, item)
  }
  return map
})

function provinceOfCard(card) {
  return card?.payload?.province || defaultProvince.value
}

function yearOptionsFor(card) {
  return provinceMetaMap.value.get(provinceOfCard(card))?.years || [2021, 2025]
}

function qtypeOptionsFor(card) {
  return provinceMetaMap.value.get(provinceOfCard(card))?.qtypes || fallbackQtypeOptions
}

async function loadMetaOptions() {
  try {
    const res = await axios.get(`${API_BASE}${API_META_OPTIONS_PATH}`)
    metaOptions.value = res.data
    defaultProvince.value = res.data?.defaultProvince || defaultProvince.value
  } catch (e) {
    console.warn("failed to load province meta options", e)
  }
}

function openMaterialLibrary() {
  activePage.value = "materials"
}

function backHome() {
  activePage.value = "home"
}

async function fetchMaterialLinks() {
  materialLoading.value = true
  materialError.value = ""
  materialQueried.value = true

  try {
    const res = await axios.get(`${API_BASE}${API_MATERIAL_LINKS_PATH}`, {
      params: {
        province: materialFilters.province,
        year: Number(materialFilters.year),
        award_level: materialFilters.awardLevel,
      },
    })
    materialResults.value = Array.isArray(res.data?.items) ? res.data.items : []
  } catch (e) {
    materialResults.value = []
    materialError.value = e?.response?.data?.error || e?.message || "查询失败，请稍后重试"
  } finally {
    materialLoading.value = false
  }
}

async function copyMaterialLink(url) {
  if (!url) return
  try {
    await navigator.clipboard?.writeText(url)
  } catch (_) {}
}

function openMaterialLink(url) {
  if (!url) return
  window.open(url, "_blank", "noopener,noreferrer")
}

// ===================== 全局聊天（不依赖查询框） =====================
const chatMessages = ref([]) // [{ role, text, thinking?, streaming? }]
const chatInput = ref("")
const chatLoading = ref(false)
const chatSessionId = ref("") // 后端返回的 session_id（多轮用）
const chatBodyRef = ref(null)
const comparePanelRef = ref(null)

function scrollChatToBottom(behavior = "auto") {
  const el = chatBodyRef.value
  if (!el) return
  el.scrollTo({
    top: el.scrollHeight,
    behavior,
  })
}

async function syncChatViewport() {
  await nextTick()
  scrollChatToBottom()

  await new Promise((resolve) => {
    requestAnimationFrame(() => {
      scrollChatToBottom()
      resolve()
    })
  })
}

async function scrollCompareIntoView() {
  await nextTick()

  await new Promise((resolve) => {
    requestAnimationFrame(() => {
      comparePanelRef.value?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      })
      resolve()
    })
  })
}

async function sendChat() {
  const q = chatInput.value.trim()
  if (!q || chatLoading.value) return

  chatLoading.value = true
  chatMessages.value.push({ role: "user", text: q })
  chatInput.value = ""

  const assistantMsg = {
    role: "assistant",
    text: "",
    thinking: true,
    streaming: true,
  }
  chatMessages.value.push(assistantMsg)
  await syncChatViewport()

  try {
    const payload = {
      question: q,
      query_contexts: buildChatContexts(),
    }
    if (chatSessionId.value) payload.session_id = chatSessionId.value

    const res = await fetch(`${API_BASE}${API_CHAT_PATH}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      let errText = `HTTP ${res.status}`
      try {
        const errJson = await res.json()
        errText = errJson?.error || errText
      } catch (_) {}
      throw new Error(errText)
    }

    if (!res.body) {
      throw new Error("浏览器不支持流式读取")
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder("utf-8")
    let buffer = ""

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const blocks = buffer.split("\n\n")
      buffer = blocks.pop() || ""

      for (const block of blocks) {
        const line = block
          .split("\n")
          .find((x) => x.trim().startsWith("data:"))

        if (!line) continue

        const jsonStr = line.replace(/^data:\s*/, "").trim()
        if (!jsonStr) continue

        let evt = null
        try {
          evt = JSON.parse(jsonStr)
        } catch (_) {
          continue
        }

        if (evt.type === "meta" && evt.session_id) {
          chatSessionId.value = evt.session_id
        }

        if (evt.type === "start") {
          assistantMsg.thinking = true
          await syncChatViewport()
        }

        if (evt.type === "delta") {
          assistantMsg.thinking = false
          assistantMsg.streaming = true
          assistantMsg.text += evt.content || ""
          await syncChatViewport()
        }

        if (evt.type === "done") {
          assistantMsg.thinking = false
          assistantMsg.streaming = false
          if (!assistantMsg.text.trim()) {
            assistantMsg.text = evt.answer || "（无回答）"
          }
          await syncChatViewport()
        }

        if (evt.type === "error") {
          assistantMsg.thinking = false
          assistantMsg.streaming = false
          assistantMsg.text = `请求失败：${evt.error || "未知错误"}`
          await syncChatViewport()
        }
      }
    }

    assistantMsg.text = assistantMsg.text
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/^\s*[*-]\s+/gm, "")
      .replace(/^#+\s+/gm, "")
      .trim()

    if (!assistantMsg.text) {
      assistantMsg.text = "（无回答）"
    }
    await syncChatViewport()
  } catch (e) {
    assistantMsg.thinking = false
    assistantMsg.streaming = false
    assistantMsg.text = `请求失败：${e?.message || "未知错误"}`
    await syncChatViewport()
  } finally {
    chatLoading.value = false
    await syncChatViewport()
  }
}

async function clearChat() {
  if (chatLoading.value) return
  try {
    if (chatSessionId.value) {
      // 如果后端实现了 /chat/clear，就会把服务端 session 也清掉；没实现也没关系
      await axios.post(`${API_BASE}/chat/clear`, { session_id: chatSessionId.value })
    }
  } catch (e) {
    // 忽略后端未实现/失败，依然允许前端清空
  } finally {
    chatMessages.value = []
    chatSessionId.value = ""
    chatInput.value = ""
    await syncChatViewport()
  }
}

// ===================== 工具：文件名安全化 =====================
function safeFileName(name) {
  return String(name || "export")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
}

// ===================== 下载对比图 =====================
const compareChartRef = ref(null)
function downloadCompare() {
  if (!compareChartData.value) return

  const comp = compareChartRef.value
  if (!comp) return

  const el = comp.$el || comp
  const canvas = el?.querySelector?.("canvas")

  if (!canvas) {
    console.warn("找不到 canvas，无法下载。请确认 ChartCanvas 内部渲染的是 <canvas>.")
    return
  }

  const dataUrl = canvas.toDataURL("image/png")
  const a = document.createElement("a")
  a.href = dataUrl
  a.download = safeFileName(compareExportTitle.value || "对比图") + ".png"
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function wordcloudUrl(year, province = defaultProvince.value) {
  return `${API_BASE}${API_WORDCLOUD_PATH}/${year}?province=${encodeURIComponent(province || defaultProvince.value)}`
}

function newId() {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function buildChatContexts() {
  return cards
    .filter((card) => card.payload && (card.view || card.raw))
    .slice()
    .sort((a, b) => (b.searchedAt || 0) - (a.searchedAt || 0))
    .slice(0, 5)
    .map((card) => ({
      province: card.payload?.province || "",
      qtype: card.payload?.qtype || "",
      year: card.payload?.year || "",
      keyword: card.payload?.keyword || "",
      title: card.exportTitle || card.title || "",
      view: card.view || "",
      searchedAt: card.searchedAt || 0,
    }))
}

// ===================== 查询卡片状态 =====================
const cards = reactive([makeEmptyCard()])

function makeEmptyCard() {
  return {
    id: newId(),
    loading: false,
    error: "",
    payload: null,

    raw: null,

    view: "", // 'chart' | 'table' | 'json' | 'wordcloud'
    resultType: "",

    chartType: "bar", // 单框图类型：bar / pie
    chartData: null,
    chartOptions: null,

    tableData: null,
    title: "",

    exportTitle: "",
    searchedAt: 0,
  }
}

// 对比状态：由“相邻对比按钮”决定 left/right
const compare = reactive({
  leftId: "",
  rightId: "",
  active: false,
})

// ---------- 用户可读标题 ----------
function qtypeZh(qtype) {
  const map = {
    geo_dist: "地理位置",
    discipline: "学科类型",
    org_level: "学校层次",
    org: "完成单位",
    theme_table: "研究主题情况表",
    completion_mode: "完成模式",
    collab: "完成人员合作情况表",
    wordcloud: "研究主题词云图",
  }
  return map[qtype] || qtype || "数据结果"
}

function provinceShortName(province) {
  const name = String(province || defaultProvince.value || "").trim()
  if (!name) return ""
  return name.replace(/省$/, "").replace(/市$/, "")
}

function exportTitleOf(payload) {
  const province = provinceShortName(payload.province)
  if (payload.qtype === "theme_table") return `${province}${payload.year}年教学成果奖研究主题情况表`
  if (payload.qtype === "wordcloud") return `${province}${payload.year}年教学成果奖研究主题词云图`
  if (payload.qtype === "completion_mode") return `${province}${payload.year}年教学成果奖完成模式情况`
  return `${province}${payload.year}年教学成果奖${qtypeZh(payload.qtype)}分布`
}

function cloneData(data) {
  try {
    if (typeof structuredClone === "function") return structuredClone(data)
    return JSON.parse(JSON.stringify(data))
  } catch (_) {
    return data
  }
}

function decorateChartData(data, chartType) {
  const next = cloneData(data)
  if (!next?.datasets?.length) return next

  next.datasets = next.datasets.map((dataset, index) => {
    if (chartType === "pie") {
      return {
        ...dataset,
        backgroundColor: next.labels.map((_, i) => piePalette[i % piePalette.length]),
        borderColor: "#ffffff",
        borderWidth: 2,
      }
    }

    const color = chartPalette[index % chartPalette.length]
    return {
      ...dataset,
      backgroundColor: color,
      borderColor: color,
      borderRadius: 10,
      borderSkipped: false,
      maxBarThickness: 24,
    }
  })

  return next
}

// ---------- 新增/删除卡片 ----------
function addCard() {
  cards.push(makeEmptyCard())
}

function removeCard(id) {
  const idx = cards.findIndex((c) => c.id === id)
  if (idx !== -1) cards.splice(idx, 1)

  // 删除影响对比对象则关闭对比
  if (compare.leftId === id || compare.rightId === id) cancelCompare()
}

// ---------- 查询逻辑（每卡片独立） ----------
async function onSearch(cardId, payload) {
  const card = cards.find((c) => c.id === cardId)
  if (!card) return

  card.loading = true
  card.error = ""
  card.raw = null
  card.view = ""
  card.resultType = ""
  card.chartType = "bar"
  card.chartData = null
  card.chartOptions = null
  card.tableData = null
  card.title = ""
  card.payload = payload
  card.exportTitle = exportTitleOf(payload)
  card.searchedAt = Date.now()

  try {
    // ✅ 分流0：词云图（不请求 /api/dist；图片由 <img src="/api/wordcloud/<year>"> 获取）
    if (payload.qtype === "wordcloud") {
      card.view = "wordcloud"
      card.title = `研究主题词云图（${payload.year})`
      card.resultType = "wordcloud"
      return
    }

    // ✅ 分流1：研究主题表走 /api/theme-table，其余走 /api/dist
    let res
    if (payload.qtype === "theme_table") {
      res = await axios.get(`${API_BASE}${API_THEME_TABLE_PATH}`, {
        params: { year: payload.year, province: payload.province },
      })
    } else {
      res = await axios.get(`${API_BASE}${API_QUERY_PATH}`, { params: payload })
    }

    card.raw = res.data
    card.resultType = payload.qtype

    // ✅ theme_table：强制按表格展示（不尝试画图）
    if (payload.qtype === "theme_table") {
      const table = normalizeTable(res.data)
      if (table) {
        card.view = "table"
        card.tableData = table
        card.title = `研究主题情况表（${payload.year}）`
      } else {
        card.view = "json"
        card.title = `研究主题情况表（${payload.year}）`
      }
      return
    }

    // 规范化为图表数据
    const chart = normalizeChart(res.data)
    if (chart) {
      card.view = "chart"
      card.title = chart.title || `查询框 ${cards.indexOf(card) + 1}`

      const pieTypes = new Set(["discipline", "org_level", "collab"])
      card.chartType = pieTypes.has(payload.qtype) ? "pie" : "bar"
      card.chartData = decorateChartData(chart.data, card.chartType)

      if (card.chartType === "bar") {
        card.chartOptions = {
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: { enabled: true },
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: "rgba(148, 163, 184, 0.18)" },
            },
            y: {
              ticks: { autoSkip: false, color: "#475569" },
              grid: { display: false },
            },
          },
        }
      } else {
        card.chartOptions = {
          plugins: {
            legend: {
              display: true,
              position: "right",
              labels: {
                color: "#334155",
                usePointStyle: true,
                boxWidth: 10,
              },
            },
            tooltip: { enabled: true },
          },
        }
      }

      return
    }

    // 规范化为表格
    const table = normalizeTable(res.data)
    if (table) {
      card.view = "table"
      card.tableData = table
      card.title = `查询框 ${cards.indexOf(card) + 1}`
      return
    }

    // 否则显示 JSON
    card.view = "json"
    card.title = `查询框 ${cards.indexOf(card) + 1}`
  } catch (e) {
    const msg =
      e?.response?.data?.error ||
      e?.response?.data?.message ||
      e?.message ||
      "请求失败：请确认后端接口可用 / 参数正确"
    card.error = `请求失败：${msg}`
    card.raw = e?.response?.data || null
  } finally {
    card.loading = false
  }
}

// ---------- 解析：把后端返回转成 Chart.js data ----------
function normalizeChart(data) {
  // 后端直接给 chart（/api/dist）
  if (data?.chart?.labels && data?.chart?.datasets) {
    return {
      title: data?.title || "",
      data: data.chart,
    }
  }

  // {labels:[], values:[]}
  if (Array.isArray(data?.labels) && Array.isArray(data?.values)) {
    return {
      title: data?.title || "",
      data: {
        labels: data.labels,
        datasets: [{ label: data?.seriesName || "数量", data: data.values }],
      },
    }
  }

  // 数组对象 [{name,count}] 或 [{label,value}]
  if (Array.isArray(data)) {
    const labels = []
    const values = []
    for (const r of data) {
      const label = r?.label ?? r?.name ?? r?.key
      const value = r?.value ?? r?.count ?? r?.num
      if (label != null && value != null) {
        labels.push(String(label))
        values.push(Number(value))
      }
    }
    if (labels.length) {
      return {
        title: "",
        data: {
          labels,
          datasets: [{ label: "数量", data: values }],
        },
      }
    }
  }

  return null
}

// ---------- 解析：表格 ----------
function normalizeTable(data) {
  if (data?.columns && data?.rows && Array.isArray(data.columns) && Array.isArray(data.rows)) {
    return { columns: data.columns, rows: data.rows }
  }
  if (Array.isArray(data) && data.length && typeof data[0] === "object") {
    const columns = Object.keys(data[0])
    return { columns, rows: data }
  }
  return null
}

// ===================== 相邻对比按钮逻辑 =====================

// 每两个相邻卡片之间插一个“对比”
const rowItems = computed(() => {
  const items = []
  cards.forEach((card, idx) => {
    items.push({ kind: "card", key: card.id, card, index: idx })
    if (idx < cards.length - 1) {
      items.push({
        kind: "compare",
        key: `cmp_${card.id}_${cards[idx + 1].id}`,
        leftId: card.id,
        rightId: cards[idx + 1].id,
      })
    }
  })
  return items
})

function canComparePair(leftId, rightId) {
  const L = cards.find((c) => c.id === leftId)
  const R = cards.find((c) => c.id === rightId)
  if (!L || !R) return false
  if (!L.payload || !R.payload) return false

  // ✅ 表格：明确不支持对比
  if (L.payload.qtype === "theme_table" || R.payload.qtype === "theme_table") {
    return false
  }

  // ✅ 词云图：两边都选 wordcloud 才支持对比
  const Lwc = L.payload.qtype === "wordcloud"
  const Rwc = R.payload.qtype === "wordcloud"
  if (Lwc || Rwc) return Lwc && Rwc

  // ✅ 图表：保持原逻辑
  if (!L.chartData || !R.chartData) return false
  if (L.payload.qtype !== R.payload.qtype) return false
  return true
}

function pairHint(leftId, rightId) {
  const L = cards.find((c) => c.id === leftId)
  const R = cards.find((c) => c.id === rightId)
  if (!L?.payload || !R?.payload) return "两边都先查询"

  if (L.payload.qtype === "theme_table" || R.payload.qtype === "theme_table") return "表格不支持对比"

  const Lwc = L.payload.qtype === "wordcloud"
  const Rwc = R.payload.qtype === "wordcloud"
  if (Lwc || Rwc) return Lwc && Rwc ? "" : "两边都需选择词云图"

  if (L.payload.qtype !== R.payload.qtype) return "需同类型"
  if (!L.chartData || !R.chartData) return "需图表结果"
  return ""
}

function doComparePair(leftId, rightId) {
  if (!canComparePair(leftId, rightId)) return
  compare.leftId = leftId
  compare.rightId = rightId
  compare.active = true
  scrollCompareIntoView()
}

function cancelCompare() {
  compare.active = false
  compare.leftId = ""
  compare.rightId = ""
}

// ---------- 对比图数据 ----------
const leftCard = computed(() => cards.find((c) => c.id === compare.leftId) || null)
const rightCard = computed(() => cards.find((c) => c.id === compare.rightId) || null)

const leftTitle = computed(() => leftCard.value?.exportTitle || "左侧")
const rightTitle = computed(() => rightCard.value?.exportTitle || "右侧")

const isWordcloudCompare = computed(() => {
  const L = leftCard.value?.payload
  const R = rightCard.value?.payload
  if (!L || !R) return false
  return L.qtype === "wordcloud" && R.qtype === "wordcloud"
})

const compareExportTitle = computed(() => {
  const L = leftCard.value?.payload
  const R = rightCard.value?.payload
  if (!L || !R) return ""
  if (L.qtype === "wordcloud" && R.qtype === "wordcloud") return ""
  const leftProvince = provinceShortName(L.province)
  const rightProvince = provinceShortName(R.province)
  return `${leftProvince}${L.year} vs ${rightProvince}${R.year} ${qtypeZh(L.qtype)}分布对比`
})

const compareChartData = computed(() => {
  if (isWordcloudCompare.value) return null

  const Lc = leftCard.value
  const Rc = rightCard.value
  if (!Lc?.chartData || !Rc?.chartData) return null

  const L = extractDist(Lc.chartData)
  const R = extractDist(Rc.chartData)
  if (!L || !R) return null

  const labelSet = new Set([...L.labels, ...R.labels])
  const labels = Array.from(labelSet)

  const leftMap = new Map(L.labels.map((lab, i) => [lab, L.values[i]]))
  const rightMap = new Map(R.labels.map((lab, i) => [lab, R.values[i]]))

  const leftValues = labels.map((lab) => leftMap.get(lab) ?? 0)
  const rightValues = labels.map((lab) => rightMap.get(lab) ?? 0)

  return {
    labels,
    datasets: [
      {
        label: `${Lc.payload.year}年`,
        data: leftValues,
        backgroundColor: "#0f766e",
        borderColor: "#0f766e",
        borderRadius: 10,
        borderSkipped: false,
        maxBarThickness: 22,
      },
      {
        label: `${Rc.payload.year}年`,
        data: rightValues,
        backgroundColor: "#f97316",
        borderColor: "#f97316",
        borderRadius: 10,
        borderSkipped: false,
        maxBarThickness: 22,
      },
    ],
  }
})

const compareChartOptions = computed(() => ({
  indexAxis: "y",
  plugins: {
    legend: {
      display: true,
      labels: {
        color: "#334155",
        usePointStyle: true,
        boxWidth: 10,
      },
    },
    tooltip: { enabled: true },
  },
  scales: {
    x: {
      beginAtZero: true,
      grid: { color: "rgba(148, 163, 184, 0.16)" },
      ticks: { color: "#475569" },
    },
    y: {
      ticks: { autoSkip: false, color: "#334155" },
      grid: { display: false },
    },
  },
}))

function extractDist(chartData) {
  if (!chartData?.labels || !chartData?.datasets?.length) return null
  const labels = chartData.labels.map(String)
  const values = (chartData.datasets[0]?.data || []).map((v) => Number(v))
  if (!labels.length) return null
  return { labels, values }
}

watch(
  () => cards.map((c) => c.id),
  (ids) => {
    if (!compare.active) return
    if (!ids.includes(compare.leftId) || !ids.includes(compare.rightId)) cancelCompare()
  }
)

onMounted(() => {
  loadMetaOptions()
})
</script>

<style scoped>
.page {
  padding: 16px;
  background: #f3f4f6;
  min-height: 100vh;
}

.row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  overflow-x: auto;
  padding-bottom: 10px;
}

.add {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  border: 1px dashed #9ca3af;
  background: white;
  cursor: pointer;
  font-size: 26px;
  line-height: 1;
  flex: 0 0 auto;
}

/* ================== 全局问答 ================== */
.chatPanel {
  width: 100%;
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 12px;
}

.chatHeaderRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.chatHeader {
  font-weight: 900;
}

.chatClear {
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 8px 12px;
  background: #fafafa;
  cursor: pointer;
}
.chatClear:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.chatBody {
  max-height: 260px;
  overflow: auto;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 10px;
  background: #fafafa;
}

.chatHint {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.chatMsg {
  margin-bottom: 10px;
}

.chatRole {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.chatText {
  margin: 0;
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
}

.chatInputRow {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.chatInput {
  flex: 1;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 10px 12px;
  outline: none;
}

.chatSend {
  border: 1px solid #111827;
  border-radius: 12px;
  padding: 10px 14px;
  background: #111827;
  color: #fff;
  cursor: pointer;
}

.chatSend:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 相邻对比按钮插槽 */
.compareSlot {
  width: 90px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding-top: 40px;
}

.compareBtn {
  border: 1px solid #111827;
  border-radius: 12px;
  padding: 10px 14px;
  background: #111827;
  color: #fff;
  cursor: pointer;
}
.compareBtn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.compareHint {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  line-height: 1.2;
}

/* ================== 对比面板 ================== */
.comparePanel {
  margin-top: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  padding: 12px;

  position: relative;
  padding-bottom: 62px;
}

.panelHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panelTitle {
  font-weight: 900;
  display: flex;
  align-items: center;
  gap: 10px;
}

.panelEmpty {
  color: #6b7280;
  border: 1px dashed #d1d5db;
  border-radius: 12px;
  padding: 10px;
}

/* ================== 统一图标按钮（用于对比框：X / 下载） ================== */
.iconBtn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  cursor: pointer;
  border: 1px solid transparent;
  padding: 0;
  line-height: 1;
}

.iconBtn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.iconBtn--ghost {
  background: transparent;
  color: #6b7280;
  border-color: transparent;
}

.iconBtn--ghost:hover {
  background: #f3f4f6;
  color: #111827;
}

.iconBtn--solid {
  background: #111827;
  color: #fff;
  border-color: #111827;
}

.iconBtn--solid:hover {
  background: #000;
}

.iconSvg {
  width: 18px;
  height: 18px;
  display: block;
}

/* ✅ 对比面板下载按钮：右下角 */
.compareDownload {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 10;
}

/* ✅ 给 canvas 留出右/下边距，避免按钮遮挡刻度数字 */
.comparePanel :deep(canvas) {
  margin-right: 14px;
  margin-bottom: 14px;
}
.thinkingRow {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  color: #6b7280;
  margin-bottom: 6px;
}

.thinkingDot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #9ca3af;
  display: inline-block;
  animation: thinkingBounce 1.2s infinite ease-in-out;
}

.thinkingDot:nth-child(1) { animation-delay: 0s; }
.thinkingDot:nth-child(2) { animation-delay: 0.15s; }
.thinkingDot:nth-child(3) { animation-delay: 0.3s; }

.thinkingText {
  margin-left: 4px;
  font-size: 13px;
}

@keyframes thinkingBounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.45;
  }
  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}

.aiNotice {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 10px;
}

.page {
  --bg: #f4f7fb;
  --surface: rgba(255, 255, 255, 0.86);
  --surface-strong: #ffffff;
  --border: rgba(148, 163, 184, 0.2);
  --text-main: #10233d;
  --text-muted: #52637a;
  --teal: #0f766e;
  --orange: #f97316;
  position: relative;
  min-height: 100vh;
  padding: 40px 28px 56px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.14), transparent 28%),
    radial-gradient(circle at top right, rgba(249, 115, 22, 0.14), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, #eef3f9 100%);
}

.heroGlow {
  position: absolute;
  border-radius: 999px;
  filter: blur(12px);
  pointer-events: none;
}

.heroGlow--left {
  top: 72px;
  left: -80px;
  width: 240px;
  height: 240px;
  background: rgba(15, 118, 110, 0.1);
}

.heroGlow--right {
  top: 120px;
  right: -60px;
  width: 220px;
  height: 220px;
  background: rgba(249, 115, 22, 0.12);
}

.hero,
.section {
  position: relative;
  z-index: 1;
  width: min(1440px, 100%);
  margin: 0 auto;
}

.hero {
  display: block;
  margin-bottom: 32px;
}

.heroCopy,
.workspaceBoard,
.comparePanel,
.chatPanel,
.supportCard {
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
}

.heroCopy {
  position: relative;
  min-height: 420px;
  margin: 0 auto;
  padding: 72px 88px;
  border-radius: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  text-align: center;
  border: 1px solid rgba(175, 235, 255, 0.24);
  background:
    linear-gradient(135deg, rgba(5, 16, 34, 0.76), rgba(8, 30, 56, 0.56)),
    url("./assets/hero-tech-bg.svg");
  background-position: center;
  background-size: cover;
  box-shadow:
    0 28px 70px rgba(8, 22, 46, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.heroCopy::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 18%, rgba(63, 223, 255, 0.16), transparent 24%),
    radial-gradient(circle at 86% 24%, rgba(113, 255, 221, 0.14), transparent 22%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0));
  pointer-events: none;
}

.eyebrow,
.sectionEyebrow,
.panelEyebrow {
  margin: 0 0 8px;
  color: var(--teal);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.heroCopy .eyebrow {
  position: relative;
  z-index: 1;
  margin-bottom: 14px;
  color: #97f3ff;
  text-shadow: 0 0 22px rgba(52, 235, 255, 0.26);
}

.heroTitle {
  position: relative;
  z-index: 1;
  margin: 0;
  max-width: none;
  white-space: nowrap;
  word-break: keep-all;
  color: #f7fbff;
  font-size: clamp(38px, 4.6vw, 54px);
  line-height: 1.12;
  font-weight: 800;
  letter-spacing: -0.03em;
  text-shadow: 0 10px 32px rgba(5, 16, 34, 0.34);
}

.heroLead {
  position: relative;
  z-index: 1;
  margin: 24px 0 0;
  max-width: 920px;
  color: rgba(236, 246, 255, 0.9);
  font-size: 18px;
  line-height: 1.95;
  text-shadow: 0 8px 24px rgba(5, 16, 34, 0.2);
}

.section {
  margin-bottom: 26px;
}

.featureEntrySection {
  margin-top: -6px;
}

.featureEntryCard {
  width: 100%;
  display: grid;
  justify-items: start;
  gap: 8px;
  padding: 24px 28px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(239, 253, 250, 0.9)),
    var(--surface);
  box-shadow: 0 18px 46px rgba(15, 23, 42, 0.08);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.featureEntryCard:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.36);
  box-shadow: 0 24px 58px rgba(15, 118, 110, 0.14);
}

.featureEntryMeta {
  color: var(--teal);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.featureEntryTitle {
  color: var(--text-main);
  font-size: clamp(22px, 2.4vw, 30px);
  font-weight: 800;
  line-height: 1.25;
}

.featureEntryText {
  color: var(--text-muted);
  font-size: 15px;
  line-height: 1.75;
}

.featureEntryAction {
  margin-top: 6px;
  color: #0f766e;
  font-size: 14px;
  font-weight: 800;
}

.materialPage {
  min-height: 70vh;
  padding-top: 36px;
}

.materialShell {
  margin-top: 18px;
  padding: 36px;
  border: 1px solid var(--border);
  border-radius: 28px;
  background: var(--surface);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
}

.materialFilters {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr)) auto;
  gap: 16px;
  align-items: end;
  margin-top: 28px;
  padding: 18px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 22px;
  background: rgba(248, 250, 252, 0.78);
}

.materialField {
  display: grid;
  gap: 8px;
}

.materialLabel {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 800;
}

.materialSelect {
  width: 100%;
  height: 48px;
  padding: 0 16px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #ffffff;
  color: var(--text-main);
  font-size: 15px;
  outline: none;
}

.materialSelect:focus {
  border-color: rgba(15, 118, 110, 0.42);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.12);
}

.materialSearchBtn {
  height: 48px;
  min-width: 132px;
  padding: 0 22px;
  border: 0;
  border-radius: 16px;
  background: linear-gradient(135deg, #16345a, #1d4f82);
  color: #ffffff;
  cursor: pointer;
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 16px 34px rgba(29, 79, 130, 0.18);
}

.materialSearchBtn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
  box-shadow: none;
}

.materialResultArea {
  margin-top: 18px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 22px;
  background: #ffffff;
}

.materialResultHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.materialResultEyebrow {
  margin: 0 0 6px;
  color: var(--teal);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.materialResultTitle {
  margin: 0;
  color: var(--text-main);
  font-size: 20px;
  font-weight: 800;
}

.materialResultBadge {
  flex: 0 0 auto;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.materialState {
  padding: 34px 18px;
  border: 1px dashed rgba(15, 118, 110, 0.26);
  border-radius: 18px;
  background: rgba(240, 253, 250, 0.55);
  color: var(--text-muted);
  font-size: 15px;
  font-weight: 700;
  text-align: center;
}

.materialState--error {
  border-color: rgba(220, 38, 38, 0.28);
  background: rgba(254, 242, 242, 0.8);
  color: #dc2626;
}

.backBtn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 11px 16px;
  border: 1px solid rgba(15, 118, 110, 0.2);
  border-radius: 14px;
  background: #ffffff;
  color: #0f766e;
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.materialTableWrap {
  overflow-x: auto;
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 18px;
}

.materialTable {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  background: #ffffff;
}

.materialTable th,
.materialTable td {
  padding: 16px 18px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.84);
  text-align: left;
  vertical-align: middle;
}

.materialTable th {
  background: rgba(248, 250, 252, 0.9);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 800;
}

.materialTable tr:last-child td {
  border-bottom: 0;
}

.materialTitleCell {
  width: 46%;
  color: var(--text-main);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.7;
}

.materialLinkCell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.materialLinkText {
  min-width: 0;
  color: #2563eb;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-all;
}

.materialLinkActions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.materialMiniBtn {
  height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: 12px;
  background: #ffffff;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.materialMiniBtn--solid {
  border-color: transparent;
  background: #1d4ed8;
  color: #ffffff;
}

.sectionHeader {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.sectionTitle,
.chatHeader,
.supportTitle,
.panelTitle {
  margin: 0;
  color: var(--text-main);
  font-weight: 800;
}

.sectionTitle {
  font-size: clamp(24px, 3vw, 32px);
}

.sectionText {
  margin: 8px 0 0;
  max-width: 760px;
  color: var(--text-muted);
  font-size: 15px;
  line-height: 1.8;
}

.workspaceBoard {
  border-radius: 28px;
  padding: 18px;
}

.workspaceRail {
  display: flex;
  align-items: stretch;
  gap: 18px;
  overflow-x: auto;
  padding-bottom: 10px;
}

.workspaceRail::-webkit-scrollbar,
.chatBody::-webkit-scrollbar {
  height: 10px;
  width: 10px;
}

.workspaceRail::-webkit-scrollbar-thumb,
.chatBody::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.32);
  border-radius: 999px;
}

.add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 18px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.98), rgba(13, 148, 136, 0.88));
  color: #ffffff;
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 18px 40px rgba(15, 118, 110, 0.22);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.add:hover,
.compareBtn:hover,
.chatSend:hover,
.promptChip:hover,
.supportPrompt:hover,
.iconBtn--solid:hover {
  transform: translateY(-1px);
}

.add--top {
  min-width: 138px;
  padding: 14px 18px;
}

.add--rail {
  min-width: 146px;
  padding: 18px;
  flex: 0 0 auto;
}

.addRailWrap {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-width: 164px;
}

.addRailHint {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
}

.addIcon {
  font-size: 20px;
  line-height: 1;
}

.compareSlot {
  position: relative;
  width: 110px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.compareConnector {
  position: relative;
  width: 2px;
  height: 46px;
  margin-top: 4px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.22), rgba(249, 115, 22, 0.28));
}

.compareConnector::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -8px;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 10px solid rgba(249, 115, 22, 0.75);
}

.compareBtn,
.chatSend {
  border: none;
  border-radius: 14px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #10233d, #1e3a5f);
  color: #ffffff;
  cursor: pointer;
  font-weight: 700;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.compareBtn:disabled,
.chatSend:disabled,
.chatClear:disabled,
.promptChip:disabled,
.supportPrompt:disabled,
.iconBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.compareHint {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.45;
  text-align: center;
}

.analysisLayout {
  width: min(1440px, 100%);
  margin: 0 auto;
}

.analysisMain {
  display: grid;
  gap: 18px;
  width: min(1320px, 100%);
  margin: 0 auto;
}

.comparePanel,
.chatPanel,
.supportCard {
  position: relative;
  border-radius: 28px;
  padding: 22px;
}

.panelHeader,
.chatHeaderRow,
.chatToolbar {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 14px;
}

.panelTitle,
.chatHeader,
.supportTitle {
  font-size: 24px;
  line-height: 1.3;
}

.panelVs {
  color: var(--orange);
  font-size: 18px;
  text-transform: uppercase;
}

.panelBody {
  margin-top: 18px;
}

.panelEmpty {
  padding: 18px;
  border-radius: 20px;
  border: 1px dashed rgba(148, 163, 184, 0.4);
  background: rgba(248, 250, 252, 0.7);
  color: var(--text-muted);
  line-height: 1.7;
}

.panelEmpty--idle {
  margin-top: 18px;
}

.wordcloudCompareGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.wordcloudCard {
  padding: 16px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.9));
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.wordcloudYear {
  margin-bottom: 12px;
  color: var(--text-main);
  font-size: 15px;
  font-weight: 700;
}

.wordcloudImage {
  width: 100%;
  display: block;
  border-radius: 18px;
  background: #ffffff;
}

.compareChartWrap {
  position: relative;
  padding-top: 56px;
}

.iconBtn {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  padding: 0;
  line-height: 1;
  cursor: pointer;
  transition: transform 0.2s ease, background 0.2s ease;
}

.iconBtn--ghost {
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-muted);
  border-color: rgba(148, 163, 184, 0.16);
}

.iconBtn--ghost:hover {
  background: rgba(241, 245, 249, 0.95);
  color: var(--text-main);
}

.iconSvg {
  width: 18px;
  height: 18px;
  display: block;
}

.compareDownloadBtn {
  position: absolute;
  top: 0;
  right: 0;
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

.compareDownloadBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.compareDownloadIcon {
  width: 16px;
  height: 16px;
}

.promptBar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.promptChip,
.supportPrompt,
.chatClear {
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-main);
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.promptChip,
.supportPrompt {
  padding: 10px 14px;
  border-radius: 999px;
  text-align: left;
  font-size: 13px;
  line-height: 1.45;
}

.chatClear {
  border-radius: 14px;
  padding: 10px 14px;
  font-size: 14px;
}

.chatBody {
  max-height: 420px;
  margin-top: 16px;
  padding: 14px;
  overflow: auto;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.8), rgba(241, 245, 249, 0.78));
}

.chatHint {
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.8;
}

.chatMsg {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.86);
}

.chatMsg--user {
  margin-left: auto;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.1), rgba(13, 148, 136, 0.08));
}

.chatRole {
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chatText {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-main);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
}

.chatInputRow {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.chatInput {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  padding: 14px 16px;
  color: var(--text-main);
  font-size: 14px;
  outline: none;
}

.chatInput:focus {
  border-color: rgba(15, 118, 110, 0.42);
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08);
}

.thinkingRow {
  color: var(--text-muted);
}

.aiNotice {
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
  background: transparent;
  border: none;
  padding: 0;
}

@media (max-width: 1200px) {
  .analysisLayout {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .page {
    padding: 24px 16px 40px;
  }

  .heroCopy,
  .workspaceBoard,
  .comparePanel,
  .chatPanel,
  .supportCard {
    border-radius: 22px;
  }

  .heroCopy {
    min-height: 360px;
    padding: 48px 32px;
  }

  .sectionHeader,
  .chatInputRow {
    grid-template-columns: 1fr;
    display: grid;
  }

  .wordcloudCompareGrid {
    grid-template-columns: 1fr;
  }

  .compareDownloadBtn {
    position: static;
    margin-bottom: 14px;
  }

  .compareChartWrap {
    padding-top: 0;
  }

  .materialFilters {
    grid-template-columns: 1fr;
  }

  .materialSearchBtn {
    width: 100%;
  }

  .materialLinkCell {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 18px 12px 32px;
  }

  .heroTitle {
    font-size: 30px;
    white-space: normal;
  }

  .heroLead {
    font-size: 15px;
    line-height: 1.85;
  }

  .panelTitle,
  .chatHeader,
  .supportTitle,
  .sectionTitle {
    font-size: 22px;
  }

  .add--top,
  .add--rail,
  .chatSend {
    width: 100%;
  }

  .compareSlot {
    width: 84px;
  }
}
</style>
