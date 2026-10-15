<template>
  <div class="ai-container">
    <!-- 触发按钮 -->
    <div class="trigger" @click="toggleChat">
      <el-icon :size="24" color="#fff">
        <ChatDotRound />
      </el-icon>
    </div>

    <!-- 对话窗口 -->
    <transition name="slide-fade">
      <div v-if="showChat" class="chat-wrapper" @click.self="closeChat">
        <div class="chat-window">
          <div class="clear-history" @click="clearChatHistory">Clear Conversation</div>
          <!-- 消息显示区域 -->
          <div class="message-area">
            <transition-group name="message" tag="div">
              <div v-for="(msg, index) in messages" :key="index" class="message-wrapper">
                <div :class="['message', msg.role]">
                  <img 
                    :src="msg.role === 'user' ? userAvatar : aiAvatar" 
                    class="avatar"
                    alt="avatar"
                  >
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
            <textarea
              v-model="inputText"
              placeholder="Please enter your question..."
              @keydown.enter="sendMessage"
            ></textarea>
            <button @click="sendMessage">Send</button>
          </div>

        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick,onMounted,watch } from 'vue'
import { ChatDotRound } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { aiChat,initChat } from "../../api/ai/index"


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

// 监听messages变化自动保存
// watch(messages, (newVal) => {
//   saveChatData()
// }, { deep: true })

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
  initChatContent()
}

// 控制显示状态
const showChat = ref(false)

// 头像图片
const userAvatar = 'src/common/image/jimao.png'
const aiAvatar = 'src/common/image/xiaobai.png'

// 消息列表
const messages = ref([])

// 用户输入内容
const inputText = ref('')

// 切换聊天窗口
const toggleChat = () => {
  showChat.value = !showChat.value
}

// 关闭聊天窗口
const closeChat = () => {
  showChat.value = false
}

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
    // messages.value.push({
    //   role: 'assistant',
    //   content: 'Sorry, the request failed. Please try again later.'
    // })
    scrollToBottom()
    saveChatData()
  }
}

// 流式输出状态
const isStreaming = ref(false)
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
    // console.log(response.data)
    
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
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1000;
  .trigger {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background-color: #67c23a;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
  }

  .trigger:hover {
    transform: scale(1.1);
  }

  .chat-wrapper {
    position: fixed;
    right: 80px;
    bottom: 20px;
    width: 100vw;
    height: 100vh;
      .chat-window {
      position: fixed;
      right: 80px;
      bottom: 20px;
      width: 420px;
      height: 60vh;
      background-color: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      // 清除历史按钮
      .clear-history {
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1001;
        padding: 4px 8px;
        background: #ff4d4f;
        color: white;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      }
      .message-area {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        margin-bottom: 10px;
        .message-wrapper {
          margin-bottom: 20px;
        }
        .message {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          max-width: 80%;
        }
        .message.user {
            margin-left: auto;
            flex-direction: row-reverse;
          }

          .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 1px #666 solid;
            flex-shrink: 0;
          }

          .bubble {
            padding: 1px 10px;
            border-radius: 8px;
            position: relative;
            word-break: break-word;
            font-size: 0.8em;
            line-height: 1;
            // height: fit-content;
            max-width: 90%;
            p {
              margin: 0; 
            }
            /* Markdown样式 */
            :deep(code) {
              background-color: #f5f7fa;
              padding: 2px 4px;
              border-radius: 4px;
              font-family: monospace;
            }
            
            :deep(pre) {
              background-color: #f5f7fa;
              padding: 12px;
              border-radius: 4px;
              overflow-x: auto;
              code {
                background-color: transparent;
                padding: 0;
              }
            }
            
            :deep(blockquote) {
              border-left: 4px solid #ddd;
              padding-left: 12px;
              color: #666;
              margin: 12px 0;
            }
            
            :deep(ul),
            :deep(ol) {
              padding-left: 20px;
              margin: 12px 0;
            }
            
            :deep(li) {
              margin: 4px 0;
            }
            
            :deep(a) {
              color: #409eff;
              text-decoration: none;
              &:hover {
                text-decoration: underline;
              }
            }
            
            :deep(h1),
            :deep(h2),
            :deep(h3) {
              margin: 16px 0;
              line-height: 1.2;
            }
            
            :deep(h1) {
              font-size: 1.5em;
            }
            
            :deep(h2) {
              font-size: 1.3em;
            }
            
            :deep(h3) {
              font-size: 1.1em;
            }
          }

          .message-area {
            scroll-behavior: smooth;
            padding-bottom: 20px;
          }

          .loading-indicator {
            display: flex;
            justify-content: center;
            padding: 10px 0;
          }

          .dot-flashing {
            position: relative;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: #409eff;
            color: #409eff;
            animation: dotFlashing 1s infinite linear alternate;
            animation-delay: .5s;
          }

          .dot-flashing::before, .dot-flashing::after {
            content: '';
            display: inline-block;
            position: absolute;
            top: 0;
          }

          .dot-flashing::before {
            left: -15px;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: #409eff;
            color: #409eff;
            animation: dotFlashing 1s infinite alternate;
            animation-delay: 0s;
          }

          .dot-flashing::after {
            left: 15px;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: #409eff;
            color: #409eff;
            animation: dotFlashing 1s infinite alternate;
            animation-delay: 1s;
          }

          @keyframes dotFlashing {
            0% {
              background-color: #409eff;
            }
            50%, 100% {
              background-color: rgba(64, 158, 255, 0.2);
            }
          }

          button:disabled {
            background-color: #a0cfff;
            cursor: not-allowed;
          }

          .user .bubble {
            background-color: #409eff;
            color: white;
            border-top-right-radius: 4px;
          }

          .assistant .bubble {
            background-color: #f0f0f0;
            color: #333;
            border-top-left-radius: 4px;
          }
      }
    }
  }

  .input-area {
    display: flex;
    gap: 10px;
    padding: 10px;
    background-color: #f5f7fa;
    textarea {
      flex: 1;
      padding: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
      resize: none;
    }
    button {
        padding: 0 20px;
        background-color: #409eff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
      }
    button:hover {
      background-color: #66b1ff;
    }
  }
   /* 窗口过渡动画 */
  .slide-fade-enter-active {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .slide-fade-leave-active {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .slide-fade-enter-from,
  .slide-fade-leave-to {
    opacity: 0;
  }

  /* 消息过渡动画 */
  .message-move,
  .message-enter-active,
  .message-leave-active {
    transition: all 0.3s ease;
  }
  .message-enter-from {
    opacity: 0;
    transform: translateY(20px);
  }
  .message-leave-to {
    opacity: 0;
    transform: translateY(-20px);
  }
  .message-leave-active {
    position: absolute;
  }
}
</style>


