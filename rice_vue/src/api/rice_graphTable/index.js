import request from '../../util/request'
import { getToken, removeToken } from "../../util/auth";

// 查询Basic
export function getGeneBasicInfo(gene_id){
    return request({
        method: "get",
        url: "/graph/getGeneBasicInfo",
        params:{
            gene_id:gene_id
        },
    })
}

// 查询ExpressionInfo
export function getExpressionInfo(gene_id){
    return request({
        method: "get",
        url: '/graph/getExpressionInfo',
        params:{
            gene_id:gene_id
        }
    })
}

// 查询HomologuesInfo
export function getHomologuesInfo(gene_id){
    return request({
        method: "get",
        url: '/graph/getHomologuesInfo',
        params:{
            gene_id:gene_id
        }
    })
}

// 查询SVInfo
export function getSVInfo(sv_id){
    return request({
        method: "get",
        url: '/graph/getSVInfo',
        params:{
            sv_id:sv_id
        }
    })
}