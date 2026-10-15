<template>
    <div class="header">
      <div class="card">
        <div 
        class="inquire"
        v-for="(item,index) in inquiriesClass"
        :key="index"
        :class="{ active: selectedIndex === index }"
        @click="selectInquire(index)"
        >
          {{ item }}
        </div>
      </div>
    </div>
    <!-- eslint-disable  -->
    <div class="pagination" >
        <el-table :data="inquireData" v-show="!WatchAllNewBool">
          <el-table-column prop="identifier" label="ID" />
          <el-table-column prop="name" label="Name" />
          <el-table-column label="Description" width="500px">
            <template #default="{ row }">
                <el-tooltip 
                  effect="dark" 
                  placement="bottom"
                >
                  <template #content>
                    <div style="white-space: pre-line">
                      {{ row.describe.split('。').join('。\n') }}
                    </div>
                  </template>
                  <div class="describe-text">
                    {{ row.describe.length > 50 ? row.describe.slice(0, 50) + '...' : row.describe }}
                  </div>
                </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="View" width="300px">
            <template #header>
              <el-input v-model="searchKeyword"  placeholder="Search"  style="width: 250px" :prefix-icon="Search" @input="handleInput" clearable>
                <template #append>
                  <el-button type="success" color="#2fb9c2" plain :icon="Search" @click="handleInput"/>
                </template>
              </el-input>
            </template>
            <template #default="{ row }">
              <el-button 
                type="success" 
                color="#2fb9c2" 
                plain 
                @click="lookAllNewData(row)"
              >
                View Details
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 详细信息展示 -->
        <div v-if="WatchAllNewBool" class="cardBanner">
          <el-descriptions
            :column="1"
            border
            :title="AllNewBoolData.title + ' - ' + AllNewBoolData.name"
            direction="vertical"
          >
            <template #extra>
              <el-button type="success" color="#2fb9c2" plain @click="backViews()">Back</el-button>
            </template>
             <!-- 公共属性 -->
            <el-descriptions-item label="Public Attributes">
              <el-descriptions :column="1" class="public_label">
                <el-descriptions-item label="Identifier:">{{ AllNewBoolData.identifier }}</el-descriptions-item>
                <el-descriptions-item label="Description:">{{ AllNewBoolData.describe }}</el-descriptions-item>
                <el-descriptions-item label="Registration Status:"><el-tag size="small">{{ AllNewBoolData.status }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="Create Time:">{{ AllNewBoolData.time }}</el-descriptions-item>
              </el-descriptions>
            </el-descriptions-item>
           
            <!-- 管理信息 -->
            <el-descriptions-item label="Management Information">
              <el-descriptions :column="1" border>
                <el-descriptions-item v-if="AllNewBoolData.version" label="Version">{{ AllNewBoolData.version }}</el-descriptions-item>
                <el-descriptions-item label="Creator ID">{{ AllNewBoolData.personId }}</el-descriptions-item>
                <el-descriptions-item label="Name">{{ AllNewBoolData.name }}</el-descriptions-item>
                <el-descriptions-item label="Creator Organization">{{ AllNewBoolData.department }}</el-descriptions-item>
              </el-descriptions>
            </el-descriptions-item>
            
            
            <el-descriptions-item label="Relationship" v-if="AllNewBoolData.object_class || AllNewBoolData.property || AllNewBoolData.conceptual_domain || AllNewBoolData.data_element_concept || AllNewBoolData.value_domain">
              <el-descriptions :column="1" border>
                <el-descriptions-item v-if="AllNewBoolData.object_class" label="Object Class">
                      {{ AllNewBoolData.object_class.name }} -> {{ AllNewBoolData.object_class.identifier }}
                    <el-icon @click="getDataByIdentifier(AllNewBoolData.object_class.identifier)" class="icon" :size="15"><View /></el-icon>
                </el-descriptions-item>
                <el-descriptions-item v-if="AllNewBoolData.property" label="Property">
                    {{ AllNewBoolData.property.name }} -> {{ AllNewBoolData.property.identifier }}
                    <el-icon @click="getDataByIdentifier(AllNewBoolData.property.identifier)" class="icon" :size="15"><View /></el-icon>
                </el-descriptions-item>
                <el-descriptions-item v-if="AllNewBoolData.conceptual_domain" label="Conceptual Domain">
                    {{ AllNewBoolData.conceptual_domain.name }} -> {{ AllNewBoolData.conceptual_domain.identifier }}
                    <el-icon @click="getDataByIdentifier(AllNewBoolData.conceptual_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                </el-descriptions-item>
                <el-descriptions-item v-if="AllNewBoolData.data_element_concept" label="Data Element Concept">
                    {{ AllNewBoolData.data_element_concept.name }} -> {{ AllNewBoolData.data_element_concept.identifier }}
                    <el-icon @click="getDataByIdentifier(AllNewBoolData.data_element_concept.identifier)" class="icon" :size="15"><View /></el-icon>
                </el-descriptions-item>
                <el-descriptions-item v-if="AllNewBoolData.value_domain" label="Value Domain">
                    {{ AllNewBoolData.value_domain.name }} -> {{ AllNewBoolData.value_domain.identifier }}
                    <el-icon @click="getDataByIdentifier(AllNewBoolData.value_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                </el-descriptions-item>
              </el-descriptions>
            </el-descriptions-item>
            

          </el-descriptions>
          <br>
          <!-- 可允许值 -->
          <div v-if="AllNewBoolData.value_meanings">
            <el-divider>{{ AllNewBoolData.valueTitle }}</el-divider>
            <div class="card-container">
              <el-card 
                v-for="(item,index) in AllNewBoolData.value_meanings"
                :key="index"
                class="custom-card"
              >
              <el-descriptions :column="1" border>
                <el-descriptions-item label="Identifier:">{{ item.identifier }}</el-descriptions-item>
                <el-descriptions-item label="Status:"><el-tag size="small">{{ item.status }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="Create Time:">{{ item.time }}</el-descriptions-item>
                <el-descriptions-item label="Version:">{{ item.version }}</el-descriptions-item>
                <el-descriptions-item label="Value Meaning:">{{ item.name }}</el-descriptions-item>
              </el-descriptions>
              </el-card>
            </div>
          </div>
          <!-- 值域 -->
          <div v-if="AllNewBoolData.permissible_values">
            <el-divider>{{ AllNewBoolData.valueTitle }}</el-divider>
            <div class="card-container">
              <el-card 
                v-for="(item,index) in AllNewBoolData.permissible_values"
                :key="index"
                class="custom-card"
              >
              <el-card>
                <el-descriptions :column="1">
                  <el-descriptions-item label="Identifier:">{{ item.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Value:">{{ item.name }}</el-descriptions-item>
              </el-descriptions>
              </el-card>
              <el-card style="margin-top: 15px">
                <el-descriptions :column="1"  >
                  <el-descriptions-item label="Identifier:">{{ item.value_meanings.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Value meaning:">{{ item.value_meanings.name }}</el-descriptions-item>
                  <el-descriptions-item label="Status:"><el-tag size="small">{{ item.value_meanings.status }}</el-tag></el-descriptions-item>
                  <el-descriptions-item label="Create Time:">{{ item.value_meanings.time }}</el-descriptions-item>
                  <el-descriptions-item label="Version:">{{ item.value_meanings.version }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
              </el-card>
            </div>
          </div>
        </div>

    </div>
</template>

<script setup>
import { ref, onMounted, computed,} from 'vue';
import { Search } from '@element-plus/icons-vue'
import { throttle,debounce } from '../../util/optimize';
import { 
  getConceptualDomainList,
  getDataElementConceptList,
  getObjectClassList,
  getPropertyList,
  getValueDomainList,
  getDataElementList,
  getConceptualDomainByIdentifier,
  getDataElementConceptByIdentifier,
  getObjectClassByIdentifier,
  getPropertyByIdentifier,
  getValueDomainByIdentifier,
} from '../../api/metadata_inquire';

// 模糊匹配搜索
let searchKeyword = ref('')
let tableData = {}
const searchResults = computed(() => {
  if (!searchKeyword.value.trim()) return Object.values(tableData);
  return Object.values(tableData).filter(item => {
    const searchFields = ['name', 'describe', 'department', 'identifier'];
    return searchFields.some(field => 
      String(item[field] ?? '').toLowerCase().includes(searchKeyword.value.toLowerCase())
    );
  });
});

const handleInput = debounce(() =>{
  if(searchKeyword.value === ''){
    inquireData.value = tableData;
  }else{
    inquireData.value = searchResults.value
  }
},300)

// 返回上个页面
function backViews(){
  if(viewFlag.value.length != 0){
    AllNewBoolData.value = viewFlag.value.pop();
    // viewFlag.value = false
  }else{
    selectInquire(selectedIndex.value)
  }
}

// 查看所有详细信息
let WatchAllNewBool = ref(false)
let AllNewBoolData = ref()
function lookAllNewData(row){
  WatchAllNewBool.value = true;
  AllNewBoolData.value = row;
  AllNewBoolData.value.title = inquiriesClass.value[selectedIndex.value]
  // console.log(AllNewBoolData.value)
  if(AllNewBoolData.value.value_meanings && AllNewBoolData.value.value_meanings.length != 0){
    AllNewBoolData.value.valueTitle = "Permissible Value Meanings"
  }else if(AllNewBoolData.value.permissible_values && AllNewBoolData.value.permissible_values.length != 0){
    AllNewBoolData.value.valueTitle = "Permissible Values"
  }
}


// 绑定高亮属性并且查询
let inquireData = ref()
const inquiriesClass = ref(['Object Class', 'Property', 'Conceptual Domain', 'Data Element Concept', 'Value Domain', 'Data Element']);
const selectedIndex = ref(null);
const selectInquire = throttle((index) => {
  WatchAllNewBool.value = false;
  selectedIndex.value = index;
  if(index === 0){
    getObjectClassData();
  }else if(index === 1){
    getPropertyData();
  }else if(index === 2){
    getConceptualDomainData();
  }else if(index === 3){
    getDataElementConceptData();
  }else if(index === 4){
    getValueDomainData();
  }else if(index === 5){
    getDataElementData();
  }
  setTimeout(() => {
    console.log(tableData)
    tableData = inquireData.value;
    // console.log(tableData)
  }, 1000);
},300)

//  获取对象类数据
function getObjectClassData(){
  getObjectClassList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(inquireData.value)
  }).catch(err =>{
    console.log(err)
  })
}

// 获取属性数据
function getPropertyData(){
  getPropertyList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(inquireData.value)
    // console.log(res.data)
  }).catch(err =>{
    console.log(err)
  })
}

// 获取概念域数据
function getConceptualDomainData(){
  getConceptualDomainList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(inquireData.value)
    // console.log(res.data)
  }).catch(err =>{
    console.log(err)
  })
}

//获取数据元概念数据
function getDataElementConceptData(){
  getDataElementConceptList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(res.data)
  })
} 

