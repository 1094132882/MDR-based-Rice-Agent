import request from '../../util/request'
import { getToken, removeToken } from "../../util/auth";
import { id } from 'element-plus/es/locale/index.mjs';

// 获取对象类列表
export function getObjectClassList(){
    return request({
        method: "get",
        url: "/mdr/getObjectClassList",
    });
}

// 获取属性列表
export function getPropertyList(){
    return request({
        method: "get",
        url: "/mdr/getPropertyList"
    })
}

// 获取概念域列表
export function getConceptualDomainList(){
    return request({
        method: "get",
        url: "/mdr/getConceptualDomainList"
    })
}

// 获取数据元概念列表
export function getDataElementConceptList(){
    return request({
        method: "get",
        url: "/mdr/getDataElementConceptList"
    })
}

// 获取值域列表
export function getValueDomainList(){
    return request({
        method: "get",
        url: "/mdr/getValueDomainList"
    })
}

// 获取数据元列表
export function getDataElementList(){
    return request({
        method: "get",
        url: "/mdr/getDataElementList"
    })
}

// 根据ID查询对象类
export function getObjectClassByIdentifier(identifier){
    return request({
        method: "get",
        url: "/mdr/getObjectClassByIdentifier",
        params:{
            identifier:identifier
        }
    })
}

// 根据ID查询属性
export function getPropertyByIdentifier(identifier){
    return request({
        method: "get",
        url: "/mdr/getPropertyByIdentifier",
        params:{
            identifier: identifier
        }
    })
}

// 根据ID查询概念域
export function getConceptualDomainByIdentifier(identifier){
    return request({
        method: "get",
        url: "/mdr/getConceptualDomainByIdentifier",
        params:{
            identifier:identifier
        }
    })
}

// 根据ID查询数据元概念
export function getDataElementConceptByIdentifier(identifier){
    return request({
        method: "get",
        url: "/mdr/getDataElementConceptByIdentifier",
        params:{
            identifier:identifier
        }
    })
}

// 根据ID查询值域
export function getValueDomainByIdentifier(identifier){
    return request({
        method: "get",
        url: "/mdr/getValueDomainByIdentifier",
        params: {
            identifier:identifier
        }
    })
}