<template>
  <div class="layout-container">
    <keep-alive>
      <aiChat v-if="showAiChat"> </aiChat>
    </keep-alive>
    <div class="left-side">
      <left-header/>
    </div>
    <div class="right-side">
      <router-view v-slot="{Component}"> 
        <keep-alive>
          <component :is="Component">
          </component>
        </keep-alive>
      </router-view> 
    </div>
  </div>
</template>

<script setup>
import { ref,watch,onMounted } from 'vue';
import { useRouter } from 'vue-router';
const router = useRouter();

let showAiChat = ref(true)
watch(() => router.currentRoute.value.path,(newValue,oldValue) => {
  if(newValue === "/aiChat"){
    showAiChat.value = false
  }else{
    showAiChat.value = true
  }
})

onMounted(()=>{
  if(router.currentRoute.value.path === "/aiChat")[
    showAiChat.value = false
  ]
})
</script>

<style scoped lang="less">
.layout-container {
    display: flex;
    height: 100vh;
    .left-side {
        // width: 240px;
        // border-right: 1px solid #e8e8e8;
    }
    .right-side {
      flex: 1;
      padding: 10px;
      overflow-y: auto;
    }
}


</style>
