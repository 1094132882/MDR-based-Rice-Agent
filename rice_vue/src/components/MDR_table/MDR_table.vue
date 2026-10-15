<template>
    <!-- 详细信息展示 -->
    <div v-if="WatchAllNewBool" class="cardBanner">
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
            <el-descriptions :column="1" class="public_label">
            <el-descriptions-item label="Identifier:">{{ AllNewBoolData.identifier }}</el-descriptions-item>
            <el-descriptions-item label="Description:">{{ AllNewBoolData.describe }}</el-descriptions-item>
            <el-descriptions-item label="Registration Status:"><el-tag size="small">{{ AllNewBoolData.status }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="Creation Time:">{{ AllNewBoolData.time }}</el-descriptions-item>
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
            <el-descriptions-item v-if="AllNewBoolData.object_class" label="Class">
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
            <el-descriptions-item label="Registration Status:"><el-tag size="small">{{ item.status }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="Creation Time:">{{ item.time }}</el-descriptions-item>
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
                <el-descriptions-item label="Value Meaning:">{{ item.value_meanings.name }}</el-descriptions-item>
                <el-descriptions-item label="Registration Status:"><el-tag size="small">{{ item.value_meanings.status }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="Creation Time:">{{ item.value_meanings.time }}</el-descriptions-item>
                <el-descriptions-item label="Version:">{{ item.value_meanings.version }}</el-descriptions-item>
            </el-descriptions>
            </el-card>
            </el-card>
        </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, computed,} from 'vue';

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

</script>