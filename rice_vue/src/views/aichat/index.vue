<template>
    <div class="ai-container">
        <!-- 对话窗口 -->
        <div class="chat-wrapper">
            <div class="chat-window">
                <!-- 头部 -->
                <div class="chat-header">
                <div class="header-title">AI Assistant</div>
                <div class="clear-history" @click="clearChatHistory()">
                    <el-icon><Delete /></el-icon>
                    <span>Clear Conversation</span>
                </div>
                </div>

                <!-- 消息显示区域 -->
                <div class="message-area">
                  <transition-group name="message" tag="div">
                      <div v-for="(msg, index) in messages" :key="index" class="message-wrapper">
                      <div :class="['message', msg.role, { loading: isStreaming && msg.role === 'assistant' }]">
                          <!-- 新增头像部分 -->
                          <div class="avatar-container">
                          <img 
                              :src="msg.role === 'user' ? userAvatar : aiAvatar" 
                              class="avatar"
                              alt="avatar"
                          >
                          </div>
                          <div class="bubble" v-html="marked.parse(msg.content)"></div>
                      </div>
                      </div>
                  </transition-group>
                  <div v-if="isStreaming" class="loading-indicator">
                    <div class="dot-flashing"></div>
                  </div>
                </div>


                <!-- 输入区域 -->
                <div class="input-area">
                <div class="input-container">
                    <textarea
                    v-model="inputText"
                    placeholder="Please enter your question..."
                    @keydown.enter.prevent="sendMessage"
                    ></textarea>
                    <button @click="sendMessage" :disabled="!inputText.trim()">
                    <el-icon :size="20"><Promotion /></el-icon>
                    </button>
                </div>
                <div class="input-footer">Powered by MDR-based</div>
                </div>
            </div>
        </div>
    </div>
</template>
  
<script setup>
import { ref, nextTick,onMounted,watch } from 'vue'
import { marked } from 'marked'
import { aiChat,initChat } from "../../api/ai/index"
import { ElMessage } from 'element-plus'

// 优化marked样式
marked.setOptions({
  breaks: true,
  gfm: true,
  xhtml: true,
  highlight: (code) => hljs.highlightAuto(code).value
})

// 初始化时从本地存储加载数据
onMounted(() => {
const savedData = localStorage.getItem('ai_chat_data')
if (savedData) {
    const { session_id: savedId, messages: savedMessages } = JSON.parse(savedData)
    session_id = savedId
    messages.value = savedMessages
} else {
    initChatContent()
}
})

// 保存数据方法
const saveChatData = () => {
  const dataToSave = {
      session_id,
      messages: messages.value,
  }
  localStorage.setItem('ai_chat_data', JSON.stringify(dataToSave))
}

// 手动清除历史记录
const clearChatHistory = () => {
  localStorage.removeItem('ai_chat_data')
  messages.value = []
  ElMessage({
    showClose: true,
    center: true,
    message: 'Conversation cleared successfully',
    type: 'success',
  })
  setTimeout(() => {
    initChatContent()
  }, 100);
}


// 头像图片
const userAvatar = 'src/common/image/jimao.png'
const aiAvatar = 'src/common/image/xiaobai.png'

// 消息列表
const messages = ref([])

// 用户输入内容
const inputText = ref('')


// 滚动到底部
const scrollToBottom = () => {
nextTick(() => {
    const messageArea = document.querySelector('.message-area')
    if (messageArea) {
    messageArea.scrollTop = messageArea.scrollHeight
    }
})
}

// 发送消息
const sendMessage = async () => {
if (!inputText.value.trim()) return

// 添加用户消息
messages.value.push({
    role: 'user',
    content: inputText.value
})

// 清空输入框
const userMessage = inputText.value
inputText.value = ''

// 滚动到底部
scrollToBottom()

try {
    // AI响应
    await fetchAIResponse(userMessage)
    // 滚动到底部
    scrollToBottom()
    saveChatData()
} catch (error) {
    console.error('Request failed:', error)
    scrollToBottom()
    saveChatData()
}
}

