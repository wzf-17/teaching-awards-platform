<template>
  <div class="chatbox">
    <div class="header">智能问答</div>

    <div class="chat-window" ref="chatWindowEl">
      <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
        <div class="bubble">{{ m.text }}</div>
      </div>
    </div>

    <div class="composer">
      <el-input
        v-model="userMessage"
        placeholder="向模型提问..."
        @keyup.enter="sendMessage"
        clearable
      />
      <el-button
        type="primary"
        :loading="sending"
        @click="sendMessage"
        style="margin-top:8px; width:100%;"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import axios from 'axios'

const props = defineProps({
  year: { type: [Number, String], default: null },
  dimension: { type: String, default: 'geo' }
})

const userMessage = ref('')
const messages = ref([])
const sending = ref(false)
const chatWindowEl = ref(null)

// ✅ 新增：澄清会话 id（为空表示不在澄清流程中）
const clarifySessionId = ref(null)

// 你也可以把后端地址抽成环境变量；这里先写死和你之前一致
const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:5000')

// ✅ 开关：true 使用澄清链路（会追问）；false 走你原来的 /chat
const USE_CLARIFY = true

function scrollToBottom() {
  const el = chatWindowEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

// 可选：把后端返回的结果压缩成一句可读文本（避免直接把大 JSON 丢进气泡）
function formatResultToText(data) {
  // 优先用后端的 answer
  if (data?.answer) return data.answer
  if (data?.result?.narrative) return data.result.narrative
  return '已完成分析。'
}

async function sendMessage() {
  const text = userMessage.value.trim()
  if (!text || sending.value) return

  // 1) 先显示用户消息
  messages.value.push({ role: 'user', text })
  userMessage.value = ''
  sending.value = true

  try {
    // ===== 方案A：澄清链路（会追问） =====
    if (USE_CLARIFY) {
      // 还没进入澄清：先 start
      if (!clarifySessionId.value) {
        const resp = await axios.post(`${BASE_URL}/api/rag/clarify/start`, {
          question: text
        })
        const data = resp?.data

        if (!data?.ok) throw new Error(data?.error || 'clarify/start failed')

        if (data.done) {
          // ✅ 直接完成：输出结果
          messages.value.push({ role: 'assistant', text: formatResultToText(data) })
          clarifySessionId.value = null
        } else {
          // ✅ 需要追问：显示追问，并保存 session_id
          clarifySessionId.value = data.session_id
          messages.value.push({ role: 'assistant', text: data.clarify_question || '请补充信息。' })
        }
      } else {
        // 已在澄清：把用户输入当作 answer
        const resp = await axios.post(`${BASE_URL}/api/rag/clarify/answer`, {
          session_id: clarifySessionId.value,
          answer: text
        })
        const data = resp?.data

        if (!data?.ok) throw new Error(data?.error || 'clarify/answer failed')

        if (data.done) {
          // ✅ 完成：输出结果并退出澄清
          messages.value.push({ role: 'assistant', text: formatResultToText(data) })
          clarifySessionId.value = null
        } else {
          // 继续追问
          messages.value.push({ role: 'assistant', text: data.clarify_question || '请继续补充信息。' })
        }
      }

      await nextTick()
      scrollToBottom()
      return
    }

    // ===== 方案B：你原来的 /chat（不追问） =====
    const payload = {
      message: text,
      year: props.year,
      dimension: props.dimension,
      messages: messages.value.map(m => ({ role: m.role, text: m.text }))
    }

    const resp = await axios.post(`${BASE_URL}/chat`, payload)
    const reply = resp?.data?.response ?? '后端未返回 response'
    messages.value.push({ role: 'assistant', text: reply })

    await nextTick()
    scrollToBottom()
  } catch (e) {
    // 出错时建议退出澄清，避免 session 卡住
    clarifySessionId.value = null
    messages.value.push({ role: 'assistant', text: '请求失败：' + (e?.message || '请确认后端接口已启动') })
    await nextTick()
    scrollToBottom()
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.chatbox{
  width: 100%;
  height: 100%;
  display:flex;
  flex-direction:column;
}

.header{
  font-weight:600;
  margin-bottom:10px;
}

.chat-window{
  flex:1;
  overflow:auto;
  padding:10px;
  background:#fafafa;
  border:1px solid #eee;
  border-radius:10px;
}

.msg{
  display:flex;
  margin-bottom:10px;
}

.msg.user{
  justify-content:flex-end;
}

.msg.assistant{
  justify-content:flex-start;
}

.bubble{
  max-width: 85%;
  padding:8px 10px;
  border-radius:10px;
  line-height:1.4;
  background:#fff;
  border:1px solid #eee;
  word-break: break-word;
}

.msg.user .bubble{
  background:#eaf3ff;
  border-color:#d6e7ff;
}

.composer{
  margin-top:10px;
}
</style>
