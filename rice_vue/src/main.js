import { createApp } from "vue";
import App from "./App.vue";
import ElementPlus from "element-plus";
import "/node_modules/element-plus/dist/index.css";
import router from "./router";
import elementIcons from "./components/SvgIcon/svgicon.js";
// 引入导航栏
import aiChat from "./components/ai/ai.vue"
import left_header from "./components/left_header/left_header.vue";

// vue实例
const app = createApp(App);

// 全局注册
app.use(ElementPlus);
app.use(router);
app.use(elementIcons);

// 全局组件挂载
app.component("aiChat", aiChat);
app.component("left-header", left_header)


app.mount("#app");