// 获取值域数据
function getValueDomainData(){
  getValueDomainList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(res.data)
  }).catch(err =>{
    console.log(err)
  })
}

// 获取数据元数据
function getDataElementData(){
  getDataElementList()
  .then(res =>{
    inquireData.value = res.data
    // console.log(res.data)
  }).catch(err =>{
    console.log(err)
  })
}

// 根据ID查询数据
let viewFlag = ref([])
const getDataByIdentifier = throttle((identifier) =>{
  let flag = identifier.slice(0,3);
  let title = ref()
  viewFlag.value.push(AllNewBoolData.value)
  if(flag === "OCL"){ //查询对象类
    title.value = "Object Class";
    getObjectClassByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      // watchAllData(res.data,title)
    }).catch(err =>{
      console.log(err)
    }
    )
  }else if(flag === "PRP"){ //查询属性
    title.value = "Property";
    getPropertyByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      // watchAllData(res.data,title)
    }).catch(err =>{
      console.log(err)
    }
    )
  }else if(flag === "CDM"){ //查询概念域
    title.value = "Conceptual Domain";
    getConceptualDomainByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      // watchAllData(res.data,title)
    }).catch(err =>{
      console.log(err)
    }
    )
  }else if(flag === "DEC"){ //查询数据元概念
    title.value = "Data Element Concept";
    getDataElementConceptByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      // watchAllData(res.data,title)
    }).catch(err =>{
      console.log(err)
    }
    )
  }else if(flag === "VDM"){ //查询值域
    title.value = "Value Domain";
    getValueDomainByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      // watchAllData(res.data,title)
    }).catch(err =>{
      console.log(err)
    }
    )
  }
},300)

