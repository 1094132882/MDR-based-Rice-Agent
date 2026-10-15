import request from '../../util/request'
import { getToken, removeToken } from "../../util/auth";

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
