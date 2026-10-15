<template>
  <div v-if="!WatchAllNewBool">
    <div class="header">
      <h1 v-if="!showDataSet">Subdomain Data</h1>
      <h1 v-if="showDataSet">Subdomain Detail Page</h1>
    </div>
    <el-divider />
    <div class="Banner" v-if="!showDataSet">
      <el-card v-for="(item,index) in subdomainListData" 
      :key="index" 
      class="custom-card" 
      @click="handleCardClick(item.identifier)">
        <el-descriptions border :column="1">
          <el-descriptions-item label="ID:">{{ item.identifier }}</el-descriptions-item>
          <el-descriptions-item label="Name:">{{ item.name }}</el-descriptions-item>
          <el-descriptions-item label="Email:">{{ item.access }}</el-descriptions-item>
          <el-descriptions-item label="Dataset Count:">{{ item.datasets_count }}</el-descriptions-item>
          <el-descriptions-item label="Description:">{{ item.description }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
    <div class="subdomain" v-if="showDataSet">
      <el-card class="subdomainHead">
        <el-descriptions border :column="2" title="Subdomain">
          <template #extra>
            <el-button type="success" plain color="#2fb9c2" @click="backViews()">Back</el-button>
          </template>
          <el-descriptions-item label="ID:">{{ subdomainDataSet.identifier }}</el-descriptions-item>
          <el-descriptions-item label="Name:">{{ subdomainDataSet.name }}</el-descriptions-item>
          <el-descriptions-item label="Email:">{{ subdomainDataSet.access }}</el-descriptions-item>
          <el-descriptions-item label="Description:">{{ subdomainDataSet.description }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <div class="subdomainBanner">
        <div class="dataset-tabs" v-if="subdomainDataSet.datasets.length > 1">
          <div 
            v-for="(item, index) in subdomainDataSet.datasets"
            :key="index"
            class="tab-item"
            :class="{ active: activeDatasetIndex === index }"
            @click="switchDataset(index)"
          >
            {{ item.name || `Dataset ${index + 1}` }}
          </div>
        </div>
        <el-card v-for="(item,index) in subdomainDataSet.datasets" :key="index" v-show="activeDatasetIndex === index">
          <el-descriptions :column="3" title="Dataset" >
            <el-descriptions-item label="Name:">{{ item.name }}</el-descriptions-item>
            <el-descriptions-item label="ID:">{{ item.identifier }}</el-descriptions-item>
            <el-descriptions-item label="Description:">{{ item.description }}</el-descriptions-item>
          </el-descriptions>
          <el-divider></el-divider>
          <div class="showData">
            <div class="inquire"
              v-for="(i,j) in inquiriesClass"
              :key="j"
              :class="{ active: (item.selectedIndex === j) }"
              @click="showViewData(j,item,index)">
              {{ i }}
            </div>
          </div>
          <el-divider></el-divider>

          <!-- table_metaData -->
          <el-card v-if="item.isShowTableMetaData">
            <el-descriptions border :column="2" title="Table Metadata">
              <el-descriptions-item label="ID:">{{ item.table_metadata.identifier }}</el-descriptions-item>
              <el-descriptions-item label="Sample Data:">{{ item.table_metadata.sample }}</el-descriptions-item>
            </el-descriptions>
            <div class="tableMetaData">
              <el-card v-for="(itemData, index) in item.table_metadata.table_metadata_elements" :key="index" class="tableMetaDataBanner">
                <el-descriptions  :column="2" title="Table Metadata Element">
                  <el-descriptions-item label="Table Metadata ID:">{{ itemData.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Sample Data:">{{ itemData.sample }}</el-descriptions-item>
                  <el-descriptions-item label="Name:">{{ itemData.name }}</el-descriptions-item>
                  <el-descriptions-item label="Data Element ID:">{{ itemData.data_element_identifier }}</el-descriptions-item>
                </el-descriptions>
                <el-descriptions border :column="2" title="Data Element">
                  <el-descriptions-item label="ID:">{{ itemData.data_element.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Name:">{{ itemData.data_element.name }}</el-descriptions-item>
                  <el-descriptions-item label="Description:">{{ itemData.data_element.describe }}</el-descriptions-item>
                  <el-descriptions-item label="Data Element Concept:">{{ itemData.data_element.data_element_concept.name }} -> {{ itemData.data_element.data_element_concept.identifier }}
                    <el-icon @click="getDataByIdentifier(itemData.data_element.data_element_concept.identifier )" class="icon" :size="15"><View /></el-icon>
                  </el-descriptions-item>
                  <el-descriptions-item label="Value Domain:">{{ itemData.data_element.value_domain.name }} -> {{ itemData.data_element.value_domain.identifier }}
                    <el-icon @click="getDataByIdentifier(itemData.data_element.value_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </div>
          </el-card>

          <!-- column_metaData -->
           <!-- 表格第一行数据 -->
          <el-card v-if="item.isShowColumnData">
            <el-descriptions border :column="2" title="Table Data - First Row" >
              <template #extra>
                <el-button type="primary" plain color="#2fb9c2" @click="toggleTable(item)">{{ item.isTableExpanded ? 'Collapse' : 'Expand' }}</el-button>
              </template>
              <el-descriptions-item label="ID:">{{ item.tables.data[0].table.identifier }}</el-descriptions-item>
              <el-descriptions-item label="Name:">{{ item.tables.data[0].table.name }}</el-descriptions-item>
            </el-descriptions>
            <transition
              name="table-collapse"
              v-on="transitionEvents"
            >
            <div v-show="item.isTableExpanded" style="width: 100%" class="collapsible-table">
              <el-table :data="item.tables.data[0].sample_data" style="width: 100%"  >
                <el-table-column 
                  v-for="colIndex in Object.keys(item.tables.data[0].sample_data[0]).length - 1" 
                  :key="colIndex"
                  :label="item.tables.data[0].table[`column_name_${colIndex}`]"
                >
                  <template #default="{ row }">
                    <el-tooltip effect="dark" placement="bottom">
                      <template #content>
                        <div style="white-space: pre-line">
                          {{ row[`value${colIndex}`] }}
                        </div>
                      </template>
                      <div class="describe-text">
                        {{ row[`value${colIndex}`]?.length > 50 
                          ? row[`value${colIndex}`].slice(0, 50) + '...' 
                          : row[`value${colIndex}`] }}
                      </div>
                    </el-tooltip>
                  </template>
                </el-table-column>
              </el-table> 
            </div>
              
            </transition>
          </el-card>

          <div v-if="item.isShowColumnData" :class="{rowClass: item.is_column_first === false}">
            <el-card 
            v-for="(itemData, i) in item.column_metadata || item.row_metadata" 
            :key="i" 
            class="columnDataClass"  
            :class="{
              rowActive: item.is_column_first === false,
              columnActive: item.is_column_first === true
              }"
            >
              <!-- 列数据展示 -->
              <div class="columnData">
                <div class="columnDataLeft">
                  <el-descriptions :column="1" :title="'Column Metadata:'+ itemData.name" v-if="item.column_metadata" >
                    <el-descriptions-item label="ID:">{{ itemData.identifier }}</el-descriptions-item>
                    <el-descriptions-item label="Name:">{{ itemData.name }}</el-descriptions-item>
                    <el-descriptions-item label="Data Element ID:" v-if="itemData.data_element_identifier">{{ itemData.data_element_identifier }}</el-descriptions-item>
                  </el-descriptions>
                </div>
                <div class="columnDataCenter" >
                  <div class="arrow"></div>
                </div>
                <div class="columnDataRight">
                  <el-descriptions border :column="3" title="Data Element" v-if="item.column_metadata">
                    <el-descriptions-item label="ID:">
                      {{ itemData.data_element?.identifier || 'No Data' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Name:">
                      {{ itemData.data_element?.name || 'No Data' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Description:">
                      {{ itemData.data_element?.describe || 'No Data' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Data Element Concept:">
                      {{ itemData.data_element?.data_element_concept?.name && itemData.data_element?.data_element_concept?.identifier
                        ? `${itemData.data_element?.data_element_concept.name} -> ${itemData.data_element?.data_element_concept.identifier}`
                        : 'No Data' }}
                      <el-icon v-if="itemData.data_element?.data_element_concept?.identifier" @click="getDataByIdentifier(itemData.data_element.data_element_concept?.identifier)" class="icon" :size="15">
                        <View />
                      </el-icon>
                    </el-descriptions-item>
                    <el-descriptions-item label="Value Domain:">
                      {{ itemData.data_element?.value_domain?.name && itemData.data_element?.value_domain?.identifier
                        ? `${itemData.data_element?.value_domain.name} -> ${itemData.data_element?.value_domain.identifier}`
                        : 'No Data' }}
                      <el-icon v-if="itemData.data_element?.value_domain?.identifier" @click="getDataByIdentifier(itemData.data_element.value_domain?.identifier)" class="icon" :size="15">
                        <View />
                      </el-icon>
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </div>


              <div v-if="(item.column_metadata && itemData.column_metadata_elements.length != 0)">

                <el-descriptions border :column="5" title="Column Metadata" >
                  <el-descriptions-item label="ID:">{{ itemData.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Name:">{{ itemData.name }}</el-descriptions-item>
                  <el-descriptions-item label="Sample:" v-if="itemData.sample">{{ itemData.sample }}</el-descriptions-item>
                  <el-descriptions-item label="Data Element ID:" v-if="itemData.data_element_identifier">{{ itemData.data_element_identifier }}</el-descriptions-item>
                </el-descriptions>

                <el-card v-for="(itemColumnData, index) in itemData.column_metadata_elements" :key="index" style="margin-top: 10px;">
                  <div class="columnData">
                    <div class="columnDataLeft">
                      <el-descriptions :column="1" :title="'Column Metadata Element:'+itemColumnData.name" >
                        <el-descriptions-item label="ID:">{{ itemColumnData.identifier }}</el-descriptions-item>
                        <el-descriptions-item label="Name:">{{ itemColumnData.name }}</el-descriptions-item>
                        <el-descriptions-item label="Sample:" v-if="itemColumnData.sample">{{ itemColumnData.sample }}</el-descriptions-item>
                        <el-descriptions-item label="Data Element ID:" v-if="itemColumnData.data_element_identifier">{{ itemColumnData.data_element_identifier }}</el-descriptions-item>
                      </el-descriptions>
                    </div>
                    <div class="columnDataCenter" >
                      <div class="arrow"></div>
                    </div>
                    <div class="columnDataRight">
                      <el-descriptions border :column="3" title="Data Element"  >
                          <el-descriptions-item label="ID:">{{ itemColumnData.data_element.identifier }}</el-descriptions-item>
                          <el-descriptions-item label="Name:">{{ itemColumnData.data_element.name }}</el-descriptions-item>
                          <el-descriptions-item label="Description:">{{ itemColumnData.data_element.describe }}</el-descriptions-item>
                          <el-descriptions-item label="Data Element Concept:">{{ itemColumnData.data_element.data_element_concept.name }} -> {{ itemColumnData.data_element.data_element_concept.identifier }}
                            <el-icon @click="getDataByIdentifier(itemColumnData.data_element.data_element_concept.identifier )" class="icon" :size="15"><View /></el-icon>
                          </el-descriptions-item>
                          <el-descriptions-item label="Value Domain:">{{ itemColumnData.data_element.value_domain.name }} -> {{ itemColumnData.data_element.value_domain.identifier }}
                            <el-icon @click="getDataByIdentifier(itemColumnData.data_element.value_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                          </el-descriptions-item>
                      </el-descriptions>
                    </div>
                  </div>
                </el-card>
              </div>

              <!-- 行数据展示 -->
              <el-descriptions border :column="2" title="Row Metadata" v-if="item.row_metadata">
                <el-descriptions-item label="ID:">{{ itemData.identifier }}</el-descriptions-item>
                <el-descriptions-item label="Name:">{{ itemData.name }}</el-descriptions-item>
                <el-descriptions-item label="Segmentation:">{{ itemData.segmentation }}</el-descriptions-item>
              </el-descriptions>
              <el-divider v-if="item.row_metadata"></el-divider>

              <div v-for="(I, J) in itemData.column_metadata" :key="J" v-if="item.row_metadata">
                <el-descriptions border :column="2" title="Column Metadata" >
                  <el-descriptions-item label="ID:">{{ I.identifier }}</el-descriptions-item>
                  <el-descriptions-item label="Name:">{{ I.name }}</el-descriptions-item>
                  <el-descriptions-item label="Sample:" v-if="I.sample">{{ I.sample }}</el-descriptions-item>
                  <el-descriptions-item label="Data Element Identifier:" v-if="I.data_element_identifier">{{ I.data_element_identifier }}</el-descriptions-item>
                </el-descriptions>

                <el-card v-for="(itemColumnData, index) in I.column_metadata_elements" :key="index" style="margin-top: 10px;">
                  <el-descriptions :column="2" title="Column Metadata Element" >
                    <el-descriptions-item label="ID:">{{ itemColumnData.identifier }}</el-descriptions-item>
                    <el-descriptions-item label="Name:">{{ itemColumnData.name }}</el-descriptions-item>
                    <el-descriptions-item label="Sample:" v-if="itemColumnData.sample">{{ itemColumnData.sample }}</el-descriptions-item>
                    <el-descriptions-item label="Data Element Identifier:" v-if="itemColumnData.data_element_identifier">{{ itemColumnData.data_element_identifier }}</el-descriptions-item>
                  </el-descriptions>
                  <el-descriptions border :column="2" title="Data Element"  >
                      <el-descriptions-item label="ID:">{{ itemColumnData.data_element.identifier }}</el-descriptions-item>
                      <el-descriptions-item label="Name:">{{ itemColumnData.data_element.name }}</el-descriptions-item>
                      <el-descriptions-item label="Description:">{{ itemColumnData.data_element.describe }}</el-descriptions-item>
                      <el-descriptions-item label="Data Element Concept:">{{ itemColumnData.data_element.data_element_concept.name }} -> {{ itemColumnData.data_element.data_element_concept.identifier }}
                        <el-icon @click="getDataByIdentifier(itemColumnData.data_element.data_element_concept.identifier )" class="icon" :size="15"><View /></el-icon>
                      </el-descriptions-item>
                      <el-descriptions-item label="Value Domain:">{{ itemColumnData.data_element.value_domain.name }} -> {{ itemColumnData.data_element.value_domain.identifier }}
                        <el-icon @click="getDataByIdentifier(itemColumnData.data_element.value_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                      </el-descriptions-item>
                  </el-descriptions>
                </el-card>  

                <div v-if="I.column_metadata_elements.length === 0" style="margin-top: 10px;">
                  <el-descriptions border :column="2" title="Data Element">
                    <el-descriptions-item label="ID:">{{ I.data_element.identifier }}</el-descriptions-item>
                    <el-descriptions-item label="Name:">{{ I.data_element.name }}</el-descriptions-item>
                    <el-descriptions-item label="Description:">{{ I.data_element.describe }}</el-descriptions-item>
                    <el-descriptions-item label="Data Element Concept:">{{ I.data_element.data_element_concept.name }} -> {{ I.data_element.data_element_concept.identifier }}
                      <el-icon @click="getDataByIdentifier(I.data_element.data_element_concept.identifier )" class="icon" :size="15"><View /></el-icon>
                    </el-descriptions-item>
                    <el-descriptions-item label="Value Domain:">{{ I.data_element.value_domain.name }} -> {{ I.data_element.value_domain.identifier }}
                      <el-icon @click="getDataByIdentifier(I.data_element.value_domain.identifier)" class="icon" :size="15"><View /></el-icon>
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </div>

            </el-card>
          </div>

          <!-- table -->
          <div v-if="item.isShowTableData" class="table">
            <el-table :data="item.tables.data" style="width: 100%" >
              <el-table-column type="expand">
                <template #default="props">
                  <el-divider>First Four Rows of the File</el-divider>
                  <el-table :data="props.row.sample_data" >
                    <el-table-column label="Row Number" width="100" :class-name="'column-color'">
                      <template #default="{ $index }">
                        {{ $index + 1 }}
                      </template>
                    </el-table-column>
                    <el-table-column 
                      v-for="colIndex in Object.keys(props.row.sample_data[0]).length - 1" 
                      :key="colIndex"
                      :label="props.row.table[`column_name_${colIndex}`]"
                      :class-name="'column-color'"
                    >
                      <template #default="{ row }">
                        <el-tooltip effect="dark" placement="bottom">
                          <template #content>
                            <div style="white-space: pre-line">
                              {{ row[`value${colIndex}`] }}
                            </div>
                          </template>
                          <div class="describe-text">
                            {{ row[`value${colIndex}`]?.length > 50 
                              ? row[`value${colIndex}`].slice(0, 50) + '...' 
                              : row[`value${colIndex}`] }}
                          </div>
                        </el-tooltip>
                      </template>
                    </el-table-column>
                  </el-table>
                </template>
              </el-table-column>
              <el-table-column label="ID" prop="table.identifier" />
              <el-table-column label="Name" prop="table.name" />
            </el-table> 
            <!-- 分页控制按钮 -->
             <div class="tablePagination">
                <el-pagination
                  background
                  :current-page="item.tables.pagination.page"
                  :page-size="item.tables.pagination.per_page"
                  :total="item.tables.pagination.total_tables"
                  layout="total,prev, pager, next,jumper"
                  @current-change="(page) => handleCurrentChange(page, subdomainDataSet.identifier, item.identifier,index)"
                />
              </div>
          </div>
        </el-card>
      </div>

    </div>
  </div>

  <!-- 查看详细信息 -->
  <el-card v-if="WatchAllNewBool">
    <div class="cardBanner">
      <el-descriptions
        :column="1"
        border
        :title="AllNewBoolData.title"
        direction="vertical"
      >
        <template #extra>
          <el-button type="success" color="#2fb9c2" plain @click="backViews()">Back</el-button>
        </template>
          <!-- 公共属性 -->
        <el-descriptions-item label="Public Attributes">
          <el-descriptions :column="1" border >
            <el-descriptions-item label="Identifier">{{ AllNewBoolData.identifier }}</el-descriptions-item>
            <el-descriptions-item label="Description">{{ AllNewBoolData.describe }}</el-descriptions-item>
            <el-descriptions-item label="Registration Status"><el-tag size="small">{{ AllNewBoolData.status }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="Creation Time">{{ AllNewBoolData.time }}</el-descriptions-item>
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
            <el-descriptions-item label="Identifier：">{{ item.identifier }}</el-descriptions-item>
            <el-descriptions-item label="Registration Status："><el-tag size="small">{{ item.status }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="Creation Time：">{{ item.time }}</el-descriptions-item>
            <el-descriptions-item label="Version：">{{ item.version }}</el-descriptions-item>
            <el-descriptions-item label="Value Meaning：">{{ item.name }}</el-descriptions-item>
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
              <el-descriptions-item label="Identifier：">{{ item.identifier }}</el-descriptions-item>
              <el-descriptions-item label="Value：">{{ item.name }}</el-descriptions-item>
          </el-descriptions>
          </el-card>
          <el-card style="margin-top: 15px">
            <el-descriptions :column="1"  >
              <el-descriptions-item label="Identifier：">{{ item.value_meanings.identifier }}</el-descriptions-item>
              <el-descriptions-item label="Value Meaning：">{{ item.value_meanings.name }}</el-descriptions-item>
              <el-descriptions-item label="Registration Status："><el-tag size="small">{{ item.value_meanings.status }}</el-tag></el-descriptions-item>
              <el-descriptions-item label="Creation Time：">{{ item.value_meanings.time }}</el-descriptions-item>
              <el-descriptions-item label="Version：">{{ item.value_meanings.version }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
          </el-card>
        </div>
      </div>
    </div>
  </el-card>

</template>

<script setup>
import { 
  getSubdomainList,
  getSubdomainByIdentifier,
  geTablesBySubdomainIdentifierAndDatasetIdentifier
 } from '../../api/subdomain_inquire/index';
 import { 
  getValueDomainByIdentifier,
  getDataElementConceptByIdentifier,
  getObjectClassByIdentifier,
  getPropertyByIdentifier,
  getConceptualDomainByIdentifier,
 } from '../../api/metadata_inquire/index'
import { ref, onMounted, reactive } from 'vue';
import { ElMessage } from 'element-plus'
import { throttle } from "../../util/optimize"

onMounted(()=>{
  getSubdomainListData();
})

// 展示切换
function toggleTable(item) {
  item.isTableExpanded = !item.isTableExpanded
}
const transitionEvents = {
  beforeEnter(el) {
    el.style.height = '0'
  },
  enter(el) {
    el.style.height = el.scrollHeight + 'px';
    el.style.overflow = 'hidden'
  },
  afterEnter(el) {
    el.style.height = ''
  },
  beforeLeave(el) { 
    el.style.height = `${el.scrollHeight}px`
    el.style.overflow = 'hidden'
  },
  leave(el) {
    setTimeout(() => {
      el.style.height = '0'
    })
  },
  afterLeave(el) {
    el.style.height = ''
    el.style.overflow = ''
  }
}


// 调用分页查询
function handleCurrentChange(page,subdomain_identifier,dataset_identifier,index){
  // console.log(page,subdomain_identifier,dataset_identifier)
  getTablesBySubdomainIdentifierAndDatasetIdentifier(subdomain_identifier,dataset_identifier,page,index)

}

// 切换数据集展示
const activeDatasetIndex = ref(0)
const switchDataset = (index) => {
  activeDatasetIndex.value = index
}

// 切换展示页面
const inquiriesClass = ['Table Metadata', 'Column Metadata', 'Table Examples']
function showViewData(flag,i,j){
  i.selectedIndex = flag
  if(flag === 0){
    i.isShowTableMetaData = true
    i.isShowColumnData = false
    i.isShowTableData = false
  }else if(flag === 1){
    i.isShowTableMetaData = false
    i.isShowColumnData = true
    i.isShowTableData = false
  }else{
    i.isShowTableMetaData = false
    i.isShowColumnData = false
    i.isShowTableData = true
  }
} 

// 查看子页面信息
let subdomainDataSet = ref(null)
let showDataSet = ref(false)
const searchSubdomainData = throttle(async (id) => {
  loadingId.value = id;
  try {
    await getSubdomainByIdentifierData(id);
    setTimeout(()=>{
      if(subdomainDataSet.value != null){
        ElMessage({
          showClose: true,
          center: true,
          message: 'Query successful',
          type: 'success',
        });
        showDataSet.value = true;
      }
    },300)
  } catch (error) {
    ElMessage.error('Query failed');
  } finally {
    loadingId.value = null;
  }
}, 300);



// 点击事件
const loadingId = ref(null);
const handleCardClick = (id) => {
  if (loadingId.value) return; // 防止重复点击
  searchSubdomainData(id);
};

// 返回上个页面
let DataSetFlag = ref(false);
function backViews(){
  if(viewFlag.value.length != 0){
    AllNewBoolData.value = viewFlag.value.pop();
  }else if(viewFlag.value.length === 0){
    WatchAllNewBool.value = false;
    showDataSet.value =  DataSetFlag.value;
    DataSetFlag.value = false
    AllNewBoolData.value = null
  }
}

// 获取子域列表数据
let subdomainListData = ref()
function getSubdomainListData(){
  getSubdomainList()
  .then(res => {
    // console.log(res.data)
    subdomainListData.value = res.data
  }).catch(err => {
    console.log(err)
  })
}

// 获取子页面详细信息
function getSubdomainByIdentifierData(id){
  getSubdomainByIdentifier(id)
  .then(res => {
    console.log(res.data)
    subdomainDataSet.value = res.data
    activeDatasetIndex.value = 0
    subdomainDataSet.value.datasets = subdomainDataSet.value.datasets.map(item => ({
      ...item, 
      isShowTableMetaData: true,  // 控制表元数据显示
      isShowColumnData: false, // 控制行列数据展示
      isShowTableData: false, // 控制表格展示
      isTableExpanded: true, // 控制行列数据展示的表格数据展开和收缩
      selectedIndex: 0
    }));
    // console.log(subdomainDataSet.value.datasets)
  }).catch(err => {
    console.log(err)
  })
}

// 分页查询数据
function getTablesBySubdomainIdentifierAndDatasetIdentifier(subdomain_identifier,dataset_identifier,page,index){
  geTablesBySubdomainIdentifierAndDatasetIdentifier(subdomain_identifier,dataset_identifier,page)
  .then(res => {
    // console.log(res.data)
    subdomainDataSet.value.datasets[index].tables = res.data
    subdomainDataSet.value.datasets[index].total_tables = res.data.pagination.total_tables
  }).catch(err=>{
    console.log(err)
  })
}

// 根据ID查询数据
const AllNewBoolData = ref(null)
const WatchAllNewBool = ref(false)
let viewFlag = ref([])
const getDataByIdentifier = throttle((identifier) =>{
  let flag = identifier.slice(0,3);
  console.log(flag)
  let title = ref('')
  if(AllNewBoolData.value != null)
    viewFlag.value.push(AllNewBoolData.value)
  DataSetFlag.value = true
  if(flag === "OCL"){ //查询对象类
    title.value = "Object Class";
    getObjectClassByIdentifier(identifier)
    .then(res =>{
      AllNewBoolData.value = res.data
      AllNewBoolData.value.title = title
      WatchAllNewBool.value = true
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
      WatchAllNewBool.value = true
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
      WatchAllNewBool.value = true
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
      WatchAllNewBool.value = true
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
        AllNewBoolData.value.valueTitle = "Permissible Values"
        WatchAllNewBool.value = true
      }).catch(err =>{
        console.log(err)
      }
    )
}
  ElMessage({
    showClose: true,
    center: true,
    message: 'Query successful',
    type: 'success',
  });
},300)
</script>

<style lang="less" scoped>
.header{
  display: flex;
  align-items: center;
  justify-content: center;
  height: 5vh;
  color: #2fb9c2;
}

.Banner{
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 20px;
  .custom-card{
    cursor: pointer;
    width: calc((100% - 40px) /3);
    min-width: 20vw;
    box-sizing: border-box;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
  }
  .custom-card:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2); 
    transform: scale(1.03); 
  }
}

.subdomain{
  .subdomainHead{
    // height: 15vh;
    margin-bottom: 1vh;
  }
  .subdomainBanner{
    // height: 70vh;
    .dataset-tabs {
      display: flex;
      gap: 15px;
      padding: 10px 20px;
      background: #f5f7fa;
      border-radius: 4px;
      margin-bottom: 20px;

      .tab-item {
        padding: 8px 20px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.3s;
        border: 1px solid #dcdfe6;
        background: white;

        &:hover {
          color: #2fb9c2;
          border-color: #2fb9c2;
        }

        &.active {
          background: #2fb9c2;
          color: white;
          border-color: #2fb9c2;
        }
      }
    }
    .rowClass{
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      padding: 20px;
    }
    .columnDataClass{
      margin-bottom: 10px;
      &.rowActive {
        width: calc((100% - 20px) /2);
        min-width: 20vw;
        box-sizing: border-box;
      }
      &.columnActive{
        min-width: 20vw;
        // box-sizing: border-box;
        .columnData{
          display: flex;
          flex-wrap: wrap-reverse;
          padding: 20px;
          .columnDataLeft{
            width: 20%;
            box-sizing: border-box;
          }
          .columnDataCenter{
            width: 20%;
            box-sizing: border-box;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            .arrow {
              position: absolute;
              width: 0;
              height: 0;
              border-top: 20px solid transparent; 
              border-bottom: 20px solid transparent; 
              border-left: 30px solid #2fb9c2; 
            } 
          }
          .columnDataRight{
            width: 60%;
            box-sizing: border-box;
          }
        }
      }
    }
    // 行列表格展开收缩动画
    .table-collapse-enter-active,
    .table-collapse-leave-active {
      transition: height 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      //overflow: hidden;
    }

    .collapsible-table {
      //margin-top: 10px;
      // opacity: 0.8; 
      transform: translateZ(0);
    }

    .icon{
      cursor: pointer;
      color: #999;
      &:hover{
        color: #2fb9c2;
      }
    }
    .showData{
      display: flex;
      justify-content: space-between;
      margin-left: 10%;
      margin-right: 10%;
      
      .inquire {
        display: flex;
        justify-content: center;
        align-items: center;
        flex: 1;
        border: 1px solid #2fb9c2;
        color: #2fb9c2;
        border-radius: 10px;
        max-width: 200px;
        height: 50px;
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
    .tableMetaData{
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      padding: 20px;
      .tableMetaDataBanner{
        width: calc((100% - 40px)/3);
        min-width: 20vw;
        box-sizing: border-box;
        margin-bottom: 10px;
        .icon{
          cursor: pointer;
          color: #999;
        }
        .icon:hover{
          color: #2fb9c2;
        }
      }
    }

    .table{
      :deep(.column-color){
        color: #2fb9c2;
      }
      .tablePagination{
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 2vh;
      }
    }
    :deep(.fixed-pagination) {
        position: fixed;
        bottom: 10px;
        left: 50%;
        transform: translateX(-50%);
        width: auto;
        z-index: 1000;
        background: #fff;
        box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.1);
        border-radius: 4px 4px 0 0;
        padding: 0%;
        display: flex;
        align-items: center;
        justify-content: center;
      }
  }
}

.cardBanner {
    width: 85vw;
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
</style>
