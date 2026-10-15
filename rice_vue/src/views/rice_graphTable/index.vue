<template>
  <div class="main-container" v-if="!showSv_id">
    <div 
        class="sidebar-mask"
        v-show="isCollapsed"
        @click="toggleSidebar"
    ></div>
    <!-- 新增侧边栏 -->
    <div 
      class="side-collapse" 
      :class="{ 'is-expanded': isCollapsed }"
      @click="toggleSidebar"
    >
      <div class="sidebar-content">
        <div class="toggle-button">
          <el-icon :size="24">
            <component :is="isCollapsed ? 'ArrowLeft' : 'ArrowRight'" />
          </el-icon>
        </div>
        <div class="sidebar-body">
            <!-- 这里添加侧边栏内容 -->
            <div v-if="graphTableData">
                <el-card v-if="selectedIndex === 0" style="overflow: scroll;">
                    <h1 style="text-align: center; color: #2fb9c2; margin-top: auto;">BasicInfo</h1>
                    <el-descriptions border :column="1" v-if="graphTableData" title="BasicInfo" >
                        <el-descriptions-item label="Gene_ID:">{{ graphTableData.table['Gene ID'] }}</el-descriptions-item>
                        <el-descriptions-item label="OGI#|Score:">{{ graphTableData.table['OGI#|Score'] }}</el-descriptions-item>
                        <el-descriptions-item label="Accession:">{{ graphTableData.table.Accession }}</el-descriptions-item>
                        <el-descriptions-item label="Location:">{{ graphTableData.table.Location }}</el-descriptions-item>
                        <el-descriptions-item label="Mutant:">
                            <el-descriptions border :column="1" v-if="graphTableData.table.Mutant !== '-'"> 
                                <el-descriptions-item v-for="(item,index) in graphTableData.table.Mutant" :key="index" :label="item.name">
                                    {{ item.URL }}
                                </el-descriptions-item>
                            </el-descriptions>
                            <span v-else>{{ graphTableData.table.Mutant }}</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="Function:">{{ graphTableData.table.Function }}</el-descriptions-item>
                        <el-descriptions-item label="Strand:">{{ graphTableData.table.Strand }}</el-descriptions-item>
                        <el-descriptions-item label="Structural Variations:">
                            <template v-if="graphTableData.table['Structural Variations']?.length">
                                <!-- 直接遍历数组渲染 -->
                                <span 
                                v-for="(item, index) in graphTableData.table['Structural Variations']" 
                                :key="index"
                                class="variation-item"
                                >
                                    <span @click="handleVariationClick(item)">
                                        {{ escapeHTML(String(item)) }}
                                    </span>
                                    <!-- 添加逗号分隔符（最后一个不添加） -->
                                    <span v-if="index !== graphTableData.table['Structural Variations'].length - 1">, </span>
                                </span>
                            </template>
                        <span v-else class="no-data">N/A</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="URL:">
                            <template #default>
                                <a :href="graphTableData.table.URL" target="_blank" rel="noopener noreferrer">
                                    {{ graphTableData.table.URL }}
                                </a>
                            </template>
                        </el-descriptions-item>
                    </el-descriptions>
                    <el-divider />
                    <el-descriptions border :column="1" v-if="graphTableData" title="Transcript"> 
                        <el-descriptions-item v-for="(item,index) in graphTableData.table.Transcript" :key="index" :label="index+'ID'">
                            {{ item }}
                        </el-descriptions-item>
                    </el-descriptions>
                </el-card>
                
                <el-card v-if="selectedIndex === 1" style="overflow: scroll;">
                    <h1 style="text-align: center; color: #2fb9c2; margin-top: auto;">ExpressionInfo</h1>
                    <el-descriptions border :column="2" v-if="graphTableData" title="ExpressionInfo" direction="vertical">  
                        <el-descriptions-item label="gene">{{ graphTableData.table.gene }}</el-descriptions-item>
                        <el-descriptions-item label="leaf">{{ graphTableData.table.leaf }}</el-descriptions-item>
                        <el-descriptions-item label="panicle">{{ graphTableData.table.panicle }}</el-descriptions-item>
                        <el-descriptions-item label="root">{{ graphTableData.table.root }}</el-descriptions-item>
                    </el-descriptions>
                </el-card>

                <el-card v-if="selectedIndex === 2" style="overflow: scroll;">
                    <h1 style="text-align: center; color: #2fb9c2; margin-top: auto;">HomologuesInfo</h1>
                    <el-table :data="graphTableData.table" style="width: 100%" v-if="graphTableData" >
                        <el-table-column prop="Homologues" label="Homologues" />
                        <el-table-column prop="type" label="Type"  />
                        <el-table-column label="Expression(FPKM)">
                            <el-table-column prop="Leaf" label="Leaf" width="120" />
                            <el-table-column prop="Root" label="Root" width="120" />
                            <el-table-column prop="Panicle" label="Panicle" width="120" />
                        </el-table-column>
                    </el-table>
                </el-card>
            </div>
            <div v-if="!graphTableData">
                <h1>No information available</h1>
            </div>
        </div>
      </div>
    </div>

    <div class="search">
        <!-- 搜索容器 -->
        <div class="search-container">
            <input 
            type="text" 
            placeholder="Please enter gene ID..."
            class="search-input"
            v-model="inputId"
            @keyup.enter="handleSearch()"
            @focus="showHistory = true"
            @blur="onInputBlur"
            >
            <div class="suggestions" v-show="showHistory && filteredHistory.length">
                <div 
                    v-for="(item, index) in filteredHistory"
                    :key="index"
                    class="suggestion-item"
                    @mousedown.prevent="selectHistory(item)"
                    v-html="highlightMatch(item, inputId)"
                    >
                </div>
            </div>
            <button 
                class="search-button"
                @click="handleSearch()"
                >
                <span class="button-text">Search</span>
                <div class="hover-effect"></div>
            </button>
        </div>
    </div>

    <div class="graphBanner">
        <div class="left">
            <div class="inquire"
                v-for="(item,index) in inquireRice" 
                :key="index"
                :class = "{active: selectedIndex === index}"
                @click="selectInquire(index)">
                {{ item }}
            </div>
        </div>
        <div class="right">
            <div ref="chartRef" class="graph"></div>
        </div>
    </div>
  </div>

  <!-- Svid展示 -->
    <div class="mainSV_id" v-if="showSv_id">
        <div class="head">
            <h1>Stuctural Variations</h1>
        </div>
        <div class="search">
            <!-- 搜索容器 -->
            <div class="search-container">
                <input 
                type="text" 
                placeholder="Please enter gene ID..."
                class="search-input"
                v-model="inputSvId"
                @keyup.enter="handleSearchSvid()"
                @focus="showHistory = true"
                @blur="onInputBlur"
                >
                <div class="suggestions" v-show="showHistory && filteredHistory.length">
                    <div 
                        v-for="(item, index) in filteredHistory"
                        :key="index"
                        class="suggestion-item"
                        @mousedown.prevent="selectHistory(item,666)"
                        v-html="highlightMatch(item, inputSvId)"
                        >
                    </div>
                </div>
                <button 
                class="search-button"
                @click="handleSearchSvid()"
                >
                <span class="button-text">Search</span>
                <div class="hover-effect"></div>
                </button>
            </div>
        </div>
        
        <div class="graphBanner">
            <div class="Banner">
                <div ref="chartSvRef" class="graph"></div>
            </div>
            <!-- 表格展示 -->
            <div class="Svtable">
                <el-descriptions border :column="1" title="Stuctural Variations"> 
                    <template #extra>
                        <el-button type="primary" color="#2fb9c2" plain @click="showSv_id = false">Back</el-button>
                    </template>
                    <el-descriptions-item label="Chromosome ">{{ svGraphTableData.table.Chromosome }}</el-descriptions-item>
                    <el-descriptions-item label="Query End">{{ svGraphTableData.table['Query End'] }}</el-descriptions-item>
                    <el-descriptions-item label="Query Genome">{{ svGraphTableData.table['Query Genome'] }}</el-descriptions-item>
                    <el-descriptions-item label="Query Start">{{ svGraphTableData.table['Query Start'] }}</el-descriptions-item>
                    <el-descriptions-item label="Ref End">{{ svGraphTableData.table['Ref End'] }}</el-descriptions-item>
                    <el-descriptions-item label="Ref Genome">{{ svGraphTableData.table['Ref Genome'] }}</el-descriptions-item>
                    <el-descriptions-item label="Ref Start">{{ svGraphTableData.table['Ref Start'] }}</el-descriptions-item>
                    <el-descriptions-item label="SV Length">{{ svGraphTableData.table['SV Length'] }}</el-descriptions-item>
                    <el-descriptions-item label="Variant Type">{{ svGraphTableData.table['Variant Type'] }}</el-descriptions-item>
                    <el-descriptions-item label="Variation ID">{{ svGraphTableData.table['Variation ID'] }}</el-descriptions-item>
                </el-descriptions>
            </div>
        </div>
    </div>