onMounted(() => {
  selectInquire(0);
})
</script>

<style lang='less' scoped>
.header {
  width: 100%;
  height: 8%;
  padding: 1%;
  border-bottom: 1px solid #e8e8e8;

  .card {
    display: flex;
    justify-content: space-between;
    height: 100%;
    padding-left: 50px;
    padding-right: 50px;

    .inquire {
      display: flex;
      justify-content: center;
      align-items: center;
      flex: 1;
      border: 1px solid #2fb9c2;
      color: #2fb9c2;
      border-radius: 10px;
      max-width: 150px;
      height: 80%;
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
}

.pagination {
  width: 100%;
  height: 92%;
  padding: 2%;

  .describe-text {
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 800px;
  }

  :deep(.describe-tooltip) {
    max-width: 300px !important;
    word-wrap: break-word;
    white-space: normal;
  }

  .cardBanner {
    width: 85vw;
    .public_label{
      :deep(.el-descriptions__label){ 
        display: inline-block;
        width: 70px !important; 
        color: #959595 !important;
        font-weight: 800;
      }
    }
    .icon{
      cursor: pointer;
      color: #999;
    }
    .icon:hover{
      color: #2fb9c2;
    }
    .card-container {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      padding: 20px;

      .custom-card {
        width: calc((100% - 40px) / 3); 
        min-width: 20vw;
        // height: 45vh;
        margin-bottom: 20px;
        box-sizing: border-box;
      }
    }
  }

  
}
</style>