// 流式输出状态
const isStreaming = ref(false)
const loadingPosition = ref('bottom') // 新增loading位置状态
const streamingContent = ref('')

// 调用API获取响应
const fetchAIResponse = async (message) => {
try {
    isStreaming.value = true;
    streamingContent.value = '';
    
    // 添加初始AI消息
    messages.value.push({
        role: 'assistant',
        content: ''
    });

    const response = await aiChat(message, session_id);
    const fullContent = response.data.message.content.split('```',1)[0];
    // console.log(fullContent)
    
    // 将响应内容转换为字符数组
    const messageIndex = messages.value.length - 1;
    
    // 使用异步循环逐个字符添加
    const chunkSize = 3;
    for (let i = 0; i < fullContent.length; i += chunkSize) {
      const chunk = fullContent.slice(i, i + chunkSize);
      await new Promise(resolve => setTimeout(resolve, 30));
      streamingContent.value += chunk;
      messages.value[messageIndex].content = streamingContent.value;
    }

} catch (err) {
    console.error('API request failed:', err);
    messages.value[messages.value.length - 1].content += 'Sorry, the request failed. Please try again later.';
    throw err;
} finally {
    isStreaming.value = false;
    saveChatData()
}
};

// 分配对话ID和开场白
let session_id = ''
// 初始化
async function initChatContent() {
try {
    const res = await initChat()
    session_id = res.data.session_id
    // 只在首次初始化时添加欢迎消息
    if (messages.value.length === 0) {
    messages.value.push(res.data.message)
    }
    saveChatData()
} catch (err) {
    console.log(err)
}
}

</script>