</template>

<script setup>
import { 
    getExpressionInfo,
    getGeneBasicInfo,
    getHomologuesInfo,
    getSVInfo
} from '../../api/rice_graphTable';
import { ref,computed } from 'vue';
import * as echarts from 'echarts';
import { ElMessage } from 'element-plus'

// 展示sv_id信息
let showSv_id = ref(false)
let svGraphTableData = ref()
let inputSvId = ref('')
// Sv输入查询
const handleSearchSvid = () => {
    getSVInfoData(inputSvId.value)
}
const chartSvRef = ref(null) 
let chartSvInstance = ref(null) //sv图表实例
// sv图形绘制函数
function updateChartOfSvGraph(graphData) {
    chartSvInstance.value = echarts.init(chartSvRef.value);
    
    // 动态生成分类配置
    const categories = [
        { name: 'Gene', itemStyle: { color: '#FF6B6B' } },
        { name: 'Chromosome', itemStyle: { color: '#4ECDC4' } },
        { name: 'Position', itemStyle: { color: '#45B7D1' } },
        { name: 'Strand', itemStyle: { color: '#96CEB4' } },
        { name: 'Accession', itemStyle: { color: '#FFEEAD' } },
        { name: 'OGI', itemStyle: { color: '#D4A5A5' } },
        { name: 'StructuralVariations', itemStyle: { color: '#11CC99' } },
        { name: 'Transcript', itemStyle: { color: '#A8D8B9' } },
    ];

    // 节点样式映射配置
    const nodeStyleMap = {
        'Gene': { symbolSize: 80, color: '#FF6B6B' },
        'Chromosome': { symbolSize: 60, color: '#4ECDC4' },
        'Position': { symbolSize: 40, color: '#45B7D1' },
        'Strand': { symbolSize: 30, color: '#96CEB4' },
        'Accession': { symbolSize: 50, color: '#FFEEAD' },
        'OGI': { symbolSize: 70, color: '#D4A5A5' },
        'StructuralVariations': { symbolSize: 65, color: '#99CC99' },
        'Transcript': { symbolSize: 55, color: '#A8D8B9' }
    };

    // 转换节点数据
    const nodes = graphData.graph.data.map(node => ({
        id: node.ID,
        name: node.name,
        category: categories.findIndex(cat => cat.name === node.label),
        label: {
            show: true,
            formatter: '{b}',
            fontSize: node.label === 'Gene' ? 14 : 12
        },
        symbolSize: nodeStyleMap[node.label]?.symbolSize || 40,
        itemStyle: {
            color: typeof nodeStyleMap[node.label]?.color === 'function' 
                 ? nodeStyleMap[node.label].color(node)
                 : nodeStyleMap[node.label]?.color || '#666'
        },
        tooltip: {
            formatter: params => {
                const info = [
                    `Type: ${node.label}`,
                    `name: ${node.name}`,
                    ...Object.entries(node)
                        .filter(([k]) => !['ID','label','name'].includes(k))
                        .map(([k,v]) => `${k}: ${v}`)
                ];
                return info.join('<br>');
            }
        }
    }));

    // 转换边数据
    const links = graphData.graph.links.map(link => ({
        source: link.source,
        target: link.target,
        lineStyle: {
            color: getLinkColor(link.value),
            width: 2,
            type: link.value === 'in_this_region' ? 'dashed' : 'solid'
        },
        label: {
            show: true,
            formatter: link.value.replace(/_/g, ' '),
            fontSize: 10
        }
    }));

    const option = {
        title: {
            text: 'SVInfo Network',
            textStyle: {
                fontSize: 20,
                color: '#2c3e50'
            }
        },
        tooltip: {},
        legend: {
            orient: 'horizontal',
            top: 50,
            itemGap: 20, 
            itemWidth: 20, 
            itemHeight: 12,
            data: categories.map(cat => cat.name),
            textStyle: {
                color: '#666'
            },
            selected: Object.fromEntries(
                categories.map(cat => [cat.name, true])
            )
        },
        series: [{
            type: 'graph',
            layout: 'force',
            force: {
                repulsion: 200,
                edgeLength: 300,
                gravity: 0.05,
                friction: 0.6
            },
            draggable: true,
            roam: true,
            emphasis: {
                focus: 'adjacency'
            },
            categories,
            nodes,
            links,
            edgeLabel: {
                show: true,
                color: '#666',
                fontSize: 10
            },
            lineStyle: {
                curveness: 0.3,
                opacity: 0.8
            }
        }]
    };

    chartSvInstance.value.setOption(option);
    // 监听图例点击事件
    chartSvInstance.value.on('legendselectchanged', (params) => {
        const selectedCategories = new Set(Object.keys(params.selected).filter(key => params.selected[key]));
        
        // 更新节点可见性
        nodes.forEach(node => {
            const categoryName = categories[node.category].name;
            node.itemStyle.opacity = selectedCategories.has(categoryName) ? 1 : 0;
            node.label.show = selectedCategories.has(categoryName);
        });

        // 更新边可见性
        links.forEach(link => {
            const sourceNode = nodes.find(n => n.id === link.source);
            const targetNode = nodes.find(n => n.id === link.target);
            const sourceVisible = selectedCategories.has(categories[sourceNode.category].name);
            const targetVisible = selectedCategories.has(categories[targetNode.category].name);
            link.lineStyle.opacity = (sourceVisible && targetVisible) ? 1 : 0;
        });

        // 更新图表
        chartSvInstance.value.setOption({
            series: [{
                nodes: nodes,
                links: links
            }]
        });
    });
    window.addEventListener('resize', () => chartSvInstance.value.resize());
}

