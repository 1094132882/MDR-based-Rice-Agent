<template>
  <div class="dashboard-container">
    <img src="../../common/image/HZAUagent_2.png" alt="System Logo" class="floating-logo">
    <!-- 左侧面板 -->
    <div class="left-panel">
      <div class="chart-box top">
        <div ref="leftTopChart" class="chart-container"></div>
      </div>
      <div class="chart-box bottom">
        <div ref="leftBottomChart" class="chart-container"></div>
      </div>
    </div>

    <!-- 右侧面板 -->
    <div class="right-panel">
      <div class="chart-box top">
        <div ref="rightTopChart" class="chart-container"></div>
      </div>
      <div class="chart-box bottom">
        <div ref="rightBottomChart" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';
import { nextTick } from 'vue';
import { 
  getConceptualDomainList,
  getDataElementConceptList,
  getObjectClassList,
  getPropertyList,
  getValueDomainList,
  getDataElementList,
} from '../../api/metadata_inquire';
import { 
  getSubdomainList,
  getSubdomainByIdentifier 
} from '../../api/subdomain_inquire/index'

// 图表引用
const leftTopChart = ref(null);
const leftBottomChart = ref(null);
const rightTopChart = ref(null);
const rightBottomChart = ref(null);

// 图表实例
let leftTopChartInstance = null;
let leftBottomChartInstance = null

const GraphPieData = ref([]);
const GraphhorizontalBarData = ref([])
// 生命周期
onMounted(async () => {
  console.log("Page loaded");

  // ✅ 先初始化空图表（立刻渲染）
  initCharts();

  // ✅ 饼图数据（异步加载）
  getGraphData().then(() => {
    setPieChartOption();
  });

  // ✅ 柱图数据（异步加载）
  getSubdomainList().then(res => {
    GraphhorizontalBarData.value = res.data;
    sethorizontalBarChart();
  });

  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  leftTopChartInstance?.dispose();
  leftBottomChartInstance?.dispose();
});

// 获取子域信息
async function getSubdomainListData(){
  try {
    const res = await getSubdomainList();
    console.log("API response:", res);
    GraphhorizontalBarData.value = res.data;

    console.log(leftBottomChartInstance)

    // ✅ 关键：数据回来后再渲染图表
    sethorizontalBarChart();

  } catch (err) {
    console.log(err);
  }
}

// 获取子页面详细信息
function getSubdomainByIdentifierData(id){
  getSubdomainByIdentifier(id)
  .then(res => {
    console.log(res.data)
   
  }).catch(err => {
    console.log(err)
  })
}


// 获取数据方法
async function getGraphData() {
  GraphPieData.value = [
    { name: 'Object', value: 0 },
    { name: 'Data Element', value: 0 },
    { name: 'Data Element Concept', value: 0 },
    { name: 'Conceptual Domain', value: 0 },
    { name: 'Value Domain', value: 0 },
    { name: 'Property', value: 0 }
  ];

  setPieChartOption(); // ✅ 先渲染一个“空骨架”

  const apiList = [
    getObjectClassList,
    getDataElementList,
    getDataElementConceptList,
    getConceptualDomainList,
    getValueDomainList,
    getPropertyList
  ];

  apiList.forEach(async (api, index) => {
    try {
      const res = await api();

      const count = Array.isArray(res?.data)
        ? res.data.length
        : (res?.data?.list?.length || 0);

      GraphPieData.value[index].value = count;

      // ✅ 每次回来一个数据就更新一次图表
      setPieChartOption();

    } catch (e) {
      console.log(`API request ${index} failed`, e);
    }
  });
}

// 初始化图表
function initCharts() {
  if (!leftTopChart.value) return;
  if (!leftBottomChart.value) return;

  if (leftTopChartInstance) {
    leftTopChartInstance.dispose();
    leftBottomChartInstance.dispose();
  }

  leftTopChartInstance = echarts.init(leftTopChart.value);
  leftBottomChartInstance = echarts.init(leftBottomChart.value);

  setPieChartOption();
}

// 设置饼图选项
function setPieChartOption() {
  const option = {
    backgroundColor: 'transparent',
    title: {
      text: 'Metadata Distribution',
      left: 'center',
      textStyle: {
        color: '#2FB9C2',
        fontSize: 16
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      textStyle: {
        color: '#666'
      }
    },
    series: [{
      name: 'Metadata type',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '55%'],
      data: GraphPieData.value,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2,
        color: params => {
          const colors = [
            '#2FB9C2', '#6FD6E3', '#9FE3ED',
            '#C4EDF2', '#E3F6F8', '#F0FBFC'
          ];
          return colors[params.dataIndex % colors.length];
        }
      },
      label: {
        show: true,
        color: '#333',
        formatter: '{b}: {c}'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      animationType: 'scale',
      animationEasing: 'elasticOut'
    }]
  };

  leftTopChartInstance.setOption(option);
}

