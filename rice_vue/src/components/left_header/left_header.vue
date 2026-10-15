<template>
  <div class="left">
    <el-menu
        :default-active="defaultActive"
        class="el-menu-vertical-demo"
        text-color="black"
        active-text-color="#2fb9c2"
        :collapse="isCollapse"
        :router="true"
      >
      <el-button icon="TurnOff" class="Button" color="#2fb9c2" size="large" plain circle @click="openOrOff"></el-button>
        <el-menu-item index="/home_page">
          <el-icon><House /></el-icon>
          <span>Home</span>
        </el-menu-item>
        <el-menu-item index="/metadata_inquire">
          <el-icon><location /></el-icon>
          <span>Shared Domain</span>
        </el-menu-item>
        <el-menu-item index="/subdomain_inquire">
          <el-icon><document /></el-icon>
          <span>Subdomain</span>
        </el-menu-item>
        <el-menu-item index="/rice_graphTable">
          <el-icon><Place /></el-icon>
          <span>Kownledge Graph</span>
        </el-menu-item>
        <el-menu-item index="/aiChat">
          <el-icon><ChatDotRound /></el-icon>
          <span>Intelligent Q&A</span>
        </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup>
import { ref, computed } from "vue"
import { useRouter } from "vue-router";

const router = useRouter()

const defaultActive = computed(() => {
    return "/" + router.currentRoute.value.path.split("/")[1];
});

const isCollapse = ref(false)

function openOrOff(){
  isCollapse.value = !isCollapse.value
}
</script>

<style lang='less' scoped>
.left{
  .el-menu-vertical-demo{
    height: 100vh;
    // width: 200px;
    .Button{
      margin-left: 1vw;
    }
  }
}

</style>