// sv_id点击查询
const handleVariationClick = (sv_id) => {
    getSVInfoData(sv_id)
};

// 正确展示表格信息Structural Variations
const escapeHTML = (str) => {
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
};

// 侧边栏状态
const isCollapsed = ref(localStorage.getItem('sidebarCollapsed') !== 'false')
const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sidebarCollapsed', isCollapsed.value)
}

// 查询信息
const inquireRice = ['BasicInfo','ExpressionInfo','HomologuesInfo']
let selectedIndex = ref(0)
let selectBack = -1
const selectInquire = (index) =>{
    selectBack = selectedIndex.value
    selectedIndex.value = index
    graphTableData.value = null
    if(inputId.value !== ''){
        handleSearch()
    }
}

// 新增响应式数据
const showHistory = ref(false);
const searchHistory = ref(JSON.parse(localStorage.getItem('geneSearchHistory')) || []);

// 计算属性输入历史
const filteredHistory = computed(() => {
  return searchHistory.value
    .filter(item => item.toLowerCase().includes(inputId.value.toLowerCase()))
    .slice(0, 5); // 最多显示5条
});

// 选择历史方法
const selectHistory = (item,flag = 0) => {
  inputId.value = item;
  if(flag === 0){
    handleSearch();
  }else{
    handleSearchSvid()
  }
  showHistory.value = false;
};