// 设置横向柱图来展示
function sethorizontalBarChart() {
    const processedData = [...GraphhorizontalBarData.value]
      .sort((a, b) => b.datasets_count - a.datasets_count)
      .map(item => ({
        ...item,
        name: item.name || 'Unknown'
      }));
    const option = {

        grid: {
            top: '15%',
            left: '3%',      // 1. 改回一个小数值
            right: '10%',
            bottom: '12%',
            containLabel: true // 2. 关键！设为 true，ECharts 会自动调整位置以包含所有文字
        },
        title: {
            text: 'Database Subdomain Distribution',
            subtext: `Total ${processedData.length} subdomains | Data Owner: Professor Zhang`,
            left: 'center',
            top: '2%'
        },
        tooltip: {
            trigger: 'axis', // 增加触发方式，方便触碰
            axisPointer: { type: 'shadow' },
            confine: true,
            formatter: (params) => {
                const data = params[0].data;
                return `
                    <div style="padding: 10px; line-height: 1.8;">
                        <b style="color:#36c6d9; font-size:14px">${data.name}</b><br/>
                        <span style="color:#999">Identifier:</span> ${data.identifier}<br/>
                        <span style="color:#999">Datasets:</span> <b style="color:#36c6d9">${data.datasets_count}</b><br/>
                        <hr style="border:none; border-top:1px solid #eee; margin:3px 0;">
                        <div style="font-size:12px; color:#666; max-width:220px; white-space:pre-wrap;line-height: 1.0; margin-top: 0;">
                            ${data.description || 'No description'}
                        </div>
                    </div>
                `;
            }
        },
        xAxis: {
            type: 'value',
            name: 'Count',
            splitLine: { lineStyle: { type: 'dashed' } }
        },
        yAxis: {
            type: 'category',
            axisLabel: {
                // 3. 彻底去掉截断逻辑，直接返回完整的 name
                formatter: name => name,
                margin: 15,
                color: '#666',
                fontSize: 12,
                interval: 0, // 确保每一个标签都显示
            },
            axisTick: { show: false },
            data: processedData.map(item => item.name),
            inverse: true
        },
        series: [{
            name: 'Datasets',
            type: 'bar',
            data: processedData,
            barWidth: '60%',
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: '#83bff6' },
                    { offset: 0.5, color: '#188df0' },
                    { offset: 1, color: '#188df0' }
                ]),
                borderRadius: [0, 5, 5, 0]
            },
            label: {
                show: true,
                position: 'right',
                formatter: '{c}',
                color: '#36c6d9',
                fontWeight: 'bold'
            }
        }],
        dataZoom: [
            {
                type: 'slider',
                yAxisIndex: 0,
                startValue: 0,
                endValue: 7,
                width: 20,
                right: 10,
                borderColor: 'transparent',
                fillerColor: 'rgba(54,198,217,0.2)',
                showDetail: false
            },
            {
                type: 'inside',
                yAxisIndex: 0
            }
        ]
    };
    leftBottomChartInstance.setOption(option);
}

// 处理窗口缩放
const handleResize = () => {
  leftTopChartInstance?.resize();
  leftBottomChartInstance?.resize();
};

// 在函数内添加工具方法
function splitLongDescription(desc, maxLen = 35) {
    if (desc.length <= maxLen) return desc;
    const part1 = desc.substr(0, Math.floor(maxLen/2));
    const part2 = desc.substr(Math.floor(maxLen/2));
    return `${part1}<br>${part2}`;
}
</script>

<style lang='less' scoped>
.dashboard-container {
  display: flex;
  height: 100vh;
  padding: 15px;
  gap: 15px;
  /* 3. 必须设置为 relative，否则 Logo 会相对于浏览器窗口定位 */
  position: relative; 

  /* 4. Logo 的浮动样式控制 */
  .floating-logo {
    position: absolute;
    top: 25px;    /* 距离顶部边距 */
    right: 30px;  /* 距离右侧边距 */
    height: 70px; /* 设置高度，宽度会自动按比例缩放 */
    width: auto;
    z-index: 999; /* 确保 Logo 位于所有图表之上 */
    
    /* 如果 Logo 遮挡了右上角图表的交互（如全屏、下载按钮），开启下面这行 */
    /* pointer-events: none; */
    
    /* 可选：如果 Logo 背景色与图表冲突，可以加一个微弱的半透明背景或投影 */
    // filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
  }

  .left-panel, .right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 15px;

    .chart-box {
      flex: 1; 
      position: relative;
      background: white;
      border-radius: 12px;
      box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
      overflow: hidden;

      .chart-container {
        width: 100%;
        height: 100%;
      }
    }
  }
}
</style>