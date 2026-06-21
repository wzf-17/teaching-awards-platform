<template>
  <div class="chartWrap" :style="{ height: height + 'px' }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, toRaw } from 'vue'
import Chart from 'chart.js/auto'

const props = defineProps({
  type: { type: String, default: 'bar' },
  data: { type: Object, required: true },
  options: { type: Object, default: () => ({}) },
  height: { type: Number, default: 260 },
  titleText: { type: String, default: '' },
  backgroundColor: { type: String, default: '#ffffff' },
})

const canvasRef = ref(null)
let chart = null

function toPlain(obj) {
  try {
    const raw = toRaw(obj) ?? obj
    if (typeof structuredClone === 'function') return structuredClone(raw)
    return JSON.parse(JSON.stringify(raw))
  } catch {
    return Array.isArray(obj) ? obj.slice() : { ...(toRaw(obj) ?? obj) }
  }
}

const bgAndTitlePlugin = {
  id: 'bgAndTitle',
  beforeDraw(c, args, pluginOptions) {
    const { ctx } = c
    ctx.save()
    ctx.fillStyle = pluginOptions?.backgroundColor || '#ffffff'
    ctx.fillRect(0, 0, c.width, c.height)
    ctx.restore()
  },
  afterDraw(c, args, pluginOptions) {
    const title = pluginOptions?.titleText
    if (!title) return
    const { ctx } = c
    ctx.save()
    ctx.fillStyle = '#111827'
    ctx.font = 'bold 16px sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText(title, 12, 10)
    ctx.restore()
  },
}

function build() {
  if (!canvasRef.value) return
  const ctx = canvasRef.value.getContext('2d')
  const safeData = toPlain(props.data)
  const finalOptions = toPlain(props.options)

  chart = new Chart(ctx, {
    type: props.type,
    data: safeData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: props.titleText ? 34 : 8, right: 8, bottom: 8, left: 8 } },
      ...finalOptions,
      plugins: {
        ...(finalOptions.plugins || {}),
        bgAndTitle: {
          titleText: props.titleText,
          backgroundColor: props.backgroundColor,
        },
      },
    },
    plugins: [bgAndTitlePlugin],
  })
}

function destroy() {
  if (chart) {
    chart.destroy()
    chart = null
  }
}

function update() {
  if (!chart) return

  chart.config.type = props.type
  chart.data = toPlain(props.data)

  const finalOptions = toPlain(props.options)
  chart.options = {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { top: props.titleText ? 34 : 8, right: 8, bottom: 8, left: 8 } },
    ...finalOptions,
    plugins: {
      ...(finalOptions.plugins || {}),
      bgAndTitle: {
        titleText: props.titleText,
        backgroundColor: props.backgroundColor,
      },
    },
  }

  chart.update()
}

function getPngDataUrl() {
  if (!chart) return ''
  return chart.toBase64Image('image/png', 1)
}

function downloadPng(filename = 'chart.png') {
  const url = getPngDataUrl()
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

defineExpose({ downloadPng, getPngDataUrl })

onMounted(() => build())
onBeforeUnmount(() => destroy())

watch(
  () => [props.type, props.data, props.options, props.titleText, props.backgroundColor],
  () => {
    if (!chart) build()
    else update()
  },
  { deep: true }
)
</script>

<style scoped>
.chartWrap { width: 100%; }
</style>