// 保存历史记录
const saveSearchHistory = (query) => {
  // 去重处理
  const index = searchHistory.value.findIndex(item => item === query);
  if (index !== -1) {
    searchHistory.value.splice(index, 1);
  }
  // 添加到开头
  searchHistory.value.unshift(query);
  // 保留最近10条
  if (searchHistory.value.length > 10) {
    searchHistory.value.pop();
  }
  localStorage.setItem('geneSearchHistory', JSON.stringify(searchHistory.value));
};

// 高亮输入信息
const highlightMatch = (text, match) => {
  if (!match) return text;
  const regex = new RegExp(`(${match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
};
const onInputBlur = () => {
  setTimeout(() => {
    showHistory.value = false;
  }, 200);
};

// 查询函数
let inputId = ref('')
const handleSearch = () =>{
    inputId.value = inputId.value.replace(/\s+/g, '')
    const query = inputId.value.replace(/\s+/g, '');
    if (query) {
        saveSearchHistory(query);
        if(selectedIndex.value === 0){
            getGeneBasicInfoData(inputId.value)
        }else if(selectedIndex.value === 1){
            getExpressionInfoData(inputId.value)
        }else if(selectedIndex.value === 2){
            getHomologuesInfoData(inputId.value)
        }
    }
    showHistory.value = false;
    // inputId.value = ''
}

// 图标实例
const chartRef = ref(null)
let chartInstance = ref(null); // ECharts 实例

//图形绘制函数
function updateChartOfGraph(graphData) {
    if (chartRef.value) {
        chartInstance.value = echarts.init(chartRef.value);
    }

    // 动态生成分类配置
    const categories = Array.from(new Set(graphData.graph.data.map(node => node.label)))
        .map((label, index) => {
            // 动态生成颜色（基于固定颜色数组或随机生成）
            const color = generateColor(index);
            return {
                name: label,
                itemStyle: { color }
            };
        });

    // 动态生成节点样式映射配置
    const nodeStyleMap = categories.reduce((map, category) => {
        map[category.name] = {
            symbolSize: getSymbolSizeByLabel(category.name), // 根据标签动态设置大小
            color: category.itemStyle.color // 使用 categories 中的颜色
        };
        return map;
    }, {});

    // 转换节点数据
    const nodes = graphData.graph.data.map(node => ({
        id: node.ID,
        name: node.name,
        category: categories.findIndex(cat => cat.name === node.label),
        label: {
            show: true,
            formatter: '{b}',
            fontSize: node.label === 'Gene' ? 14 : 12
        },
        symbolSize: nodeStyleMap[node.label]?.symbolSize || 40,
        itemStyle: {
            color: typeof nodeStyleMap[node.label]?.color === 'function' 
                 ? nodeStyleMap[node.label].color(node)
                 : nodeStyleMap[node.label]?.color || '#666'
        },
        tooltip: {
            formatter: params => {
                const info = [
                    `Type: ${node.label}`,
                    `name: ${node.name}`,
                    ...Object.entries(node)
                        .filter(([k]) => !['ID','label','name'].includes(k))
                        .map(([k,v]) => `${k}: ${v}`)
                ];
                return info.join('<br>');
            }
        }
    }));

    // 转换边数据
    const links = graphData.graph.links.map(link => ({
        source: link.source,
        target: link.target,
        lineStyle: {
            color: getLinkColor(link.value),
            width: 2,
            type: link.value === 'in_this_region' ? 'dashed' : 'solid'
        },
        label: {
            show: true,
            formatter: link.value.replace(/_/g, ' '),
            fontSize: 10
        }
    }));

    const option = {
        title: {
            text: 'Gene Relationship Network',
            textStyle: {
                fontSize: 20,
                color: '#2c3e50'
            }
        },
        tooltip: {},
        legend: {
            orient: 'horizontal',
            top: 50,
            itemGap: 20, 
            itemWidth: 20, 
            itemHeight: 12,
            data: categories.map(cat => cat.name),
            textStyle: {
                color: '#666'
            },
            selected: Object.fromEntries(
                categories.map(cat => [cat.name, true])
            )
        },
        series: [{
            type: 'graph',
            layout: 'force',
            force: {
                repulsion: 200,
                edgeLength: 300,
                gravity: 0.05,
                friction: 0.6
            },
            draggable: true,
            roam: true,
            emphasis: {
                focus: 'adjacency'
            },
            categories,
            nodes,
            links,
            edgeLabel: {
                show: true,
                color: '#666',
                fontSize: 10
            },
            lineStyle: {
                curveness: 0.3,
                opacity: 0.8
            }
        }]
    };

    // 初始化图表
    chartInstance.value.setOption(option);

    // 监听图例点击事件
    chartInstance.value.on('legendselectchanged', (params) => {
        const selectedCategories = new Set(Object.keys(params.selected).filter(key => params.selected[key]));
        
        // 更新节点可见性
        nodes.forEach(node => {
            const categoryName = categories[node.category].name;
            node.itemStyle.opacity = selectedCategories.has(categoryName) ? 1 : 0;
            node.label.show = selectedCategories.has(categoryName);
        });

        // 更新边可见性
        links.forEach(link => {
            const sourceNode = nodes.find(n => n.id === link.source);
            const targetNode = nodes.find(n => n.id === link.target);
            const sourceVisible = selectedCategories.has(categories[sourceNode.category].name);
            const targetVisible = selectedCategories.has(categories[targetNode.category].name);
            link.lineStyle.opacity = (sourceVisible && targetVisible) ? 1 : 0;
        });

        // 更新图表
        chartInstance.value.setOption({
            series: [{
                nodes: nodes,
                links: links
            }]
        });
    });

    // 监听节点点击事件
    chartInstance.value.off('click');
    chartInstance.value.on('click', params => {
        if(categories[params.data.category].name === 'StructuralVariations'){
            handleVariationClick(params.data.name)
        }
    });

    window.addEventListener('resize', () => chartInstance.value.resize());
}

// Homelog图像绘制函数
function updateChartOfGraphHomeloguesInfo(graphData) {
    if (chartRef.value) {
        chartInstance.value = echarts.init(chartRef.value);
    }
    // 分类配置（与边的分类一致）
    // 修改分类配置（添加颜色属性）
    const categories = [
        { name: 'RBH', itemStyle: { color: '#FF6B6B' } },
        { name: 'SBH', itemStyle: { color: '#4ECDC4' } },
        { name: 'Root', itemStyle: { color: '#45B7D1' } }
    ];

    // 节点样式配置
    const nodeStyleMap = {
        'RBH': { symbolSize: 30, color: '#FF6B6B' },
        'SBH': { symbolSize: 30, color: '#4ECDC4' },
        'Root': { symbolSize: 40, color: '#45B7D1' },
        'default': { symbolSize: 30, color: '#666' }
    };

    // 边样式配置
    const linkStyleMap = {
        'RBH': { color: '#FF6B6B', curveness: 0.3 },
        'SBH': { color: '#4ECDC4', curveness: 0.3 },
        'Root': { color: '#45B7D1', curveness: 0.3 }, 
        default: { color: '#ddd', curveness: 0.1 }
    };

    // 自动布局计算
    const centerNode = graphData.graph.data.find(node => node.label === 'Root') || graphData.graph.data[0]; // 中心节点
    const otherNodes = graphData.graph.data.filter(node => node !== centerNode);
    const radius = 180 + (otherNodes.length * 8); // 动态半径

    // 转换节点数据
    const nodes = graphData.graph.data.map((node, index) => {
        // 确定节点类别
        let category;
        if (node === centerNode) {
            category = 'Root'; // 中心节点为Root
        } else {
            // 查找与中心节点相连的边，确定节点类别
            const link = graphData.graph.links.find(link => link.source === centerNode.ID && link.target === node.ID);
            category = link ? link.value : 'default';
        }

        // 计算坐标
        let x = 0, y = 0;
        if (node !== centerNode) {
            const nodeIndex = otherNodes.indexOf(node);
            if (nodeIndex !== -1) {
                const angle = (2 * Math.PI * nodeIndex) / otherNodes.length;
                x = radius * Math.cos(angle);
                y = radius * Math.sin(angle);
            }
        }

        return {
            id: node.ID,
            name: node.name,
            category: categories.findIndex(cat => cat.name === category), // 节点类别索引
            x, y,
            label: {
                show: true,
                fontSize: 10,
                color: '#666', // 节点名称字体颜色
                position: 'inside'
            },
            symbolSize: nodeStyleMap[category]?.symbolSize || nodeStyleMap.default.symbolSize,
            itemStyle: {
                color: nodeStyleMap[category]?.color || nodeStyleMap.default.color
            },
            tooltip: {
                formatter: () => [
                    `Name: ${node.name}`,
                    `Label: ${node.label}`,
                    `URL: ${node.URL}`
                ].join('<br>')
            }
        };
    });

    // 转换边数据
    const links = graphData.graph.links.map(link => {
        const linkType = link.value || 'RBH';
        return {
            source: link.source,
            target: link.target,
            value: linkType,
            lineStyle: {
                ...linkStyleMap[linkType] || linkStyleMap.default,
                width: 1.5,
                opacity: 0.9
            }
        };
    });

    const option = {
        title: {
            text: 'Gene Relationship Network',
            textStyle: {
                fontSize: 20,
                color: '#2c3e50',
                fontWeight: 'normal'
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: params => params.value ? params.value : params.data.tooltip.formatter()
        },
        legend: {
            data: categories.map(cat => ({
                name: cat.name,
                itemStyle: { color: cat.itemStyle.color } 
            })),
            orient: 'horizontal', 
            top: 30, 
            textStyle: {
                color: '#666',
                fontSize: 14
            },
            itemGap: 20, 
            itemWidth: 20, 
            itemHeight: 12,
            selected: Object.fromEntries(
                categories.map(cat => [cat.name, true])
            )
        },
        series: [{
            type: 'graph',
            layout: 'none',
            roam: true,
            draggable: false,
            edgeSymbol: ['none', 'arrow'],
            edgeSymbolSize: 8,
            categories,
            nodes,
            links: links.map(link => ({
                ...link,
                lineStyle: {
                    ...linkStyleMap[link.value] || linkStyleMap.default,
                    width: 1.5,
                    opacity: 0.9
                }
            })),
            lineStyle: {
                opacity: 0.8
            },
            edgeLabel: {
                show: true,
                formatter: '{@value}',
                fontSize: 12,
                color: '#666',
                backgroundColor: 'rgba(255,255,255,0.9)',
                padding: [3, 5]
            },
            emphasis: {
                disabled: true
            }
        }]
    };

    chartInstance.value.setOption(option);
    // 监听图例点击事件
    chartInstance.value.on('legendselectchanged', (params) => {
        const selectedCategories = new Set(Object.keys(params.selected).filter(key => params.selected[key]));
        
        // 更新节点可见性
        nodes.forEach(node => {
            const categoryName = categories[node.category].name;
            node.itemStyle.opacity = selectedCategories.has(categoryName) ? 1 : 0;
            node.label.show = selectedCategories.has(categoryName);
        });

        // 更新边可见性
        links.forEach(link => {
            const sourceNode = nodes.find(n => n.id === link.source);
            const targetNode = nodes.find(n => n.id === link.target);
            const sourceVisible = selectedCategories.has(categories[sourceNode.category].name);
            const targetVisible = selectedCategories.has(categories[targetNode.category].name);
            link.lineStyle.opacity = (sourceVisible && targetVisible) ? 1 : 0;
        });

        // 更新图表
        chartInstance.value.setOption({
            series: [{
                nodes: nodes,
                links: links
            }]
        });
    });

    // 监听节点点击事件
    chartInstance.value.off('click');
    chartInstance.value.on('click', params => {
        // console.log(params.data)
        inputId.value = params.data.name
        handleSearch();
    });
    window.addEventListener('resize', () => chartInstance.value.resize());
}

// 辅助函数：根据关系类型获取连接线颜色
function getLinkColor(relationType) {
    const colorMap = {
        'chromosome_no': '#3498db',
        'start_pos': '#e74c3c',
        'end_pos': '#e67e22',
        'strand_info': '#2ecc71',
        'has_a_transcript': '#9b59b6',
        'in_this_region': '#f1c40f'
    };
    return colorMap[relationType] || '#95a5a6';
}

// 动态设置节点颜色和大小
function generateColor(index) {
    // 使用固定颜色数组
    const colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
        '#FFEEAD', '#D4A5A5', '#11CC99', '#A8D8B9',
        '#FF9999', '#99CC99', '#FFCC99', '#99CCFF'
    ];
    return colors[index % colors.length]; // 循环使用颜色
}
function getSymbolSizeByLabel(label) {
    const sizeMap = {
        'Gene': 80,
        'Chromosome': 60,
        'Position': 40,
        'Strand': 30,
        'Accession': 50,
        'OGI': 70,
        'StructuralVariations': 65,
        'Transcript': 55
    };
    return sizeMap[label] || 40; // 默认大小为 40
}



// 存储查询数据
let graphTableData = ref()

// 查询ExpressionInfo
function getExpressionInfoData(gene_id){
    getExpressionInfo(gene_id)
    .then(res =>{
        console.log(res.data)
        ElMessage({
            type: 'success',
            message: 'Query successful'
        })
        graphTableData.value = res.data
        if (chartInstance.value) {
            chartInstance.value.dispose(); // 销毁实例
            chartInstance.value = null;
        }
        updateChartOfGraph(graphTableData.value)
    }).catch(err =>{
        console.log(err)
        ElMessage({
            type: 'error',
            message: 'Query failed'
        })
        selectedIndex.value = selectBack
    })
}

// 查询GeneBasicInfo
function getGeneBasicInfoData(gene_id){
    getGeneBasicInfo(gene_id)
    .then(res =>{
        console.log(res.data)
        ElMessage({
            type: 'success',
            message: 'Query successful'
        })
        graphTableData.value = res.data
        if (chartInstance.value) {
            chartInstance.value.dispose(); // 销毁实例
            chartInstance.value = null;
        }
        updateChartOfGraph(graphTableData.value)
    }).catch(err =>{
        console.log(err)
        ElMessage({
            type: 'error',
            message: 'Query failed'
        })
        selectedIndex.value = selectBack
    })
}

// 查询HomologuesInfo
function getHomologuesInfoData(gene_id){
    getHomologuesInfo(gene_id)
    .then(res =>{
        console.log(res.data)
        ElMessage({
            type: 'success',
            message: 'Query successful'
        })
        graphTableData.value = res.data
        if (chartInstance.value) {
            chartInstance.value.dispose(); // 销毁实例
            chartInstance.value = null;
        }
        updateChartOfGraphHomeloguesInfo(graphTableData.value)
    }).catch(err => {
        console.log(err)
        ElMessage({
            type: 'error',
            message: 'Query failed'
        })
        selectedIndex.value = selectBack
    })
}

// 查询SVInfo
function getSVInfoData(sv_id){
    getSVInfo(sv_id)
    .then(res => {
        console.log(res.data)
        svGraphTableData.value = res.data
        ElMessage({
            type: 'success',
            message: 'Query successful'
        })
        showSv_id.value = true
        if (chartSvInstance.value) {
            chartSvInstance.value.dispose(); // 销毁实例
            chartSvInstance.value = null;
        }
        setTimeout(()=>{
            updateChartOfSvGraph(svGraphTableData.value)
        },500)
    }).catch(err => {
        console.log(err)
        ElMessage({
            type: 'error',
            message: 'Query failed'
        })
    })
}
</script>

<style lang='less' scoped>
.main-container{
    position: relative;
    height: 98vh;
    .search{
        height: 10%;
        padding: 1%;
        box-sizing: border-box;
        .search-container {
            position: relative;
            max-width: 80%;
            margin: 0 auto;
            display: flex;
            gap: 12px;
            height: 100%;
            align-items: center;
            
            // 保存历史记录
            .suggestions {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                max-height: 200px;
                overflow-y: auto;
                background: white;
                border: 1px solid #eee;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                z-index: 1000;
                margin-top: 4px;
            }

            .suggestion-item {
            padding: 8px 16px;
            cursor: pointer;
            transition: background 0.2s;
            color: #666;

            &:hover {
                background: #f5f7fa;
            }

            mark {
                background: rgba(47, 185, 194, 0.2);
                color: #2fb9c2;
                padding: 0 2px;
                border-radius: 2px;
            }
            }
            // 输入框样式
            .search-input {
                flex: 1;
                height: 80%;
                padding: 0 24px;
                border: none;
                border-radius: 30px;
                font-size: 16px;
                color: #2a2a2a;
                background: rgba(255, 255, 255, 0.95);
                box-shadow: 0 4px 20px rgba(47, 185, 194, 0.15);
                transition: all 0.3s ease;

            &::placeholder {
                color: #9e9e9e;
            }

            &:focus {
                outline: none;
                box-shadow: 0 4px 25px rgba(47, 185, 194, 0.3);
                border: 1px solid #2fb9c2;
            }
            }

            // 按钮样式
            .search-button {
                position: relative;
                height: 80%;
                padding: 0 36px;
                border: none;
                border-radius: 30px;
                background: #2fb9c2;
                color: white;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                overflow: hidden;
                transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);

            .button-text {
                position: relative;
                z-index: 2;
            }

            .hover-effect {
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(
                120deg,
                transparent,
                rgba(255, 255, 255, 0.3),
                transparent
                );
                transition: left 0.6s;
            }

            &:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 25px rgba(47, 185, 194, 0.4);

                .hover-effect {
                left: 100%;
                }
            }

            &:active {
                transform: translateY(0);
                background: darken(#2fb9c2, 8%);
            }
            }
        }
    }

    .graphBanner{
        height: 90%;
        display: flex;
        .left{
            display: flex;
            align-items: center;
            // justify-content: space-between;
            flex-direction: column;
            width: 10vw;
            height: 100%;
            // background-color: #fc8686;
            .inquire{
                display: flex;
                justify-content: center;
                align-items: center;
                text-align: center;
                flex: 1;
                width: 90%;
                min-width: 150px;
                max-height: 10%;
                margin-top: 20%;
                border: 1px solid #2fb9c2;
                color: #2fb9c2;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.3s ease;
                &:hover {
                    background-color: #2fb9c2;
                    color: white;
                }

                &.active {
                    background-color: #2fb9c2;
                    color: white;
                    border-color: #2fb9c2;
                }
            }
        }
        .right{
            flex: 1;
            height: 100%;
            transition: margin-right 0.3s;
            margin-right: 0;
            
            .side-collapse.is-expanded ~ .graphBanner & {
                margin-right: 50vw;
            }
            // background-color: #ffb8b8;
            .graph{
                width: 100%;
                height: 100%;
            }
        }
    }

    .side-collapse {
    position: fixed;
    right: 0;
    top: 0;
    height: 100vh;
    width: 50vw;
    background: white;
    box-shadow: -4px 0 15px rgba(0,0,0,0.1);
    z-index: 1000;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    transform: translateX(100%);
    
    &.is-expanded {
        transform: translateX(0);
    }

    .sidebar-content {
        position: relative;
        height: 100%;
        display: flex;

        .toggle-button {
            position: absolute;
            left: -40px;
            top: 50%;
            transform: translateY(-50%);
            width: 40px;
            height: 80px;
            background: white;
            border-radius: 8px 0 0 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: -4px 0 8px rgba(0,0,0,0.05);
            transition: all 0.3s;

            &:hover {
                background: #f5f7fa;
                box-shadow: -4px 0 12px rgba(0,0,0,0.1);
            }
        }

        .sidebar-body {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            // display: flex;
            // align-items: center;
            // justify-content: center;
            .variation-item {
                cursor: pointer;
                color: #409eff; /* 蓝色，类似链接 */
                text-decoration: underline;
            }

            .variation-item:hover {
                color: #66b1ff; /* 鼠标悬停时的颜色 */
            }
        }
    }
    }
    .sidebar-mask {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.3);
        z-index: 999;
    }
}

.mainSV_id{
    position: relative;
    height: 98vh;
    .head{
        width: 100%;
        height: 10%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #2fb9c2;
        box-sizing: border-box;
    }
    .search{
        height: 10%;
        padding: 1%;
        box-sizing: border-box;
        .search-container {
            position: relative;
            max-width: 80%;
            margin: 0 auto;
            display: flex;
            gap: 12px;
            height: 100%;
            align-items: center;
            // 保存历史记录
            .suggestions {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                max-height: 200px;
                overflow-y: auto;
                background: white;
                border: 1px solid #eee;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                z-index: 1000;
                margin-top: 4px;
            }

            .suggestion-item {
                padding: 8px 16px;
                cursor: pointer;
                transition: background 0.2s;
                color: #666;

                &:hover {
                    background: #f5f7fa;
                }

                mark {
                    background: rgba(47, 185, 194, 0.2);
                    color: #2fb9c2;
                    padding: 0 2px;
                    border-radius: 2px;
                }
            }
            // 输入框样式
            .search-input {
                flex: 1;
                height: 80%;
                padding: 0 24px;
                border: none;
                border-radius: 30px;
                font-size: 16px;
                color: #2a2a2a;
                background: rgba(255, 255, 255, 0.95);
                box-shadow: 0 4px 20px rgba(47, 185, 194, 0.15);
                transition: all 0.3s ease;

            &::placeholder {
                color: #9e9e9e;
            }

            &:focus {
                outline: none;
                box-shadow: 0 4px 25px rgba(47, 185, 194, 0.3);
                border: 1px solid #2fb9c2;
            }
            }

            // 按钮样式
            .search-button {
                position: relative;
                height: 80%;
                padding: 0 36px;
                border: none;
                border-radius: 30px;
                background: #2fb9c2;
                color: white;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                overflow: hidden;
                transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);

            .button-text {
                position: relative;
                z-index: 2;
            }

            .hover-effect {
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(
                120deg,
                transparent,
                rgba(255, 255, 255, 0.3),
                transparent
                );
                transition: left 0.6s;
            }

            &:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 25px rgba(47, 185, 194, 0.4);

                .hover-effect {
                left: 100%;
                }
            }

            &:active {
                transform: translateY(0);
                background: darken(#2fb9c2, 8%);
            }
            }
        }
    }
    .graphBanner{
        width: 100%;
        height: 80%;
        display: flex;
        .Banner{
            width: 70%;
            height: 100%;
            transition: margin-right 0.3s;
            margin-right: 0;
            
            .side-collapse.is-expanded ~ .graphBanner & {
                margin-right: 50vw;
            }
            // background-color: #ffb8b8;
            .graph{
                width: 100%;
                height: 100%;
            }
        }
        .table{
            flex: 1;
            height: 100%;

        }
    }
}
</style>