<style lang="less" scoped>
.ai-container {
  height: 98vh;
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;

  .chat-wrapper {
    width: 100%;
    height: 100%;
    .chat-window {
      background: #ffffff;
      border-radius: 16px;
      height: 100%;
      display: flex;
      flex-direction: column;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12);

      .chat-header {
        padding: 16px 24px;
        border-bottom: 1px solid #f0f3f6;
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #fafcfe;
        border-radius: 16px 16px 0 0;

        .header-title {
          font-size: 18px;
          font-weight: 600;
          color: #1a1a1a;
          display: flex;
          align-items: center;
          gap: 8px;

          &::before {
            content: '';
            display: block;
            width: 6px;
            height: 18px;
            background: #2fb9c2;
            border-radius: 2px;
          }
        }

        .clear-history {
          display: flex;
          align-items: center;
          gap: 6px;
          color: #666;
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
          padding: 8px 12px;
          border-radius: 8px;

          &:hover {
            background: #f5f7fa;
            color: #2fb9c2;
          }

          .el-icon {
            font-size: 16px;
          }
        }
      }

      .message-area {
        flex: 1;
        overflow-y: auto;
        padding: 24px;
        display: flex;
        flex-direction: column;
        background: linear-gradient(180deg, #fafcfe 0%, #ffffff 100%);

        .message-wrapper {
          margin: 12px 0;
    
            .message {
              display: flex;
              align-items: flex-start;
              gap: 12px;
              margin: 16px 0;
              max-width: 85%;
              
              &.user {
                  flex-direction: row-reverse;
                  margin-left: auto;

                  .avatar-container {
                  margin-left: 12px;
                  margin-right: 0;
                  }
              }

              .avatar-container {
                  width: 36px;
                  height: 36px;
                  flex-shrink: 0;
                  margin-right: 12px;
                  position: relative;
                  
                  .avatar {
                  width: 100%;
                  height: 100%;
                  border-radius: 50%;
                  border: 2px solid #fff;
                  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                  object-fit: cover;
                  }
              }

              .bubble {
                  padding: 12px 16px;
                  border-radius: 16px;
                  line-height: 1.6;
                  font-size: 14px;
                  position: relative;
                  // min-width: 120px;
                  max-width: 600px;
                  word-break: break-word;
                  transition: all 0.3s ease;
                  
                  // 移除默认p标签边距
                  :deep(p) {
                    margin: 0 !important;
                  }
                  
                  // Markdown代码块样式
                  :deep(pre) {
                  background: rgba(0, 0, 0, 0.05);
                  padding: 12px;
                  border-radius: 8px;
                  overflow-x: auto;
                  margin: 8px 0 !important;
                  }
                  
                  // 列表样式
                  :deep(ul),
                  :deep(ol) {
                  padding-left: 24px;
                  margin: 8px 0;
                  }
                  
                  // 链接样式
                  :deep(a) {
                  color: #2fb9c2;
                  text-decoration: underline;
                  }
                  
                  // 标题样式
                  :deep(h1),
                  :deep(h2),
                  :deep(h3) {
                  margin: 12px 0 8px;
                  line-height: 1.3;
                  }
              }

              // 用户消息样式
              &.user .bubble {
                  background: #2fb9c2;
                  color: #fff;
                  border-radius: 16px 4px 16px 16px;
              }

              // AI消息样式
              &.assistant .bubble {
                  background: #fff;
                  color: #333;
                  border-radius: 4px 16px 16px 16px;
                  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                  
                  // 加载状态
                  &.loading {
                      &::after {
                          content: "";
                          position: absolute;
                          top: 0;
                          left: 0;
                          width: 100%;
                          height: 100%;
                          background: linear-gradient(
                          90deg,
                          rgba(255,255,255,0) 0%,
                          rgba(255,255,255,0.6) 50%,
                          rgba(255,255,255,0) 100%
                          );
                          animation: shimmer 1.5s infinite;
                          border-radius: inherit;
                      }
                  }
              }
            }
        }
      }


      .input-area {
        padding: 16px 24px;
        border-top: 1px solid #f0f3f6;

        .input-container {
          position: relative;
          border: 1px solid #e6e9ed;
          border-radius: 24px;
          background: #ffffff;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          padding: 8px;

          &:focus-within {
            border-color: #2fb9c2;
            box-shadow: 0 0 0 3px rgba(47, 185, 194, 0.15);
          }

          textarea {
            flex: 1;
            border: none;
            resize: none;
            padding: 8px 16px;
            font-size: 14px;
            line-height: 1.6;
            min-height: 40px;
            max-height: 120px;
            background: transparent;
            min-height: 40px;
            max-height: 120px;
            line-height: 1.6;

            &::placeholder {
              color: #999;
            }

            &:focus {
              outline: none;
            }
          }

          button {
            width: 40px;
            height: 40px;
            border: none;
            border-radius: 50%;
            background: #2fb9c2;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
            margin-left: 8px;

            &:hover {
              background: #26a2aa;
              transform: rotate(15deg);
            }

            &:disabled {
              background: #e6e9ed;
              cursor: not-allowed;
            }

            .el-icon {
              transition: transform 0.2s;
            }
          }
        }

        .input-footer {
          text-align: center;
          color: #999;
          font-size: 12px;
          margin-top: 12px;
        }
      }
    }
  }
}

/* 定义进入动画 */
.message-enter-active {
  animation: messageAppear 0.3s ease;
}

/* 定义离开动画（可选） */
.message-leave-active {
  animation: messageLeave 0.3s ease;
}

/* 位置变化动画（可选） */
.message-move {
  transition: transform 0.3s ease;
}

@keyframes messageAppear {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0);}
}
@keyframes messageLeave {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-10px); }
}

// 加载动画
@keyframes dot-flashing {
  0% { opacity: 0.2; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-4px); }
  100% { opacity: 0.2; transform: translateY(0); }
}

// loading动画
.loading-indicator {
  text-align: center;
  padding: 16px 0;
  
  .dot-flashing {
    display: inline-block;
    position: relative;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #2fb9c2;
    animation: dot-flashing 1.2s infinite linear;
    
    &::before,
    &::after {
      content: '';
      position: absolute;
      top: 0;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: #2fb9c2;
    }
    
    &::before {
      left: -12px;
      animation: dot-flashing 1.2s infinite linear;
      animation-delay: 0.2s;
    }
    
    &::after {
      left: 12px;
      animation: dot-flashing 1.2s infinite linear;
      animation-delay: 0.4s;
    }
  }
}

@keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}
</style>
